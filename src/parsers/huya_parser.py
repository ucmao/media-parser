
import random

from configs.general_constants import USER_AGENT_PC
from src.parsers.base_parser import BaseParser
from utils.web_fetcher import UrlParser


class HuyaParser(BaseParser):
    def __init__(self, real_url):
        super().__init__(real_url)
        self.headers = {
            "User-Agent": random.choice(USER_AGENT_PC),
            "Referer": "https://www.huya.com/",
        }
        self.data = self.fetch_html_data()

    def fetch_html_data(self):
        video_id = UrlParser.get_video_id(self.real_url)
        if not video_id or not str(video_id).isdigit():
            return {}
        req_url = f"https://liveapi.huya.com/moment/getMomentContent?videoId={video_id}"
        try:
            resp = self.session.get(req_url, headers=self.headers, timeout=10)
            resp.raise_for_status()
            return resp.json()
        except Exception:
            return {}
    def get_real_video_url(self):
        try: return self.data["data"]["moment"]["videoInfo"]["definitions"][0]["url"]
        except: return None
    def get_cover_photo_url(self):
        try: return self.data["data"]["moment"]["videoInfo"]["videoCover"]
        except: return None
    def get_title_content(self):
        try: return self.data["data"]["moment"]["videoInfo"]["videoTitle"]
        except: return None
