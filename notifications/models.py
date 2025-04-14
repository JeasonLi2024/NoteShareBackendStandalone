from django.db import models
from user.models import User

NOTIFICATION_TYPE_CHOICES = (
    ('note_like', '笔记点赞'),
    ('note_comment', '笔记评论'),
    ('note_favorite', '笔记收藏'),
    ('comment_reply', '评论回复'),
    ('comment_like', '评论点赞'),
    ('follow', '关注'),
    ('new_note', '关注作者的新笔记'),
)


class Notification(models.Model):
    recipient = models.ForeignKey(
        User, on_delete=models.CASCADE,
        related_name='notifications'
    )
    sender = models.ForeignKey(
        User, on_delete=models.CASCADE,
        null=True, blank=True, related_name='sent_notifications'
    )
    notification_type = models.CharField(max_length=20, choices=NOTIFICATION_TYPE_CHOICES)
    message = models.TextField(blank=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    extra_data = models.JSONField(blank=True, null=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        sender_str = self.sender.username if self.sender else '系统'
        return f"{self.get_notification_type_display()} - {sender_str} -> {self.recipient.username}"
