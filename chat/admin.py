# chat/admin.py
from django.contrib import admin
from .models import Conversation, Message

@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ['id', 'author_username', 'visitor_username', 'created_at']
    filter_horizontal = ['participants']

    def author_username(self, obj):
        return obj.author.username
    author_username.short_description = '作者'

    def visitor_username(self, obj):
        return obj.visitor.username
    visitor_username.short_description = '访客'

@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ['id', 'conversation', 'sender', 'timestamp']
