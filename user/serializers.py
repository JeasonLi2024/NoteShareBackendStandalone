from rest_framework import serializers
from .models import User


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'phone']  # 不返回密码字段，保护用户隐私


class UserCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'password', 'phone']
        extra_kwargs = {
            'password': {'write_only': True}  # 密码只写不读
        }
