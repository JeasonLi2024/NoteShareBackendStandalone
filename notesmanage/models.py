from django.db import models
from django.contrib.auth import get_user_model
from django_ckeditor_5.fields import CKEditor5Field#富文本编辑器
from django.db.models import OuterRef, Subquery
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver
import os
import uuid
import shutil
from model_utils import FieldTracker
from NoteShareBackend import settings

User = get_user_model()

def note_image_upload_path(instance, filename):
    return f'note_images/{instance.published_note.id}/{filename}'

def draft_image_upload_path(instance, filename):
    return f'draft_images/{instance.draft_note.id}/{filename}'

def note_video_upload_path(instance, filename):
    return f'note_videos/{instance.id}/{filename}'

def draft_video_upload_path(instance, filename):
    return f'draft_videos/{instance.id}/{filename}'

def note_cover_upload_path(instance, filename):
    return f'note_covers/{instance.id}/{filename}'

def draft_cover_upload_path(instance, filename):
    return f'draft_covers/{instance.id}/{filename}'

def note_file_upload_path(instance, filename):
    return f'note_files/{instance.id}/{filename}'

def draft_file_upload_path(instance, filename):
    return f'draft_files/{instance.id}/{filename}'



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

def get_note_image_path(instance, filename):
    """
    根据实例是草稿或已发布笔记，动态生成图片存储路径。
    """
    ext = os.path.splitext(filename)[1]
    if getattr(instance, 'draft_note', None):
        return f'draft_images/{instance.draft_note.id}/{uuid.uuid4().hex}{ext}'
    return f'published_images/{instance.published_note.id}/{uuid.uuid4().hex}{ext}'

def get_note_file_path(instance, filename):
    ext = os.path.splitext(filename)[1]
    if getattr(instance, 'draft_note', None):
        return f'draft_files/{instance.draft_note.id}/{uuid.uuid4().hex}{ext}'
    return f'published_files/{instance.published_note.id}/{uuid.uuid4().hex}{ext}'

class DraftNote(models.Model):
    title = models.CharField(max_length=20, verbose_name='标题')
    content = models.CharField(max_length=200, verbose_name='内容概括')
    category = models.CharField(max_length=10, verbose_name='类别')
    is_private = models.BooleanField(default=False, verbose_name='是否私有')
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name='draft_notes', verbose_name='作者')
    note_video = models.FileField(upload_to=draft_video_upload_path, blank=True, null=True, verbose_name='视频')
    body = CKEditor5Field(verbose_name='正文内容', config_name='extends')
    cover_image = models.ImageField(upload_to=draft_cover_upload_path, blank=True, null=True, verbose_name='封面图片')
    generated_covers = models.JSONField(default=list, verbose_name='生成封面选项')
    uploaded_cover_type = models.CharField(
        max_length=10,
        choices=[('image', '图片'), ('video', '视频')],
        blank=True, null=True,
        verbose_name='上传封面类型'
    )
    is_pinned = models.BooleanField(default=False, verbose_name='是否置顶')
    uploaded_cover_path = models.CharField(max_length=255, blank=True, null=True, verbose_name='上传封面路径')
    last_modified = models.DateTimeField(auto_now=True, verbose_name='最后修改时间')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')
    change_history = models.JSONField(default=list, verbose_name='修改历史')


    class Meta:
        db_table = 'draft_note'
        verbose_name = '草稿笔记'
        verbose_name_plural = '草稿笔记'
        indexes = [models.Index(fields=['author', 'created_at'])]

    def __str__(self):
        return f"{self.title} (草稿)"


