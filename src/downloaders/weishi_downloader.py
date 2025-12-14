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


if __name__ == '__main__':
    real_url = 'https://isee.weishi.qq.com/ws/app-pages/share/index.html?wxplay=1&id=7QRTVTOFI1SyqHPE6&spid=6120560151859271791&qua=v1_iph_weishi_8.125.1_300_app_a&chid=100081014&pkg=3670&attach=cp_reserves3_1000370011'
    dl = WeishiDownloader(real_url)
    print(dl.get_title_content())
    print(dl.get_cover_photo_url())
    print(dl.get_real_video_url())
