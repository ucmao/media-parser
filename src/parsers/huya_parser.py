
from src.parsers.base_parser import BaseParser
from utils.web_fetcher import UrlParser

class HuyaParser(BaseParser):
    def fetch_html_data(self):
        video_id = UrlParser.get_video_id(self.real_url)
        req_url = f"https://liveapi.huya.com/moment/getMomentContent?videoId={video_id}"
        resp = self.session.get(req_url, headers=self.headers)
        return resp.json()
    def get_real_video_url(self):
        try: return self.data["data"]["moment"]["videoInfo"]["definitions"][0]["url"]
        except: return None
    def get_cover_photo_url(self):
        try: return self.data["data"]["moment"]["videoInfo"]["videoCover"]
        except: return None
    def get_title_content(self):
        try: return self.data["data"]["moment"]["videoInfo"]["videoTitle"]
        except: return None
