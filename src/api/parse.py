from flask import Blueprint, request
from configs.logging_config import logger
from configs.general_constants import DOMAIN_TO_NAME
from utils.web_fetcher import WebFetcher, UrlParser
from src.parser_factory import ParserFactory
from utils.common_utils import make_response

bp = Blueprint('parse', __name__)


@bp.route('/parse', methods=['POST'])
def parse():
    try:
        data = request.json
        text = data.get('text')
        
        # 1. 解析基础信息
        redirect_url = WebFetcher.fetch_redirect_url(UrlParser.get_url(text))
        platform = DOMAIN_TO_NAME.get(UrlParser.get_domain(redirect_url))
        real_url = UrlParser.extract_video_address(redirect_url)
        logger.debug(f'real_url {real_url}')

        if not platform:
            logger.error(f'This link is not supported for extraction: {real_url}')
            return make_response(400, '该链接尚未支持提取', None, False), 400

        # 2. 获取解析器
        parser = ParserFactory.create_parser(platform, real_url)
        
        # 3. 核心抓取逻辑
        content_data = _fetch_with_retry(parser, platform)

        if not content_data['video_url'] and not content_data['image_list']:
            logger.error(f"Failed to retrieve media content for {platform}")

        processed_image_list = []
        if content_data.get('image_list'):
            for img in content_data['image_list']:
                if isinstance(img, dict):
                    processed_image_list.append({
                        'url': UrlParser.convert_to_https(img.get('url')),
                        'live_photo_url': UrlParser.convert_to_https(img.get('live_photo_url'))
                    })
                else:
                    processed_image_list.append(UrlParser.convert_to_https(img))

        # 4. 统一转换 HTTPS
        data_dict = {
            'video_id': UrlParser.get_video_id(redirect_url),
            'platform': platform,
            'title': content_data['title'],
            'video_url': UrlParser.convert_to_https(content_data['video_url']),
            'audio_url': UrlParser.convert_to_https(content_data.get('audio_url')),
            'cover_url': UrlParser.convert_to_https(content_data['cover_url']),
            'author': content_data['author'],
            'image_list': processed_image_list
        }
        
        logger.debug(f'Parse Success for platform {platform}')
        return make_response(200, '成功', data_dict, True), 200

    except Exception as e:
        logger.exception("Parse Error") # 使用 exception 会带上堆栈信息
        return make_response(500, '功能太火爆啦，请稍后再试', None, False), 500


def _fetch_with_retry(parser, platform):
    """提取公共的抓取逻辑，小红书特殊处理"""
    max_attempts = 3 if platform == '小红书' else 1
    
    for i in range(max_attempts):
        res = {
            'title': parser.get_title_content(),
            'video_url': parser.get_real_video_url(),
            'cover_url': parser.get_cover_photo_url(),
            'author': safe_execute(parser.get_author_info),
            'image_list': safe_execute(parser.get_image_list, default=[]),
            'audio_url': safe_execute(parser.get_audio_url)
        }
        if res['video_url'] or res['image_list']:
            return res
            
        if i < max_attempts - 1:
            logger.debug(f"Attempt {i + 1} failed. Retrying...")
            
    return res


def safe_execute(func, default=None):
    """安全执行辅助函数，减少 try-except 视觉噪音"""
    try:
        return func()
    except Exception:
        return default
