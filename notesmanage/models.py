
from django.db import models
from django.contrib.auth import get_user_model
from django_ckeditor_5.fields import CKEditor5Field#富文本编辑器
from django.db.models import OuterRef, Subquery

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

# Note模型
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
    is_pinned = models.BooleanField(default=False, verbose_name='是否置顶')
    cover_image = models.ImageField(upload_to='covers/', verbose_name='封面图片')
    note_video = models.FileField(upload_to='note_videos/', blank=True, null=True, verbose_name='视频')
    body = CKEditor5Field('正文内容',config_name='extends')
    popularity = models.FloatField(default=0.0, verbose_name='热度')

    objects = NoteQuerySet.as_manager()  # 替换默认管理器

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

# 笔记评论模型
class Comment(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='comments')
    note = models.ForeignKey('Note', on_delete=models.CASCADE, related_name='comments')
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='评论发布时间')
    # 用于实现评论的嵌套结构，允许回复其他评论
    parent_comment = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='replies')
    likes_count = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name_plural = '评论管理'
        ordering = ['-created_at']

    def __str__(self):
        return f"Comment by {self.user.username} on {self.note.title}"

# 笔记评论点赞模型
class CommentLike(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    comment = models.ForeignKey(Comment, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'comment')

# 笔记热度排序模型
class TopNote(models.Model):
    note = models.OneToOneField(Note, on_delete=models.CASCADE, related_name='top_note')
    popularity = models.FloatField(verbose_name='热度')
    rank = models.IntegerField(verbose_name='排名')  # 添加 rank 字段

    class Meta:
        verbose_name_plural = '热度排行'

    def __str__(self):
        return f"Top Note: {self.note.title} - Popularity: {self.popularity}"

# 通知模型
class Notification(models.Model):
    NOTIFICATION_TYPES = (
        ('reply', '回复通知'),
        ('like', '点赞通知'),
        ('mention', '@提及通知'),
    )

    recipient = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='received_notifications'
    )
    sender = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='sent_notifications',
        null=True
    )
    comment = models.ForeignKey(
        Comment,
        on_delete=models.CASCADE,
        null=True
    )
    notification_type = models.CharField(
        max_length=20,
        choices=NOTIFICATION_TYPES
    )
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    content = models.TextField()  # 冗余字段用于快速展示

    class Meta:
        indexes = [
            models.Index(fields=['recipient', 'is_read']),
            models.Index(fields=['created_at']),
        ]
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.get_notification_type_display()} - {self.recipient}"


