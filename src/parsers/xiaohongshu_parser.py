from src.parser_factory import register_parser
import re
import json
from src.parsers.base_parser import BaseParser
from configs.logging_config import get_logger
import requests
logger = get_logger(__name__)


@register_parser("小红书")
class XiaohongshuParser(BaseParser):
    def __init__(self, real_url):
        super().__init__(real_url)
        self.headers = {
            "content-type": "application/json; charset=UTF-8",
            'User-Agent': "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
            'referer': 'https://www.xiaohongshu.com/'
        }

        # 获取 HTML 并解析 JSON 状态
        html_content = self.fetch_html_content()
        pattern = re.compile(r'window\.__INITIAL_STATE__\s*=\s*(\{.*\})', re.DOTALL)
        json_str = BaseParser.parse_html_data(html_content, pattern)

        # 初始化数据容器
        self.note_data = {}
        try:
            if json_str:
                full_data = json.loads(json_str)
                first_note_id = full_data.get('note', {}).get('firstNoteId')
                if first_note_id:
                    self.note_data = full_data['note']['noteDetailMap'].get(first_note_id, {}).get('note', {})
        except (json.JSONDecodeError, KeyError) as e:
            logger.error(f"初始化解析数据失败: {e}")

    def fetch_html_content(self):
        try:
            resp = self.session.get(self.real_url, headers=self.headers, timeout=5)
            resp.raise_for_status()
            if "xiaohongshu.com/login" in resp.url:
                logger.error("小红书解析提示: 请求被重定向到了登录页面。")
            elif "xiaohongshu.com/404" in resp.url:
                logger.error("小红书解析提示: 遭遇安全拦截或页面未找到（404）。")
            self.html_content = resp.text
            return self.html_content
        except requests.RequestException as e:
            logger.error(f"Failed to get the page: {self.real_url}, Error: {e}")
            return None
        except Exception as e:
            logger.error(f"An unexpected error occurred while fetching {self.real_url}: {e}")
            return None


    def get_author_info(self):
        """
        获取作者信息，返回固定格式字典
        """
        user = self.note_data.get('user', {})
        return {
            'nickname': user.get('nickname', ''),
            'author_id': user.get('userId', ''),
            'avatar': user.get('avatar', '')
        }

    def get_real_video_url(self):
        try:
            video_info = self.note_data.get('video', {})
            master_url = video_info['media']['stream']['h264'][0].get('masterUrl', '')
            return master_url.replace("\\u002F", "/") if master_url else None
        except (KeyError, IndexError):
            return None

    def get_title_content(self):
        title = self.note_data.get('title', '')
        desc = self.note_data.get('desc', '')
        return f"{title}\n{desc}".strip()

    def get_cover_photo_url(self):
        try:
            image_list = self.note_data.get('imageList', [])
            if image_list:
                cover_url = image_list[0].get('urlDefault', '')
                return cover_url.replace("\\u002F", "/")
            return None
        except (KeyError, IndexError):
            return None

    def get_image_list(self):
        image_url_list = []
        image_list = self.note_data.get('imageList', [])
        for image in image_list:
            url = image.get('urlDefault', '')
            if url:
                img_data = url.replace("\\u002F", "/")
                # 检查是否有livePhoto
                if image.get('livePhoto', False):
                    stream = image.get('stream', {})
                    h264_data = stream.get('h264', [])
                    if h264_data:
                        master_url = h264_data[0].get('masterUrl', '')
                        if master_url:
                            img_data = {
                                'url': img_data,
                                'live_photo_url': master_url.replace("\\u002F", "/")
                            }
                image_url_list.append(img_data)
        return image_url_list
