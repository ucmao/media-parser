
import random
from urllib.parse import parse_qs, urlparse

from src.parsers.base_parser import BaseParser
from configs.general_constants import USER_AGENT_PC

class ZuiyouParser(BaseParser):
    def __init__(self, real_url):
        super().__init__(real_url)
        self.headers = {
            "Content-Type": "application/json",
            "User-Agent": random.choice(USER_AGENT_PC),
            "Referer": "https://share.xiaochuankeji.cn/",
        }
        self.data = self.fetch_html_data()

    def fetch_html_data(self):
        video_id = parse_qs(urlparse(self.real_url).query).get("pid", [None])[0]
        if not video_id:
            return {}
        try:
            int_video_id = int(video_id)
        except (TypeError, ValueError):
            return {}
        req_url = "https://share.xiaochuankeji.cn/planck/share/post/detail_h5"
        post_data = {"h_av": "5.2.13.011", "pid": int_video_id}
        try:
            resp = self.session.post(req_url, headers=self.headers, json=post_data, timeout=10)
            resp.raise_for_status()
            return resp.json()
        except Exception:
            return {}
    def get_real_video_url(self):
        try:
            data = self.data["data"]["post"]
            video_key = str(data["imgs"][0]["id"])
            return data["videos"][video_key]["url"]
        except: return None
    def get_cover_photo_url(self): return None
    def get_title_content(self):
        try: return self.data["data"]["post"]["content"]
        except: return None
    def get_author_info(self):
        try:
            member = self.data["data"]["post"]["member"]
            avatar_urls = member.get("avatar_urls", {}).get("origin", {}).get("urls", [])
            return {
                "nickname": member.get("name", ""),
                "author_id": str(member.get("id", "")),
                "avatar": avatar_urls[0] if avatar_urls else "",
            }
        except (KeyError, TypeError):
            return {}
