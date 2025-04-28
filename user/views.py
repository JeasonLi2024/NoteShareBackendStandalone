import logging
from datetime import datetime
from rest_framework import viewsets
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework import status, generics
from rest_framework.generics import RetrieveUpdateAPIView
from django.db import transaction
from .models import Goods, PointHistory
from django.db.models import F
from .serializers import UserSerializer, UserCreateSerializer, LoginSerializer, PointHistorySerializer, GoodsSerializer, \
    EmailLoginSerializer
from django.shortcuts import get_object_or_404
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.exceptions import PermissionDenied, NotFound
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.token_blacklist.models import OutstandingToken, BlacklistedToken
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.conf import settings
import random
from django.core.cache import cache
from rest_framework.exceptions import ValidationError
from django.utils.translation import override
from django.utils import timezone


User = get_user_model()

# 邮箱验证码发送功能
class SendVerificationCodeView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        email = request.data.get('email')
        if not email:
            return Response({
                "code": status.HTTP_400_BAD_REQUEST,
                "message": "邮箱为必填项",
                "data": {}
            }, status=status.HTTP_400_BAD_REQUEST)

        code = str(random.randint(100000, 999999))

        cache.set(f'verification_code:{email}', code, timeout=600)

        send_mail(
            subject='验证码',
            message=f'''您好！欢迎使用NoteShare，您的验证码是：{code}。
    请在10分钟内完成填写，若非本人操作，请立即联系客服。''',
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[email]
        )

        return Response({
            "code": status.HTTP_200_OK,
            "message": "Verification code sent",
            "data": {}
        }, status=status.HTTP_200_OK)

# 注册功能
class RegisterView(generics.CreateAPIView):
    queryset = get_user_model().objects.all()
    serializer_class = UserCreateSerializer
    permission_classes = [AllowAny]

    def create(self, request, *args, **kwargs):
        verification_code = request.data.get('verification_code')
        email = request.data.get('email')
        cache_key = f'verification_code:{email}'
        stored_code = cache.get(cache_key)

        # 基础验证：邮箱和验证码必填
        if not email or not verification_code:
            return Response({
                "code": status.HTTP_400_BAD_REQUEST,
                "message": "邮箱和验证码不能为空",
                "data": {}
            }, status=status.HTTP_400_BAD_REQUEST)

        # 验证码校验逻辑
        if not stored_code or verification_code != stored_code:
            return Response({
                "code": status.HTTP_400_BAD_REQUEST,
                "message": "验证码无效或已过期",
                "data": {}
            }, status=status.HTTP_400_BAD_REQUEST)

        # 使用中文环境处理创建流程
        try:
            with override('zh-hans'):  # 确保序列化器错误返回中文
                response = super().create(request, *args, **kwargs)

        except ValidationError as e:
            # 处理字段验证错误
            return Response({
                "code": status.HTTP_400_BAD_REQUEST,
                "message": self.get_error_message(e.detail),
                "data": {}
            }, status=status.HTTP_400_BAD_REQUEST)

        # 处理创建成功的情况
        if response.status_code == status.HTTP_201_CREATED:
            cache.delete(cache_key)  # 清除已使用的验证码
            return Response({
                "code": status.HTTP_201_CREATED,
                "message": "注册成功",
                "data": response.data
            }, status=status.HTTP_201_CREATED)

        # 处理其他异常状态（理论上不会执行到这里）
        return Response({
            "code": response.status_code,
            "message": self.get_error_message(response.data),
            "data": response.data
        }, status=response.status_code)

    # 统一错误消息格式化方法（与UserUpdateView保持复用）
    def get_error_message(self, error_data):
        """将DRF的错误数据结构转换为中文字符串"""
        if isinstance(error_data, dict):
            errors = []
            for field, messages in error_data.items():
                if isinstance(messages, list):
                    errors.append(f"{field}: {messages[0]}")
                else:
                    errors.append(f"{field}: {messages}")
            return "; ".join(errors)
        elif isinstance(error_data, list):
            return "; ".join(error_data)
        return str(error_data)

