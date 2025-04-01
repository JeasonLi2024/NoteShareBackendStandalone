from django.db.models import F
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from .models import Note, Like, Comment

@receiver(post_save, sender=Note)
def update_popularity(sender, instance, **kwargs):
    Note.objects.filter(id=instance.id).update(
        popularity=0.6 * F('views_count') + 0.3 * F('likes_count') + 0.1 * F('comments_count')
    )

@receiver(post_save, sender=Like)
@receiver(post_delete, sender=Like)
def update_note_popularity_on_like_change(sender, instance, **kwargs):
    note = instance.note
    Note.objects.filter(id=note.id).update(
        likes_count=note.likes.count(),
        popularity=0.6 * F('views_count') + 0.3 * F('likes_count') + 0.1 * F('comments_count')
    )

@receiver(post_save, sender=Comment)
@receiver(post_delete, sender=Comment)
def update_note_popularity_on_comment_change(sender, instance, **kwargs):
    note = instance.note
    Note.objects.filter(id=note.id).update(
        comments_count=note.comments.count(),
        popularity=0.6 * F('views_count') + 0.3 * F('likes_count') + 0.1 * F('comments_count')
    )