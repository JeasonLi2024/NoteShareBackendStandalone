from django.db.models import Func, IntegerField

class UnixTimestamp(Func):
    function = 'UNIX_TIMESTAMP'
    template = '%(function)s(%(expressions)s)'
    output_field = IntegerField()  # 强制指定为整数类型