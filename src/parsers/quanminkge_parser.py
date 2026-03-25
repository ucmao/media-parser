
import json
import re
from src.parsers.base_parser import BaseParser
from utils.web_fetcher import UrlParser

class QuanminkgeParser(BaseParser):
    def fetch_html_data(self):
        video_id = UrlParser.get_video_id(self.real_url)
        req_url = f"https://kg.qq.com/node/play?s={video_id}"
        resp = self.session.get(req_url, headers=self.headers)
        pattern = re.compile(r"window\.__DATA__\s*=\s*(.*?); </script>")
        match = pattern.search(resp.text)
        if match: return json.loads(match.group(1))
        return {}
    def get_real_video_url(self):
        try: return self.data["detail"]["playurl_video"]
        except: return None
    def get_cover_photo_url(self):
        try: return self.data["detail"]["cover"]
        except: return None
    def get_title_content(self):
        try: return self.data["detail"]["content"]
        except: return None
