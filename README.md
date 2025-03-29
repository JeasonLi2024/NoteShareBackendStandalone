# NoteShareBackend
该项目为笔记分享的后端

## 下载项目
```shell
git clone https://github.com/wjt123454321/NoteShareBackend.git
cd NoteShareBackend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```


## 运行项目
#### 创建数据库
打开MySql Workbench，创建数据库
```sql
CREATE DATABASE note_share CHARACTER SET utf8;
```

#### 生成数据库迁移文件
```shell
python manage.py makemigrations (app_name)
```

#### 迁移数据库
```shell
python manage.py migrate (app_name)
```

#### 创建管理员用户
```shell
python manage.py createsuperuser
```

#### 运行项目
```shell
python manage.py runserver
python manage.py runserver 0.0.0.0:8000
```

## 拉取更新
```shell
git pull origin master
```
## 分支合并
```shell
git checkout B #首先切换到分支B
git merge A    #将分支A的更改合并到分支B上
```

## 提交项目
#### 生成依赖文件
```shell
pip freeze > requirements.txt
```

#### 提交项目
```shell
git add .
git commit -m "commit message"
git push origin master
```

#### 启动 Redis （cmd管理员运行）
```cmd
cd /d d:\redis # 进入Redis目录下（根据下载地址更改）
Redis-server.exe redis.windows.conf #启动redis服务
redis-cli.exe #另开一个cmd输入指令打开Redis客户端
ping #在命令中输入ping命令来检测redis服务器与redis客户端的连通性，返回PONG则说明连接成功了。
```

#### celery 启动和异步任务的运行
```shell
celery -A NoteShareBackend worker --loglevel=info 
celery -A NoteShareBackend beat --loglevel=info
```




## 更新日志
2025-03-07 wjt
1. 搭建项目框架：
- 添加django-cors-headers：支持跨端口请求
- 添加djangorestframework：用于构建api 
- 添加django_filter：用于过滤查询
- 添加drf_yasg：用于自动生成接口文档
    - 在路由里查看路径，访问路径即可查看接口文档
- 添加mysqlclient：用于连接数据库
- 添加python-dotenv：用于读取.env文件
- 添加pipdeptree：用于查看依赖树
- 配置MySQL数据库
2. 创建user应用：
- 创建user模型（数据表）
- 创建user序列化器
- 创建user视图
- 创建user路由
- 创建后台管理admin

2025-03-08 lwr（新增头像上传模块）
1. 更新user模型
- 新增用户头像，电子邮箱，创建时间和用户登陆时间
- AbstractBaseUser 是一个抽象模型类，提供了实现自定义用户模型所需的最少属性和方法。它允许开发者完全控制用户模型的定义，而不必受限于 Django 默认的 User 模型。
- BaseUserManager 是一个帮助类，提供了创建用户和超级用户（管理员）的工具方法，同时也允许开发者自定义用户查询集和创建用户的方式。
- PermissionsMixin 则包含了实现 Django 权限系统所需的方法和字段。
2. 更新user序列化器
- 新增一个 create 方法，用于创建一个新的用户实例同时处理头像上传。
3. 更新user视图
- 新增用户查询集： 定义一个get_queryset方法，用于根据当前用户的角色返回不同用户集合。
普通用户只能查看自己的信息，管理员可以查看所有用户。
- 新增用户名检索自定义行为： 重写 get_object 方法，使得可以通过用户名获取用户实例
- 新增 update_avatar 方法，处理用户头像的更新操作。
4. 更新user路由
- 新增处理用户头像更新的请求
5. 编写头像上传test.py文件，测试头像上传功能

2025-03-19 lwr
1. 完善用户注册登录模块，并添加了专业、学校、年级字段
2. 修改代码return Response内容格式，以便于前端得到code信息
3. 增加注册时的邮箱验证码认证功能

2025-03-26 lwr
1. 修改邮箱验证码存储方式，使用Redis缓存
2. 修改用户更改信息的逻辑，在修改密码时使现有的Token失效，要求用户重新登录
3. 增加笔记分享应用模块，初步建立功能雏形
4. 细化用户上传笔记功能，使用CKEditor5实现类似Blog编辑功能（利用表单）
5. 尝试使用 Celery 异步任务队列定期计算热门Top 10笔记，并将结果存储在数据库中，每次发送请求直接从库中调出最新排行，而不用现排
- 也有原始方案。每次请求现排
6. 增加笔记不同格式下的预览功能（转化为HTML链接）
7. 设计浏览量计数逻辑，只有笔记所有者以外的用户访问才会激活计数
8. 增加路由注释

2025-03-29 lwr
1. 修改Django自带admin管理页面相关功能操作
- 页面改为中文，时区设为Asia/Shanghai
- 针对用户信息管理，修改创建用户时的密码存储为哈希处理
- 管理员可以修改用户除密码外的基础信息，管理员有重置用户密码的功能（重置为默认密码并邮件通知用户）
2. 修改部分继承父类的视图在return Response时直接使用的是父类的报错信息而非自定义反馈（try except办法捕获父类报错信息并转为自定义返回内容)
- 使用override暂时翻译报错信息为中文
3. 修改部分使用自定义APIView的视图不能自动连接上下文，手动设置request，可将上传的文件转为绝对路径
