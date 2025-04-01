
from django.db import models
from django.contrib.auth import get_user_model
from django_ckeditor_5.fields import CKEditor5Field#富文本编辑器

User = get_user_model()


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
    # 新增物化热度字段
    popularity = models.FloatField(default=0.0, verbose_name='热度')

    # def save(self, *args, **kwargs):
    #     # 每次保存时更新热度（公式：0.6*v + 0.3*l + 0.1*c）
    #     self.popularity = 0.6 * self.views_count + 0.3 * self.likes_count + 0.1 * self.comments_count
    #     super().save(*args, **kwargs)

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


class Like(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    note = models.ForeignKey(Note, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'note')


class Comment(models.Model):
    note = models.ForeignKey(Note, on_delete=models.CASCADE, related_name='comments', verbose_name='笔记')
    author = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name='作者')
    content = models.TextField(verbose_name='内容')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')

    def __str__(self):
        return f'Comment by {self.author.username} on {self.note.title}'

class TopNote(models.Model):
    note = models.OneToOneField(Note, on_delete=models.CASCADE, related_name='top_note')
    popularity = models.FloatField(verbose_name='热度')
    rank = models.IntegerField(verbose_name='排名')  # 添加 rank 字段

    def __str__(self):
        return f"Top Note: {self.note.title} - Popularity: {self.popularity}"


