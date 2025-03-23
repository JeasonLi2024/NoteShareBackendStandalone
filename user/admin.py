from django.contrib import admin
from .models import User

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
    fields = ['username', 'password', 'phone']

