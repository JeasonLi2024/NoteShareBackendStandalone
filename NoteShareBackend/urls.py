"""
URL configuration for NoteShareBackend project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls.py import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls.py'))
"""

from django.contrib import admin
from django.urls import path,include
from user.views import (
    UserViewSet, RegisterView, LoginView,
    UserUpdateView, SendVerificationCodeView
)

from rest_framework.routers import SimpleRouter
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)
from django.conf import settings
from django.conf.urls.static import static

router = SimpleRouter()
# router.register(r'user', UserViewSet, basename='user')
urlpatterns = [
    path('send-code/', SendVerificationCodeView.as_view(), name='send-verification-code'),
    path('register/', RegisterView.as_view(), name='register'),
    path('login/', LoginView.as_view(), name='login'),
    path('api/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path("admin/", admin.site.urls),
    path('user/', include('user.urls')),
    path('notesmanage/', include('notesmanage.urls')),
    path('user/update/', UserUpdateView.as_view(), name='user-update'),
    path('user/<int:pk>/update-avatar/', UserViewSet.as_view({'post': 'update_avatar'})),
]


if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

