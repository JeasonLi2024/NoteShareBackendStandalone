from django.db.models import F
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.template.loader import render_to_string
from .models import Note, Like, Comment, Notification

def update_note_popularity(note_id):
    """统一更新热度的原子操作"""
    Note.objects.filter(id=note_id).update(
        popularity=F('views_count') * 0.6 + F('likes_count') * 0.3 + F('comments_count') * 0.1
    )

# 处理点赞
@receiver(post_save, sender=Like)
@receiver(post_delete, sender=Like)
def handle_like_change(sender, instance, **kwargs):
    note = instance.note
    delta = 1 if kwargs.get('created', False) else -1
    Note.objects.filter(id=note.id).update(likes_count=F('likes_count') + delta)
    update_note_popularity(note.id)

# 处理评论
@receiver(post_save, sender=Comment)
@receiver(post_delete, sender=Comment)
def handle_comment_change(sender, instance, **kwargs):
    note = instance.note
    delta = 1 if kwargs.get('created', False) else -1
    Note.objects.filter(id=note.id).update(comments_count=F('comments_count') + delta)
    update_note_popularity(note.id)


# @receiver(post_save, sender=Comment)
# def create_comment_notifications(sender, instance, created, **kwargs):
#     if created:
#         # 处理回复通知
#         if instance.parent_comment:
#             notification_content = render_to_string('notifications/reply.txt', {
#                 'sender': instance.user,
#                 'comment': instance
#             })
#
#             Notification.objects.create(
#                 recipient=instance.parent_comment.user,
#                 sender=instance.user,
#                 comment=instance,
#                 notification_type='reply',
#                 content=notification_content
#             )
#
#         # 处理@提及通知
#         mentioned_users = extract_mentioned_users(instance.content)
#         for user in mentioned_users:
#             notification_content = render_to_string('notifications/mention.txt', {
#                 'sender': instance.user,
#                 'comment': instance
#             })
#
#             Notification.objects.create(
#                 recipient=user,
#                 sender=instance.user,
#                 comment=instance,
#                 notification_type='mention',
#                 content=notification_content
#             )
#
#
# def extract_mentioned_users(content):
#     """使用正则表达式提取被@的用户"""
#     from django.contrib.auth import get_user_model
#     import re
#
#     User = get_user_model()
#     usernames = re.findall(r'@([\w.@+-]+)', content)
#     return User.objects.filter(username__in=usernames)