# 登录功能
class LoginView(APIView):
    permission_classes = [AllowAny]
    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.validated_data['user']
            user.last_login = timezone.now()  # 使用 Django 的时区工具
            user.save(update_fields=['last_login'])
            refresh = RefreshToken.for_user(user)
            return Response({
                "code": status.HTTP_200_OK,
                "message": "success",
                "data": {
                    'refresh': str(refresh),
                    'access': str(refresh.access_token),
                    # 现在应该不需要user.id来向后端发送请求了，已经修改为request.user利用有效的Token自动匹配获取相应的用户
                    'user_id': user.id
                }
            }, status=status.HTTP_200_OK)
        return Response({
            "code": status.HTTP_401_UNAUTHORIZED,
            "message": "用户名或密码错误",
            "data": serializer.errors
        }, status=status.HTTP_401_UNAUTHORIZED)


# 邮箱+验证码登录
class EmailLoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = EmailLoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data['user']

        # 生成 JWT
        refresh = RefreshToken.for_user(user)
        data = {
            'access': str(refresh.access_token),
            'refresh': str(refresh)
        }
        return Response({
            'code': status.HTTP_200_OK,
            'message': '登录成功',
            'data': data
        }, status=status.HTTP_200_OK)


# # 用户更新信息功能，添加若更改密码则拉黑现有Token并要求用户重新登录
# class UserUpdateView(RetrieveUpdateAPIView):
#     queryset = get_user_model().objects.all()
#     serializer_class = UserSerializer
#     permission_classes = [IsAuthenticated]
#
#     def get_object(self):
#         return self.request.user
#
#     def update(self, request, *args, **kwargs):
#         if 'password' in request.data:
#             user = self.get_object()
#             user.set_password(request.data['password'])
#             user.save()
#
#             # 黑名单处理
#             tokens = OutstandingToken.objects.filter(user=user)
#             for token in tokens:
#                 BlacklistedToken.objects.get_or_create(token=token)
#
#         # 处理其他字段的更新，异常捕获：使用 try-except 捕获 ValidationError，确保父类 update 方法中的验证错误能被处理，避免直接返回未包装的响应。
#         try:
#             # 临时切换语言环境为中文
#             with override('zh-hans'):
#                 response = super().update(request, *args, **kwargs)
#         except ValidationError as e:
#             error_message = self.get_error_message(e.detail)
#             return Response({
#                 "code": status.HTTP_400_BAD_REQUEST,
#                 "message": error_message,
#                 "data": None
#             }, status=status.HTTP_400_BAD_REQUEST)
#
#         if response.status_code == status.HTTP_200_OK:
#             return Response({
#                 "code": status.HTTP_200_OK,
#                 "message": "success",
#                 "data": response.data
#             }, status=status.HTTP_200_OK)
#         else:
#             error_message = self.get_error_message(response.data)
#             return Response({
#                 "code": response.status_code,
#                 "message": error_message,
#                 "data": None
#             }, status=response.status_code)
#
#     # 将 DRF 默认的错误结构（如字典或列表）转换为字符串，便于前端直接显示。
#     def get_error_message(self, error_data):
#         if isinstance(error_data, dict):
#             errors = []
#             for key, value in error_data.items():
#                 if isinstance(value, list):
#                     errors.append(f"{key}: {value[0]}")
#                 else:
#                     errors.append(f"{key}: {value}")
#             return "; ".join(errors)
#         elif isinstance(error_data, list):
#             return "; ".join(error_data)
#         else:
#             return str(error_data)

logger = logging.getLogger(__name__)


