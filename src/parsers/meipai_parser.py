
import re
import base64
from bs4 import BeautifulSoup
from src.parsers.base_parser import BaseParser

class MeipaiParser(BaseParser):
    def fetch_html_data(self):
        resp = self.session.get(self.real_url, headers=self.headers)
        return resp.text
    def get_real_video_url(self):
        try:
            pattern = re.compile(r'data-video="(.*?)"')
            match = pattern.search(self.data)
            if match:
                video_bs64 = match.group(1)
                # Decode base64 
                video_url = "https:" + base64.b64decode(video_bs64).decode("utf-8")
                return video_url
        except: return None
        return None
    def get_cover_photo_url(self):
        soup = BeautifulSoup(self.data, "html.parser")
        img = soup.select_one("#detailVideo img")
        return img["src"] if img else None
    def get_title_content(self):
        soup = BeautifulSoup(self.data, "html.parser")
        title = soup.select_one(".detail-cover-title")
        return title.text.strip() if title else None
