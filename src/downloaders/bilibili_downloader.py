import re
import json
import random
from src.downloaders.base_downloader import BaseDownloader
from configs.general_constants import USER_AGENT_PC
from configs.logging_config import logger


class BilibiliDownloader(BaseDownloader):
    def __init__(self, real_url):
        super().__init__(real_url)
        self.headers = {
            "content-type": "application/json; charset=UTF-8",
            'User-Agent': random.choice(USER_AGENT_PC),
            'referer': self.real_url
        }
        self.data, self.data2 = self.fetch_html_data()

    def fetch_html_data(self):
        self.html_content = self.fetch_html_content()
        pattern_playinfo = re.compile(r'window\.__playinfo__\s*=\s*(\{.*\})', re.DOTALL)
        json_data = BaseDownloader.parse_html_data(self.html_content, pattern_playinfo)
        pattern_initial = re.compile(r'window\.__INITIAL_STATE__\s*=\s*(\{.*\});', re.DOTALL)
        json_data2 = BaseDownloader.parse_html_data(self.html_content, pattern_initial)
        return json_data, json_data2

    def get_real_video_url(self):
        try:
            data_dict = json.loads(self.data)
            video_url = data_dict['data']['dash']['video'][0]['baseUrl']
            return video_url
        except (KeyError, json.JSONDecodeError) as e:
            logger.warning(f"Failed to parse video URL: {e}")

    def get_title_content(self):
        try:
            data_dict = json.loads(self.data2)
            title_content = data_dict['videoData']['title']
            return title_content
        except (KeyError, json.JSONDecodeError) as e:
            logger.warning(f"Failed to parse title content:: {e}")

    def get_cover_photo_url(self):
        try:
            data_dict = json.loads(self.data2)
            cover_url = data_dict['videoData']['pic']
            return cover_url
        except (KeyError, json.JSONDecodeError) as e:
            logger.warning(f"Failed to parse cover URL: {e}")


if __name__ == '__main__':
    real_url = 'https://www.bilibili.com/video/BV1df421v7xm/?share_source=copy_web&vd_source=5ac2e55972f5e2fd96b63d01ee42ff01'
    bilibili_dl = BilibiliDownloader(real_url)
    print(bilibili_dl.get_title_content())
    print(bilibili_dl.get_cover_photo_url())
    print(bilibili_dl.get_real_video_url())
