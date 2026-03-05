from flask import Blueprint, request, send_file, redirect
from utils.common_utils import make_response, generate_share_cover_logic
from configs.logging_config import logger
import os

bp = Blueprint('share', __name__)


@bp.route('/share/cover', methods=['POST'])
def get_share_cover():
    """
    前端点击分享时调用：获取/生成分享专用封面 (已弃用，建议使用 /api/share/cover_image)
    """
    try:
        data = request.json
        video_id = data.get('video_id')
        cover_url = data.get('cover_url')

        if not video_id or not cover_url:
            return make_response(400, '缺少必要参数', None, None, False), 400

        # 生成处理后的封面路径
        processed_url = generate_share_cover_logic(video_id, cover_url)

        # 返回处理后的分享封面路径
        return make_response(200, '成功', {"share_cover_url": processed_url}, None, True), 200

    except Exception as e:
        logger.error(f"Share cover API error: {e}")
        return make_response(500, '封面生成失败', None, None, False), 500


@bp.route('/share/cover_image', methods=['GET'])
def get_share_cover_image():
    """
    动态获取/生成分享封面图片流
    用法: /api/share/cover_image?video_id=xxx&cover_url=encoded_url
    """
    try:
        video_id = request.args.get('video_id')
        cover_url = request.args.get('cover_url')

        if not video_id or not cover_url:
            return "Missing parameters", 400

        # 调用处理逻辑
        # generate_share_cover_logic 如果成功会返回 /static/images/shares/xxx.jpg
        # 如果失败或环境不支持，会返回原始的 cover_url
        result = generate_share_cover_logic(video_id, cover_url)

        # 如果返回的是原始 URL (以 http 开头)，说明处理失败或 Pillow 不可用，直接重定向到原图
        if result.startswith('http'):
            return redirect(result)

        # 否则，返回本地生成的图片文件
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        # result 是 /static/images/shares/xxx.jpg，我们要去掉开头的 /
        file_path = os.path.join(base_dir, result.lstrip('/'))

        if os.path.exists(file_path):
            response = send_file(file_path, mimetype='image/jpeg')
            # 添加强缓存，减少重复处理
            response.headers['Cache-Control'] = 'public, max-age=31536000'
            return response
        else:
            # 如果文件没生成成功，回退到原图
            return redirect(cover_url)

    except Exception as e:
        logger.error(f"Dynamic share cover image error: {e}")
        # 出错时重定向到原图，保证不影响显示
        return redirect(cover_url)
