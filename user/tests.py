from django.test import TestCase

# Create your tests here.
from django.test import TestCase, override_settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.conf import settings
from .models import User
from django.test import TestCase, Client
import os


class UserAvatarUploadTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            password='testpassword',
            phone='12345678901',
            email='test@example.com'
        )

    @override_settings(MEDIA_ROOT='/tmp/media/')
    def test_upload_valid_avatar(self):
        # 使用实际的图像文件
        test_image_path = os.path.join(settings.BASE_DIR, 'test.jpg')
        with open(test_image_path, 'rb') as f:
            image = SimpleUploadedFile("test.jpg", f.read(), content_type="image/jpeg")

        # 登录测试用户
        self.client.login(username='testuser', password='testpassword')

        # 发送POST请求上传头像
        response = self.client.post(f'/user/{self.user.pk}/update-avatar/', {'avatar': image})

        # 检查响应状态码
        self.assertEqual(response.status_code, 200)

        # 检查用户头像是否已更新
        updated_user = User.objects.get(pk=self.user.pk)
        self.assertIsNotNone(updated_user.avatar)
        # 检查响应状态码
        self.assertEqual(response.status_code, 200)

        # 检查用户头像是否已更新
        updated_user = User.objects.get(pk=self.user.pk)
        self.assertIsNotNone(updated_user.avatar)

        # 打印头像路径
        print("Avatar path:", updated_user.avatar.path)

        # 检查文件是否实际存储
        # avatar_path = updated_user.avatar.path
        # self.assertTrue(os.path.exists(avatar_path))
        # with open(avatar_path, 'rb') as f:
        #     self.assertEqual(f.read(), open(test_image_path, 'rb').read())