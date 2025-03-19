from rest_framework import serializers
from .models import User
from django.contrib.auth import authenticate
from django.contrib.auth import get_user_model

UserModel = get_user_model()
class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserModel
        fields = (
            'id', 'username', 'email', 'avatar', 'phone', 'created_at', 'last_login',
            'school', 'major', 'grade'  # 添加新的字段
        )# 不返回密码字段，保护用户隐私
        read_only_fields = ('created_at', 'last_login')

class UserCreateSerializer(serializers.ModelSerializer):
    avatar = serializers.ImageField(required=False, allow_null=True)
    verification_code = serializers.CharField(write_only=True)
    class Meta:
        model = UserModel
        fields = [
            'id', 'username', 'password', 'email', 'avatar', 'phone',
            'school', 'major', 'grade', 'verification_code'  # 添加新的字段
        ]
        extra_kwargs = {
            'password': {'write_only': True}  # 密码只写不读
        }

    def create(self, validated_data):
        avatar = validated_data.pop('avatar', None)
        school = validated_data.pop('school', None)
        major = validated_data.pop('major', None)
        grade = validated_data.pop('grade', None)
        validated_data.pop('verification_code')
        user = UserModel.objects.create_user(
            username=validated_data['username'],
            password=validated_data['password'],
            email=validated_data['email'],
            phone=validated_data['phone'],
            avatar=avatar,
            school=school,
            major=major,
            grade=grade,
        )
        user.set_password(validated_data['password'])
        user.save()
        return user

class LoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField()

    def validate(self, data):
        user = authenticate(**data)
        if user and user.is_active:
            return user
        raise serializers.ValidationError("Invalid credentials")