# 笔记模型
class Note(models.Model):
    """正式笔记模型"""
    title = models.CharField(max_length=20, verbose_name='标题')
    content = models.CharField(max_length=200, verbose_name='内容概括')
    category = models.CharField(max_length=10, verbose_name='类别')
    is_private = models.BooleanField(default=False, verbose_name='是否私有')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name='published_notes', verbose_name='作者')
    likes = models.ManyToManyField(User, through='Like', related_name='liked_published_notes', verbose_name='点赞')
    views_count = models.PositiveIntegerField(default=0, verbose_name='浏览次数')
    likes_count = models.PositiveIntegerField(default=0, verbose_name='点赞数')
    comments_count = models.PositiveIntegerField(default=0, verbose_name='评论数')
    favorites_count = models.PositiveIntegerField(default=0, verbose_name='收藏数')
    is_pinned = models.BooleanField(default=False, verbose_name='是否置顶')
    cover_image = models.ImageField(upload_to=note_cover_upload_path, verbose_name='封面图片')
    note_video = models.FileField(upload_to=note_video_upload_path, blank=True, null=True, verbose_name='视频')
    body = CKEditor5Field('正文内容', config_name='extends')
    popularity = models.FloatField(default=0.0, verbose_name='热度')

    objects = NoteQuerySet.as_manager()  # 复用原有管理器
    tracker = FieldTracker(fields=['views_count', 'likes_count', 'comments_count'])

    class Meta:
        db_table = 'published_note'
        verbose_name = '正式笔记'
        verbose_name_plural = '正式笔记'
        indexes = [
            models.Index(
                fields=['is_private', '-popularity'],
                name='idx_published_note_pri_pop'
            )
        ]

    def calculate_popularity(self):
        return 0.6 * self.views_count + 0.3 * self.likes_count + 0.1 * self.comments_count

    @property
    def author_info(self):
        return {
            'id': self.author.id,
            'username': self.author.username,
            'avatar': self.author.avatar.url if self.author.avatar else None
        }

    def __str__(self):
        return self.title


class NoteImage(models.Model):
    image = models.ImageField(upload_to=draft_image_upload_path)

    draft_note = models.ForeignKey(
        DraftNote,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='draft_images'       # ← 从 'images' 改成 'draft_images'
    )
    published_note = models.ForeignKey(
        Note,
        null=True, blank=True,
        on_delete=models.CASCADE,
        related_name='published_images'   # ← 从 'images' 改成 'published_images'
    )

    def __str__(self):
        return f"Image for draft={self.draft_note_id} pub={self.published_note_id}"

class NoteFile(models.Model):
    file = models.FileField(upload_to=draft_file_upload_path)

    draft_note = models.ForeignKey(
        DraftNote,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='draft_files'        # ← 确保与 NoteImage 的 related_name 不同
    )
    published_note = models.ForeignKey(
        Note,
        null=True, blank=True,
        on_delete=models.CASCADE,
        related_name='published_files'    # ← 确保与 NoteImage 的 related_name 不同
    )

    def __str__(self):
        return f"File for draft={self.draft_note_id} pub={self.published_note_id}"


# 信号处理
@receiver(post_delete, sender=DraftNote)
def delete_draft_note_files(sender, instance, **kwargs):
    """
    删除 DraftNote 及其所有关联文件和目录：
    - draft_covers/<id>/
    - draft_videos/<id>/
    - draft_images/<id>/
    - draft_files/<id>/
    - generated_covers/<id>/
    """
    media_root = settings.MEDIA_ROOT
    # 列举需要删除的子目录
    subdirs = [
        os.path.join(media_root, 'draft_covers', str(instance.id)),
        os.path.join(media_root, 'draft_videos', str(instance.id)),
        os.path.join(media_root, 'draft_images', str(instance.id)),
        os.path.join(media_root, 'draft_files', str(instance.id)),
        os.path.join(media_root, 'generated_covers', str(instance.id)),
    ]
    # 删除目录及其内部所有文件
    for d in subdirs:
        if os.path.isdir(d):
            shutil.rmtree(d, ignore_errors=True)

@receiver(post_delete, sender=Note)
def delete_note_files(sender, instance, **kwargs):
    """
    删除正式 Note 及其所有关联文件和目录：
    - covers/<id>/
    - note_videos/<id>/
    - note_images/<id>/
    - note_files/<id>/
    """
    media_root = settings.MEDIA_ROOT
    subdirs = [
        os.path.join(media_root, 'covers', str(instance.id)),
        os.path.join(media_root, 'note_videos', str(instance.id)),
        os.path.join(media_root, 'note_images', str(instance.id)),
        os.path.join(media_root, 'note_files', str(instance.id)),
    ]
    for d in subdirs:
        if os.path.isdir(d):
            shutil.rmtree(d, ignore_errors=True)

# 可保留个别文件级删除（可选）
@receiver(post_delete, sender=NoteImage)
def delete_note_image_file(sender, instance, **kwargs):
    # 删除单个 NoteImage 迁移到对应子目录时已通过 rmtree 处理，可根据需求保留
    if instance.image:
        try:
            instance.image.delete(save=False)
        except Exception:
            pass

@receiver(post_delete, sender=NoteFile)
def delete_note_file_file(sender, instance, **kwargs):
    # 删除单个 NoteFile 同上
    if instance.file:
        try:
            instance.file.delete(save=False)
        except Exception:
            pass

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