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
from rest_framework_simplejwt.tokens import RefreshToken, OutstandingToken, BlacklistedToken
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
                "message": "Email and verification code are required",
                "data": {}
            }, status=status.HTTP_400_BAD_REQUEST)

        # 从Redis中获取生成的验证码
        stored_code = cache.get(f'verification_code:{email}')

        if not stored_code or verification_code != stored_code:
            return Response({
                "code": status.HTTP_400_BAD_REQUEST,
                "message": "Invalid verification code",
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
            "message": "error",
            "data": serializer.errors
        }, status=status.HTTP_401_UNAUTHORIZED)

# 用户更新信息功能，添加若更改密码则拉黑现有Token并要求用户重新登录
class UserUpdateView(RetrieveUpdateAPIView):
    queryset = get_user_model().objects.all()
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        return self.request.user

    def update(self, request, *args, **kwargs):
        # 检查请求中是否包含了新密码
        if 'password' in request.data:
            # 获取当前用户
            user = self.get_object()
            # 更新用户密码
            user.set_password(request.data['password'])
            user.save()

            # 黑名单所有未过期的Token
            for token in OutstandingToken.objects.filter(user=user):
                BlacklistedToken.objects.get_or_create(token=token)

            # 返回需要重新登录的信息，可能需要前端跳转页面的操作
            return Response({
                "code": status.HTTP_200_OK,
                "message": "Password updated, please log in again.",
                "data": None
            }, status=status.HTTP_200_OK)
        # 调用了父类的 `update` 方法，更新其他字段，返回值 `response` 是一个 `Response` 对象，包含了更新后的数据和状态码
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

    # 上传头像 我觉得好像不用单独设置一个头像上传的功能，在UserUpdateView里好像就可以实现
    # @action(detail=True, methods=['put', 'patch'], permission_classes=[IsAuthenticated])
    # def update_avatar(self, request, pk=None):
    #     user = get_object_or_404(User, pk=pk)
    #
    #     # Ensure the authenticated user is updating their own avatar
    #     if user != request.user:
    #         raise PermissionDenied("You can only update your own avatar.")
    #
    #     serializer = UserCreateSerializer(user, data=request.data, partial=True)
    #     if serializer.is_valid():
    #         serializer.save()
    #         return Response({
    #             "code": status.HTTP_200_OK,
    #             "message": "success",
    #             "data": serializer.data
    #         }, status=status.HTTP_200_OK)
    #     return Response({
    #         "code": status.HTTP_400_BAD_REQUEST,
    #         "message": "error",
    #         "data": serializer.errors
    #     }, status=status.HTTP_400_BAD_REQUEST)
