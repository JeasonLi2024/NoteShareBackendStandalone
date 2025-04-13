from django.db.models import Func, IntegerField
from django.urls import reverse


class UnixTimestamp(Func):
    function = 'UNIX_TIMESTAMP'
    template = '%(function)s(%(expressions)s)'
    output_field = IntegerField()  # 强制指定为整数类型

def get_share_link(request, note_id):
    relative_url = reverse('note-retrieve-update-destroy', args=[note_id])
    return request.build_absolute_uri(relative_url)
