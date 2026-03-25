
import json
import re
from src.parsers.base_parser import BaseParser

class XinpianchangParser(BaseParser):
    def fetch_html_data(self):
        resp = self.session.get(self.real_url, headers=self.headers)
        pattern = re.compile(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>')
        match = pattern.search(resp.text)
        if match: return json.loads(match.group(1))
        return {}
    def get_real_video_url(self):
        try:
            return self.data["props"]["pageProps"]["detail"]["media_info"]["source"]["progressive"][0]["url"]
        except: return None
    def get_cover_photo_url(self):
        try: return self.data["props"]["pageProps"]["detail"]["cover"]
        except: return None
    def get_title_content(self):
        try: return self.data["props"]["pageProps"]["detail"]["title"]
        except: return None
