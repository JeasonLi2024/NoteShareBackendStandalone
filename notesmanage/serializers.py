# serializers.py
from rest_framework import serializers
from .models import Note, Comment


class NoteSerializer(serializers.ModelSerializer):
    author_info = serializers.SerializerMethodField()
    like_count = serializers.SerializerMethodField()
    comment_count = serializers.SerializerMethodField()
    is_liked = serializers.SerializerMethodField()

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

    def get_like_count(self, obj):
        return obj.likes.count()

    def get_comment_count(self, obj):
        return obj.comments.count()

    def create(self, validated_data):
        validated_data['author'] = self.context['request'].user
        return super().create(validated_data)

    def get_is_liked(self, obj):
        # 判断当前用户是否已点赞该笔记
        user = self.context['request'].user
        if user.is_authenticated:
            return obj.likes.filter(id=user.id).exists()
        return False


class CommentSerializer(serializers.ModelSerializer):
    author = serializers.StringRelatedField(read_only=True)

    class Meta:
        model = Comment
        fields = '__all__'
        read_only_fields = ['author', 'note']

    def create(self, validated_data):
        validated_data['author'] = self.context['request'].user
        validated_data['note'] = self.context['view'].get_object()
        return super().create(validated_data)

class NoteSimpleSerializer(serializers.ModelSerializer):
    author_username = serializers.ReadOnlyField(source='author.username')
    avatar = serializers.SerializerMethodField()
    cover_image = serializers.SerializerMethodField()
    rank = serializers.SerializerMethodField()

    class Meta:
        model = Note
        fields = [
            'id', 'author_username', 'avatar', 'cover_image', 'likes_count',
            'views_count', 'popularity', 'title', 'content', 'rank'
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

    def get_rank(self, obj):
        top_note = getattr(obj, 'top_note', None)
        return top_note.rank if top_note else None
