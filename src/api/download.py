import os
import requests
from flask import Blueprint, request
from configs.logging_config import logger
from utils.common_utils import make_response, validate_request
from utils.web_fetcher import UrlParser
from configs.general_constants import (
    MINI_PROGRAM_LEGAL_DOMAIN,
    SAVE_VIDEO_PATH,
    DOMAIN,
    MAX_CACHE_SIZE_BYTES,
)

bp = Blueprint('download', __name__)


def _server_cache_download(request_video_url: str, request_video_id: str, wx_open_id: str):
    """
    通用的服务端下载 + 缓存逻辑：
    - 如果本地已有 {video_id}.mp4，则直接返回本地 URL
    - 否则从源站拉取并保存到 SAVE_VIDEO_PATH 后返回本地 URL
    """
    video_filename = f'{request_video_id}.mp4'
    video_path = os.path.join(SAVE_VIDEO_PATH, video_filename)

    if not os.path.exists(video_path):
        response = requests.get(request_video_url, stream=True)
        if response.status_code == 200:
            with open(video_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=1024):
                    if chunk:
                        f.write(chunk)
            download_url = f'{DOMAIN}/static/videos/{video_filename}'
            logger.debug(f'{wx_open_id} 返回视频地址(新缓存): {download_url}')
            return make_response(200, '成功', {'download_url': download_url}, None, True), 200
        else:
            logger.error(f'{wx_open_id} Failed to download video: status={response.status_code}')
            return make_response(500, 'Failed to download video', None, None, False), 500
    else:
        download_url = f'{DOMAIN}/static/videos/{video_filename}'
        logger.debug(f'{wx_open_id} 返回视频地址(命中缓存): {download_url}')
        return make_response(200, '成功', {'download_url': download_url}, None, True), 200


@bp.route('/download', methods=['POST'])
def download():
    try:
        data = request.json
        request_video_url = data.get('video_url')
        request_video_id = data.get('video_id')
        wx_open_id = request.headers.get('WX-OPEN-ID', 'Guest')

        validation_result = validate_request(request_video_url)
        if validation_result:
            # 如果验证不通过，则返回错误代码
            return validation_result

        domain = UrlParser.get_domain(request_video_url)

        # 判断视频链接的域名是否为小程序的合法域名
        if domain in MINI_PROGRAM_LEGAL_DOMAIN:
            # 合法域名：先尝试通过 HEAD 获取 Content-Length，按大小决定是否缓存
            size = None
            try:
                head_resp = requests.head(request_video_url, allow_redirects=True, timeout=5)
                cl = head_resp.headers.get('Content-Length')
                if cl and cl.isdigit():
                    size = int(cl)
            except Exception as e:
                logger.warning(f'{wx_open_id} 获取 Content-Length 失败: {e}')

            # 如果能拿到大小且不超过阈值，则走服务端缓存；否则直接返回源 URL
            if size is not None and size <= MAX_CACHE_SIZE_BYTES:
                logger.debug(
                    f'{wx_open_id} 合法域名小文件走服务端缓存, size={size}B, threshold={MAX_CACHE_SIZE_BYTES}B'
                )
                return _server_cache_download(request_video_url, request_video_id, wx_open_id)
            else:
                logger.debug(
                    f'{wx_open_id} 合法域名大文件或未知大小，直接返回视频链接, size={size}, threshold={MAX_CACHE_SIZE_BYTES}B'
                )
                return make_response(200, '成功', {'download_url': request_video_url}, None, True), 200
        else:
            # 非合法域名：前端不能直连，必须走服务端缓存
            logger.debug(f'{wx_open_id} 非合法域名，走服务端缓存逻辑, domain={domain}')
            return _server_cache_download(request_video_url, request_video_id, wx_open_id)

    except Exception as e:
        logger.error(e)
        return make_response(500, '功能太火爆啦，请稍后再试', None, None, False), 500
