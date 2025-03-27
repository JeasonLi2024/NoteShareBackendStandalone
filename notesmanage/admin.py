from django.contrib import admin
from django_ckeditor_5.fields import CKEditor5Field
from django_ckeditor_5.widgets import CKEditor5Widget
from .models import Note
from django.core.mail import send_mail
from django.conf import settings


@admin.register(Note)
class NoteAdmin(admin.ModelAdmin):
    # 列表显示字段
    list_display = ('title', 'author', 'created_at', 'is_private', 'body')

    # 过滤器
    list_filter = ('is_private', 'created_at')

    # 搜索字段
    search_fields = ('title', 'content', 'author')

    # 只读字段
    readonly_fields = ('created_at', 'updated_at')

    # 动作
    actions = ['delete_selected_notes']

    def delete_selected_notes(self, request, queryset):
        for note in queryset:
            email = note.author.email
            subject = '您的笔记已被删除'
            message = '您的笔记不符合规范已被管理员删除。'
            from_email = settings.DEFAULT_FROM_EMAIL
            recipient_list = [email]
            send_mail(subject, message, from_email, recipient_list)
            note.delete()
        self.message_user(request, f"已成功删除 {queryset.count()} 条笔记，并通知了用户。")

    delete_selected_notes.short_description = "删除选中的笔记并通知用户"

    formfield_overrides = {
        CKEditor5Field: {'widget': CKEditor5Widget(config_name='extends')}
    }