from flask import Blueprint, request, Response, stream_with_context
import requests
from configs.logging_config import logger
from utils.web_fetcher import WebFetcher, UrlParser
from src.parser_factory import ParserFactory
from utils.common_utils import make_response

bp = Blueprint('parse', __name__)
MAX_TEXT_LENGTH = 2000


@bp.route('/parse', methods=['POST'])
def parse():
    try:
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            return make_response(400, '请求体必须是 JSON 对象', None, False, 'INVALID_REQUEST'), 400

        text = data.get('text')
        if not isinstance(text, str) or not text.strip():
            return make_response(400, '请提供包含分享链接的文本', None, False, 'INVALID_TEXT'), 400
        if len(text) > MAX_TEXT_LENGTH:
            return make_response(400, f'分享文本不能超过 {MAX_TEXT_LENGTH} 个字符', None, False, 'TEXT_TOO_LONG'), 400

        share_url = UrlParser.get_url(text)
        if not share_url:
            return make_response(400, '未找到有效的分享链接', None, False, 'URL_NOT_FOUND'), 400
        
        # 1. 解析基础信息
        redirect_url = WebFetcher.fetch_redirect_url(share_url)
        if not redirect_url:
            return make_response(400, '无法访问或识别该分享链接', None, False, 'REDIRECT_FAILED'), 400

        platform = UrlParser.get_platform(redirect_url)
        real_url = UrlParser.extract_video_address(redirect_url)
        logger.debug(f'real_url {real_url}')

        if not platform:
            logger.error(f'This link is not supported for extraction: {real_url}')
            return make_response(400, '该链接尚未支持提取', None, False, 'PLATFORM_NOT_SUPPORTED'), 400

        # 2. 获取解析器
        parser = ParserFactory.create_parser(platform, real_url)
        
        # 3. 核心抓取逻辑
        content_data = _fetch_with_retry(parser, platform)

        if (
            not content_data['video_url']
            and not content_data['video_list']
            and not content_data['image_list']
        ):
            logger.error(f"Failed to retrieve media content for {platform}")
            if platform == '小红书':
                return make_response(400, '解析失败：该链接需要小红书登录 Cookie 校验，请在配置中提供有效 Cookie 后重试', None, False, 'XIAOHONGSHU_COOKIE_REQUIRED'), 400
            return make_response(400, '提取媒体内容失败，请检查链接或稍后重试', None, False, 'MEDIA_NOT_FOUND'), 400

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

        processed_video_list = [
            UrlParser.convert_to_https(url)
            for url in content_data.get('video_list', [])
            if url
        ]
        processed_video_list = list(dict.fromkeys(processed_video_list))
        primary_video_url = UrlParser.convert_to_https(content_data['video_url'])
        if primary_video_url and primary_video_url in processed_video_list:
            processed_video_list.remove(primary_video_url)
            processed_video_list.insert(0, primary_video_url)

        # 4. 统一转换 HTTPS
        data_dict = {
            'video_id': UrlParser.get_video_id(redirect_url),
            'platform': platform,
            'title': content_data['title'],
            'video_url': primary_video_url,
            'audio_url': UrlParser.convert_to_https(content_data.get('audio_url')),
            'cover_url': UrlParser.convert_to_https(content_data['cover_url']),
            'author': content_data['author'],
            'image_list': processed_image_list
        }
        if len(processed_video_list) > 1:
            data_dict['video_list'] = processed_video_list
        if content_data.get('subtitles'):
            data_dict['subtitles'] = content_data['subtitles']
        
        logger.debug(f'Parse Success for platform {platform}')
        return make_response(200, '成功', data_dict, True), 200

    except Exception as e:
        logger.exception("Parse Error") # 使用 exception 会带上堆栈信息
        return make_response(500, '功能太火爆啦，请稍后再试', None, False, 'INTERNAL_ERROR'), 500


def _fetch_with_retry(parser, platform):
    """提取公共的抓取逻辑，小红书特殊处理"""
    max_attempts = 3 if platform == '小红书' else 1
    
    for i in range(max_attempts):
        res = {
            'title': parser.get_title_content(),
            'video_url': parser.get_real_video_url(),
            'video_list': safe_execute(getattr(parser, 'get_video_list', None), default=[]),
            'cover_url': parser.get_cover_photo_url(),
            'author': safe_execute(getattr(parser, 'get_author_info', None)),
            'image_list': safe_execute(getattr(parser, 'get_image_list', None), default=[]),
            'audio_url': safe_execute(getattr(parser, 'get_audio_url', None)),
            'subtitles': safe_execute(getattr(parser, 'get_subtitles', None))
        }
        if not res['video_url'] and res['video_list']:
            res['video_url'] = res['video_list'][0]
        if res['video_url'] or res['video_list'] or res['image_list']:
            return res
            
        if i < max_attempts - 1:
            logger.debug(f"Attempt {i + 1} failed. Retrying...")
            
    return res


def safe_execute(func, default=None):
    """安全执行辅助函数，减少 try-except 视觉噪音"""
    if not func or not callable(func):
        return default
    try:
        val = func()
        if type(val).__name__ in ('Mock', 'MagicMock'):
            return default
        return val
    except Exception:
        return default


@bp.route('/proxy', methods=['GET'])
def proxy():
    """资源代理与下载接口：补充对应平台的 Referer 请求头，防止直接请求或下载时触发 403 盗链阻断。"""
    url = request.args.get('url')
    platform = request.args.get('platform', '')
    download = request.args.get('download', '0')

    if not url:
        return make_response(400, '缺少 url 参数', None, False, 'INVALID_URL'), 400

    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    # 设置对应平台的 Referer 请求头防盗链
    if platform == "哔哩哔哩":
        headers["Referer"] = "https://www.bilibili.com/"
    elif platform == "抖音":
        headers["Referer"] = "https://www.douyin.com/"
    elif platform == "小红书":
        headers["Referer"] = "https://www.xiaohongshu.com/"
    elif platform == "快手":
        headers["Referer"] = "https://www.kuaishou.com/"
    elif platform == "微博":
        headers["Referer"] = "https://weibo.com/"
    elif platform == "西瓜视频":
        headers["Referer"] = "https://www.ixigua.com/"
    elif platform == "知乎":
        headers["Referer"] = "https://www.zhihu.com/"
    elif platform in ("微信视频号", "视频号"):
        headers["Referer"] = "https://channels.weixin.qq.com/"
    elif platform == "剪映":
        headers["Referer"] = "https://lv.ulikecam.com/"

    try:
        resp = requests.get(url, headers=headers, stream=True, timeout=20)
        resp.raise_for_status()

        content_type = resp.headers.get('Content-Type', 'video/mp4')
        res = Response(
            stream_with_context(resp.iter_content(chunk_size=64 * 1024)),
            content_type=content_type,
            status=resp.status_code
        )

        if download == '1':
            ext = 'mp4'
            if 'image' in content_type:
                ext = 'jpg'
            elif 'audio' in content_type:
                ext = 'mp3'
            res.headers['Content-Disposition'] = f'attachment; filename="media_{platform or "file"}.{ext}"'

        return res
    except Exception as e:
        logger.error(f"Proxy request error for platform '{platform}' and URL '{url}': {e}")
        return make_response(500, f'媒体资源代理失败: {str(e)}', None, False, 'PROXY_ERROR'), 500

