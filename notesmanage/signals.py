from django.db.models import F
from django.db.models.signals import post_save, post_delete, m2m_changed
from django.dispatch import receiver
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from user.models import PointHistory
from .models import Note, Like, Comment, Favorite, DraftNote, TopNote
from django.contrib.auth import get_user_model
from django.db import transaction
import os
import glob
from django.conf import settings
# 导入通知模型
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
    if delta == -1 and note.author.total_likes ==0:
        note.author.total_likes = 0
    else:
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

@receiver(post_save, sender=TopNote)
def reward_on_top_quality(sender, instance, created, **kwargs):
    """
    当 TopNote 新增或更新时，如果排名进入前 10 并且笔记未标记过优质，则标记并奖励。
    """
    note = instance.note
    # 只处理进入 Top10 的情况
    if instance.rank <= 10 and not note.is_top_quality:
        with transaction.atomic():
            # 标记 Note 为优质笔记
            Note.objects.filter(pk=note.pk).update(is_top_quality=True)
            # 锁定作者并奖励积分
            author = User.objects.select_for_update().get(pk=note.author_id)
            author.points = F('points') + 100
            author.save(update_fields=['points'])
            author.refresh_from_db()
            # 记录积分变动
            PointHistory.objects.create(
                user=author,
                amount=100,
                source='top_quality',
                description=f'笔记《{note.title}》成为 Top10 优质笔记，奖励 100 分'
            )

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
                 'note_id': notification.extra_data.get('note_id', None),
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
                message=f"{user.username} 点赞了你的笔记《{note.title}》",
                extra_data={
                    'like_id': instance.id,
                    'note_id': instance.note.id,
                }
            )
            push_notification(note.author, notification)

@receiver(post_delete, sender=Like)
def delete_note_like_notification(sender, instance, **kwargs):
    Notification.objects.filter(
        recipient=instance.note.author,
        sender=instance.user,
        notification_type='note_like',
        extra_data__like_id=instance.id
    ).delete()


# 2. 笔记收藏通知
@receiver(post_save, sender=Favorite)
def send_note_favorite_notification(sender, instance, created, **kwargs):
    if created:
        note = instance.note
        user = instance.user
        # 避免自己收藏自己的笔记
        if note.author != user:
            notification = Notification.objects.create(
                recipient=note.author,
                sender=user,
                notification_type='note_favorite',
                message=f"{user.username} 收藏了你的笔记《{note.title}》",
                extra_data={
                    'favorite_id': instance.id,
                    'note_id': instance.note.id,
                }
            )
            push_notification(note.author, notification)

@receiver(post_delete, sender=Favorite)
def delete_note_favorite_notification(sender, instance, **kwargs):
    Notification.objects.filter(
        recipient=instance.note.author,
        sender=instance.user,
        notification_type='note_favorite',
        extra_data__favorite_id=instance.id
    ).delete()


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
                    message=f"{user.username} 评论了你的笔记《{note.title}》",
                    extra_data={
                        'comment_id': instance.id,
                        'note_id': note.id
                    }
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
                    message=f"{user.username} 回复了你的评论：{instance.content[:20]}...",
                    extra_data={
                        'comment_id': instance.id,
                        'note_id': note.id
                    }
                )
                push_notification(parent_user, notification)

@receiver(post_delete, sender=Comment)
def update_notification_on_comment_delete(sender, instance, **kwargs):
    notifications = Notification.objects.filter(
        extra_data__comment_id=instance.id,
        notification_type__in=['note_comment', 'comment_reply']
    )
    for notification in notifications:
        notification.message = "该评论不存在。"
        notification.save(update_fields=["message"])


# 4. 评论点赞通知：使用 m2m_changed 信号监听 Comment.likes 变化
@receiver(m2m_changed, sender=Comment.likes.through)
def send_comment_like_notification(sender, instance, action, pk_set, **kwargs):
    if action == "post_add":
        for user_id in pk_set:
            try:
                liker = User.objects.get(id=user_id)
                if liker != instance.user:
                    notification = Notification.objects.create(
                        recipient=instance.user,
                        sender=liker,
                        notification_type='comment_like',
                        message=f"{liker.username} 给你的评论点赞",
                        extra_data={
                            'comment_id': instance.id,
                            'note_id': instance.note.id
                        }
                    )
                    push_notification(instance.user, notification)
            except User.DoesNotExist:
                continue
    elif action == "post_remove":
        for user_id in pk_set:
            Notification.objects.filter(
                recipient=instance.user,
                sender_id=user_id,
                notification_type='comment_like',
                extra_data__comment_id=instance.id
            ).delete()


# 5. 用户关注
@receiver(m2m_changed, sender=User.following.through)
def send_follow_notification(sender, instance, action, pk_set, **kwargs):
    if action == 'post_add':
        for target_user_id in pk_set:
            try:
                target_user = User.objects.get(pk=target_user_id)
            except User.DoesNotExist:
                continue
            # 避免用户关注自己
            if target_user == instance:
                continue
            notification = Notification.objects.create(
                recipient=target_user,
                sender=instance,
                notification_type='follow',
                message=f"{instance.username} 关注了你",
                extra_data={'followed_user_id': instance.id}
            )
            # 推送通知到 target_user 的 websocket 连接
            push_notification(target_user, notification)


# 6. 关注的作者的新笔记通知
@receiver(post_save, sender=Note)
def send_new_note_notification(sender, instance, created, **kwargs):
    if created:
        # 获取笔记的作者和该作者的粉丝(即 User.followers)
        author = instance.author
        # 假设在自定义 User 模型中，关注是通过 ManyToManyField（related_name='followers') 实现
        followers = author.followers.all()
        for follower in followers:
            # 避免作者关注自己导致重复通知
            if follower.id == author.id:
                continue
            # 创建通知记录
            notification = Notification.objects.create(
                recipient=follower,
                sender=author,
                notification_type='new_note',
                message=f"你关注的 {author.username} 发布了新的笔记，快去看看吧",
            )
            notification.extra_data = {'note_id': instance.id}
            notification.save(update_fields=['extra_data'])

            push_notification(follower, notification)
