生成依赖文件
pip freeze > requirements.txt

安装依赖包
pip install -r requirements.txt

生成数据库迁移文件
python manage.py makemigrations (app_name)
迁移数据库
python manage.py migrate (app_name)
