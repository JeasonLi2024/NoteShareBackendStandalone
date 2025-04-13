from django.db.models import F
from django.db.models.signals import post_save, post_delete, m2m_changed
from django.dispatch import receiver
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from .models import Note, Like, Comment, Favorite
from django.contrib.auth import get_user_model

# 导入通知模型（注意确保 notifications 应用在 INSTALLED_APPS 中）
from notifications.models import Notification

User = get_user_model()

def update_note_popularity(note_id):
    """统一更新热度的原子操作"""
    Note.objects.filter(id=note_id).update(
        popularity=F('views_count') * 0.6 + F('likes_count') * 0.3 + F('comments_count') * 0.1
    )

# 处理收藏
@receiver(post_save, sender=Favorite)
@receiver(post_delete, sender=Favorite)
def handle_like_change(sender, instance, **kwargs):
    note = instance.note
    delta = 1 if kwargs.get('created', False) else -1
    Note.objects.filter(id=note.id).update(favorites_count=F('favorites_count') + delta)

# 处理点赞
@receiver(post_save, sender=Like)
@receiver(post_delete, sender=Like)
def handle_like_change(sender, instance, **kwargs):
    note = instance.note
    # 判断是点赞还是取消点赞
    delta = 1 if kwargs.get('created', False) else -1
    Note.objects.filter(id=note.id).update(likes_count=F('likes_count') + delta)
    # 更新作者的总获赞数（确保不为负）
    note.author.total_likes = F('total_likes') + delta
    note.author.save()
    update_note_popularity(note.id)

# 处理评论
@receiver(post_save, sender=Comment)
@receiver(post_delete, sender=Comment)
def handle_comment_change(sender, instance, **kwargs):
    note = instance.note
    delta = 1 if kwargs.get('created', False) else -1
    Note.objects.filter(id=note.id).update(comments_count=F('comments_count') + delta)
    update_note_popularity(note.id)

def push_notification(user, notification):
    """
    通过 websocket 将通知推送给用户
    """
    channel_layer = get_channel_layer()
    group_name = f"notifications_{user.id}"
    async_to_sync(channel_layer.group_send)(
         group_name,
         {
             'type': 'notify',  # 对应 consumers.py 中的 notify 方法
             'notification': {
                 'id': notification.id,
                 'notification_type': notification.notification_type,
                 'message': notification.message,
                 'is_read': notification.is_read,
                 'created_at': notification.created_at.strftime('%Y-%m-%d %H:%M:%S'),
             }
         }
    )

# 1. 笔记点赞通知：在 Like 创建时发送通知
@receiver(post_save, sender=Like)
def send_note_like_notification(sender, instance, created, **kwargs):
    if created:
        note = instance.note
        user = instance.user
        # 避免自己点赞自己的笔记
        if note.author != user:
            notification = Notification.objects.create(
                recipient=note.author,
                sender=user,
                notification_type='note_like',
                message=f"{user.username} 点赞了你的笔记《{note.title}》"
            )
            push_notification(note.author, notification)

# 2. 笔记收藏通知
@receiver(post_save, sender=Favorite)
def send_note_like_notification(sender, instance, created, **kwargs):
    if created:
        note = instance.note
        user = instance.user
        # 避免自己收藏自己的笔记
        if note.author != user:
            notification = Notification.objects.create(
                recipient=note.author,
                sender=user,
                notification_type='note_favorite',
                message=f"{user.username} 收藏了你的笔记《{note.title}》"
            )
            push_notification(note.author, notification)

# 3. 笔记评论 & 评论回复通知：在 Comment 创建时根据 parent 字段区分
@receiver(post_save, sender=Comment)
def send_comment_notification(sender, instance, created, **kwargs):
    if created:
        note = instance.note
        user = instance.user
        if instance.parent is None:
            # 直接对笔记的评论，通知笔记作者（排除自己评论自己的情况）
            if note.author != user:
                notification = Notification.objects.create(
                    recipient=note.author,
                    sender=user,
                    notification_type='note_comment',
                    message=f"{user.username} 评论了你的笔记《{note.title}》"
                )
                push_notification(note.author, notification)
        else:
            # 评论回复，通知被回复的评论发布者（如果不是自己回复自己则发送通知）
            parent_user = instance.parent.user
            if parent_user != user:
                notification = Notification.objects.create(
                    recipient=parent_user,
                    sender=user,
                    notification_type='comment_reply',
                    message=f"{user.username} 回复了你的评论：{instance.content[:20]}..."
                )
                push_notification(parent_user, notification)

# 4. 评论点赞通知：使用 m2m_changed 信号监听 Comment.likes 变化
@receiver(m2m_changed, sender=Comment.likes.through)
def send_comment_like_notification(sender, instance, action, pk_set, **kwargs):
    if action == "post_add":
        for user_id in pk_set:
            try:
                liker = User.objects.get(pk=user_id)
            except User.DoesNotExist:
                continue
            # 避免用户给自己点赞的情况
            if instance.user != liker:
                notification = Notification.objects.create(
                    recipient=instance.user,
                    sender=liker,
                    notification_type='comment_like',
                    message=f"{liker.username} 给你的评论点赞"
                )
                push_notification(instance.user, notification)

# 5. 用户关注
@receiver(m2m_changed, sender=User.following.through)
def send_follow_notification(sender, instance, action, pk_set, **kwargs):
    """
    当 instance 的 following 字段发生变化时发送关注通知
    - instance：表示执行操作的用户（即发起关注的人）
    - pk_set：为被关注用户的ID集合
    """
    if action == 'post_add':
        for target_user_id in pk_set:
            try:
                target_user = User.objects.get(pk=target_user_id)
            except User.DoesNotExist:
                continue
            # 避免用户关注自己
            if target_user == instance:
                continue
            # 创建关注通知（此处通知类型可以定义为 'follow'）
            notification = Notification.objects.create(
                recipient=target_user,
                sender=instance,
                notification_type='follow',
                message=f"{instance.username} 关注了你"
            )
            # 推送通知到 target_user 的 websocket 连接
            push_notification(target_user, notification)