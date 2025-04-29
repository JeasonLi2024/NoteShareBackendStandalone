from celery import shared_task
from .models import Note, TopNote, Comment
from datetime import timedelta
from django.utils import timezone
from django.core.cache import cache
from django.db import transaction
from django_redis import get_redis_connection  # 新增导入

# @shared_task
# def periodic_update_top_notes():
#     """
#     定时任务：批量更新所有笔记的热度值，并排序
#     """
#     # 获取所有公开笔记并按热度排序
#     all_public_notes = Note.objects.filter(is_private=False).order_by('-popularity')
#
#     # 清空旧的TopNote记录
#     TopNote.objects.all().delete()
#
#     # 创建新的TopNote记录
#     bulk_data = [
#         TopNote(note=note, popularity=note.popularity, rank=index + 1)
#         for index, note in enumerate(all_public_notes)
#     ]
#     TopNote.objects.bulk_create(bulk_data)
#
#     print("All public notes updated and saved in TopNote.")


@shared_task
def periodic_update_top_notes():
    """
    全量更新全局和分类缓存
    """
    conn = get_redis_connection("default")  # 使用django_redis的专用方法
    pipe = conn.pipeline()

    # 1. 更新全局缓存
    global_key = "top_notes:all"
    all_notes = Note.objects.filter(is_private=False).order_by('-popularity')
    pipe.delete(global_key)
    for note in all_notes:
        pipe.zadd(global_key, {note.id: note.popularity})
    pipe.expire(global_key, 3600 * 24)  # 24小时过期

    # 2. 更新分类缓存
    categories = Note.objects.values_list('category', flat=True).distinct()
    for category in categories:
        category_key = f"top_notes:category:{category}"
        category_notes = all_notes.filter(category=category)
        pipe.delete(category_key)
        for note in category_notes:
            pipe.zadd(category_key, {note.id: note.popularity})
        pipe.expire(category_key, 3600 * 24)

    # 3. 更新数据库的TopNote表（原逻辑）
    with transaction.atomic():
        TopNote.objects.all().delete()
        bulk_data = [
            TopNote(note=note, popularity=note.popularity, rank=index + 1)
            for index, note in enumerate(all_notes)
        ]
        TopNote.objects.bulk_create(bulk_data)

    pipe.execute()
    print("Global and category caches updated with database.")


@shared_task
def refresh_comments_order():
    """
    每 5 分钟执行一次任务，将创建时间超过 20 分钟且未刷新过的评论
    标记为已刷新，此时这些评论将在排序时采用点赞数排序。
    """
    threshold = timezone.now() - timedelta(minutes=20)
    updated = Comment.objects.filter(is_refreshed=False, created_at__lte=threshold).update(is_refreshed=True)
    return updated



