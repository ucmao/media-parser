import re
import json
import random
import requests
from bs4 import BeautifulSoup
from utils.web_fetcher import UrlParser
from src.downloaders.base_downloader import BaseDownloader
from configs.general_constants import USER_AGENT_PC
from configs.logging_config import logger


class LishipinDownloader(BaseDownloader):
    def __init__(self, real_url):
        super().__init__(real_url)
        self.headers = {
            "content-type": "application/json; charset=UTF-8",
            'User-Agent': random.choice(USER_AGENT_PC),
            'referer': self.real_url
        }
        self.video_id = UrlParser.get_video_id(self.real_url)
        self.data = self.fetch_html_data()
        self.html_content = self.fetch_html_content()

    def fetch_html_data(self):
        jsp_url = "https://www.pearvideo.com/videoStatus.jsp"
        params = {
            "contId": f"{''.join(filter(str.isdigit, self.video_id))}",
            "mrd": random.random()
        }
        response = requests.get(jsp_url, params=params, headers=self.headers)
        if response.status_code == 200:
            return response.json()
        else:
            logger.warning(f"请求失败，状态码: {response.status_code}")
            return None

    def get_real_video_url(self):
        try:
            data_dict = self.data
            video_url = data_dict['videoInfo']['videos']['srcUrl']
            new_value = f"cont-{self.video_id}"
            pattern = r'(\d+)-(\d+-hd\.mp4)'
            video_addr = re.sub(pattern, new_value + r'-\2', video_url)
            return video_addr
        except (KeyError, json.JSONDecodeError) as e:
            logger.warning(f"Failed to parse video URL: {e}")

    def get_title_content(self):
        try:
            soup = BeautifulSoup(self.html_content, 'html.parser')
            summary_div = soup.find('div', class_='summary')
            if summary_div:
                summary_text = summary_div.get_text(strip=True)
            else:
                logger.warning("未找到匹配的div标签")
                summary_text = None
            return summary_text
        except (KeyError, json.JSONDecodeError) as e:
            logger.warning(f"Failed to parse title content: {e}")

    def get_cover_photo_url(self):
        try:
            data_dict = self.data
            cover_url = data_dict['videoInfo']['video_image']
            return cover_url
        except (KeyError, json.JSONDecodeError) as e:
            logger.warning(f"Failed to parse cover URL: {e}")


if __name__ == '__main__':
    real_url = 'https://www.pearvideo.com/video_1795870'
    dl = LishipinDownloader(real_url)
    print(dl.get_title_content())
    print(dl.get_cover_photo_url())
    print(dl.get_real_video_url())
