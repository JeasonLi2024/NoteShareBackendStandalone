# serializers.py
from rest_framework import serializers
from .models import Note, Comment, Like, Notification
from django.contrib.auth import get_user_model
import pytz

User = get_user_model()

class UserSerializer(serializers.ModelSerializer):
    avatar = serializers.SerializerMethodField()
    class Meta:
        model = User
        fields = ['id', 'username', 'avatar']

    def get_avatar(self, obj):
        request = self.context.get('request')
        # 假设 avatar 是一个 ImageField 或者其他类型的字段
        # 返回头像的 URL 或其他相关信息
        if obj.avatar:
            return request.build_absolute_uri(obj.avatar.url)
        return None


class CommentSerializer(serializers.ModelSerializer):
    note = serializers.PrimaryKeyRelatedField(read_only=True)  # 不让前端传递
    user = UserSerializer(read_only=True)
    like_count = serializers.IntegerField(source='annotated_likes', read_only=True)
    dislike_count = serializers.IntegerField(read_only=True)
    is_liked = serializers.SerializerMethodField()
    is_disliked = serializers.SerializerMethodField()
    display_content = serializers.SerializerMethodField()
    top_replies = serializers.SerializerMethodField()
    total_replies = serializers.SerializerMethodField()

    class Meta:
        model = Comment
        fields = [
            'id', 'note', 'user', 'parent', 'content', 'dislike_count','created_at',
            'updated_at', 'like_count', 'is_liked', 'is_disliked', 'display_content', 'top_replies', 'total_replies'
        ]
        read_only_fields = ['id', 'user', 'created_at', 'updated_at', 'like_count', 'is_liked', 'is_disliked']

    def get_top_replies(self, obj):
        replies = getattr(obj, 'filtered_replies', [])[:5]
        return CommentSerializer(
            replies,
            many=True,
            context=self.context
        ).data

    def get_total_replies(self, obj):
        # 获取该根评论的总回复数
        return obj.replies.count()

    def get_is_liked(self, obj):
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return False
        return obj.likes.filter(id=request.user.id).exists()

    def get_is_disliked(self, obj):
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return False
        return obj.dislikes.filter(id=request.user.id).exists()

    def get_display_content(self, obj):
        """根据不喜欢状态返回不同内容"""
        if self.get_is_disliked(obj):
            return "该评论被折叠"
        return obj.get_display_content()  # 保持原有显示逻辑

    def validate(self, data):
        # 不再限制回复层级，允许对任何评论进行回复
        return data

    def create(self, validated_data):
        # 自动设置评论作者
        request = self.context.get('request')
        validated_data['user'] = request.user
        return super().create(validated_data)


class NoteSerializer(serializers.ModelSerializer):
    author_info = serializers.SerializerMethodField()
    # likes_count = serializers.SerializerMethodField()
    # comments_count = serializers.SerializerMethodField()
    is_liked = serializers.SerializerMethodField()
    comments = CommentSerializer(many=True, read_only=True)

    class Meta:
        model = Note
        fields = '__all__'
        read_only_fields = ['author', 'likes', 'views_count', 'likes_count', 'comments_count']
    def get_author_info(self, obj):
        request = self.context.get('request')
        author_info = obj.author_info
        if author_info['avatar']:
            author_info['avatar'] = request.build_absolute_uri(author_info['avatar'])
        return author_info

    def validate_title(self, value):
        if len(value) < 5:
            raise serializers.ValidationError("标题至少需要5个字符")
        return value

    def validate_content(self, value):
        if len(value) < 10:
            raise serializers.ValidationError("内容至少需要10个字符")
        return value

    # def get_likes_count(self, obj):
    #     return obj.likes.count()
    #
    # def get_comments_count(self, obj):
    #     return obj.comments.count()

    def create(self, validated_data):
        validated_data['author'] = self.context['request'].user
        return super().create(validated_data)

    def get_is_liked(self, obj):
        # 判断当前用户是否已点赞该笔记
        user = self.context['request'].user
        if user.is_authenticated:
            return obj.likes.filter(id=user.id).exists()
        return False

# 简化笔记信息
class NoteSimpleSerializer(serializers.ModelSerializer):
    author_username = serializers.ReadOnlyField(source='author.username')
    avatar = serializers.SerializerMethodField()
    cover_image = serializers.SerializerMethodField()

    class Meta:
        model = Note
        fields = [
            'id', 'author_username', 'avatar', 'cover_image', 'likes_count',
            'views_count', 'popularity', 'title', 'content', 'comments_count'
        ]

    def get_avatar(self, obj):
        request = self.context.get('request')
        if obj.author.avatar:
            return request.build_absolute_uri(obj.author.avatar.url)
        return None

    def get_cover_image(self, obj):
        request = self.context.get('request')
        if obj.cover_image:
            return request.build_absolute_uri(obj.cover_image.url)
        return None


class NoteLikeSerializer(serializers.ModelSerializer):
    author_username = serializers.ReadOnlyField(source='author.username')
    avatar = serializers.SerializerMethodField()
    cover_image = serializers.SerializerMethodField()
    liked_time = serializers.SerializerMethodField()

    class Meta:
        model = Note
        fields = [
            'id', 'author_username', 'avatar', 'cover_image', 'likes_count',
            'views_count', 'popularity', 'title', 'content', 'liked_time'
        ]

    def get_avatar(self, obj):
        request = self.context.get('request')
        if obj.author.avatar:
            return request.build_absolute_uri(obj.author.avatar.url)
        return None

    def get_cover_image(self, obj):
        request = self.context.get('request')
        if obj.cover_image:
            return request.build_absolute_uri(obj.cover_image.url)
        return None

    def get_liked_time(self, obj):
        # 获取当前用户对该笔记的点赞时间
        user = self.context['request'].user
        like = Like.objects.filter(user=user, note=obj).first()
        if like:
            # 将 UTC 时间转换为北京时间
            beijing_tz = pytz.timezone('Asia/Shanghai')
            local_time = like.created_at.astimezone(beijing_tz)
            return local_time.isoformat()
        else:
            return None

# class NotificationSerializer(serializers.ModelSerializer):
#     sender = CommentUserSerializer()
#     comment = CommentSerializer()
#
#     class Meta:
#         model = Notification
#         fields = [
#             'id',
#             'notification_type',
#             'content',
#             'is_read',
#             'created_at',
#             'sender',
#             'comment'
#         ]