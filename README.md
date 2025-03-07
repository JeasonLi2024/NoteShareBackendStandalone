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

#### 运行项目
```shell
python manage.py runserver
```

## 拉取更新
```shell
git pull origin master
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



