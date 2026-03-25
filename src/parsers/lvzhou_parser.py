
from src.parsers.base_parser import BaseParser
import re
from bs4 import BeautifulSoup

class LvzhouParser(BaseParser):
    def fetch_html_data(self):
        resp = self.session.get(self.real_url, headers=self.headers)
        return resp.text
    def get_real_video_url(self):
        soup = BeautifulSoup(self.data, "html.parser")
        video = soup.select_one("video")
        return video["src"] if video else None
    def get_cover_photo_url(self):
        match = re.search(r"background-image:url\((.*?)\)", self.data)
        return match.group(1) if match else None
    def get_title_content(self):
        soup = BeautifulSoup(self.data, "html.parser")
        title = soup.select_one("div.status-title")
        return title.text if title else None
