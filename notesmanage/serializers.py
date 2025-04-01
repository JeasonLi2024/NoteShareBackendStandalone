# serializers.py
from rest_framework import serializers
from .models import Note, Comment, Like, Notification
from django.contrib.auth import get_user_model
import pytz

User = get_user_model()


class UserBriefSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'avatar']

    def get_avatar(self, obj):
        request = self.context.get('request')
        if obj.avatar:
            return request.build_absolute_uri(obj.avatar.url) if request else obj.avatar.url
        return None


class CommentSerializer(serializers.ModelSerializer):
    user = UserBriefSerializer(read_only=True)
    reply_to_user = serializers.SerializerMethodField()  # 新增回复目标用户字段
    is_liked = serializers.SerializerMethodField()
    likes_count = serializers.IntegerField(read_only=True)
    replies = serializers.SerializerMethodField()

    class Meta:
        model = Comment
        fields = [
            'id', 'user', 'content', 'likes_count', 'is_liked',
            'created_at', 'parent_comment', 'reply_to_user', 'replies'
        ]
        extra_kwargs = {
            'parent_comment': {'write_only': True}
        }

    def get_replies(self, obj):
        """获取扁平化的子评论列表"""
        request = self.context.get('request')

        # 获取所有直接子评论（不限制层级）
        child_comments = obj.replies.all().select_related('user', 'parent_comment__user')

        return CommentSerializer(
            child_comments,
            many=True,
            context={'request': request}
        ).data

    def get_reply_to_user(self, obj):
        """获取被回复用户信息"""
        if obj.parent_comment:
            return UserBriefSerializer(
                obj.parent_comment.user,
                context={'request': self.context.get('request')}
            ).data
        return None

    def get_is_liked(self, obj):
        # 原有逻辑保持不变
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return obj.commentlike_set.filter(user=request.user).exists()
        return False

    def to_representation(self, instance):
        """重写展示逻辑，处理内容格式化"""
        data = super().to_representation(instance)

        # 如果是子评论且需要显示回复关系
        if instance.parent_comment and instance.parent_comment.parent_comment:
            parent_user = instance.parent_comment.user
            data['content'] = f"回复@{parent_user.username}：{data['content']}"

        # 移除嵌套层级结构
        if instance.parent_comment and instance.parent_comment.parent_comment:
            data['parent_comment'] = instance.parent_comment.parent_comment.id

        return data


class CreateCommentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Comment
        fields = ['content', 'parent_comment']

    def validate_parent_comment(self, value):
        """验证评论层级不超过两级"""
        if value and value.parent_comment:
            raise serializers.ValidationError("评论层级不能超过两级")
        return value

    def create(self, validated_data):
        """创建评论时自动处理内容格式"""
        parent_comment = validated_data.get('parent_comment')

        if parent_comment:
            # 自动添加回复前缀
            prefix = f"回复@{parent_comment.user.username}："
            if not validated_data['content'].startswith(prefix):
                validated_data['content'] = prefix + validated_data['content']

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


class NoteSimpleSerializer(serializers.ModelSerializer):
    author_username = serializers.ReadOnlyField(source='author.username')
    avatar = serializers.SerializerMethodField()
    cover_image = serializers.SerializerMethodField()

    class Meta:
        model = Note
        fields = [
            'id', 'author_username', 'avatar', 'cover_image', 'likes_count',
            'views_count', 'popularity', 'title', 'content'
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

class NotificationSerializer(serializers.ModelSerializer):
    sender = UserBriefSerializer()
    comment = CommentSerializer()

    class Meta:
        model = Notification
        fields = [
            'id',
            'notification_type',
            'content',
            'is_read',
            'created_at',
            'sender',
            'comment'
        ]