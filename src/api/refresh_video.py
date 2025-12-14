from flask import Blueprint, request
from configs.logging_config import logger
from utils.web_fetcher import UrlParser
from src.database.data_storage_manager import DataStorageManager
from src.downloader_factory import DownloaderFactory
from utils.common_utils import make_response, validate_request
from configs.general_constants import PLATFORM_MAP

bp = Blueprint('refresh_video', __name__)


@bp.route('/refresh_video', methods=['POST'])
def refresh_video():
    try:
        data = request.json
        request_platform = data.get('platform')
        request_video_id = data.get('video_id')
        wx_open_id = request.headers.get('WX-OPEN-ID', 'Guest')

        reversed_platform_map = {value: key for key, value in PLATFORM_MAP.items()}
        platform = reversed_platform_map.get(request_platform, '')

        if not platform:
            return make_response(400, '失败', None, None, False), 400

        validation_result = validate_request(platform, request_video_id)
        if validation_result:
            # 如果验证不通过，则返回错误代码
            return validation_result

        real_url = UrlParser.generate_video_url(platform, request_video_id)

        # 获取封面 视频 和标题
        title = cover_url = video_url = None
        if platform == '小红书':
            max_attempts = 5
            attempts = 0
            while attempts < max_attempts:
                downloader = DownloaderFactory.create_downloader(platform, real_url)
                title = downloader.get_title_content()
                video_url = downloader.get_real_video_url()
                cover_url = downloader.get_cover_photo_url()
                if video_url:
                    break
                attempts += 1
                logger.debug(f"Attempt {attempts} failed. Retrying...")
            if not video_url:
                logger.error("Failed to retrieve video URL after 5 attempts.")
        else:
            downloader = DownloaderFactory.create_downloader(platform, real_url)
            title = downloader.get_title_content()
            video_url = downloader.get_real_video_url()
            cover_url = downloader.get_cover_photo_url()

        updated_video_url = UrlParser.convert_to_https(video_url)
        updated_cover_url = UrlParser.convert_to_https(cover_url)

        data_dict = {'video_id': request_video_id, 'platform': request_platform, 'title': title, 'video_url': updated_video_url,
                     'cover_url': updated_cover_url}
        trans_data_dict = {'video_id': request_video_id, 'platform': platform, 'title': title, 'video_url': updated_video_url,
                           'cover_url': updated_cover_url}

        # 保存数据库
        user_id = DataStorageManager.get_or_create_user_id(wx_open_id)
        manager = DataStorageManager(request_video_id, real_url, user_id)
        manager.update_parse(trans_data_dict)
        logger.debug(f'{wx_open_id} {platform} Parse Success')
        return make_response(200, '成功', data_dict, None, True), 200

    except Exception as e:
        logger.error(e)
        return make_response(500, '功能太火爆啦，请稍后再试', None, None, False), 500
