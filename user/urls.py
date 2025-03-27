from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import UserViewSet
from drf_yasg.views import get_schema_view
from drf_yasg import openapi
from rest_framework.permissions import AllowAny

router = DefaultRouter()
router.register(r'users', UserViewSet, basename='user')

schema_view = get_schema_view(
    openapi.Info(
        title="API平台",
        default_version="v1",
        description="接口文档",
        terms_of_service="",
        contact=openapi.Contact(email='2495128088@qq.com'),
        license=openapi.License(name="BSD License"),
    ),
    public=True,
    permission_classes = [AllowAny]
)

urlpatterns = [
    path('', include(router.urls)),
    # 获取当前用户信息
    path('users/me/', UserViewSet.as_view({'get': 'me'}), name='user-me'),
    # 注销当前用户
    path('users/delete_me/', UserViewSet.as_view({'delete': 'delete_me'}), name='user-delete-me'),

    path('docs/', schema_view.with_ui('swagger', cache_timeout=0), name='schema-swagger-ui'),
]