class UserUpdateView(RetrieveUpdateAPIView):
    queryset = get_user_model().objects.all()
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        return self.request.user

    def update(self, request, *args, **kwargs):
        user = self.request.user
        old_email = user.email
        try:
            email_update_success = False
            with transaction.atomic():
                # 处理邮箱修改验证
                new_email = request.data.get('new_email')
                email_code = request.data.get('email_code')

                if new_email:
                    self._validate_email_change(new_email, email_code)
                    email_update_success = True

                # 处理密码修改
                password_updated = False
                if 'new_password' in request.data:
                    password_updated = self._handle_password_update(request)

                # 处理其他字段更新
                with override('zh-hans'):
                    response = super().update(request, *args, **kwargs)

            # 事务外操作
            if email_update_success:
                self._send_email_update_notification(user, old_email, new_email)

            if password_updated:
                self._send_password_change_email(user)

            return self._build_success_response(response)

        except ValidationError as e:
            return self._build_validation_error(e)

        except Exception as e:
            logger.error(f"用户更新失败: {str(e)}", exc_info=True)
            return self._build_server_error(e)

    def _validate_email_change(self, new_email, submitted_code):
        """验证邮箱修改请求"""
        cache_key = f'verification_code:{new_email}'
        stored_code = cache.get(cache_key)

        if not stored_code or stored_code != submitted_code:
            raise ValidationError({"email_code": "邮箱验证码无效或已过期"})

        # 验证邮箱是否已被使用
        if get_user_model().objects.filter(email=new_email).exists():
            raise ValidationError({"new_email": "该邮箱已被其他账号使用"})

        # 执行邮箱更新
        user = self.get_object()
        old_email = user.email
        user.email = new_email
        user.save(update_fields=['email'])
        cache.delete(cache_key)  # 清除已使用的验证码

        # 记录日志
        logger.info(f"用户 {user.id} 邮箱修改: {old_email} -> {new_email}")

    def _handle_password_update(self, request):
        """处理密码修改逻辑"""
        user = self.get_object()
        new_password = request.data['new_password']
        confirm_password = request.data['confirm_password']
        old_password = request.data['old_password']

        if new_password != confirm_password:
            raise ValidationError({"confirm_password": "两次输入的密码不一致"})

        if not user.check_password(old_password):
            raise ValidationError({"old_password": "旧密码验证失败"})

        user.set_password(new_password)
        user.save()

        # 令牌失效处理
        valid_tokens = OutstandingToken.objects.filter(
            user=user,
            expires_at__gt=datetime.now()
        )
        BlacklistedToken.objects.bulk_create(
            [BlacklistedToken(token=t) for t in valid_tokens],
            ignore_conflicts=True
        )
        logger.info(f"用户 {user.id} 密码更新，已失效 {len(valid_tokens)} 个令牌")
        return True

    def _send_email_update_notification(self, user, old_email, new_email):
        """发送邮箱修改通知"""
        try:
            # 给旧邮箱发送通知
            send_mail(
                subject='邮箱修改通知',
                message=f'''尊敬的 {user.username}：
            您的账号邮箱已从 {old_email}  变更为 {new_email}。
            若非本人操作，请立即联系客服。''',
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[old_email]  # 原邮箱
            )
            # 给新邮箱发送确认
            send_mail(
                subject='邮箱绑定确认',
                message=f'''尊敬的 {user.username}：
            您已成功将账号邮箱变更为本邮箱。
            若非本人操作，请立即联系客服。''',
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[new_email]
            )
        except Exception as e:
            logger.error(f"邮箱通知发送失败: {str(e)}")

    def _send_password_change_email(self, user):
        """发送密码修改通知邮件"""
        try:
            send_mail(
                subject='账户安全通知 - 密码已修改',
                message=f'''尊敬的 {user.username}：
            您的账户密码已于 {datetime.now().strftime("%Y-%m-%d %H:%M:%S")} 成功修改。
            若非本人操作，请立即联系客服。''',
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.email],
                fail_silently=True
            )
        except Exception as e:
            logger.warning(f"密码修改邮件发送失败: {str(e)}")

    def _build_success_response(self, response):
        """构建成功响应"""
        return Response({
            "code": status.HTTP_200_OK,
            "message": "更新成功",
            "data": response.data
        }, status=status.HTTP_200_OK)

    def _build_validation_error(self, exception):
        """构建验证错误响应"""
        return Response({
            "code": status.HTTP_400_BAD_REQUEST,
            "message": self._format_errors(exception.detail),
            "data": None
        }, status=status.HTTP_400_BAD_REQUEST)

    def _build_server_error(self, exception):
        """构建服务器错误响应"""
        return Response({
            "code": status.HTTP_500_INTERNAL_SERVER_ERROR,
            "message": "系统错误，请稍后重试",
            "data": None,
            "detail": str(exception)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def _format_errors(self, error_detail):
        if isinstance(error_detail, dict):
            parts = []
            for k, v in error_detail.items():
                msg = v[0] if isinstance(v, (list, tuple)) else v
                parts.append(f"{k}: {msg}")
            return "; ".join(parts)
        return None


# 视图集
class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [AllowAny]

    # 获取用户列表 '/user/users'
    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        serializer = self.get_serializer(queryset, many=True, context={'request': request})
        return Response({
            "code": status.HTTP_200_OK,
            "message": "success",
            "data": serializer.data
        }, status=status.HTTP_200_OK)

    # 获取单个用户信息 访问`user/users/<pk>/` 就会映射到 `UserViewSet` 的 `retrieve` 方法，其中 `<pk>` 是用户的主键（通常是用户ID）
    def retrieve(self, request, pk=None):
        user = self.get_object()  # 利用 ModelViewSet 内置的对象检索方法
        serializer = self.get_serializer(user, context={'request': request})
        return Response({
            "code": status.HTTP_200_OK,
            "message": "success",
            "data": serializer.data
        }, status=status.HTTP_200_OK)

    # 获取当前用户信息 'user/users/me'
    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated])
    def me(self, request):
        serializer = self.get_serializer(request.user, context={'request': request})
        return Response({
            "code": status.HTTP_200_OK,
            "message": "success",
            "data": serializer.data
        }, status=status.HTTP_200_OK)

    # 用户选择注销当前账号 'user/users/delete_me‘
    @action(detail=False, methods=['delete'], permission_classes=[IsAuthenticated])
    def delete_me(self, request):
        # DRF 已经处理了认证，所以直接删除用户
        request.user.delete()
        return Response({
            "code": status.HTTP_204_NO_CONTENT,
            "message": "Account deleted successfully",
            "data": {}
        }, status=status.HTTP_204_NO_CONTENT)

