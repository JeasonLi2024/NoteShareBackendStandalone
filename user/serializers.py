from rest_framework import serializers
from .models import User


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ('id', 'username', 'phone', 'avatar', 'email', 'created_at', 'last_login')  # 不返回密码字段，保护用户隐私


class UserCreateSerializer(serializers.ModelSerializer):
    avatar = serializers.ImageField(required=False)
    class Meta:
        model = User
        fields = ['id', 'username', 'password', 'phone', 'avatar', 'email']
        extra_kwargs = {
            'password': {'write_only': True}  # 密码只写不读
        }
    def create(self, validated_data):
        avatar = validated_data.pop('avatar', None)
        user = User.objects.create_user(
            username=validated_data['username'],
            password=validated_data['password'],
            phone=validated_data['phone'],
            email=validated_data.get('email'),
            avatar=avatar,
        )
        return user