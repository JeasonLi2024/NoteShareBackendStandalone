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
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.conf import settings
import random
import datetime



class SendVerificationCodeView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        if not request.session.session_key:
            request.session.create()
        email = request.data.get('email')
        if not email:
            return Response({
                "code": status.HTTP_400_BAD_REQUEST,
                "message": "Email is required",
                "data": {}
            }, status=status.HTTP_400_BAD_REQUEST)

        code = str(random.randint(100000, 999999))

        # Store the code in session
        request.session['verification_code'] = code
        request.session.set_expiry(300)  # expire in 5 minutes


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

class RegisterView(generics.CreateAPIView):
    queryset = get_user_model().objects.all()
    serializer_class = UserCreateSerializer
    permission_classes = [AllowAny]

    def create(self, request, *args, **kwargs):
        verification_code = request.data.get('verification_code')
        stored_code = request.session.get('verification_code')
        email = request.data.get('email')

        if not email or not verification_code:
            return Response({
                "code": status.HTTP_400_BAD_REQUEST,
                "message": "Email and verification code are required",
                "data": {}
            }, status=status.HTTP_400_BAD_REQUEST)

        if verification_code != stored_code:
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
                }
            }, status=status.HTTP_200_OK)
        return Response({
            "code": status.HTTP_401_UNAUTHORIZED,
            "message": "error",
            "data": serializer.errors
        }, status=status.HTTP_401_UNAUTHORIZED)


class UserUpdateView(RetrieveUpdateAPIView):
    queryset = get_user_model().objects.all()
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        return self.request.user

    def update(self, request, *args, **kwargs):
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


User = get_user_model()


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

    # 获取用户列表
    def list(self, request):
        users = User.objects.all()
        serializer = UserSerializer(users, many=True)
        return Response({
            "code": status.HTTP_200_OK,
            "message": "success",
            "data": serializer.data
        }, status=status.HTTP_200_OK)

    # 获取单个用户信息
    def retrieve(self, request, pk=None):
        user = get_object_or_404(User, pk=pk)
        serializer = UserSerializer(user)
        return Response({
            "code": status.HTTP_200_OK,
            "message": "success",
            "data": serializer.data
        }, status=status.HTTP_200_OK)

    # 创建用户
    def create(self, request):
        serializer = UserCreateSerializer(data=request.data, files=request.FILES)
        if serializer.is_valid():
            serializer.save()
            return Response({
                "code": status.HTTP_201_CREATED,
                "message": "success",
                "data": serializer.data
            }, status=status.HTTP_201_CREATED)
        return Response({
            "code": status.HTTP_400_BAD_REQUEST,
            "message": "error",
            "data": serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)

    # 更新用户信息
    def update(self, request, pk=None):
        user = get_object_or_404(User, pk=pk)

        # Ensure the authenticated user is updating their own profile
        if user != request.user:
            raise PermissionDenied("You can only update your own profile.")

        serializer = UserCreateSerializer(user, data=request.data, files=request.FILES, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response({
                "code": status.HTTP_200_OK,
                "message": "success",
                "data": serializer.data
            }, status=status.HTTP_200_OK)
        return Response({
            "code": status.HTTP_400_BAD_REQUEST,
            "message": "error",
            "data": serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)

    # 删除用户
    def destroy(self, request, pk=None):
        user = get_object_or_404(User, pk=pk)

        # Ensure the authenticated user is deleting their own profile
        if user != request.user:
            raise PermissionDenied("You can only delete your own profile.")

        user.delete()
        return Response({
            "code": status.HTTP_204_NO_CONTENT,
            "message": "success",
            "data": {}
        }, status=status.HTTP_204_NO_CONTENT)

    # 上传头像
    @action(detail=True, methods=['put', 'patch'], permission_classes=[IsAuthenticated])
    def update_avatar(self, request, pk=None):
        user = get_object_or_404(User, pk=pk)

        # Ensure the authenticated user is updating their own avatar
        if user != request.user:
            raise PermissionDenied("You can only update your own avatar.")

        serializer = UserCreateSerializer(user, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response({
                "code": status.HTTP_200_OK,
                "message": "success",
                "data": serializer.data
            }, status=status.HTTP_200_OK)
        return Response({
            "code": status.HTTP_400_BAD_REQUEST,
            "message": "error",
            "data": serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)
