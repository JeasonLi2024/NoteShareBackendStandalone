from celery import shared_task
from .models import Note, TopNote, Comment
from datetime import timedelta
from django.utils import timezone


@shared_task
def periodic_update_top_notes():
    """
    定时任务：批量更新所有笔记的热度值，并排序
    """
    # 获取所有公开笔记并按热度排序
    all_public_notes = Note.objects.filter(is_private=False).order_by('-popularity')

    # 清空旧的TopNote记录
    TopNote.objects.all().delete()

    # 创建新的TopNote记录
    for index, note in enumerate(all_public_notes):
        TopNote.objects.create(note=note, popularity=note.popularity, rank=index + 1)

    print("All public notes updated and saved in TopNote.")

@shared_task
def refresh_comments_order():
    """
    每 20 分钟执行一次任务，将创建时间超过 20 分钟且未刷新过的评论
    标记为已刷新，此时这些评论将在排序时采用点赞数排序。
    """
    threshold = timezone.now() - timedelta(minutes=20)
    updated = Comment.objects.filter(is_refreshed=False, created_at__lte=threshold).update(is_refreshed=True)
    return updated



