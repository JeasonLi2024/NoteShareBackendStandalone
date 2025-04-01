from django.contrib import admin
from django_ckeditor_5.fields import CKEditor5Field
from django_ckeditor_5.widgets import CKEditor5Widget
from .models import Note, TopNote
from django.core.mail import send_mail
from django.conf import settings
from django.db.models import Q


@admin.register(Note)
class NoteAdmin(admin.ModelAdmin):
    class Media:
        css = {
            'all': ('css/ckeditor5_custom.css',)
        }
    # 列表显示字段
    list_display = ('id', 'title', 'author', 'views_count', 'category', 'created_at', 'is_private', 'body', 'popularity')

    # 可跳转的字段
    list_display_links = ['id', 'title', 'author']

    # 过滤器
    list_filter = ('is_private', 'created_at')

    # 搜索字段
    search_fields = ('title', 'content', 'author__username', 'body')

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

    def get_search_results(self, request, queryset, search_term):
        # 使用Q对象构建复杂的查询条件
        queries = (Q(title__icontains=search_term) |
                   Q(author__username__icontains=search_term) |
                   Q(body__icontains=search_term))  # 添加对 body 字段的模糊搜索
        return queryset.filter(queries), False  # 返回新的queryset以及是否可能有重复结果

    formfield_overrides = {
        CKEditor5Field: {'widget': CKEditor5Widget(config_name='extends')}
    }

@admin.register(TopNote)
class TopNoteAdmin(admin.ModelAdmin):
    # 列表显示字段
    list_display = ('note_id', 'note_title', 'note_category', 'popularity', 'rank')

    # 可跳转的字段
    list_display_links = ['note_id', 'note_title']

    # 过滤器
    list_filter = ('note__category',)

    # 搜索字段
    search_fields = ('note__title', 'note__category')

    # 只读字段
    readonly_fields = ('note_id', 'note_title', 'popularity', 'rank')

    # 排序
    ordering = ('rank',)

    # 自定义方法（可选）
    def note_title(self, obj):
        return obj.note.title

    note_title.short_description = '笔记标题'

    def note_category(self, obj):
        return obj.note.category

    note_category.short_description = '笔记类别'
