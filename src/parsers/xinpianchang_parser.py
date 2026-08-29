from src.parser_factory import register_parser
import re
from urllib.parse import urlparse

from configs.general_constants import USER_AGENT_M
from configs.logging_config import get_logger
from src.parsers.base_parser import BaseParser

logger = get_logger(__name__)


@register_parser("新片场")
class XinpianchangParser(BaseParser):
    """新片场作品解析器，使用移动端 API 提取视频与作者信息。"""

    ARTICLE_API = "https://app.xinpianchang.com/article/{article_id}"
    MEDIA_API = "https://mod-api.xinpianchang.com/mod/api/v2/media/{vid}?appKey={app_key}"

    def __init__(self, real_url):
        super().__init__(real_url)
        self.headers = {
            "User-Agent": USER_AGENT_M[0],
            "Accept": "application/json, text/plain, */*",
        }
        self.article_id = self._extract_article_id()
        self.title = None
        self.cover_url = None
        self.video_url = None
        self.video_list = []
        self.author = None
        self._parse()

    def _extract_article_id(self):
        text = (self.real_url or "").strip()
        if not text:
            return None
        path = urlparse(text).path
        match = re.search(r'(?:a|article/)?(\d+)', path)
        if match:
            return match.group(1)
        match_digits = re.search(r'\d+', text)
        if match_digits:
            return match_digits.group()
        return None

    def _parse(self):
        if not self.article_id:
            logger.warning("Unable to extract Xinpianchang article_id from URL: %s", self.real_url)
            return

        article_url = self.ARTICLE_API.format(article_id=self.article_id)
        try:
            resp = self.session.get(article_url, headers=self.headers, timeout=10)
            resp.raise_for_status()
            res_json = resp.json()
            if res_json.get("status") != 0 or not isinstance(res_json.get("data"), dict):
                logger.warning("Xinpianchang article API returned error: %s", res_json)
                return

            data = res_json["data"]
            self.title = data.get("title")
            self.cover_url = data.get("cover")

            author_info = data.get("author", {}).get("userinfo", {})
            if isinstance(author_info, dict) and author_info:
                author_id = author_info.get("id")
                self.author = {
                    "nickname": author_info.get("username") or "",
                    "author_id": str(author_id) if author_id else "",
                    "avatar": author_info.get("avatar") or "",
                }

            vid = data.get("vid") or data.get("media_id")
            app_key = data.get("video", {}).get("appKey") or "61a2f329348b3bf77"

            if vid:
                mod_url = self.MEDIA_API.format(vid=vid, app_key=app_key)
                mod_resp = self.session.get(mod_url, headers=self.headers, timeout=10)
                if mod_resp.status_code == 200:
                    mod_json = mod_resp.json()
                    if mod_json.get("status") == 0 and isinstance(mod_json.get("data"), dict):
                        mod_data = mod_json["data"]
                        progressive = mod_data.get("resource", {}).get("progressive", [])
                        urls = [
                            p["url"]
                            for p in progressive
                            if isinstance(p, dict) and p.get("url") and p["url"].startswith("http")
                        ]
                        self.video_list = list(dict.fromkeys(urls))
                        if self.video_list:
                            self.video_url = self.video_list[0]
        except Exception as exc:
            logger.warning("Failed to fetch Xinpianchang data: %s", exc)

    def get_real_video_url(self):
        return self.video_url

    def get_video_list(self):
        return self.video_list

    def get_title_content(self):
        return self.title or ""

    def get_cover_photo_url(self):
        return self.cover_url

    def get_author_info(self):
        return self.author
