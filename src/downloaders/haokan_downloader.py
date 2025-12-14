import re
import json
import random
from urllib.parse import unquote
from src.downloaders.base_downloader import BaseDownloader
from configs.general_constants import USER_AGENT_M
from configs.logging_config import logger


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
            video_url = data_dict['curVideoMeta']['clarityUrl'][-1]['url']
            play_addr = unquote(video_url)
            video_addr = play_addr.replace("\/", "/")
            return video_addr
        except (KeyError, json.JSONDecodeError) as e:
            logger.warning(f"Failed to parse video URL: {e}")

    def get_title_content(self):
        try:
            data_dict = json.loads(self.data)
            title_content = data_dict['curVideoMeta']['title']
            return title_content
        except (KeyError, json.JSONDecodeError) as e:
            logger.warning(f"Failed to parse title content: {e}")

    def get_cover_photo_url(self):
        try:
            data_dict = json.loads(self.data)
            cover_url = data_dict['curVideoMeta']['poster']
            cover_url = cover_url.replace("\/", "/")
            return cover_url
        except (KeyError, json.JSONDecodeError) as e:
            logger.warning(f"Failed to parse cover URL: {e}")


if __name__ == '__main__':
    real_url = 'https://haokan.baidu.com/v?vid=17831460188721240800&pd=pcshare&hkRelaunch=p1%3Dpc%26p2%3Dvideoland%26p3%3Dshare_input'
    dl = HaokanDownloader(real_url)
    print(dl.get_title_content())
    print(dl.get_cover_photo_url())
    print(dl.get_real_video_url())
