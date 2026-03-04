from flask import Blueprint, request
from utils.common_utils import make_response, generate_share_cover_logic
from configs.logging_config import logger

bp = Blueprint('share', __name__)


@bp.route('/share/cover', methods=['POST'])
def get_share_cover():
    """
    前端点击分享时调用：获取/生成分享专用封面
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
