from django.db import models
from django.contrib.auth import get_user_model
from django_ckeditor_5.fields import CKEditor5Field#富文本编辑器
from django.db.models import OuterRef, Subquery
from django.core.cache import cache
from django.db.models import Count, Q
from django.utils import timezone

from model_utils import FieldTracker

User = get_user_model()


# 自定义获取笔记liked_time方式
class NoteQuerySet(models.QuerySet):
    def annotate_liked_time(self, user):
        # 子查询获取点赞时间
        subquery = (
            Like.objects
            .filter(note=OuterRef('pk'), user=user)
            .values('created_at')[:1]
        )
        return self.annotate(liked_time=Subquery(subquery))


# 笔记模型
class Note(models.Model):
    title = models.CharField(max_length=20, verbose_name='标题')
    content = models.CharField(max_length=200, verbose_name='内容概括')
    file = models.FileField(upload_to='notes/', blank=True, null=True, verbose_name='笔记文件')
    category = models.CharField(max_length=10, verbose_name='类别')
    is_private = models.BooleanField(default=False, verbose_name='是否私有')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notes', verbose_name='作者')
    likes = models.ManyToManyField(User, through='Like', related_name='liked_notes', verbose_name='点赞')
    views_count = models.PositiveIntegerField(default=0, verbose_name='浏览次数')
    likes_count = models.PositiveIntegerField(default=0, verbose_name='点赞数')
    comments_count = models.PositiveIntegerField(default=0, verbose_name='评论数')
    favorites_count = models.PositiveIntegerField(default=0, verbose_name='收藏数')
    is_pinned = models.BooleanField(default=False, verbose_name='是否置顶')
    cover_image = models.ImageField(upload_to='covers/', verbose_name='封面图片')
    note_video = models.FileField(upload_to='note_videos/', blank=True, null=True, verbose_name='视频')
    body = CKEditor5Field('正文内容',config_name='extends')
    popularity = models.FloatField(default=0.0, verbose_name='热度')

    objects = NoteQuerySet.as_manager()  # 替换默认管理器
    tracker = FieldTracker(fields=['views_count', 'likes_count', 'comments_count'])

    def calculate_popularity(self):
        return 0.6 * self.views_count + 0.3 * self.likes_count + 0.1 * self.comments_count

    class Meta:
        db_table = 'note'
        verbose_name = '笔记'
        verbose_name_plural = '笔记'
        indexes = [
            models.Index(
                fields=['is_private', '-popularity'],
                name='idx_note_private_popularity'
            )
        ]

    def __str__(self):
        return self.title

    @property
    def author_info(self):
        """返回作者的信息"""
        return {
            'id': self.author.id,
            'username': self.author.username,
            'avatar': self.author.avatar.url if self.author.avatar else None
        }


# 笔记Like模型
class Like(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    note = models.ForeignKey(Note, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='点赞时间')

    class Meta:
        unique_together = ('user', 'note')
        ordering = ['-created_at']



# 笔记收藏
class Favorite(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='favorites')
    note = models.ForeignKey(Note, on_delete=models.CASCADE, related_name='favorited_by')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='收藏时间')

    class Meta:
        unique_together = ('user', 'note')
        ordering = ['-created_at']



# 笔记热度排序模型
class TopNote(models.Model):
    note = models.OneToOneField(Note, on_delete=models.CASCADE, related_name='top_note')
    popularity = models.FloatField(verbose_name='热度')
    rank = models.IntegerField(verbose_name='排名')  # 添加 rank 字段

    class Meta:
        verbose_name_plural = '热度排行'

    def __str__(self):
        return f"Top Note: {self.note.title} - Popularity: {self.popularity}"


