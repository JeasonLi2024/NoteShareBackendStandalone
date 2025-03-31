from django.apps import AppConfig


class NotesmanageConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "notesmanage"
    verbose_name = '笔记管理'

    def ready(self):
        import notesmanage.signals  # 导入信号处理器
