from rest_framework import viewsets
from rest_framework.response import Response
from rest_framework import status, generics
from rest_framework.generics import RetrieveUpdateAPIView
from .serializers import UserSerializer, UserCreateSerializer, LoginSerializer
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

User = get_user_model()

# 邮箱验证码发送功能
class SendVerificationCodeView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        email = request.data.get('email')
        if not email:
            return Response({
                "code": status.HTTP_400_BAD_REQUEST,
                "message": "Email is required",
                "data": {}
            }, status=status.HTTP_400_BAD_REQUEST)

        code = str(random.randint(100000, 999999))

        # Store the code in Redis with a 5-minute expiration
        cache.set(f'verification_code:{email}', code, timeout=600)

        # Send email
        subject = 'Verification Code'
        message = f'Your verification code is {code}'
        from_email = settings.DEFAULT_FROM_EMAIL
        recipient_list = [email]
        send_mail(subject, message, from_email, recipient_list)

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

        if not email or not verification_code:
            return Response({
                "code": status.HTTP_400_BAD_REQUEST,
                "message": "邮箱和验证码不能为空",
                "data": {}
            }, status=status.HTTP_400_BAD_REQUEST)

        # 从Redis中获取生成的验证码
        stored_code = cache.get(f'verification_code:{email}')

        if not stored_code or verification_code != stored_code:
            return Response({
                "code": status.HTTP_400_BAD_REQUEST,
                "message": "验证码无效",
                "data": {}
            }, status=status.HTTP_400_BAD_REQUEST)

        response = super().create(request, *args, **kwargs)
        if response.status_code == status.HTTP_201_CREATED:
            return Response({
                "code": status.HTTP_201_CREATED,
                "message": "success",
                "data": response.data
            }, status=status.HTTP_201_CREATED)
        return Response({
            "code": response.status_code,
            "message": "error",
            "data": response.data
        }, status=response.status_code)

# 登录功能
class LoginView(APIView):
    permission_classes = [AllowAny]
    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.validated_data
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

# 用户更新信息功能，添加若更改密码则拉黑现有Token并要求用户重新登录
class UserUpdateView(RetrieveUpdateAPIView):
    queryset = get_user_model().objects.all()
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]  # 修正为需要认证

    def get_object(self):
        return self.request.user

    def update(self, request, *args, **kwargs):
        if 'password' in request.data:
            user = self.get_object()
            user.set_password(request.data['password'])
            user.save()

            # 黑名单处理
            tokens = OutstandingToken.objects.filter(user=user)
            for token in tokens:
                BlacklistedToken.objects.get_or_create(token=token)

            return Response({
                "code": status.HTTP_200_OK,
                "message": "Password updated, please log in again.",
                "data": None
            }, status=status.HTTP_200_OK)

        # 处理其他字段更新
        response = super().update(request, *args, **kwargs)
        if response.status_code == status.HTTP_200_OK:
            return Response({
                "code": status.HTTP_200_OK,
                "message": "success",
                "data": response.data
            }, status=status.HTTP_200_OK)
        return Response({
            "code": response.status_code,
            "message": "error",
            "data": response.data
        }, status=response.status_code)

# 视图集
class UserViewSet(viewsets.ViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [AllowAny]

    def get_object(self, pk):
        try:
            return User.objects.get(pk=pk)
        except User.DoesNotExist:
            raise NotFound("User not found")

    def get_serializer(self, *args, **kwargs):
        return self.serializer_class(*args, **kwargs)

    # 获取用户列表 '/user/users'
    def list(self, request):
        users = User.objects.all()
        serializer = UserSerializer(users, many=True)
        return Response({
            "code": status.HTTP_200_OK,
            "message": "success",
            "data": serializer.data
        }, status=status.HTTP_200_OK)

    # 获取单个用户信息 访问`user/users/<pk>/` 就会映射到 `UserViewSet` 的 `retrieve` 方法，其中 `<pk>` 是用户的主键（通常是用户ID）
    def retrieve(self, request, pk=None):
        # 检查请求的用户是否是管理员或请求的用户ID是否与当前用户ID匹配
        if not (request.user.is_staff or str(request.user.id) == pk):
            return Response({
                "code": status.HTTP_403_FORBIDDEN,
                "message": "You do not have permission to access this user's information.",
                "data": None
            }, status=status.HTTP_403_FORBIDDEN)

        user = get_object_or_404(User, pk=pk)
        serializer = self.get_serializer(user)
        return Response({
            "code": status.HTTP_200_OK,
            "message": "success",
            "data": serializer.data
        }, status=status.HTTP_200_OK)


    # 获取当前用户信息 'user/users/me'
    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated])
    def me(self, request):
        if not request.user.is_authenticated:
            return Response({
                "code": status.HTTP_401_UNAUTHORIZED,
                "message": "unauthenticated",
                "data": {}
            }, status=status.HTTP_401_UNAUTHORIZED)

        serializer = self.get_serializer(request.user)
        return Response({
            "code": status.HTTP_200_OK,
            "message": "success",
            "data": serializer.data
        }, status=status.HTTP_200_OK)

    # 用户选择注销当前账号 'user/users/delete_me‘
    @action(detail=False, methods=['delete'], permission_classes=[IsAuthenticated])
    def delete_me(self, request):
        if not request.user.is_authenticated:
            return Response({
                "code": status.HTTP_401_UNAUTHORIZED,
                "message": "unauthenticated",
                "data": {}
            }, status=status.HTTP_401_UNAUTHORIZED)

        # 获取当前认证的用户
        current_user = request.user
        # 删除用户
        current_user.delete()
        return Response({
            "code": status.HTTP_204_NO_CONTENT,
            "message": "success",
            "data": {}
        }, status=status.HTTP_204_NO_CONTENT)
