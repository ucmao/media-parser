from flask import Blueprint, request
from configs.logging_config import logger
from configs.general_constants import DOMAIN_TO_NAME
from utils.web_fetcher import WebFetcher, UrlParser
from src.downloader_factory import DownloaderFactory
from utils.common_utils import make_response

bp = Blueprint('parse', __name__)


@bp.route('/parse', methods=['POST'])
def parse():
    try:
        data = request.json
        text = data.get('text')
        
        redirect_url = WebFetcher.fetch_redirect_url(UrlParser.get_url(text))
        platform = DOMAIN_TO_NAME.get(UrlParser.get_domain(redirect_url))
        video_id = UrlParser.get_video_id(redirect_url)
        real_url = UrlParser.extract_video_address(redirect_url)
        logger.debug(f'real_url {real_url}')

        if not platform:
            logger.error(f'This link is not supported for extraction: {real_url}')
            return make_response(400, '该链接尚未支持提取', None, None, False), 400

        title = cover_url = video_url = author = image_list = None
        
        if platform == '小红书':
            max_attempts = 5
            attempts = 0
            while attempts < max_attempts:
                downloader = DownloaderFactory.create_downloader(platform, real_url)
                title = downloader.get_title_content()
                video_url = downloader.get_real_video_url()
                cover_url = downloader.get_cover_photo_url()
                try:
                    author = downloader.get_author_info()
                except Exception:
                    author = None
                try:
                    image_list = downloader.get_image_list()
                except Exception:
                    image_list = []
                if video_url or image_list:
                    break
                attempts += 1
                logger.debug(f"Attempt {attempts} failed. Retrying...")
            if not video_url and not image_list:
                logger.error("Failed to retrieve media content after 5 attempts.")
        else:
            downloader = DownloaderFactory.create_downloader(platform, real_url)
            title = downloader.get_title_content()
            video_url = downloader.get_real_video_url()
            cover_url = downloader.get_cover_photo_url()
            try:
                author = downloader.get_author_info()
            except Exception:
                author = None

            try:
                image_list = downloader.get_image_list()
            except Exception:
                image_list = []

        updated_video_url = UrlParser.convert_to_https(video_url)
        updated_cover_url = UrlParser.convert_to_https(cover_url)
        # Convert image list to https
        updated_image_list = [UrlParser.convert_to_https(img) for img in image_list] if image_list else []
        
        data_dict = {'video_id': video_id, 'platform': platform, 'title': title,
                     'video_url': updated_video_url, 'cover_url': updated_cover_url,
                     'author': author, 'image_list': updated_image_list}
        
        logger.debug(f'Parse Success for platform {platform}')
        return make_response(200, '成功', data_dict, None, True), 200

    except Exception as e:
        logger.error(e)
        return make_response(500, '功能太火爆啦，请稍后再试', None, None, False), 500
