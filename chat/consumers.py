# chat/consumers.py
import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from .models import Conversation, Message
from django.db.models import Q

class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.conversation_id = self.scope['url_route']['kwargs']['conversation_id']
        self.group_name = f"chat_{self.conversation_id}"
        self.user = self.scope['user']

        # 判断对话是否存在，并检查当前用户是否为参与者
        conversation = await self.get_conversation(self.conversation_id)
        if not conversation :
            await self.close()
            return

        # 检查当前用户是否为 author 或 visitor
        if not await self.user_in_conversation(self.user, conversation):
            await self.close()
            return

        # # 若当前对话中作者已拉黑访客，且当前用户是访客，则拒绝连接
        # if await self.is_user_blocked(self.user, conversation):
        #     await self.close()
        #     return

        # 加入频道组并接受连接
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        # 连接时把所有“发给我”的历史未读消息标为已读
        await self.mark_unread_as_read()
    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive(self, text_data=None, bytes_data=None):
        # 处理收到的消息，检查发送限制后保存消息并广播
        if text_data is None:
            return  # 忽略空数据

        data = json.loads(text_data)
        content = data.get('content', '')
        message_type = data.get('message_type', 'text')

        # 检查消息发送限制
        if not await self.can_send_message(self.user, self.conversation_id):
            await self.send(text_data=json.dumps({
                "type": "error",
                "code": 403,
                "detail": "发送消息数量已达到上限，请等待对方回复"
            }, ensure_ascii=False))
            return

        # 保存消息
        message = await self.create_message(self.conversation_id, self.user, content, message_type)
        response = {
            'message': {
                'id': message.id,
                'sender': self.user.username,
                'message_type': message.message_type,
                'content': message.content,
                'timestamp': message.timestamp.isoformat()
            },
            'sender_id': self.user.id,
        }
        # 广播给对话组
        await self.channel_layer.group_send(
            self.group_name,
            {
                'type': 'chat_message',
                'text': json.dumps(response, ensure_ascii=False)
            }
        )

    async def chat_message(self, event):
        """
        收到 group_send 的事件后：
         - 如果当前用户不是发送者，则立即标为已读
         - 然后推送到前端
         """
        # 先把之前发过来的 JSON 文本解析成 dict
        data = json.loads(event['text'])
        msg = data['message']
        message_id = msg['id']
        sender_username = msg['sender']
        message_type = msg['message_type']
        content = msg['content']
        timestamp = msg['timestamp']
        # 如果还需要 sender_id，就要在发送时把它也放到 data 里：data['sender_id']
        sender_id = data.get('sender_id')

        # 给在线的“我”打已读标签
        if self.user.id != sender_id:
            await self.mark_message_read(message_id)

        # 转发到前端
        await self.send(text_data=json.dumps({
            'type': 'chat_message',
            'message': {
                'id': message_id,
                'sender': sender_username,
                'message_type': message_type,
                'content': content,
                'timestamp': timestamp,
                'is_read': True if self.user.id != sender_id else False
            }
        }, ensure_ascii=False))

    async def message_retract(self, event):
        # 收到撤回广播后，根据是否为撤回者，发送不同的提示。
        retractor_id = event['retractor_id']
        message_id = event['message_id']
        if self.user.id == retractor_id:
            tip = "你撤回了一条消息"
        else:
            tip = "对方撤回了一条消息"

        await self.send(text_data=json.dumps({
            'type': 'message_retract',
            'message_id': message_id,
            'tip': tip
        }, ensure_ascii=False))

    @database_sync_to_async
    def get_conversation(self, conversation_id):
        try:
            return Conversation.objects.get(id=conversation_id)
        except Conversation.DoesNotExist:
            return None

    @database_sync_to_async
    def user_in_conversation(self, user, conversation):
        return user in conversation.participants.all()

    # @database_sync_to_async
    # def is_user_blocked(self, user, conversation):
    #     # 如果当前对话为私信（双人聊天），并且作者拉黑了访客，则当用户为访客时返回 True。
    #     if conversation.author and conversation.visitor:
    #         if user == conversation.visitor and conversation.author_blocked:
    #             return True
    #     return False

    @database_sync_to_async
    def create_message(self, conversation_id, sender, content, message_type):
        conversation = Conversation.objects.get(id=conversation_id)
        return Message.objects.create(
            conversation=conversation, sender=sender,
            content=content, message_type=message_type
        )

    @database_sync_to_async
    def can_send_message(self, user, conversation_id):
        """
        检查消息发送限制：
          - 如果当前用户是访客且对话中还未收到作者的回复，则最多允许连续发送 10 条消息；
          - 否则，每位用户在对方回复前最多可连续发送 20 条消息。
        算法：获取该对话最新的连续消息，直到发现对方的消息为止，
        判断当前用户连续发送的消息数是否超过上限。
        """
        conversation = Conversation.objects.get(id=conversation_id)
        messages = list(conversation.messages.order_by('-timestamp').all())
        if not messages:
            return True

        # 如果当前用户为 visitor 且作者还未回复，则限制为10，否则为20
        if conversation.visitor == user and not any(msg.sender == conversation.author for msg in messages):
            limit = 10
        else:
            limit = 20

        count = 0
        for msg in messages:
            if msg.sender == user:
                count += 1
            else:
                break
        return count < limit

    @database_sync_to_async
    def mark_message_read(self, message_id):
        return Message.objects.filter(id=message_id, is_read=False).update(is_read=True)

    @database_sync_to_async
    def mark_unread_as_read(self):
        conv = Conversation.objects.get(id=self.conversation_id)
        return Message.objects.filter(
            conversation=conv,
            is_read=False
        ).exclude(sender=self.user).update(is_read=True)
