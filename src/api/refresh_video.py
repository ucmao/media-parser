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
        try:
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
        except Exception as downloader_error:
            logger.error(f"Downloader Error: {downloader_error}")
            video_url = None # 确保 video_url 为 None 以进入失败逻辑

        updated_video_url = UrlParser.convert_to_https(video_url)
        updated_cover_url = UrlParser.convert_to_https(cover_url)

        # 获取现有视频 URL 以判断是否真正刷新了内容
        old_video_url = None
        try:
            db_manager_instance = DataStorageManager(request_video_id)
            existing_data = db_manager_instance.get_db_data()
            if existing_data:
                old_video_url = existing_data.get('video_url')
        except Exception as e:
            logger.error(f"Failed to get existing video data: {e}")

        # 只有当获取到新 URL 且与旧 URL 不同时，才视为刷新成功
        if updated_video_url and updated_video_url != old_video_url:
            # 成功获取视频且是新链接，重置失败次数
            try:
                DataStorageManager.reset_refresh_fail_count(request_video_id)
            except Exception as db_err:
                logger.error(f"Database Reset Fail Error: {db_err}")
        else:
            # 获取失败，或者获取到的 URL 和之前一样（说明没有刷新成功），增加失败次数
            try:
                fail_count = DataStorageManager.increment_refresh_fail_count(request_video_id)
                logger.warning(f"Video {request_video_id} refresh failed (is_same: {updated_video_url == old_video_url}), count: {fail_count}")
                if fail_count >= 3:
                    DataStorageManager.delete_video(request_video_id)
                    logger.info(f"Video {request_video_id} deleted due to {fail_count} refresh failures")
                    return make_response(200, '视频已失效并移除', None, None, False), 200
            except Exception as db_err:
                logger.error(f"Database Fail Count Error: {db_err}")
            
            return make_response(200, '视频获取中，请稍后再试', None, None, False), 200

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
