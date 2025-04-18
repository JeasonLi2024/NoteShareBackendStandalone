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


def choose_contrast_color(bg_color):
    """根据背景 RGB 三通道计算亮度，返回黑或白对比色，也可扩展为某色调"""
    r, g, b = bg_color
    # 计算相对亮度
    lum = (0.299*r + 0.587*g + 0.114*b)
    return (0,0,0) if lum > 186 else (255,255,255)


def wrap_text(text, font, max_width, draw):
    """将 text 拆分为多行，使每行宽度不超过 max_width"""
    words = list(text)
    lines = []
    current = ""
    for char in words:
        if draw.textlength(current + char, font=font) <= max_width:
            current += char
        else:
            lines.append(current)
            current = char
    if current:
        lines.append(current)
    return lines


def generate_cover_images(keyword, draft_id):
    generated_paths = []
    bg_dir = os.path.join(settings.MEDIA_ROOT, 'cover_bgs')
    font_dir = os.path.join(settings.STATIC_ROOT, 'fonts')
    illu_dir = os.path.join(settings.STATIC_ROOT, 'illustrations')

    for _ in range(5):
        # 1. 打开背景
        bg_path = os.path.join(bg_dir, random.choice(os.listdir(bg_dir)))
        img = Image.open(bg_path).convert('RGBA')
        draw = ImageDraw.Draw(img)

        # 2. 文字属性
        font_file = random.choice(os.listdir(font_dir))
        base_font_size = random.randint(48, 72)
        font = ImageFont.truetype(os.path.join(font_dir, font_file), base_font_size)

        # 3. 自动对比色
        # 取图片中心小块的平均色
        w, h = img.size
        crop = img.crop((w / 4, h / 4, w * 3 / 4, h * 3 / 4)).convert('RGB')
        avg = tuple(sum(c) // (crop.size[0] * crop.size[1]) for c in zip(*crop.getdata()))
        text_color = choose_contrast_color(avg)

        # 4. 换行并计算整个文本区域高度
        max_w = w * 0.8
        lines = wrap_text(keyword, font, max_w, draw)
        total_h = sum(
            draw.textbbox((0, 0), line, font=font)[3] - draw.textbbox((0, 0), line, font=font)[1] for line in lines)
        line_h = (draw.textbbox((0, 0), lines[0], font=font)[3] - draw.textbbox((0, 0), lines[0], font=font)[1])

        # 5. 文字起始位置（居中）
        start_y = (h - total_h) / 2
        for i, line in enumerate(lines):
            line_w = draw.textlength(line, font=font)
            x = (w - line_w) / 2
            y = start_y + i * (line_h + 10)

            # 5a. 发光描边
            for dx in (-2, -1, 0, 1, 2):
                for dy in (-2, -1, 0, 1, 2):
                    draw.text((x + dx, y + dy), line, font=font, fill=(0, 0, 0, 100))
            # 5b. 正文
            draw.text((x, y), line, font=font, fill=text_color)

        # 6. 添加装饰性线条（上下各一条）
        line_color = choose_contrast_color((255 - avg[0], 255 - avg[1], 255 - avg[2]))
        thickness = 4
        draw.line(((w * 0.1, start_y - 20), (w * 0.9, start_y - 20)), fill=line_color, width=thickness)
        draw.line(((w * 0.1, start_y + total_h + 20), (w * 0.9, start_y + total_h + 20)), fill=line_color,
                  width=thickness)

        # 7. 随机叠加小插画
        if os.path.isdir(illu_dir):
            illus = [f for f in os.listdir(illu_dir) if f.lower().endswith(('.png', '.ico'))]
            if illus:
                icon = Image.open(os.path.join(illu_dir, random.choice(illus))).convert('RGBA')
                # 身份：左下或右上
                scale = 0.2
                icon = icon.resize(
                    (int(w * scale), int(w * scale * icon.height / icon.width)),
                    resample=Image.Resampling.LANCZOS  # Pillow ≥ 10 推荐
                )
                pos = random.choice([(20, h - icon.height - 20), (w - icon.width - 20, 20)])
                img.alpha_composite(icon, dest=pos)

        # 8. 保存输出
        rgb_img = img.convert('RGB')
        filename = f'generated_covers/{draft_id}/{uuid.uuid4().hex}.jpg'
        full_path = os.path.join(settings.MEDIA_ROOT, filename)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        # 保存时显式指定格式和质量
        rgb_img.save(full_path, format='JPEG', quality=85)
        generated_paths.append(filename)

    return generated_paths