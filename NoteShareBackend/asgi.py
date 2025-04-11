# # 配置 ASGI 路由，同时引入 notifications 的 websocket 路由：
# import os
# from channels.routing import ProtocolTypeRouter, URLRouter
# from django.core.asgi import get_asgi_application
# from NoteShareBackend.middleware import TokenAuthMiddleware # 如果你使用自定义 Token 中间件
# import notifications.routing
#
# os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'myproject.settings')
#
# application = ProtocolTypeRouter({
#     "http": get_asgi_application(),
#     "websocket": TokenAuthMiddleware(
#         URLRouter(
#             notifications.routing.websocket_urlpatterns
#         )
#     ),
# })

import os
import django
from channels.routing import ProtocolTypeRouter, URLRouter
from django.core.asgi import get_asgi_application

# 必须最先设置环境变量
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'NoteShareBackend.settings')

# 初始化Django应用（关键修复步骤）
django.setup()

# 在初始化之后导入中间件和路由
from NoteShareBackend.middleware import JWTAuthMiddleware
import notifications.routing

application = ProtocolTypeRouter({
    "http": get_asgi_application(),
    "websocket": JWTAuthMiddleware(  # 改为 JWT 中间件
        URLRouter(
            notifications.routing.websocket_urlpatterns
        )
    ),
})