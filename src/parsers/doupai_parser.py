
from src.parsers.base_parser import BaseParser
from utils.web_fetcher import UrlParser

class DoupaiParser(BaseParser):
    def fetch_html_data(self):
        video_id = UrlParser.get_video_id(self.real_url)
        req_url = f"https://v2.doupai.cc/topic/{video_id}.json"
        resp = self.session.get(req_url, headers=self.headers)
        return resp.json()
    def get_real_video_url(self):
        try: return self.data["data"]["videoUrl"]
        except: return None
    def get_cover_photo_url(self):
        try: return self.data["data"]["imageUrl"]
        except: return None
    def get_title_content(self):
        try: return self.data["data"]["name"]
        except: return None
