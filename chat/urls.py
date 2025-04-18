from django.urls import path
from .views import (
    ConversationMessagesView, UserConversationsView, MessageDeleteView,
    StartConversationView,UploadAttachmentView, ToggleBlockView, ToggleDNDView
)

urlpatterns = [
    # 启动/获取对话接口：POST 请求，传入目标作者 ID
    path('start_conversation/', StartConversationView.as_view(), name='start-conversation'),
    # 获取某一聊天室的聊天记录信息
    path('conversations/<int:conversation_id>/messages/', ConversationMessagesView.as_view(), name='conversation-messages'),
    # 获取当前用户的所有对话
    path('conversations/', UserConversationsView.as_view(), name='user-conversations'),
    # 单个消息删除： DELETE /api/chat/messages/<int:pk>/
    path('messages/<int:pk>/', MessageDeleteView.as_view(), name='message-delete'),
    # # 批量删除消息： POST /api/chat/messages/bulk-delete/
    # path('messages/bulk-delete/', MessageBulkDeleteView.as_view(), name='message-bulk-delete'),
    # # 删除某个对话内的所有消息： DELETE /api/chat/conversations/<int:conversation_id>/messages/
    # path('conversations/<int:conversation_id>/messages/', ConversationMessagesDeleteView.as_view(), name='conversation-messages-delete'),
    # 附件上传发送
    path('upload_attachment/', UploadAttachmentView.as_view(), name='upload-attachment'),
    # 拉黑操作
    path('conversations/<int:pk>/toggle_block/', ToggleBlockView.as_view(), name='conversation-toggle-block'),
    # 免打扰操作
    path('conversations/<int:pk>/toggle_dnd/', ToggleDNDView.as_view(), name='conversation-toggle-dnd'),

]
