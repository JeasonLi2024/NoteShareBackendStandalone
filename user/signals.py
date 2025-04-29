from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.db.models.signals import post_save, post_delete
from notifications.models import Notification
from django.db import transaction
from django.db.models import F
from django.dispatch import receiver
from notesmanage.models import Like, Comment, Note
from .models import User, PointHistory
import logging

logger = logging.getLogger(__name__)

@receiver(post_save, sender=Like)
def reward_on_like(sender, instance, created, **kwargs):
    if not created:
        return
    note = instance.note
    actor_id = instance.user_id
    author_id = note.author_id

    # 如果点赞者是笔记作者，跳过积分处理
    if actor_id == author_id:
        return

    with transaction.atomic():
        if User.objects.filter(pk=actor_id, points_like__lt=10).update(
                points=F('points')+1, points_like=F('points_like')+1):
            PointHistory.objects.create(
                user_id=actor_id, amount=1, source='note_like',
                description=f'为笔记《{note.title}》点赞 +1 分'
            )

        if User.objects.filter(pk=author_id, points_like__lt=10).update(
                points=F('points')+1, points_like=F('points_like')+1):
            PointHistory.objects.create(
                user_id=author_id, amount=1, source='note_like',
                description=f'笔记《{note.title}》被点赞 +1 分'
            )


@receiver(post_delete, sender=Like)
def undo_on_like(sender, instance, **kwargs):
    note = instance.note
    actor_id = instance.user_id
    author_id = note.author_id

    # 如果点赞者是笔记作者，跳过积分处理
    if actor_id == author_id:
        return

    with transaction.atomic():
        if User.objects.filter(pk=actor_id, points_like__gt=0).update(
                points=F('points')-1, points_like=F('points_like')-1):
            PointHistory.objects.create(
                user_id=actor_id, amount=-1, source='undo',
                description='用户虽撤销了点赞，但请不要灰心！'
            )

        if User.objects.filter(pk=author_id, points_like__gt=0).update(
                points=F('points')-1, points_like=F('points_like')-1):
            PointHistory.objects.create(
                user_id=author_id, amount=-1, source='undo',
                description='用户虽撤销了点赞，但请不要灰心！'
            )

@receiver(post_save, sender=Comment)
def reward_on_comment(sender, instance, created, **kwargs):
    """评论创建时，给 A(评论者)和 B(作者)各 +1 分(日限额20)，但跳过自己评论自己或回复自己的评论"""
    if not created:
        return

    note      = instance.note
    actor_id  = instance.user_id
    author_id = note.author_id
    try:
        parent = instance.parent
    except:
        parent = None

    # 跳过：A 评论自己的笔记，或 A 回复自己发布的评论
    if actor_id == author_id or (parent.user_id == actor_id):
        return

    with transaction.atomic():
        # 给评论者 A
        if User.objects.filter(pk=actor_id, points_comment__lt=20).update(
                points=F('points')+1, points_comment=F('points_comment')+1):
            PointHistory.objects.create(
                user_id=actor_id, amount=1, source='note_comment',
                description=f'在笔记《{note.title}》下评论 +1 分'
            )
        # 给笔记作者 B
        if User.objects.filter(pk=author_id, points_comment__lt=20).update(
                points=F('points')+1, points_comment=F('points_comment')+1):
            PointHistory.objects.create(
                user_id=author_id, amount=1, source='note_comment',
                description=f'笔记《{note.title}》下收到评论 +1 分'
            )


@receiver(post_delete, sender=Comment)
def undo_on_comment(sender, instance, **kwargs):
    """评论删除时，给 A(评论者)和 B(作者)各 -1 分，但跳过自己撤销自己评论或自己撤销回复自己的评论"""
    note      = instance.note
    actor_id  = instance.user_id
    author_id = note.author_id
    try:
        parent = instance.parent
    except:
        parent = None

    # 跳过：A 取消自己对自己笔记的评论，或 A 取消自己回复自己的评论
    if actor_id == author_id or (parent.user_id == actor_id):
        return

    with transaction.atomic():
        # A 评论者
        if User.objects.filter(pk=actor_id, points_comment__gt=0).update(
                points=F('points')-1, points_comment=F('points_comment')-1):
            PointHistory.objects.create(
                user_id=actor_id, amount=-1, source='undo',
                description='用户虽撤销了评论，但请不要灰心！'
            )
        # B 作者
        if User.objects.filter(pk=author_id, points_comment__gt=0).update(
                points=F('points')-1, points_comment=F('points_comment')-1):
            PointHistory.objects.create(
                user_id=author_id, amount=-1, source='undo',
                description='用户虽撤销了评论，但请不要灰心！'
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

# @receiver(post_save, sender=PointHistory)
# def point_change_notification(sender, instance, created, **kwargs):
#     if not created or not instance.user:
#         return
#     user = User.objects.get(pk=instance.user.pk)
#     current_points = user.points
#     system_user = User.objects.get(username='adminLi')
#     # 创建站内通知
#     notification = Notification.objects.create(
#         recipient=user,
#         sender=system_user,
#         notification_type='points_change',
#         extra_data={},
#         message=f"您的积分发生变动：{instance.description}，当前总积分：{current_points}"
#     )
#     push_notification(user, notification)