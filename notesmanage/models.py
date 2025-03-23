# models.py
from django.db import models
from django.contrib.auth import get_user_model
from ckeditor.fields import RichTextField   #富文本编辑器

User = get_user_model()


class Note(models.Model):
    title = models.CharField(max_length=255, verbose_name='标题')
    content = models.TextField(blank=True, null=True, verbose_name='内容')
    file = models.FileField(upload_to='notes/', blank=True, null=True, verbose_name='附件')
    category = models.CharField(max_length=255, blank=True, null=True, verbose_name='类别')
    is_private = models.BooleanField(default=False, verbose_name='是否私有')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notes', verbose_name='作者')
    likes = models.ManyToManyField(User, through='Like', related_name='liked_notes', verbose_name='点赞')
    views_count = models.PositiveIntegerField(default=0, verbose_name='浏览次数')
    likes_count = models.PositiveIntegerField(default=0, verbose_name='点赞数')
    comments_count = models.PositiveIntegerField(default=0, verbose_name='评论数')
    is_pinned = models.BooleanField(default=False, verbose_name='是否置顶')
    cover_image = models.ImageField(upload_to='covers/', null=True, blank=True)
    note_image = models.ImageField(upload_to='note_images/', blank=True, null=True, verbose_name='图片')
    note_video = models.FileField(upload_to='note_videos/', blank=True, null=True, verbose_name='视频')
    body = RichTextField(blank=True, null=True, verbose_name='正文内容')

    def __str__(self):
        return self.title


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