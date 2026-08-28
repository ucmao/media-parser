import requests
from bs4 import BeautifulSoup
from configs.logging_config import get_logger
logger = get_logger(__name__)


class BaseParser:
    def __init__(self, real_url):
        self.real_url = real_url
        self.headers = None
        self.html_content = None
        self.session = requests.Session()

    def get_real_video_url(self):
        raise NotImplementedError

    def get_title_content(self):
        raise NotImplementedError

    def get_cover_photo_url(self):
        raise NotImplementedError

    def get_author_info(self):
        """获取作者信息 (昵称、头像、ID等)"""
        raise NotImplementedError

    def get_audio_url(self):
        """获取音频解析链接"""
        return None

    def get_subtitles(self):
        """获取平台原生字幕或歌词；不支持时返回 None。"""
        return None

    def get_image_list(self):
        """获取图文列表"""
        return []

    def get_video_list(self):
        """获取同一分享内容中的多个视频。"""
        return []

    def fetch_html_content(self):
        try:
            resp = self.session.get(self.real_url, headers=self.headers, timeout=5)
            resp.raise_for_status()
            self.html_content = resp.text
            return self.html_content
        except requests.RequestException as e:
            logger.error(f"Failed to get the page: {self.real_url}, Error: {e}")
            return None
        except Exception as e:
            logger.error(f"An unexpected error occurred while fetching {self.real_url}: {e}")
            return None

    @staticmethod
    def parse_html_data(html_content, pattern):
        page_obj = BeautifulSoup(html_content, 'lxml')
        script_tags = page_obj.find_all('script')
        for script in script_tags:
            if script.string:
                match = pattern.search(script.string)
                if match:
                    json_data = match.group(1)
                    json_data = json_data.rstrip(';')  # 部分需要去除分号
                    json_data = json_data.replace('undefined', 'null')  # 小红书需要这步骤
                    return json_data
        logger.error("Video object not found")
