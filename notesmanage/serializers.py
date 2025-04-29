# serializers.py
import os
from rest_framework import serializers
from NoteShareBackend import settings
from .models import Note, Comment, Like, Favorite, NoteImage, DraftNote, NoteFile
from django.contrib.auth import get_user_model
import pytz

from .utils import get_share_link

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    avatar = serializers.SerializerMethodField()
    is_following = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ['id', 'username', 'avatar', 'total_likes', 'total_views', 'following_count', 'followers_count', 'introduction', 'is_following']
        ref_name = 'NotesManageUserSerializer'

    def get_following_count(self, obj):
        return obj.following.count()

    def get_followers_count(self, obj):
        return obj.followers.count()

    def get_avatar(self, obj):
        request = self.context.get('request')
        # 假设 avatar 是一个 ImageField 或者其他类型的字段
        # 返回头像的 URL 或其他相关信息
        if obj.avatar:
            return request.build_absolute_uri(obj.avatar.url)
        return None

    def get_is_following(self, obj):
        request = self.context.get("request")
        if request and request.user and request.user.is_authenticated:
            # 检查当前请求用户的 following 集合中是否存在该对象
            return request.user.following.filter(id=obj.id).exists()
        return False


class CommentSerializer(serializers.ModelSerializer):
    note = serializers.PrimaryKeyRelatedField(read_only=True)  # 不让前端传递
    user = UserSerializer(read_only=True)
    # like_count = serializers.IntegerField(source='annotated_likes', read_only=True)
    # dislike_count = serializers.IntegerField(read_only=True)
    is_liked = serializers.SerializerMethodField()
    is_disliked = serializers.SerializerMethodField()
    display_content = serializers.SerializerMethodField()
    top_replies = serializers.SerializerMethodField()
    total_replies = serializers.SerializerMethodField()

    class Meta:
        model = Comment
        fields = [
            'id', 'note', 'user', 'parent', 'content', 'likes_count', 'dislikes_count', 'created_at',
            'is_liked', 'is_disliked', 'display_content', 'top_replies', 'total_replies'
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
        # 使用预加载的likes数据避免额外查询
        return self.context['request'].user.id in [
            u.id for u in getattr(obj, 'prefetched_likes', [])
        ]

    def get_is_disliked(self, obj):
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return False
        return obj.dislikes.filter(id=request.user.id).exists()

    def get_display_content(self, obj):
        """根据不喜欢状态返回不同内容"""
        if self.get_is_disliked(obj):
            return "该评论被折叠"
        # 直接使用缓存属性或模型中的逻辑返回显示内容
        return obj.get_display_content()

    def validate(self, data):
        # 不再限制回复层级，允许对任何评论进行回复
        return data

    def create(self, validated_data):
        # 自动设置评论作者
        request = self.context.get('request')
        validated_data['user'] = request.user
        return super().create(validated_data)


class NoteImageSerializer(serializers.ModelSerializer):
    url = serializers.SerializerMethodField()

    class Meta:
        model = NoteImage
        fields = ['id', 'url']

    def get_url(self, obj):
        return self.context['request'].build_absolute_uri(obj.image.url)

class NoteFileSerializer(serializers.ModelSerializer):
    class Meta:
        model = NoteFile
        fields = ['file']

class DraftNoteSerializer(serializers.ModelSerializer):
    draft_images = NoteImageSerializer(many=True, read_only=True)
    cover_options = serializers.SerializerMethodField()
    author = UserSerializer(read_only=True)
    draft_files = NoteFileSerializer(many=True, read_only=True)

    class Meta:
        model = DraftNote
        fields = ['id', 'title', 'content', 'category', 'body', 'draft_files', 'cover_options', 'author', 'draft_images']
        read_only_fields = ['author', 'created_at', 'updated_at', 'last_modified', 'generated_covers']

    def validate_title(self, value):
        if len(value) < 5:
            raise serializers.ValidationError("标题至少需要5个字符")
        return value

    def validate_content(self, value):
        if len(value) < 10:
            raise serializers.ValidationError("内容概要至少需要10个字符")
        return value

    def get_cover_options(self, obj):
        req = self.context['request']
        opts = []
        if obj.uploaded_cover_path:
            opts.append({
                'type': 'uploaded',
                'source': obj.uploaded_cover_type,
                'url': req.build_absolute_uri(settings.MEDIA_URL + obj.uploaded_cover_path)
            })
        for p in obj.generated_covers:
            opts.append({
                'type': 'generated',
                'url': req.build_absolute_uri(settings.MEDIA_URL + p)
            })
        return opts



class NoteSerializer(serializers.ModelSerializer):
    # author_info = serializers.SerializerMethodField()
    # cover_previews = serializers.SerializerMethodField()
    cover_image = serializers.ImageField(required=False, allow_null=True)
    # generated_covers = serializers.JSONField(read_only=True)
    author = UserSerializer(read_only=True)
    is_liked = serializers.SerializerMethodField()
    is_favorited = serializers.SerializerMethodField()
    # cover_options = serializers.SerializerMethodField()
    # comments = CommentSerializer(many=True, read_only=True)
    note_images = NoteImageSerializer(many=True, read_only=True, source='published_images')
    note_files = NoteFileSerializer(many=True, read_only=True, source='published_files')
    share_link = serializers.SerializerMethodField()

    class Meta:
        model = Note
        fields = '__all__'
        read_only_fields = ['author', 'views_count', 'likes_count', 'comments_count']

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
            raise serializers.ValidationError("内容概要至少需要10个字符")
        return value

    def get_share_link(self, obj):
        request = self.context.get('request')
        return get_share_link(request, obj.id)

    # def get_image_urls(self, obj):
    #     return [img.image.url for img in obj.images.all()]
    # def get_cover_previews(self, obj):
    #     """
    #     返回当前封面图的预览 URL 列表，通常只有一张：
    #     """
    #     request = self.context['request']
    #     if obj.cover_image:
    #         return [request.build_absolute_uri(obj.cover_image.url)]
    #     return []
    #
    # def create(self, validated_data):
    #     # 设置当前用户为作者
    #     validated_data['author'] = self.context['request'].user
    #
    #     # 提取上传的图片
    #     uploaded_images = validated_data.pop('images', [])
    #
    #     # 创建主对象
    #     note = super().create(validated_data)
    #
    #     # 处理并保存图片
    #     for img in uploaded_images:
    #         try:
    #             # 压缩图片
    #             compressed_img = compress_image(img)
    #
    #             # 创建图片记录
    #             NoteImage.objects.create(
    #                 note=note,
    #                 image=compressed_img
    #             )
    #         except Exception as e:
    #             # 可以记录日志或跳过错误
    #             continue
    #
    #     return note
    # def get_cover_options(self, obj):
    #     # 保留草稿时的生成封面记录
    #     return obj.generated_covers

    def get_is_liked(self, obj):
        # 判断当前用户是否已点赞该笔记
        user = self.context['request'].user
        if user.is_authenticated:
            return obj.likes.filter(id=user.id).exists()
        return False

    def get_is_favorited(self, obj):
        request = self.context.get("request")
        if request and request.user and request.user.is_authenticated:
            # 判断当前用户是否收藏了该笔记
            return Favorite.objects.filter(note=obj, user=request.user).exists()
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



class NoteFavoriteSerializer(serializers.ModelSerializer):
    author_username = serializers.ReadOnlyField(source='author.username')
    avatar = serializers.SerializerMethodField()
    cover_image = serializers.SerializerMethodField()
    favorited_time = serializers.SerializerMethodField()

    class Meta:
        model = Note
        fields = [
            'id', 'author_username', 'avatar', 'cover_image', 'favorites_count',
            'views_count', 'popularity', 'title', 'content', 'favorited_time'
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

    def get_favorited_time(self, obj):
        # 获取当前用户对该笔记的收藏时间
        user = self.context['request'].user
        favorite = Favorite.objects.filter(user=user, note=obj).first()
        if favorite:
            # 将 UTC 时间转换为北京时间
            beijing_tz = pytz.timezone('Asia/Shanghai')
            local_time = favorite.created_at.astimezone(beijing_tz)
            return local_time.isoformat()
        return None