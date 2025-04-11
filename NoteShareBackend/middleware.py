# NoteShareBackend/middleware.py

from channels.db import database_sync_to_async
from django.contrib.auth.models import AnonymousUser
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.tokens import AccessToken
from urllib.parse import parse_qs
from django.contrib.auth import get_user_model


class JWTAuthMiddleware:
    def __init__(self, inner):
        self.inner = inner

    async def __call__(self, scope, receive, send):
        token_key = self._get_token(scope)
        user = AnonymousUser()

        if token_key:
            try:
                # 使用 JWT 的 AccessToken 进行验证
                access_token = AccessToken(token_key)
                access_token.verify()  # 验证签名和有效期
                user = await self._get_user(access_token)
            except (InvalidToken, TokenError) as e:
                print(f"JWT验证失败: {e}")  # 调试信息，生产环境建议移除或记录日志

        scope['user'] = user
        return await self.inner(scope, receive, send)

    def _get_token(self, scope):
        """
        先尝试从 headers 中读取，如果没有则尝试从 query string 中读取 token。
        """
        token = self._get_jwt_from_headers(scope)
        if not token:
            token = self._get_jwt_from_query_string(scope)
        return token

    def _get_jwt_from_headers(self, scope):
        headers = dict(scope.get("headers", []))
        auth_header = headers.get(b'authorization', b'').decode()
        if auth_header:
            parts = auth_header.split()
            # 同时支持 Bearer 和 Token 前缀
            if len(parts) == 2 and parts[0].lower() in ('bearer', 'token'):
                return parts[1]
        return None

    def _get_jwt_from_query_string(self, scope):
        # 解析 query_string 得到字典
        query_string = scope.get("query_string", b"").decode()
        qs = parse_qs(query_string)
        token_list = qs.get('token')
        if token_list:
            return token_list[0]
        return None

    @database_sync_to_async
    def _get_user(self, access_token):
        User = get_user_model()
        try:
            user_id = access_token.payload.get('user_id')
            return User.objects.get(id=user_id)
        except User.DoesNotExist:
            return AnonymousUser()