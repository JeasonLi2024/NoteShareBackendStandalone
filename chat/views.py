import os
import subprocess
from tempfile import NamedTemporaryFile
from django.core.files import File
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

class ConversationMessagesView(generics.ListAPIView):
    """
    获取指定对话的所有消息记录（按发送时间正序排列）
    URL中需要传入 conversation_id 参数
    """
    serializer_class = MessageSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter]
    search_fields = ['content', 'message_type']

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

    def list(self, request, *args, **kwargs):
        """
        可选：自定义返回结构，包含对话ID以及消息记录
        """
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        return Response({
            "conversation_id": self.kwargs.get('conversation_id'),
            "messages": serializer.data,
        })


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


# 单个聊天信息删除接口，仅允许发送者删除自己的消息。
class MessageDeleteView(generics.DestroyAPIView):
    queryset = Message.objects.all()
    permission_classes = [IsAuthenticated]

    def delete(self, request, *args, **kwargs):
        message = self.get_object()
        # 仅允许发送者删除消息
        if request.user != message.sender:
            return Response({'detail': '没有删除该消息的权限'}, status=status.HTTP_403_FORBIDDEN)
        self.perform_destroy(message)
        return Response({'detail': '消息已删除'}, status=status.HTTP_204_NO_CONTENT)

# 批量删除聊天消息接口
class MessageBulkDeleteView(APIView):
    """
    前端需要传递一个 JSON 参数：
    {
        "ids": [1, 2, 3, ...]
    }
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        message_ids = request.data.get('ids', [])
        if not message_ids:
            return Response({'detail': '消息ID列表不能为空'}, status=status.HTTP_400_BAD_REQUEST)

        # 仅删除属于当前用户的消息
        messages = Message.objects.filter(id__in=message_ids, sender=request.user)
        if not messages.exists():
            return Response({'detail': '未找到相应消息或无权限删除'}, status=status.HTTP_404_NOT_FOUND)
        count = messages.count()
        messages.delete()
        return Response({'detail': f'{count} 条消息已删除'}, status=status.HTTP_200_OK)


# 删除某个聊天室（对话）内的所有消息。
class ConversationMessagesDeleteView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, conversation_id, *args, **kwargs):
        try:
            conversation = Conversation.objects.get(id=conversation_id)
        except Conversation.DoesNotExist:
            return Response({'detail': '对话不存在'}, status=status.HTTP_404_NOT_FOUND)

        if request.user not in conversation.participants.all():
            return Response({'detail': '无访问该对话的权限'}, status=status.HTTP_403_FORBIDDEN)

        count, _ = conversation.messages.all().delete()
        return Response({'detail': f'{count} 条消息已删除'}, status=status.HTTP_200_OK)


# 允许作者对某个对话拉黑或取消拉黑访客
class ToggleBlockView(generics.UpdateAPIView):
    queryset = Conversation.objects.all()
    permission_classes = [IsAuthenticated]

    def update(self, request, *args, **kwargs):
        conversation = self.get_object()
        # 验证当前用户是否为作者
        if conversation.author != request.user:
            return Response({'detail': '无权限操作'}, status=status.HTTP_403_FORBIDDEN)
        conversation.author_blocked = not conversation.author_blocked
        conversation.save(update_fields=['author_blocked'])
        return Response({'detail': f"拉黑状态已更新为 {conversation.author_blocked}"}, status=status.HTTP_200_OK)


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

        # 针对视频类型，生成预览图
        if message_type == "video":
            success = generate_video_preview(message)
            if not success:
                # 可选择删除记录或记录错误日志。此处仅返回提示信息
                return Response({"detail": "视频上传成功，但生成预览图失败"}, status=status.HTTP_201_CREATED)

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

def generate_video_preview(message):
    """
    使用 ffmpeg 从 message.attachment 中生成一张预览图，
    并保存到 message.preview_image 字段。返回 True/False 表示成功与否。
    """
    if not message.attachment:
        return False

    input_path = message.attachment.path
    # 创建临时文件用于存储预览图
    with NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
        output_path = tmp.name

    # 构造 ffmpeg 命令：在视频 1 秒处截取一帧
    command = ['ffmpeg', '-i', input_path, '-ss', '00:00:01.000', '-vframes', '1', output_path]
    try:
        subprocess.run(command, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        # 将生成的图片保存至 Message.preview_image 字段
        with open(output_path, 'rb') as f:
            django_file = File(f)
            filename = os.path.basename(output_path)
            message.preview_image.save(filename, django_file, save=True)
        return True
    except subprocess.CalledProcessError as e:
        print(f"生成视频预览图失败：{e}")
        return False
    finally:
        if os.path.exists(output_path):
            os.remove(output_path)