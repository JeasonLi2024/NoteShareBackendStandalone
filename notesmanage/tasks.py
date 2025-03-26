#使用 Celery 等异步任务队列定期计算热门笔记，并将结果存储在数据库中
from celery import shared_task
from notesmanage.models import Note, TopNote
import heapq

@shared_task
def update_top_notes():
    queryset = Note.objects.filter(is_private=False)

    # 定义一个最小堆，用于存储 Top 10 笔记
    top_10_notes = []

    # 分批加载数据
    batch_size = 1000
    for i in range(0, queryset.count(), batch_size):
        batch = queryset[i:i + batch_size]
        for note in batch:
            # 计算热度
            popularity = 0.6 * note.views_count + 0.3 * note.likes_count + 0.1 * note.comments_count

            # 如果堆未满或当前笔记的热度大于堆中的最小值
            if len(top_10_notes) < 10 or popularity > top_10_notes[0][0]:
                if len(top_10_notes) == 10:
                    # 如果堆已满，移除堆顶元素（最小值）
                    heapq.heappop(top_10_notes)
                # 将当前笔记加入堆中
                heapq.heappush(top_10_notes, (popularity, note))

    # 从堆中提取 Top 10 笔记
    top_10_notes = [note for _, note in heapq.nlargest(10, top_10_notes)]

    # 清空旧的TopNote记录
    TopNote.objects.all().delete()

    # 创建新的TopNote记录
    for note in top_10_notes:
        TopNote.objects.create(note=note, popularity=note.popularity)