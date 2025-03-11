# from django.contrib import admin
# from .models import User
#
# @admin.register(User)
# class CustomUserAdmin(admin.ModelAdmin):
#     # 列表页显示的字段
#     list_display = ['id', 'username', 'phone']
#
#     # 搜索字段
#     search_fields = ['username', 'phone']
#
#     # 排序
#     ordering = ['id']
#
#     # 列表页可以直接编辑的字段
#     list_editable = ['phone']
#
#     # 过滤器
#     list_filter = ['username']
#
#     # 详情页字段
#     fields = ['username', 'password', 'phone']
#
#     actions = ['custom_delete_selected']

from django.contrib import admin
from .models import User
from django.contrib.admin.models import LogEntry

@admin.register(User)
class CustomUserAdmin(admin.ModelAdmin):
    # 列表页显示的字段
    list_display = ['id', 'username', 'phone']

    # 搜索字段
    search_fields = ['username', 'phone']

    # 排序
    ordering = ['id']

    # 列表页可以直接编辑的字段
    list_editable = ['phone']

    # 过滤器
    list_filter = ['username']

    # 详情页字段
    fields = ['username', 'phone']  # 移除了 password 字段

    actions = ['custom_delete_selected']

    def custom_delete_selected(self, request, queryset):
        # 先删除相关日志记录
        LogEntry.objects.filter(user__in=queryset).delete()
        # 批量删除用户
        queryset.delete()

    custom_delete_selected.short_description = "Delete selected users and related logs"
