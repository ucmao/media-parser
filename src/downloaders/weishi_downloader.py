import re
import json
import random
from src.downloaders.base_downloader import BaseDownloader
from configs.general_constants import USER_AGENT_PC
from configs.logging_config import logger


class WeishiDownloader(BaseDownloader):
    def __init__(self, real_url):
        super().__init__(real_url)
        self.headers = {
            "content-type": "application/json; charset=UTF-8",
            'User-Agent': random.choice(USER_AGENT_PC),
            'referer': 'https://isee.weishi.qq.com'
        }
        self.data = self.fetch_html_data()

    def fetch_html_data(self):
        self.html_content = self.fetch_html_content()
        pattern = re.compile(r'window\.Vise\.initState\s*=\s*(\{.*\};)', re.DOTALL)
        json_data = BaseDownloader.parse_html_data(self.html_content, pattern)
        return json_data

    def get_real_video_url(self):
        try:
            data_dict = json.loads(self.data)
            video_url = data_dict['feedsList'][0]['videoUrl']
            video_addr = video_url.replace("\u002F", "/")
            return video_addr
        except (KeyError, json.JSONDecodeError) as e:
            logger.warning(f"Failed to parse video URL: {e}")

    def get_title_content(self):
        try:
            data_dict = json.loads(self.data)
            title_content = data_dict['feedsList'][0]['feedDesc']
            return title_content
        except (KeyError, json.JSONDecodeError) as e:
            logger.warning(f"Failed to parse title content: {e}")

    def get_cover_photo_url(self):
        try:
            data_dict = json.loads(self.data)
            cover_url = data_dict['feedsList'][0]['videoCover']
            cover_url = cover_url.replace("\u002F", "/")
            return cover_url
        except (KeyError, json.JSONDecodeError) as e:
            logger.warning(f"Failed to parse cover URL: {e}")

    def get_author_info(self):
        try:
            data_dict = json.loads(self.data)
            poster = data_dict['feedsList'][0].get('poster', {})

            author_info = {
                "nickname": poster.get('nick', '未知用户'),
                "avatar_url": poster.get('avatar', '').replace("\u002F", "/"),
                "author_id": poster.get('id', '')
            }
            return author_info
        except (KeyError, json.JSONDecodeError, IndexError) as e:
            logger.warning(f"Failed to parse author info: {e}")
            return None


if __name__ == '__main__':
    real_url = 'https://video.weishi.qq.com/5D41bben'

    dl = WeishiDownloader(real_url)

    print("-" * 30)
    print(f"作者信息：{dl.get_author_info()}")
    print(f"标题内容：{dl.get_title_content()[:30]}...")  # 仅打印前30字
    print(f"封面图片：{dl.get_cover_photo_url()}")
    print(f"视频链接：{dl.get_real_video_url()}")
    print("-" * 30)
