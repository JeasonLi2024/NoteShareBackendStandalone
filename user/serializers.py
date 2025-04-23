from rest_framework import serializers
from django.contrib.auth import get_user_model

from user.models import PointHistory, Goods

UserModel = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    phone = serializers.CharField(required=False)
    avatar = serializers.SerializerMethodField()
    is_following = serializers.SerializerMethodField()

    class Meta:
        model = UserModel
        fields = (
            'id', 'username', 'email', 'avatar', 'phone', 'created_at', 'last_login',
            'school', 'major', 'grade', 'introduction', 'total_notes', 'total_likes',
            'total_views', 'following_count', 'followers_count', 'is_following', 'ai_limits', 'points',
            'points_note_publish'
        )
        extra_kwargs = {'password': {'write_only': True}}
        read_only_fields = ('created_at', 'last_login')
        ref_name = 'UserAppUserSerializer'

    def get_following_count(self, obj):
        return obj.following.count()

    def get_followers_count(self, obj):
        return obj.followers.count()

    def get_avatar(self, obj):
        request = self.context.get('request')
        # 假设 avatar 是一个 ImageField 或者其他类型的字段
        # 返回头像的 URL 或其他相关信息
        if not request or not obj.avatar:
            return None  # 或者返回一个默认的值
        return request.build_absolute_uri(obj.avatar.url)

    def get_is_following(self, obj):
        request = self.context.get("request")
        if request and request.user and request.user.is_authenticated:
            # 检查当前请求用户的 following 集合中是否存在该对象
            return request.user.following.filter(id=obj.id).exists()
        return False



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


class PointHistorySerializer(serializers.ModelSerializer):
    # 自定义字段显示 source 的可读名称
    source_display = serializers.SerializerMethodField()
    # 格式化时间字段
    created_at = serializers.DateTimeField(format="%Y-%m-%d %H:%M:%S", read_only=True)
    signed_amount = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = PointHistory
        fields = [
            'id', 'signed_amount', 'amount', 'source', 'description', 'created_at', 'source_display'
        ]

        # read_only_fields = fields  # 所有字段均为只读

    def get_source_display(self, obj):
        """获取 source 字段的可读名称"""
        return obj.get_source_display()

    def get_signed_amount(self, obj):
        # 正数前加 "+"，负数直接 str()
        return f"+{obj.amount}" if obj.amount > 0 else str(obj.amount)


class GoodsSerializer(serializers.ModelSerializer):
    image = serializers.SerializerMethodField()

    class Meta:
        model = Goods
        fields = ['id', 'name', 'info', 'image', 'price']

    def get_image(self, obj):
        request = self.context.get('request')
        if obj.image and hasattr(obj.image, 'url'):
            return request.build_absolute_uri(obj.image.url)
        return None
     