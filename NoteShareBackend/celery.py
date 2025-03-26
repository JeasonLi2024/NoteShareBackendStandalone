from __future__ import absolute_import, unicode_literals

import os
from celery import Celery

# 设置默认的 Django 设置模块
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'NoteShareBackend.settings')

app = Celery('NoteShareBackend')

# 使用 Redis 作为消息代理
app.config_from_object('django.conf:settings', namespace='CELERY')

app.autodiscover_tasks()