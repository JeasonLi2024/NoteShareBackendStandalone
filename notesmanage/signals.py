from django.db.models import F
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.template.loader import render_to_string
from .models import Note, Like, Comment, Notification

@receiver(post_save, sender=Note)
def update_popularity(sender, instance, **kwargs):
    Note.objects.filter(id=instance.id).update(
        popularity=0.6 * F('views_count') + 0.3 * F('likes_count') + 0.1 * F('comments_count')
    )

@receiver(post_save, sender=Like)
@receiver(post_delete, sender=Like)
def update_note_popularity_on_like_change(sender, instance, **kwargs):
    note = instance.note
    # 判断操作类型并计算增量
    if 'created' in kwargs:
        # post_save 信号：只有新建点赞时触发
        if not kwargs['created']:
            return  # 忽略更新操作
        delta = 1
    else:
        # post_delete 信号：取消点赞时触发
        delta = -1

    # 使用原子操作更新 Note 的 likes_count 和 popularity
    Note.objects.filter(id=note.id).update(
        likes_count=F('likes_count') + delta,
        popularity=0.6 * F('views_count') + 0.3 * (F('likes_count') + delta) + 0.1 * F('comments_count')
    )

@receiver(post_save, sender=Comment)
@receiver(post_delete, sender=Comment)
def update_note_popularity_on_comment_change(sender, instance, **kwargs):
    note = instance.note
    Note.objects.filter(id=note.id).update(
        comments_count=F('comments_count') + (1 if kwargs.get('created', False) else -1),
        popularity=0.6 * F('views_count') + 0.3 * F('likes_count') + 0.1 * F('comments_count')
    )


@receiver(post_save, sender=Comment)
def create_comment_notifications(sender, instance, created, **kwargs):
    if created:
        # 处理回复通知
        if instance.parent_comment:
            notification_content = render_to_string('notifications/reply.txt', {
                'sender': instance.user,
                'comment': instance
            })

            Notification.objects.create(
                recipient=instance.parent_comment.user,
                sender=instance.user,
                comment=instance,
                notification_type='reply',
                content=notification_content
            )

        # 处理@提及通知
        mentioned_users = extract_mentioned_users(instance.content)
        for user in mentioned_users:
            notification_content = render_to_string('notifications/mention.txt', {
                'sender': instance.user,
                'comment': instance
            })

            Notification.objects.create(
                recipient=user,
                sender=instance.user,
                comment=instance,
                notification_type='mention',
                content=notification_content
            )


def extract_mentioned_users(content):
    """使用正则表达式提取被@的用户"""
    from django.contrib.auth import get_user_model
    import re

    User = get_user_model()
    usernames = re.findall(r'@([\w.@+-]+)', content)
    return User.objects.filter(username__in=usernames)