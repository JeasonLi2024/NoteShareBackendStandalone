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
        if not conversation or not await self.user_in_conversation(self.user, conversation):
            await self.close()
            return

        # 若当前对话中作者已拉黑访客，且当前用户是访客，则拒绝连接
        if await self.is_user_blocked(self.user, conversation):
            await self.close()
            return

        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive(self, text_data):
        """
        处理收到的消息，检查发送限制后保存消息并广播
        前端发送 JSON：{"content": "消息内容", "message_type": "text"}
        （附件情况可通过其他方式上传后返回 URL，再发送消息）
        """
        data = json.loads(text_data)
        content = data.get('content', '')
        message_type = data.get('message_type', 'text')

        # 检查消息发送限制
        if not await self.can_send_message(self.user, self.conversation_id):
            error_resp = {"error": "发送消息数量已达到上限，请等待对方回复"}
            await self.send(text_data=json.dumps(error_resp, ensure_ascii=False))
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
            }
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
        await self.send(text_data=event['text'])

    @database_sync_to_async
    def get_conversation(self, conversation_id):
        try:
            return Conversation.objects.get(id=conversation_id)
        except Conversation.DoesNotExist:
            return None

    @database_sync_to_async
    def user_in_conversation(self, user, conversation):
        return user in conversation.participants.all()

    @database_sync_to_async
    def is_user_blocked(self, user, conversation):
        """
        如果当前对话为私信（双人聊天），并且作者拉黑了访客，则当用户为访客时返回 True。
        """
        # 注意：这里假设 Conversation 必须有 author 和 visitor 两个字段
        if conversation.author and conversation.visitor:
            if user == conversation.visitor and conversation.author_blocked:
                return True
        return False

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

        # 由于明确了角色，可直接判断：
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
