import os
from datetime import timedelta
from django.utils import timezone
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from django.contrib.auth import get_user_model
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework import generics, filters, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from .models import Message, Conversation
from .serializers import ConversationSerializer, MessageSerializer
from rest_framework.response import Response
from .utils import get_overall_unread_count

User = get_user_model()
# 获取指定对话的所有消息记录（按发送时间正序排列）
class ConversationMessagesView(generics.ListAPIView):

    serializer_class = MessageSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter]
    search_fields = ['content', 'message_type']

    def get_conversation(self):
        return Conversation.objects.filter(id=self.kwargs.get('conversation_id')).first()

    def get_queryset(self):
        conversation_id = self.kwargs.get('conversation_id')
        # 验证用户是否是该对话的参与者（安全检查，可选）
        conversation = Conversation.objects.filter(id=conversation_id).first()
        if conversation:
            if self.request.user in conversation.participants.all():
                # 按时间正序排序，便于前端按顺序展示聊天记录
                return Message.objects.filter(conversation=conversation).order_by('timestamp')
        # 若不满足条件，返回空查询集
        return Message.objects.none()

    def get_serializer_context(self):
        # 把 request 透传给 serializer，为构造绝对 URL 服务
        return {'request': self.request}

    def list(self, request, *args, **kwargs):
        conv = self.get_conversation()
        if not conv or request.user not in conv.participants.all():
            return Response({
                "conversation_id": self.kwargs.get('conversation_id'),
                "messages": []
            }, status=status.HTTP_200_OK)

        qs = self.get_queryset()
        serializer = self.get_serializer(qs, many=True)
        return Response({
            "conversation_id": conv.id,
            "messages": serializer.data,
        }, status=status.HTTP_200_OK)


# 展示当前用户所有私信对话列表，每个对话可以包含最后一条消息预览等信息
class UserConversationsView(generics.ListAPIView):
    serializer_class = ConversationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        return Conversation.objects.filter(participants=user).order_by('-created_at')

    def get_serializer_context(self):
        # 确保 request 对象传递给序列化器
        return {'request': self.request}

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        serializer = self.get_serializer(queryset, many=True)

        overall_unread = get_overall_unread_count(request.user)
        return Response({
            "total_unread": overall_unread,
            "conversations": serializer.data,
        }, status=status.HTTP_200_OK)

# 消息撤回
class MessageDeleteView(generics.DestroyAPIView):
    queryset = Message.objects.all()
    permission_classes = [IsAuthenticated]

    def delete(self, request, *args, **kwargs):
        message = self.get_object()

        if request.user != message.sender:
            return Response({'detail': '没有撤回该消息的权限'}, status=status.HTTP_403_FORBIDDEN)

        now = timezone.now()
        if now - message.timestamp > timedelta(minutes=5):
            return Response({'detail': '撤回时间已过，不能撤回'}, status=status.HTTP_403_FORBIDDEN)

        # 先拿到要广播的信息
        message_id = message.id
        conversation_id = message.conversation.id
        retractor_id = request.user.id

        # 真正删除
        self.perform_destroy(message)

        # 广播给会话组，让双方客户端收到提示
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f"chat_{conversation_id}",
            {
                'type': 'message_retract',      # 对应 ChatConsumer.message_retract
                'message_id': message_id,
                'retractor_id': retractor_id,
            }
        )
        # 并且 HTTP 端也给撤回者提示
        return Response({'detail': '你撤回了一条消息'}, status=status.HTTP_200_OK)


# 允许作者对某个对话拉黑或取消拉黑访客，由于加上了单次最多发送消息数，现在不用拉黑功能
# class ToggleBlockView(generics.UpdateAPIView):
#     queryset = Conversation.objects.all()
#     permission_classes = [IsAuthenticated]
#
#     def update(self, request, *args, **kwargs):
#         conversation = self.get_object()
#         # 验证当前用户是否为作者
#         if conversation.author != request.user:
#             return Response({'detail': '无权限操作'}, status=status.HTTP_403_FORBIDDEN)
#         conversation.author_blocked = not conversation.author_blocked
#         conversation.save(update_fields=['author_blocked'])
#         return Response({'detail': f"拉黑状态已更新为 {conversation.author_blocked}"}, status=status.HTTP_200_OK)


