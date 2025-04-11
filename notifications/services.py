from django.core.cache import cache
from .models import Notification


class NotificationService:
    CACHE_TIMEOUT = 60 * 5  # 5分钟缓存

    @classmethod
    def create_notification(cls, recipient, actor, verb, target):
        """创建通知并触发推送"""
        notification = Notification.objects.create(
            user=recipient,
            actor=actor,
            verb=verb,
            target=target
        )
        cls._clear_cache(recipient)
        return notification

    @classmethod
    def get_user_notifications(cls, user):
        """获取用户通知列表（带缓存）"""
        cache_key = f"user_{user.id}_notifications"
        notifications = cache.get(cache_key)

        if not notifications:
            notifications = list(
                Notification.objects.filter(user=user)
                .select_related('actor')
                .order_by('-timestamp')[:50]
            )
            cache.set(cache_key, notifications, cls.CACHE_TIMEOUT)

        return notifications

    @classmethod
    def mark_as_read(cls, notification_id, user):
        """标记通知为已读"""
        Notification.objects.filter(
            id=notification_id,
            user=user
        ).update(read=True)
        cls._clear_cache(user)

    @classmethod
    def _clear_cache(cls, user):
        """清理用户缓存"""
        cache.delete(f"user_{user.id}_notifications")
        cache.delete(f"unread_count_{user.id}")

    @classmethod
    def get_unread_count(cls, user):
        """获取未读数量（带缓存）"""
        cache_key = f"unread_count_{user.id}"
        count = cache.get(cache_key)

        if count is None:
            count = Notification.objects.filter(
                user=user,
                read=False
            ).count()
            cache.set(cache_key, count, cls.CACHE_TIMEOUT)

        return count