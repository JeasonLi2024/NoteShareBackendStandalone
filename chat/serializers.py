from rest_framework import serializers
from .models import Conversation, Message


class MessageSerializer(serializers.ModelSerializer):
    sender_username = serializers.CharField(source='sender.username', read_only=True)
    attachment_url = serializers.SerializerMethodField()
    preview_url = serializers.SerializerMethodField()

    class Meta:
        model = Message
        fields = ['id', 'sender_username', 'message_type', 'content', 'timestamp', 'is_read', 'attachment_url', 'preview_url']

    def get_attachment_url(self, obj):
        request = self.context.get('request')
        if obj.attachment:
            return request.build_absolute_uri(obj.attachment.url)
        return None

    def get_preview_url(self, obj):
        request = self.context.get('request')
        if hasattr(obj, 'preview_image') and obj.preview_image:
            return request.build_absolute_uri(obj.preview_image.url)
        return None


class ConversationSerializer(serializers.ModelSerializer):
    participants = serializers.StringRelatedField(many=True)
    last_message = serializers.SerializerMethodField()
    unread_count = serializers.SerializerMethodField()

    author_blocked = serializers.BooleanField(read_only=True)
    author_dnd = serializers.BooleanField(read_only=True)
    visitor_dnd = serializers.BooleanField(read_only=True)
    # 返回当前用户在此会话中的 DND 状态
    current_user_dnd = serializers.SerializerMethodField()

    class Meta:
        model = Conversation
        fields = [
            'id', 'author_id', 'visitor_id', 'participants', 'created_at',
            'last_message', 'unread_count',
            'author_blocked', 'author_dnd', 'visitor_dnd', 'current_user_dnd',
        ]

    def get_last_message(self, obj):
        last_msg = obj.messages.order_by('-timestamp').first()
        if last_msg:
            return MessageSerializer(last_msg, context=self.context).data
        return None

    def get_unread_count(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            from chat.utils import get_conversation_unread_count
            return get_conversation_unread_count(obj, request.user)
        return 0

    def get_current_user_dnd(self, obj):
        """前端只需关注自己开/关免打扰"""
        user = self.context.get('request').user
        if user == obj.author:
            return obj.author_dnd
        elif user == obj.visitor:
            return obj.visitor_dnd
        return False