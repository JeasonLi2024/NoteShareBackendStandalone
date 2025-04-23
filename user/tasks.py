from celery import shared_task
from celery.schedules import crontab
from django.utils import timezone
from NoteShareBackend.celery import app
from user.models import User, PointHistory


@shared_task
def reset_daily_counters():
    User.objects.update(
        points_note_publish=0,
        points_like=0,
        points_comment=0,
    )