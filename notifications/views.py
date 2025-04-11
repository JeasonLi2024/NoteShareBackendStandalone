from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions
from .models import Notification
from .serializers import NotificationSerializer

# 获取当前用户所有通知，包含 is_read 字段，便于前端区分已读/未读样式
class NotificationListAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        notifications = Notification.objects.filter(recipient=request.user)
        serializer = NotificationSerializer(notifications, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

# 将单个通知标记为已读，如已是已读状态则返回提示信息
class NotificationMarkReadAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        try:
            notification = Notification.objects.get(pk=pk, recipient=request.user)
        except Notification.DoesNotExist:
            return Response({'detail': '通知不存在'}, status=status.HTTP_404_NOT_FOUND)

        if notification.is_read:
            return Response({'detail': '通知已经是已读状态'}, status=status.HTTP_200_OK)

        notification.is_read = True
        notification.save()
        return Response({'detail': '通知标记为已读'}, status=status.HTTP_200_OK)

# 一键将当前用户所有未读通知标记为已读
class NotificationMarkAllReadAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        unread_notifications = Notification.objects.filter(recipient=request.user, is_read=False)
        count = unread_notifications.count()
        if count == 0:
            return Response({'detail': '没有未读通知'}, status=status.HTTP_200_OK)

        unread_notifications.update(is_read=True)
        return Response({'detail': f'{count} 条通知已标记为已读'}, status=status.HTTP_200_OK)

