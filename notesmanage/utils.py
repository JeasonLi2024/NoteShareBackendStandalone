import os
import uuid
import random
import jieba
from django.db.models import Func, IntegerField
from django.urls import reverse
from io import BytesIO
from django.core.files import File
from PIL import Image, ImageDraw, ImageFont
from NoteShareBackend import settings


class UnixTimestamp(Func):
    function = 'UNIX_TIMESTAMP'
    template = '%(function)s(%(expressions)s)'
    output_field = IntegerField()  # 强制指定为整数类型

def get_share_link(request, note_id):
    relative_url = reverse('note-retrieve-update-destroy', args=[note_id])
    return request.build_absolute_uri(relative_url)

def compress_image(uploaded_image, max_size=(1920, 1080), quality=75):
    """
    图片压缩处理器
    :param uploaded_image: 上传的图片文件对象
    :param max_size: 最大尺寸元组（宽, 高）
    :param quality: 压缩质量（1-100）
    :return: 压缩后的File对象
    """
    try:
        img = Image.open(uploaded_image)

        # 转换模式（非RGB模式转为RGB）
        if img.mode != 'RGB':
            img = img.convert('RGB')

        # 调整尺寸
        img.thumbnail(max_size)

        # 创建字节流
        img_io = BytesIO()

        # 保存为JPEG格式（默认）
        img.save(
            img_io,
            format='JPEG',
            quality=quality,
            optimize=True,
            progressive=True
        )

        # 生成Django File对象
        return File(img_io, name=uploaded_image.name)

    except Exception as e:
        # 记录错误或抛出异常
        raise ValueError(f"图片处理失败: {str(e)}")

def extract_keywords(note_data):
    """从笔记内容中提取关键词（中文，不超过10个字）"""
    text = f"{note_data.get('title', '')} {note_data.get('content', '')} {note_data.get('body', '')} {note_data.get('category', '')}"
    keywords = jieba.analyse.textrank(
        text,
        topK=5,
        withWeight=False,
        allowPOS=('n', 'vn', 'v')
    )
    combined = ''.join(keywords)[:10]
    return combined or "默认封面"


def generate_cover_images(keyword):
    """生成5张艺术化封面图"""
    generated_paths = []
    bg_dir = os.path.join(settings.MEDIA_ROOT, 'cover_bgs')
    font_dir = os.path.join(settings.STATIC_ROOT, 'fonts')

    for _ in range(5):
        # 随机选择背景
        img = Image.open(os.path.join(bg_dir, random.choice(os.listdir(bg_dir)))).convert('RGBA')
        draw = ImageDraw.Draw(img)

        # 随机选择字体
        font_file = random.choice(os.listdir(font_dir))
        font_size = random.randint(36, 72)
        try:
            font = ImageFont.truetype(os.path.join(font_dir, font_file), font_size)
        except:
            font = ImageFont.load_default()

        # 随机文字样式
        text_color = (
            random.randint(50, 200),
            random.randint(50, 200),
            random.randint(50, 200)
        )
        shadow_color = (255 - text_color[0], 255 - text_color[1], 255 - text_color[2])

        # 计算文字位置
        bbox = draw.textbbox((0, 0), keyword, font=font)
        text_width = bbox[2] - bbox[0]  # right - left
        text_height = bbox[3] - bbox[1]  # bottom - top
        x = random.randint(20, img.width - text_width - 20)
        y = random.randint(20, img.height - text_height - 20)

        # 添加文字阴影
        draw.text((x + 2, y + 2), keyword, fill=shadow_color, font=font)
        draw.text((x, y), keyword, fill=text_color, font=font)

        # 保存文件
        rgb_img = img.convert('RGB')
        filename = f'generated_covers/{uuid.uuid4().hex}.jpg'
        full_path = os.path.join(settings.MEDIA_ROOT, filename)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        # 保存时显式指定格式和质量
        rgb_img.save(full_path, format='JPEG', quality=85)

        generated_paths.append(filename)

    return generated_paths