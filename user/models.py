from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.utils import timezone
import random

class UserManager(BaseUserManager):
    def create_user(self, username, password=None, **extra_fields):
        if not username:
            raise ValueError('The Username field must be set')
        user = self.model(username=username, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, username, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        return self.create_user(username, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    username = models.CharField(max_length=10, unique=True)
    phone = models.CharField(max_length=11, unique=True, verbose_name='手机号')
    avatar = models.ImageField(upload_to='avatars/', null=True, blank=True, verbose_name='头像')
    def save(self, *args, **kwargs):
        if not self.avatar:
            # 选择一个默认头像
            default_avatars = ['defaults/default1.jpg', 'defaults/default2.jpg', 'defaults/default3.jpg', 'defaults/default4.jpg']
            default_avatar_path = f'avatars/{random.choice(default_avatars)}'
            self.avatar = default_avatar_path
        super().save(*args, **kwargs)
    email = models.EmailField(unique=True, verbose_name='电子邮件')
    created_at = models.DateTimeField(default=timezone.now, verbose_name='创建时间')
    last_login = models.DateTimeField(null=True, blank=True, verbose_name='最后登录时间')
    introduction = models.CharField(max_length=200, null=True, blank=True, verbose_name='个人简介')
    school = models.CharField(max_length=100, null=True, blank=True, verbose_name='学校')
    major = models.CharField(max_length=100, null=True, blank=True, verbose_name='专业')
    grade = models.CharField(max_length=100, null=True, blank=True, verbose_name='年级')
    gender = models.CharField(max_length=5, null=True, blank=True, verbose_name='性别')

    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)

    # 获赞数：所有自己笔记的点赞数之和，初始为0
    total_likes = models.PositiveIntegerField(default=0, verbose_name='获赞数')
    # 总浏览量：所有自己笔记的浏览次数之和，初始为0
    total_views = models.PositiveIntegerField(default=0, verbose_name='总浏览')
    # 关注功能：用户关注其他用户（非对称关系，关注的用户属于 following，而粉丝则由反向关系 followers 得到）
    following = models.ManyToManyField(
        'self',
        symmetrical=False,
        related_name='followers',
        blank=True,
        verbose_name='关注的用户'
    )
    def following_count(self):
        return self.following.count()
    following_count.short_description = "关注"

    def followers_count(self):
        return self.followers.count()
    followers_count.short_description = "粉丝数"

    groups = models.ManyToManyField(
        'auth.Group',
        verbose_name='groups',
        blank=True,
        help_text='The groups this user belongs to. A user will get all permissions granted to each of their groups.',
        related_name='custom_user_set',  # 设置related_name
        related_query_name='custom_user',
    )
    user_permissions = models.ManyToManyField(
        'auth.Permission',
        verbose_name='user permissions',
        blank=True,
        help_text='Specific permissions for this user.',
        related_name='custom_user_set',  # 设置related_name
        related_query_name='custom_user',
    )

    objects = UserManager()

    USERNAME_FIELD = 'username'
    REQUIRED_FIELDS = []

    class Meta:
        db_table = 'user'
        verbose_name = '用户'
        verbose_name_plural = '用户'

    def __str__(self):
        return self.username