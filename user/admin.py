from django.contrib import admin
from django.contrib.auth.forms import ReadOnlyPasswordHashField
from django import forms
from .models import User
from django.core.mail import send_mail
from django.conf import settings
from django.utils.html import format_html
from django.urls import path
from django.http import HttpResponseRedirect
from django.contrib import messages


# 自定义创建用户的表单
class UserCreationForm(forms.ModelForm):
    """用于创建新用户的表单，包含所有必需的字段，以及一个重复的密码字段。"""
    password1 = forms.CharField(label='密码', widget=forms.PasswordInput)
    password2 = forms.CharField(label='确认密码', widget=forms.PasswordInput)

    class Meta:
        model = User
        fields = ('username', 'phone', 'email')

    def clean_password2(self):
        # 检查两次输入的密码是否一致
        password1 = self.cleaned_data.get("password1")
        password2 = self.cleaned_data.get("password2")
        if password1 and password2 and password1 != password2:
            raise forms.ValidationError("密码不匹配")
        return password2

    def save(self, commit=True):
        # 保存提供的密码并进行哈希处理
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password1"])
        if commit:
            user.save()
        return user


# 自定义更新用户的表单
class UserChangeForm(forms.ModelForm):
    """用于更新用户的表单，包含用户的所有字段，但将密码字段替换为管理员的密码哈希显示字段。"""
    password = ReadOnlyPasswordHashField()

    class Meta:
        model = User
        fields = ('username', 'phone', 'email', 'school', 'major', 'grade', 'is_active', 'is_staff', 'is_superuser')

    # def clean_password(self):
    #     # 无论用户提供什么值，都返回初始值
    #     # 这里这样做是因为字段无法访问初始值
    #     return self.initial["password"]


# 自定义 UserAdmin 类
@admin.register(User)
class CustomUserAdmin(admin.ModelAdmin):
    # 用于添加和更改用户实例的表单
    form = UserChangeForm
    add_form = UserCreationForm

    # 列表页显示的字段
    list_display = ['id', 'username', 'phone', 'email', 'school', 'major', 'reset_password']

    # 可跳转的字段
    list_display_links = ['id', 'username']

    # 搜索字段
    search_fields = ['username', 'phone', 'email', 'school', 'major', 'grade']

    # 排序
    ordering = ['id']

    # 列表页可以直接编辑的字段
    list_editable = []

    # 过滤器
    list_filter = ['username']

    # 详情页字段
    fields = ['username', 'phone', 'email', 'school', 'major', 'grade', 'is_active', 'is_staff', 'is_superuser']

    # 添加自定义操作：重置密码
    def reset_password(self, obj):
        return format_html(
            '<a class="button" href="{}">重置密码</a>',
            f'{obj.id}/reset-password/'
        )

    reset_password.short_description = '操作'
    reset_password.allow_tags = True

    # 重写 get_urls 方法以添加自定义 URL
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('<int:id>/reset-password/', self.admin_site.admin_view(self.reset_password_view),
                 name='reset_password'),
        ]
        return custom_urls + urls

    # 处理密码重置请求
    def reset_password_view(self, request, id):
        user = self.get_object(request, id)
        if user is None:
            self.message_user(request, "用户不存在", level=messages.ERROR)
            return HttpResponseRedirect(request.META.get('HTTP_REFERER'))

        # 重置密码
        new_password = '0987654321'
        user.set_password(new_password)
        user.save()

        # 发送邮件通知
        subject = '您的密码已重置'
        message = f'您的密码已被重置为初始默认密码 {new_password}。请尽快登录并更改密码。'
        from_email = settings.DEFAULT_FROM_EMAIL
        recipient_list = [user.email]
        send_mail(subject, message, from_email, recipient_list)

        self.message_user(request,
                          f"用户 {user.username} 的密码已重置为初始默认密码 {new_password}，并通过邮件通知该用户。")
        return HttpResponseRedirect(request.META.get('HTTP_REFERER'))

    # 重写保存方法
    def save_model(self, request, obj, form, change):
        if not change:  # 如果是创建新用户
            obj.set_password(form.cleaned_data['password1'])
        else:
            # 如果是修改用户且密码字段被修改
            if 'password' in form.changed_data:
                obj.set_password('0987654321')
                # 发送邮件通知
                subject = '您的密码已重置'
                message = f'您的密码已被重置为初始默认密码 0987654321。请尽快登录并更改密码。'
                from_email = settings.DEFAULT_FROM_EMAIL
                recipient_list = [obj.email]
                send_mail(subject, message, from_email, recipient_list)
                self.message_user(request,
                                  f"用户 {obj.username} 的密码已重置为初始默认密码 0987654321，并已通过邮件通知该用户。")
        super().save_model(request, obj, form, change)

    # 重写 get_form 方法以使用正确的表单
    def get_form(self, request, obj=None, **kwargs):
        if not obj:
            self.form = self.add_form
        else:
            self.form = self.form
        return super().get_form(request, obj, **kwargs)

    # 重写 get_fieldsets 方法以显示密码输入栏
    def get_fieldsets(self, request, obj=None):
        if not obj:
            return self.add_fieldsets
        return super().get_fieldsets(request, obj)

    # 重写 add_fieldsets 以显示密码输入栏
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'phone', 'email', 'password1', 'password2'),
        }),
    )

