import re
import json
import random
import time
from utils.web_fetcher import UrlParser
from src.downloaders.base_downloader import BaseDownloader
from configs.general_constants import USER_AGENT_PC
from configs.logging_config import logger


class KuaishouDownloader(BaseDownloader):
    def __init__(self, real_url):
        super().__init__(real_url)
        timestamp = int(time.time() * 1000)
        self.headers = {
            "content-type": "application/json; charset=UTF-8",
            'User-Agent': random.choice(USER_AGENT_PC),
            'referer': 'https://www.kuaishou.com/',
            # 'cookie': f'didv={timestamp}; kpf=PC_WEB; clientid=3; did=web_23e5afb8fd199a724fa05c31d1826358; kpn=KUAISHOU_VISION',
            'cookie': 'kpf=PC_WEB; clientid=3; did=web_66ce2b981cc6326ce81c6593ec91501c; userId=3978546192; kuaishou.server.webday7_st=ChprdWFpc2hvdS5zZXJ2ZXIud2ViZGF5Ny5zdBKwATXJWZrns_X3k5b6EXLF6ooCljC0gVVIPCzBhwCxWnpSihvqoREftPzm-sr8F2VyYbgWgLQ4DDNqhPAHDJ9XP5L9mqQvDejh8LnSf5_hTUDBhfmZQL9UsmohvK5xnc2CeQ_x2mXeJEm9Fg6xWe3qzvmzFgaxNDler6igGyd5uipoa-eTAr3vogs4UNuWjfwTcjYrlLjhd69ao0_PsRssIpN1JDqdmn5RW_NcaCp6ZOyPGhKFbZIQPBqwmm2qxNndD6tYkp4iIH54RTp6GjDbOO9cGXuiLNw2QAOgYTzEFhzlU9yMy_1zKAUwAQ; kuaishou.server.webday7_ph=b0edd97f04f01bde6a8f5e1a27d025a937ce; kpn=KUAISHOU_VISION',
        }
        self.data = self.fetch_html_data()
        self.video_id = UrlParser.get_video_id(self.real_url)

    def fetch_html_data(self):
        self.html_content = self.fetch_html_content()
        pattern = re.compile(r'window\.__APOLLO_STATE__\s*=\s*(\{.*\};)', re.DOTALL)
        json_data = BaseDownloader.parse_html_data(self.html_content, pattern)
        return json_data

    def get_real_video_url(self):
        try:
            data_dict = json.loads(self.data)
            video_url = data_dict['defaultClient']['VisionVideoSetRepresentation:1']['url']
            video_addr = video_url.replace("\u002F", "/")
            return video_addr
        except (KeyError, json.JSONDecodeError) as e:
            logger.warning(f"Failed to parse video URL: {e}")

    def get_title_content(self):
        try:
            data_dict = json.loads(self.data)
            title_content = data_dict['defaultClient'][f'VisionVideoDetailPhoto:{self.video_id}']['caption']
            return title_content
        except (KeyError, json.JSONDecodeError) as e:
            logger.warning(f"Failed to parse title content: {e}")

    def get_cover_photo_url(self):
        try:
            data_dict = json.loads(self.data)
            cover_url = data_dict['defaultClient'][f'VisionVideoDetailPhoto:{self.video_id}']['coverUrl']
            return cover_url
        except (KeyError, json.JSONDecodeError) as e:
            logger.warning(f"Failed to parse cover URL: {e}")


if __name__ == '__main__':
    real_url = 'https://www.kuaishou.com/short-video/3xwyjn4ipdhss5c?authorId=3xasa85baf6ipp4&streamSource=find&area=homexxbrilliant'
    ks_dl = KuaishouDownloader(real_url)
    print(ks_dl.get_title_content())
    print(ks_dl.get_cover_photo_url())
    print(ks_dl.get_real_video_url())
