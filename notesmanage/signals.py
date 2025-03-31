from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from .models import Note, Like, Comment


@receiver(post_save, sender=Note)
def update_popularity(sender, instance, **kwargs):
    instance.popularity = 0.6 * instance.views_count + 0.3 * instance.likes_count + 0.1 * instance.comments_count
    instance.save()


@receiver(post_save, sender=Like)
@receiver(post_delete, sender=Like)
def update_note_popularity_on_like_change(sender, instance, **kwargs):
    note = instance.note
    note.likes_count = note.likes.count()
    note.save()  # 触发save方法，自动更新热度


@receiver(post_save, sender=Comment)
@receiver(post_delete, sender=Comment)
def update_note_popularity_on_comment_change(sender, instance, **kwargs):
    note = instance.note
    note.comments_count = note.comments.count()
    note.save()  # 触发save方法，自动更新热度