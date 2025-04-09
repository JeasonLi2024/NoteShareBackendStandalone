from rest_framework import serializers
from django.contrib.auth import get_user_model

UserModel = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    phone = serializers.CharField(required=False)
    class Meta:
        model = UserModel
        fields = (
            'id', 'username', 'email', 'avatar', 'phone', 'created_at', 'last_login',
            'school', 'major', 'grade', 'introduction'  # 添加新的字段
        )
        extra_kwargs = {'password': {'write_only': True}}
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


#支持用户名/手机号/邮箱+密码登录
class LoginSerializer(serializers.Serializer):
    username_or_email_or_phone = serializers.CharField()
    password = serializers.CharField()

    def validate(self, data):
        username_or_email_or_phone = data.get('username_or_email_or_phone')
        password = data.get('password')

        # 尝试通过用户名、邮箱或手机号进行用户认证
        user = None
        if '@' in username_or_email_or_phone:
            print(f"Trying to find user by email: {username_or_email_or_phone}")
            user = UserModel.objects.filter(email=username_or_email_or_phone).first()
        elif username_or_email_or_phone.isdigit():
            print(f"Trying to find user by phone: {username_or_email_or_phone}")
            user = UserModel.objects.filter(phone=username_or_email_or_phone).first()
        else:
            print(f"Trying to find user by username: {username_or_email_or_phone}")
            user = UserModel.objects.filter(username=username_or_email_or_phone).first()

        if user:
            print(f"Found user: {user.username}, is_active: {user.is_active}")
            if user.check_password(password):
                data['user'] = user  # 将用户对象添加到 validated_data
                return data
            else:
                print("密码输入错误，请重试。")
        else:
            print("没用当前用户信息。")

        raise serializers.ValidationError("无法使用提供的信息登录。")