# class Comment(models.Model):
#     note = models.ForeignKey(Note, on_delete=models.CASCADE, related_name='comments', verbose_name='笔记')
#     user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name='用户')
#     parent = models.ForeignKey(
#         'self', null=True, blank=True, on_delete=models.CASCADE,  # 保持级联删除
#         related_name='replies'
#     )
#     content = models.TextField(verbose_name='评论内容')
#     created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
#     updated_at = models.DateTimeField(auto_now=True)
#     likes = models.ManyToManyField(User, related_name='liked_comments', blank=True)
#     dislikes = models.ManyToManyField(User, related_name='disliked_comments', blank=True)
#
#     def __str__(self):
#         return f"Comment({self.user}, {self.content[:20]})"
#     # 缓存查询结果
#     def get_all_descendants(self):
#         """递归获取所有后代评论（平铺列表）"""
#         cache_key = f'comment_{self.id}_descendants'
#         cached = cache.get(cache_key)
#         if cached:
#             return cached
#         descendants = []
#         current_level = self.replies.all()
#         while current_level.exists():
#             descendants.extend(current_level)
#             current_level = Comment.objects.filter(parent__in=current_level)
#         cache.set(cache_key, descendants, 60 * 15)  # 缓存15分钟
#         return descendants
#
#     def get_all_replies(self):
#         """递归获取所有回复（现在直接通过级联删除自动处理）"""
#         all_replies = []
#         for reply in self.replies.all().order_by('created_at'):
#             all_replies.append(reply)
#             all_replies.extend(reply.get_all_replies())
#         return all_replies
#
#     def get_display_content(self):
#         """决定评论显示内容的逻辑"""
#         if not self.parent:
#             return self.content
#         elif self.parent and not self.parent.parent:
#             return self.content
#         else:
#             return f"{self.user.username} 回复 {self.parent.user.username}：{self.content}"
#
#     @property
#     def like_count(self):
#         return self.likes.count()
#
#     @property
#     def dislike_count(self):
#         return self.dislikes.count()
#
#     class Meta:
#         verbose_name_plural = '笔记评论管理'
#         ordering = ['created_at']
#         indexes = [
#             models.Index(fields=['parent']),  # 加速层级查询
#             models.Index(fields=['-created_at']),
#         ]


class Comment(models.Model):
    note = models.ForeignKey(Note, on_delete=models.CASCADE, related_name='comments', verbose_name='笔记')
    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name='用户')
    parent = models.ForeignKey(
        'self', null=True, blank=True, on_delete=models.CASCADE,  # 保持级联删除
        related_name='replies'
    )
    content = models.TextField(verbose_name='评论内容')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True)
    likes = models.ManyToManyField(User, related_name='liked_comments', blank=True)
    dislikes = models.ManyToManyField(User, related_name='disliked_comments', blank=True)
    is_refreshed = models.BooleanField(default=False, verbose_name="已参与点赞排序")

    def __str__(self):
        return f"Comment({self.user}, {self.content[:20]})"

    def get_all_descendants(self):
        """递归获取所有后代评论（平铺列表），不使用缓存保证新数据能立刻显示"""
        descendants = []
        current_level = self.replies.all()
        while current_level.exists():
            descendants.extend(current_level)
            current_level = Comment.objects.filter(parent__in=current_level)
        return descendants

    def get_all_replies(self):
        """递归获取所有回复（现在直接通过级联删除自动处理）"""
        all_replies = []
        for reply in self.replies.all().order_by('created_at'):
            all_replies.append(reply)
            all_replies.extend(reply.get_all_replies())
        return all_replies

    def get_display_content(self):
        """决定评论显示内容的逻辑"""
        if not self.parent:
            return self.content
        elif self.parent and not self.parent.parent:
            return self.content
        else:
            return f"{self.user.username} 回复 {self.parent.user.username}：{self.content}"

    @property
    def like_count(self):
        return self.likes.count()

    @property
    def dislike_count(self):
        return self.dislikes.count()

    class Meta:
        verbose_name_plural = '笔记评论管理'
        # 注意：为了视图中实现动态排序，这里可不设置默认 ordering
        indexes = [
            models.Index(fields=['parent']),  # 加速层级查询
            models.Index(fields=['-created_at']),
        ]