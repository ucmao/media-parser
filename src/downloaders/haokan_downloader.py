import re
import json
import random
from urllib.parse import unquote
from src.downloaders.base_downloader import BaseDownloader
from configs.general_constants import USER_AGENT_M
from configs.logging_config import get_logger
logger = get_logger(__name__)


class HaokanDownloader(BaseDownloader):
    def __init__(self, real_url):
        super().__init__(real_url)
        self.headers = {
            "content-type": "application/json; charset=UTF-8",
            'User-Agent': random.choice(USER_AGENT_M),
            'referer': 'https://haokan.baidu.com/v'
        }
        self.data = self.fetch_html_data()

    def fetch_html_data(self):
        self.html_content = self.fetch_html_content()
        pattern = re.compile(r'window\.__PRELOADED_STATE__\s*=\s*(\{.*\};)', re.DOTALL)
        json_data = BaseDownloader.parse_html_data(self.html_content, pattern)
        return json_data

    def get_real_video_url(self):
        try:
            data_dict = json.loads(self.data)
            clarity_url = data_dict.get('curVideoMeta', {}).get('clarityUrl', [])
            if clarity_url:
                video_url = clarity_url[-1].get('url', '')
                return unquote(video_url).replace("\/", "/")
            return None
        except (KeyError, json.JSONDecodeError, TypeError) as e:
            logger.warning(f"Failed to parse Haokan video URL: {e}")
            return None

    def get_title_content(self):
        try:
            data_dict = json.loads(self.data)
            return data_dict.get('curVideoMeta', {}).get('title', '')
        except (KeyError, json.JSONDecodeError, TypeError) as e:
            logger.warning(f"Failed to parse Haokan title: {e}")
            return ""

    def get_cover_photo_url(self):
        try:
            data_dict = json.loads(self.data)
            cover_url = data_dict.get('curVideoMeta', {}).get('poster', '')
            return cover_url.replace("\/", "/") if cover_url else ""
        except (KeyError, json.JSONDecodeError, TypeError) as e:
            logger.warning(f"Failed to parse Haokan cover URL: {e}")
            return ""

    def get_author_info(self):
        try:
            data_dict = json.loads(self.data)
            # 定位到作者信息节点
            author_node = data_dict.get('curVideoMeta', {}).get('mth', {})

            # 提取并格式化为统一的字典结构
            author_info = {
                'nickname': author_node.get('author_name', ''),
                # 好看视频的作者唯一ID是 mthid
                'author_id': str(author_node.get('mthid', '')),
                # URL中可能会有转义字符，做一个安全替换
                'avatar_url': author_node.get('author_photo', '').replace('\\/', '/')
            }
            return author_info
        except (KeyError, json.JSONDecodeError, AttributeError) as e:
            logger.warning(f"Failed to parse author info: {e}")
            return {}


if __name__ == '__main__':
    real_url = 'https://haokan.baidu.com/v?vid=17831460188721240800&pd=pcshare&hkRelaunch=p1%3Dpc%26p2%3Dvideoland%26p3%3Dshare_input'

    dl = HaokanDownloader(real_url)

    print("-" * 30)
    print(f"作者信息：{dl.get_author_info()}")
    print(f"标题内容：{dl.get_title_content()[:30]}...")  # 仅打印前30字
    print(f"封面图片：{dl.get_cover_photo_url()}")
    print(f"视频链接：{dl.get_real_video_url()}")
    print("-" * 30)
