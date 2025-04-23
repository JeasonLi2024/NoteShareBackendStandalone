from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import UserViewSet, PointHistoryView, RedemptionView
from drf_yasg.views import get_schema_view
from drf_yasg import openapi
from rest_framework.permissions import AllowAny

router = DefaultRouter()
router.register(r'user', UserViewSet, basename='user')

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
    path('user/me/', UserViewSet.as_view({'get': 'me'}), name='user-me'),
    # 注销当前用户
    path('user/delete_me/', UserViewSet.as_view({'delete': 'delete_me'}), name='user-delete-me'),
    # 用户积分明细
    path('point-history/', PointHistoryView.as_view(), name='point-history'),
    # 积分商城/商品兑换
    path('redeem/', RedemptionView.as_view(), name='redeem'),

    path('docs/', schema_view.with_ui('swagger', cache_timeout=0), name='schema-swagger-ui'),
]