# 切换免打扰状态，当前用户可以设置在某个对话内是否开启免打扰。
class ToggleDNDView(generics.UpdateAPIView):
    queryset = Conversation.objects.all()
    permission_classes = [IsAuthenticated]

    def update(self, request, *args, **kwargs):
        conversation = self.get_object()
        # 确保当前用户为对话参与者中的一方
        if request.user != conversation.author and request.user != conversation.visitor:
            return Response({'detail': '无权限操作'}, status=status.HTTP_403_FORBIDDEN)
        if request.user == conversation.author:
            conversation.author_dnd = not conversation.author_dnd
            conversation.save(update_fields=['author_dnd'])
            dnd_status = conversation.author_dnd
        else:
            conversation.visitor_dnd = not conversation.visitor_dnd
            conversation.save(update_fields=['visitor_dnd'])
            dnd_status = conversation.visitor_dnd
        return Response({'detail': f"免打扰状态已更新为 {dnd_status}"}, status=status.HTTP_200_OK)


# 当访客点击“私信”按钮时，调用此接口；如果访客与目标作者之间已存在私信对话，则返回已有 Conversation 的 ID，
# 否则创建一个新的 Conversation，并返回其 ID。
class StartConversationView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        author_id = request.data.get("author_id")
        if not author_id:
            return Response({"detail": "缺少 author_id 参数"}, status=400)

        visitor = request.user
        if int(author_id) == visitor.id:
            return Response({"detail": "不能私信自己"}, status=400)

        try:
            author = User.objects.get(id=author_id)
        except User.DoesNotExist:
            return Response({"detail": "作者不存在"}, status=404)

        # 查找是否已有相同 author 和 visitor 的对话
        conversation = Conversation.objects.filter(author=author, visitor=visitor).first()
        if not conversation:
            # 创建新对话并设置参与者
            conversation = Conversation.objects.create(author=author, visitor=visitor)
            conversation.participants.set([author, visitor])

        return Response({"conversation_id": conversation.id}, status=200)


# 附件上传，创建一条消息记录并返回附件 URL，需要前端传入message_type参数（image/video)
class UploadAttachmentView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request, *args, **kwargs):
        conversation_id = request.data.get("conversation_id")
        if not conversation_id:
            return Response({"detail": "缺少 conversation_id 参数"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            conversation = Conversation.objects.get(id=conversation_id)
        except Conversation.DoesNotExist:
            return Response({"detail": "对话不存在"}, status=status.HTTP_404_NOT_FOUND)

        file_obj = request.data.get("attachment")
        if not file_obj:
            return Response({"detail": "未上传任何文件"}, status=status.HTTP_400_BAD_REQUEST)

        message_type = request.data.get("message_type", "image")  # 默认为 image，可传 video
        content = request.data.get("content", "")

        # 如果是视频，则进行格式和大小验证
        if message_type == "video":
            allowed_extensions = ['.mp4', '.mkv']
            extension = os.path.splitext(file_obj.name)[1].lower()
            if extension not in allowed_extensions:
                return Response({"detail": "仅支持 mp4 和 mkv 格式的视频"}, status=status.HTTP_400_BAD_REQUEST)
            max_size = 200 * 1024 * 1024  # 200 MB
            if file_obj.size > max_size:
                return Response({"detail": "视频文件大小不能超过 200MB"}, status=status.HTTP_400_BAD_REQUEST)

        # 创建 Message 记录（附件字段将自动处理上传）
        message = Message.objects.create(
            conversation=conversation,
            sender=request.user,
            message_type=message_type,
            content=content,
            attachment=file_obj
        )

        attachment_url = ""
        if message.attachment:
            attachment_url = request.build_absolute_uri(message.attachment.url)
        preview_url = ""
        if message.preview_image:
            preview_url = request.build_absolute_uri(message.preview_image.url)
        return Response({
            "detail": "附件上传成功",
            "attachment_url": attachment_url,
            "preview_url": preview_url,
            "message_id": message.id
        }, status=status.HTTP_201_CREATED)
