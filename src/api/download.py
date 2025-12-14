import os
import requests
from flask import Blueprint, request
from configs.logging_config import logger
from utils.common_utils import make_response, validate_request
from utils.web_fetcher import UrlParser
from configs.general_constants import MINI_PROGRAM_LEGAL_DOMAIN, SAVE_VIDEO_PATH, DOMAIN

bp = Blueprint('download', __name__)


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

        # 判断视频链接的域名是否为小程序的合法域名
        if UrlParser.get_domain(request_video_url) in MINI_PROGRAM_LEGAL_DOMAIN:
            # 如果是，直接返回视频链接
            logger.debug(f'{wx_open_id} 直接返回视频链接')
            return make_response(200, '成功', {'download_url': request_video_url}, None, True), 200
        else:
            # 如果不是，服务器端下载视频并保存
            # 生成保存视频的文件名
            video_filename = f'{request_video_id}.mp4'
            video_path = os.path.join(SAVE_VIDEO_PATH, video_filename)
            if not os.path.exists(video_path):
                response = requests.get(request_video_url, stream=True)
                if response.status_code == 200:
                    # 保存视频到服务器
                    with open(video_path, 'wb') as f:
                        for chunk in response.iter_content(chunk_size=1024):
                            f.write(chunk)
                    # 返回视频的 URL
                    download_url = f'{DOMAIN}/static/videos/{video_filename}'
                    logger.debug(f'{wx_open_id} 返回视频地址: {download_url}')
                    return make_response(200, '成功', {'download_url': download_url}, None, True), 200
                else:
                    logger.error(f'{wx_open_id} Failed to download video')
                    return make_response(500, 'Failed to download video', None, None, False), 500
            else:
                # 返回视频的 URL
                download_url = f'{DOMAIN}/static/videos/{video_filename}'
                logger.debug(f'{wx_open_id} 返回视频地址: {download_url}')
                return make_response(200, '成功', {'download_url': download_url}, None, True), 200

    except Exception as e:
        logger.error(e)
        return make_response(500, '功能太火爆啦，请稍后再试', None, None, False), 500
