from django.urls import path
from .views import (
    NotificationListAPIView,
    NotificationMarkReadAPIView,
    NotificationMarkAllReadAPIView,
)

urlpatterns = [
    # 获取通知列表
    path('list/', NotificationListAPIView.as_view(), name='notification-list'),
    # 标记已读
    path('mark-read/<int:pk>/', NotificationMarkReadAPIView.as_view(), name='notification-mark-read'),
    # 一键已读
    path('mark-all-read/', NotificationMarkAllReadAPIView.as_view(), name='notification-mark-all-read'),
]
