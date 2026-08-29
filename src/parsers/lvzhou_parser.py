from src.parser_factory import register_parser

import random
import re

from bs4 import BeautifulSoup


from configs.general_constants import USER_AGENT_M
from src.parsers.base_parser import BaseParser


@register_parser("绿洲")
class LvzhouParser(BaseParser):
    def __init__(self, real_url):
        super().__init__(real_url)
        self.headers = {
            "User-Agent": random.choice(USER_AGENT_M),
            "Referer": "https://oasis.weibo.cn/",
        }
        self.data = self.fetch_html_data()

    def fetch_html_data(self):
        try:
            resp = self.session.get(self.real_url, headers=self.headers, timeout=10)
            resp.raise_for_status()
            return resp.text
        except Exception:
            return ""

    def get_real_video_url(self):
        soup = BeautifulSoup(self.data, "html.parser")
        video = soup.select_one("video")
        return video.get("src") if video else None

    def get_image_list(self):
        soup = BeautifulSoup(self.data, "html.parser")
        return [image.get("src") for image in soup.select(".media img") if image.get("src")]

    def get_cover_photo_url(self):
        match = re.search(r"background-image:url\((.*?)\)", self.data)
        if match:
            return match.group(1)
        images = self.get_image_list()
        return images[0] if images else None

    def get_title_content(self):
        soup = BeautifulSoup(self.data, "html.parser")
        title = soup.select_one(".status-text, .status-title")
        return title.get_text(strip=True) if title else None

    def get_author_info(self):
        soup = BeautifulSoup(self.data, "html.parser")
        nickname = soup.select_one(".user .nickname")
        avatar = soup.select_one(".user .avatar img")
        if not nickname:
            return {}
        return {
            "nickname": nickname.get_text(strip=True),
            "author_id": "",
            "avatar": avatar.get("src", "") if avatar else "",
        }
