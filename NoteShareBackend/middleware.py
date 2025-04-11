# # 自定义 Token 认证中间件，将 query string 中的 token 或 header 中的 token 转换成 user 信息。
#
# from django.contrib.auth.models import AnonymousUser
# from rest_framework.authtoken.models import Token
# from channels.db import database_sync_to_async
#
# class TokenAuthMiddleware:
#     """
#     自定义的 Token 认证中间件，支持从请求 header 中读取 token。
#     header 格式一般为：
#         Authorization: Token <token>
#     """
#     def __init__(self, inner):
#         self.inner = inner
#
#     def __call__(self, scope):
#         return TokenAuthMiddlewareInstance(scope, self)
#
# class TokenAuthMiddlewareInstance:
#     def __init__(self, scope, middleware):
#         # 复制 scope，以免后续修改不影响外部数据
#         self.scope = dict(scope)
#         self.inner = middleware.inner
#
#     async def __call__(self, receive, send):
#         token_key = self.get_token_from_headers()
#         if token_key:
#             self.scope["user"] = await self.get_user(token_key)
#         else:
#             self.scope["user"] = AnonymousUser()
#         inner = self.inner(self.scope)
#         return await inner(receive, send)
#
#     def get_token_from_headers(self):
#         headers = dict(self.scope.get("headers") or [])
#         auth_header = headers.get(b"authorization", None)
#         if auth_header:
#             auth_header = auth_header.decode("utf8")
#             parts = auth_header.split()
#             if len(parts) == 2 and parts[0].lower() in ['token', 'bearer']:
#                 return parts[1]
#         return None
#
#     async def get_user(self, token_key):
#         """
#         使用 token_key 查找对应的用户，需要同步调用 Django ORM，
#         这里使用 database_sync_to_async 包装同步调用
#         """
#         from django.contrib.auth import get_user_model
#         User = get_user_model()
#         try:
#             token = await database_sync_to_async(Token.objects.get)(key=token_key)
#             return token.user
#         except Token.DoesNotExist:
#             return AnonymousUser()
#


# 自定义 Token 认证中间件，将 query string 中的 token 或 header 中的 token 转换成 user 信息。

# from channels.db import database_sync_to_async
#
#
# class TokenAuthMiddleware:
#     """
#     自定义的 Token 认证中间件，支持从请求 header 中读取 token。
#     header 格式一般为：
#         Authorization: Token <token>
#     """
#
#     def __init__(self, inner):
#         self.inner = inner
#
#     def __call__(self, scope):
#         return TokenAuthMiddlewareInstance(scope, self)
#
#
# class TokenAuthMiddlewareInstance:
#     def __init__(self, scope, middleware):
#         # 复制 scope，以免后续修改不影响外部数据
#         self.scope = dict(scope)
#         self.inner = middleware.inner
#
#     async def __call__(self, receive, send):
#         token_key = self.get_token_from_headers()
#         if token_key:
#             self.scope["user"] = await self.get_user(token_key)
#         else:
#             from django.contrib.auth.models import AnonymousUser
#             self.scope["user"] = AnonymousUser()
#         inner = self.inner(self.scope)
#         return await inner(receive, send)
#
#     def get_token_from_headers(self):
#         headers = dict(self.scope.get("headers") or [])
#         auth_header = headers.get(b"authorization", None)
#         if auth_header:
#             auth_header = auth_header.decode("utf8")
#             parts = auth_header.split()
#             if len(parts) == 2 and parts[0].lower() in ['token', 'bearer']:
#                 return parts[1]
#         return None
#
#     async def get_user(self, token_key):
#         """
#         使用 token_key 查找对应的用户，需要同步调用 Django ORM，
#         这里使用 database_sync_to_async 包装同步调用
#         """
#         from rest_framework.authtoken.models import Token
#         from django.contrib.auth import get_user_model
#         User = get_user_model()
#         try:
#             token = await database_sync_to_async(Token.objects.get)(key=token_key)
#             return token.user
#         except Token.DoesNotExist:
#             from django.contrib.auth.models import AnonymousUser
#             return AnonymousUser()


# from django.contrib.auth.models import AnonymousUser
# from rest_framework.authtoken.models import Token
# from channels.db import database_sync_to_async
#
# class TokenAuthMiddleware:
#     """
#     自定义Token认证中间件，从headers中获取Token并验证用户。
#     符合ASGI规范，正确处理三个参数：scope, receive, send。
#     """
#     def __init__(self, inner):
#         self.inner = inner
#
#     async def __call__(self, scope, receive, send):
#         # 从headers中获取token
#         token_key = self.get_token_from_headers(scope)
#         if token_key:
#             user = await self.get_user(token_key)
#         else:
#             user = AnonymousUser()
#         scope['user'] = user
#         # 调用内层应用
#         await self.inner(scope, receive, send)
#
#     def get_token_from_headers(self, scope):
#         headers = dict(scope.get("headers", []))
#         auth_header = headers.get(b"authorization", b"").decode()
#         if auth_header:
#             parts = auth_header.split()
#             if len(parts) == 2 and parts[0].lower() in ['token', 'bearer']:
#                 return parts[1]
#         return None
#
#     async def get_user(self, token_key):
#         from django.contrib.auth import get_user_model
#         User = get_user_model()
#         try:
#             token = await database_sync_to_async(Token.objects.get)(key=token_key)
#             return token.user
#         except Token.DoesNotExist:
#             return AnonymousUser()


# NoteShareBackend/middleware.py

from channels.db import database_sync_to_async
from django.contrib.auth.models import AnonymousUser
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.tokens import AccessToken


class JWTAuthMiddleware:
    def __init__(self, inner):
        self.inner = inner

    async def __call__(self, scope, receive, send):
        token_key = self._get_jwt_from_headers(scope)
        user = AnonymousUser()

        if token_key:
            try:
                # 核心修改点：使用JWT的AccessToken代替DRF Token
                access_token = AccessToken(token_key)
                access_token.verify()  # 验证签名和有效期
                user = await self._get_user(access_token)
            except (InvalidToken, TokenError) as e:
                print(f"JWT验证失败: {e}")  # 调试用，生产环境应移除

        scope['user'] = user
        return await self.inner(scope, receive, send)

    def _get_jwt_from_headers(self, scope):
        headers = dict(scope.get("headers", []))
        auth_header = headers.get(b'authorization', b'').decode()
        if auth_header:
            parts = auth_header.split()
            if len(parts) == 2 and parts[0].lower() == 'bearer':
                return parts[1]
        return None

    @database_sync_to_async
    def _get_user(self, access_token):
        from django.contrib.auth import get_user_model
        User = get_user_model()
        try:
            user_id = access_token.payload.get('user_id')
            return User.objects.get(id=user_id)
        except User.DoesNotExist:
            return AnonymousUser()