
from src.parsers.base_parser import BaseParser
from utils.web_fetcher import UrlParser

class SixroomParser(BaseParser):
    def fetch_html_data(self):
        video_id = UrlParser.get_video_id(self.real_url)
        req_url = f"https://v.6.cn/profile/tmv/getVideoInfo.php?vid={video_id}"
        resp = self.session.get(req_url, headers=self.headers)
        return resp.json()
    def get_real_video_url(self):
        try: return self.data["content"]["playurl"]
        except: return None
    def get_cover_photo_url(self):
        try: return self.data["content"]["picurl"]
        except: return None
    def get_title_content(self):
        try: return self.data["content"]["title"]
        except: return None