# 自定义分页处理
class TenPerPagePagination(PageNumberPagination):
    """每页只展示 10 条记录，前端可选通过 page_size 参数调整，但不超过最大值。"""
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 100

# 积分明细
class PointHistoryView(generics.ListAPIView):
    """积分明细视图：每页展示 10 条，返回用户总积分以及分页后的明细列表。"""
    serializer_class = PointHistorySerializer
    pagination_class = TenPerPagePagination
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = self.request.user.point_histories.all()

        # 按时间范围筛选
        start = self.request.query_params.get('start_date')
        end = self.request.query_params.get('end_date')
        if start:
            qs = qs.filter(created_at__gte=timezone.datetime.fromisoformat(start))
        if end:
            qs = qs.filter(created_at__lte=timezone.datetime.fromisoformat(end))
        return qs

    def list(self, request, *args, **kwargs):
        # 分页并序列化
        page = self.paginate_queryset(self.get_queryset())
        serializer = self.get_serializer(page, many=True)
        paginated = self.get_paginated_response(serializer.data).data
        # 改名 results -> histories 并加入 total_points
        paginated['histories'] = paginated.pop('results')
        paginated['total_points'] = request.user.points
        return Response(paginated, status=status.HTTP_200_OK)


# 积分商城
class RedemptionView(APIView):
    """积分兑换视图：支持 GET（查询可兑换商品及积分），POST（兑换商品）。"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        goods_qs = Goods.objects.filter(is_active=True)
        serializer = GoodsSerializer(goods_qs, many=True, context={'request': request})
        return Response({
            'points': user.points,
            'goods': serializer.data
        }, status=status.HTTP_200_OK)

    def post(self, request):
        goods_id = request.data.get('goods_id')
        try:
            quantity = int(request.data.get('quantity', 1))
        except (TypeError, ValueError):
            return Response({'error': 'quantity 必须是正整数'}, status=status.HTTP_400_BAD_REQUEST)

        if not goods_id:
            return Response({'error': '需要提供 goods_id'}, status=status.HTTP_400_BAD_REQUEST)
        if quantity < 1:
            return Response({'error': 'quantity 必须是正整数'}, status=status.HTTP_400_BAD_REQUEST)

        goods = get_object_or_404(Goods, pk=goods_id, is_active=True)
        total_cost = goods.price * quantity

        # 把整个用户读锁和更新放在同一个事务里
        with transaction.atomic():
            user = User.objects.select_for_update().get(pk=request.user.pk)
            if user.points < total_cost:
                return Response({'error': '您的积分不足无法兑换'}, status=status.HTTP_400_BAD_REQUEST)

            # 扣积分、加 ai_limits
            user.points = F('points') - total_cost
            user.ai_limits = F('ai_limits') + quantity
            user.save(update_fields=['points', 'ai_limits'])
            # 刷新数据库里的真实值
            user.refresh_from_db()

            # 记录兑换历史
            PointHistory.objects.create(
                user=user,
                amount=-total_cost,
                source='redeem',
                description=f'兑换{goods.name} x{quantity}'
            )

        return Response({
            'message': f'已成功兑换{goods.name} x{quantity}',
            'points': user.points,
            'ai_limits': user.ai_limits
        }, status=status.HTTP_200_OK)
