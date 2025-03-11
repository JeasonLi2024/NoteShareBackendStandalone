# from rest_framework import viewsets
# from rest_framework.response import Response
# from rest_framework import status
# from .models import User
# from .serializers import UserSerializer, UserCreateSerializer
# from django.shortcuts import get_object_or_404
#
# class UserViewSet(viewsets.ViewSet):
#     queryset = User.objects.all()
#     serializer_class = UserSerializer
#
#     def get_object(self, pk):
#         try:
#             return User.objects.get(pk=pk)
#         except User.DoesNotExist:
#             raise status.HTTP_404_NOT_FOUND
#
#     def get_serializer(self, *args, **kwargs):
#         return self.serializer_class(*args, **kwargs)
#
#     # 获取用户列表
#     def list(self, request):
#         users = User.objects.all()
#         serializer = UserSerializer(users, many=True)
#         return Response(serializer.data)
#
#     # 获取单个用户信息
#     def retrieve(self, request, pk=None):
#         user = get_object_or_404(User, pk=pk)
#         serializer = UserSerializer(user)
#         return Response(serializer.data)
#
#     # 创建用户
#     def create(self, request):
#         serializer = UserCreateSerializer(data=request.data, files=request.FILES)
#         if serializer.is_valid():
#             serializer.save()
#             return Response(serializer.data, status=status.HTTP_201_CREATED)
#         return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
#
#     # 更新用户信息
#     def update(self, request, pk=None):
#         user = get_object_or_404(User, pk=pk)
#         serializer = UserCreateSerializer(user, data=request.data, files=request.FILES, partial=True)
#         if serializer.is_valid():
#             serializer.save()
#             return Response(serializer.data)
#         return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
#
#     # 删除用户
#     def destroy(self, request, pk=None):
#         user = get_object_or_404(User, pk=pk)
#         user.delete()
#         return Response(status=status.HTTP_204_NO_CONTENT)
#
#     #上传头像
#     def update_avatar(self, request, pk=None):
#         user = self.get_object(pk)
#         serializer = self.get_serializer(user, data=request.data, partial=True)
#         if serializer.is_valid():
#             serializer.save()
#             return Response(serializer.data)
#         return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

from rest_framework import viewsets
from rest_framework.response import Response
from rest_framework import status
from .models import User
from .serializers import UserSerializer, UserCreateSerializer, LoginSerializer
from django.shortcuts import get_object_or_404
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.exceptions import PermissionDenied
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken


class RegisterView(APIView):
    permission_classes = [AllowAny]
    def post(self, request):
        serializer = UserCreateSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            return Response({'message': 'User created successfully'}, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class LoginView(APIView):
    permission_classes = [AllowAny]
    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.validated_data
            refresh = RefreshToken.for_user(user)
            return Response({
                'refresh': str(refresh),
                'access': str(refresh.access_token),
            }, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_401_UNAUTHORIZED)

class UserViewSet(viewsets.ViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer

    def get_object(self, pk):
        try:
            return User.objects.get(pk=pk)
        except User.DoesNotExist:
            raise status.HTTP_404_NOT_FOUND

    def get_serializer(self, *args, **kwargs):
        return self.serializer_class(*args, **kwargs)

    # 获取用户列表
    def list(self, request):
        users = User.objects.all()
        serializer = UserSerializer(users, many=True)
        return Response(serializer.data)

    # 获取单个用户信息
    def retrieve(self, request, pk=None):
        user = get_object_or_404(User, pk=pk)
        serializer = UserSerializer(user)
        return Response(serializer.data)

    # 创建用户
    def create(self, request):
        serializer = UserCreateSerializer(data=request.data, files=request.FILES)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    # 更新用户信息
    def update(self, request, pk=None):
        user = get_object_or_404(User, pk=pk)

        # Ensure the authenticated user is updating their own profile
        if user != request.user:
            raise PermissionDenied("You can only update your own profile.")

        serializer = UserCreateSerializer(user, data=request.data, files=request.FILES, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    # 删除用户
    def destroy(self, request, pk=None):
        user = get_object_or_404(User, pk=pk)

        # Ensure the authenticated user is deleting their own profile
        if user != request.user:
            raise PermissionDenied("You can only delete your own profile.")

        user.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

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
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)