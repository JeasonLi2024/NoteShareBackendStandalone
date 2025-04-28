from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model

class Command(BaseCommand):
    help = "批量创建 loadtest 用户"

    def handle(self, *args, **options):
        User = get_user_model()
        count = 50  # 写死
        password = 'loadtestpass'

        for i in range(1, count + 1):
            username = f"loadtest{i}"
            email = f"{username}@example.com"
            phone = f"1880000{i:04d}"  # 自动生成不同手机号
            if User.objects.filter(username=username).exists():
                self.stdout.write(f"{username} 已存在，跳过")
            else:
                User.objects.create_user(
                    username=username,
                    password=password,
                    email=email,
                    phone=phone
                )
                self.stdout.write(self.style.SUCCESS(f"创建用户 {username}"))
        self.stdout.write(self.style.SUCCESS("全部完成。"))


