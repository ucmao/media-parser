from flask import jsonify, request
from configs.logging_config import logger
import time
import requests
from io import BytesIO
import os

try:
    from PIL import Image, ImageOps
    HAS_PILLOW = True
except ImportError:
    HAS_PILLOW = False
    logger.warning("Pillow not installed, share cover generation will be disabled.")


def make_response(retcode, retdesc, data, ranking, succ):
    # 生成统一的响应格式
    return jsonify({
        'retcode': retcode,
        'retdesc': retdesc,
        'data': data,
        'ranking': ranking,
        'succ': succ
    })


def generate_share_cover_logic(video_id, remote_cover_url):
    """
    下载、裁剪并合成播放按钮封面
    """
    if not HAS_PILLOW:
        logger.warning("Pillow is not available. Returning original cover URL.")
        return remote_cover_url

    # 1. 定义路径
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    shares_dir = os.path.join(base_dir, 'static', 'images', 'shares')
    play_icon_path = os.path.join(base_dir, 'static', 'images', 'play_icon.png')

    # 确保目录存在
    if not os.path.exists(shares_dir):
        os.makedirs(shares_dir)

    save_path = os.path.join(shares_dir, f"{video_id}.jpg")
    relative_url = f"/static/images/shares/{video_id}.jpg"

    # 2. 检查缓存 (如果已经处理过，直接返回)
    if os.path.exists(save_path):
        return relative_url

    try:
        # 3. 下载远程图片
        logger.info(f"Downloading cover for share: {remote_cover_url}")
        response = requests.get(remote_cover_url, timeout=10)
        img = Image.open(BytesIO(response.content))

        # 4. 居中裁剪 (适配微信分享卡片比例 5:4)
        target_size = (500, 400)
        img = ImageOps.fit(img, target_size, Image.LANCZOS)

        # 5. 合成播放按钮
        if os.path.exists(play_icon_path):
            icon = Image.open(play_icon_path).convert("RGBA")
            # 缩放图标（封面宽度的 1/5）
            icon_w = target_size[0] // 5
            icon_h = int(icon.height * (icon_w / icon.width))
            icon = icon.resize((icon_w, icon_h), Image.LANCZOS)

            # 计算中心位置
            pos = ((target_size[0] - icon_w) // 2, (target_size[1] - icon_h) // 2)
            img.paste(icon, pos, icon)  # 第三个参数是遮罩，用于保留透明度
        else:
            logger.warning(f"Play icon not found at: {play_icon_path}")

        # 6. 保存图片 (JPEG 压缩以减小体积，方便分享)
        img.convert('RGB').save(save_path, 'JPEG', quality=85)
        return relative_url

    except Exception as e:
        logger.error(f"Error processing share cover for {video_id}: {e}")
        return remote_cover_url  # 失败则回退到原始封面

