# #使用 Celery 等异步任务队列定期计算热门笔记，并将结果存储在数据库中
# from celery import shared_task
# from .models import Note, TopNote
# from django.core.paginator import Paginator
# from .serializers import NoteSerializer
#
#
#
# # 定时任务：批量更新所有笔记的热度值，并计算Top 10笔记
# @shared_task
# def periodic_update_top_notes():
#
#     # 获取Top 10笔记
#     top_10_notes = Note.objects.filter(is_private=False).order_by('-popularity')[:10]
#
#     # 清空旧的TopNote记录
#     TopNote.objects.all().delete()
#
#     # 创建新的TopNote记录
#     for note in top_10_notes:
#         TopNote.objects.create(note=note, popularity=note.popularity)
#
#     print("Top 10 notes updated and saved.")
#
# # 按类别获取笔记并进行分页处理
# @shared_task
# def get_notes_by_category_with_pagination(category, page_number, page_size):
#     """
#     :param category: 笔记类别
#     :param page_number: 当前页码
#     :param page_size: 每页显示的笔记数量
#     """
#     # 获取所有笔记并按热度排序
#     all_notes = Note.objects.filter(is_private=False).order_by('-popularity')
#
#     # 过滤出指定类别的笔记
#     category_notes = all_notes.filter(category=category)
#
#     # 使用 Paginator 进行分页
#     paginator = Paginator(category_notes, page_size)
#     page = paginator.get_page(page_number)
#
#     # 序列化当前页的数据
#     serializer = NoteSerializer(page.object_list, many=True)
#
#     return {
#         'notes': serializer.data,
#         'total_pages': paginator.num_pages,
#         'current_page': page_number,
#     }

from celery import shared_task
from .models import Note, TopNote
from datetime import timedelta
from django.utils import timezone
from .models import Comment


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



