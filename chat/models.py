# chat/models.py
from django.db import models
from django.conf import settings

User = settings.AUTH_USER_MODEL

class Conversation(models.Model):
    author = models.ForeignKey(User, related_name='authored_conversations', on_delete=models.CASCADE)
    visitor = models.ForeignKey(User, related_name='visited_conversations', on_delete=models.CASCADE)
    # participants 保存对话双方
    participants = models.ManyToManyField(User, related_name='conversations')
    created_at = models.DateTimeField(auto_now_add=True)
    # 针对双人聊天：存储作者是否拉黑访客，默认为 False。
    # 假设发起私信的那一方为访客，其余为作者（在创建对话时确定）。
    author_blocked = models.BooleanField(default=False, verbose_name="作者拉黑访客")
    # 免打扰设置（各自的设置），可以使用两个 Boolean 字段，分别针对对话中两个人。
    # 为简单起见，这里假设 participants 按插入顺序，第一个为作者，第二个为访客
    author_dnd = models.BooleanField(default=False, verbose_name="作者免打扰")
    visitor_dnd = models.BooleanField(default=False, verbose_name="访客免打扰")

    # def __str__(self):
    #     ps = list(self.participants.all())
    #     return f"Conversation {self.id} between: " + " and ".join([str(p) for p in ps])

    def __str__(self):
        return f"{self.visitor} -> {self.author}"

    def get_group_name(self):
        return f"chat_{self.id}"

# 聊天消息：保存所属对话、发送者、消息类型、内容、附件及发送时间
class Message(models.Model):
    MESSAGE_TYPE_CHOICES = (
        ('text', '文本'),
        ('image', '图片'),
        ('video', '视频'),
    )
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name='messages')
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_messages')
    message_type = models.CharField(max_length=10, choices=MESSAGE_TYPE_CHOICES, default='text')
    content = models.TextField(blank=True)  # 文本内容（可为空，当有附件时）
    attachment = models.FileField(upload_to='chat_attachments/', blank=True, null=True)  # 图片、视频文件
    preview_image = models.ImageField(upload_to='chat_video_previews/', blank=True, null=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False, verbose_name="是否已读")

    class Meta:
        ordering = ['timestamp']

    def __str__(self):
        return f"Message({self.id}) from {self.sender} in conv {self.conversation.id}"
