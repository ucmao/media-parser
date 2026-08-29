from src.parser_factory import register_parser

import random
import re
from urllib.parse import urljoin

from src.parsers.base_parser import BaseParser
from configs.general_constants import USER_AGENT_PC

@register_parser("皮皮虾")
class PipixiaParser(BaseParser):
    def __init__(self, real_url):
        super().__init__(real_url)
        self.headers = {
            "User-Agent": random.choice(USER_AGENT_PC),
            "Referer": "https://h5.pipix.com/",
        }
        self.page_title = ""
        self.data = self.fetch_html_data()

    def fetch_html_data(self):
        try:
            resp = self.session.get(
                self.real_url, headers=self.headers, allow_redirects=False, timeout=10
            )
        except Exception:
            return {}
        location_url = resp.headers.get("location", "")
        if not location_url: location_url = self.real_url
        location_url = urljoin(self.real_url, location_url)
        video_id = location_url.split("?")[0].split("/")[-1]
        if not video_id.isdigit():
            return {}
        req_url = f"https://api.pipix.com/bds/cell/cell_comment/?offset=0&cell_type=1&api_version=1&cell_id={video_id}&ac=wifi&channel=huawei_1319_64&aid=1319&app_name=super"
        try:
            resp = self.session.get(req_url, headers=self.headers, timeout=10)
            resp.raise_for_status()
            data = resp.json()
        except Exception:
            return {}

        self.page_title = self._fetch_page_title(location_url)
        return data

    def _fetch_page_title(self, url):
        try:
            resp = self.session.get(url, headers=self.headers, timeout=10)
            resp.raise_for_status()
            match = re.search(
                r'<meta\s+property=["\']og:title["\']\s+content=["\'](.*?)["\']',
                resp.text,
                re.IGNORECASE,
            )
            title = match.group(1) if match else ""
            return re.sub(r"\s*-\s*皮皮虾\s*$", "", title).strip()
        except Exception:
            return ""
    def get_real_video_url(self):
        try:
            data = self.data["data"]["cell_comments"][0]["comment_info"]["item"]
            if data.get("video") is not None:
                return data["video"]["video_high"]["url_list"][0]["url"]
            return None
        except: return None
    def get_image_list(self):
        try:
            data = self.data["data"]["cell_comments"][0]["comment_info"]["item"]
            images = []
            if data.get("note") is not None:
                for img in data["note"]["multi_image"]:
                    images.append(img["url_list"][0]["url"])
            return images
        except: return []
    def get_cover_photo_url(self):
        try: return self.data["data"]["cell_comments"][0]["comment_info"]["item"]["cover"]["url_list"][0]["url"]
        except: return None
    def get_title_content(self):
        try:
            content = self.data["data"]["cell_comments"][0]["comment_info"]["item"].get("content", "")
            return content or self.page_title
        except (KeyError, TypeError, IndexError):
            return self.page_title
    def get_author_info(self):
        try:
            author = self.data["data"]["cell_comments"][0]["comment_info"]["item"]["author"]
            avatar_urls = author.get("avatar", {}).get("download_list", [])
            return {
                "nickname": author.get("name", ""),
                "author_id": str(author.get("id", "")),
                "avatar": avatar_urls[0].get("url", "") if avatar_urls else "",
            }
        except (KeyError, TypeError, IndexError):
            return {}
