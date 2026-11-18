from src.parser_factory import register_parser
import json
import re
from urllib.parse import urlparse

from configs.general_constants import USER_AGENT_M, USER_AGENT_PC
from configs.logging_config import get_logger
from src.parsers.base_parser import BaseParser

logger = get_logger(__name__)


@register_parser("新片场")
class XinpianchangParser(BaseParser):
    """新片场作品解析器，使用移动端 API 提取视频与作者信息。"""

    ARTICLE_API = "https://app.xinpianchang.com/article/{article_id}"
    MEDIA_API = "https://mod-api.xinpianchang.com/mod/api/v2/media/{vid}?appKey={app_key}"
    PAGE_URL = "https://www.xinpianchang.com/a{article_id}"
    DEFAULT_APP_KEY = "61a2f329348b3bf77"

    def __init__(self, real_url):
        super().__init__(real_url)
        self.headers = {
            "User-Agent": USER_AGENT_M[0],
            "Accept": "application/json, text/plain, */*",
        }
        self.media_headers = dict(self.headers, Referer="https://www.xinpianchang.com/", Origin="https://www.xinpianchang.com")
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

    def _fetch_article_from_api(self):
        article_url = self.ARTICLE_API.format(article_id=self.article_id)
        try:
            resp = self.session.get(article_url, headers=self.headers, timeout=10)
            if resp.status_code != 200:
                logger.warning("Xinpianchang article API HTTP %s for %s", resp.status_code, self.article_id)
                return None
            res_json = resp.json()
        except Exception as exc:
            logger.warning("Xinpianchang article API failed for %s: %s", self.article_id, exc)
            return None
        if res_json.get("status") != 0 or not isinstance(res_json.get("data"), dict):
            logger.warning("Xinpianchang article API returned error for %s: %s", self.article_id, str(res_json)[:200])
            return None
        return res_json["data"]

    def _fetch_article_from_page(self):
        """App 接口不可用时回退到网页 __NEXT_DATA__，其中 detail 与 App 接口 data 结构一致。"""
        page_url = self.PAGE_URL.format(article_id=self.article_id)
        # 必须使用 PC UA（移动 UA 会跳到无 __NEXT_DATA__ 的 h5 页），且不能带浏览器式 text/html Accept，
        # 否则会返回不含 __NEXT_DATA__ 的精简页面。
        headers = {
            "User-Agent": USER_AGENT_PC[0] if USER_AGENT_PC else "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
            "Accept": "*/*",
        }
        try:
            resp = self.session.get(page_url, headers=headers, timeout=10)
            if resp.status_code != 200:
                logger.warning("Xinpianchang page HTTP %s for %s", resp.status_code, self.article_id)
                return None
            match = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', resp.text or "", re.S)
            if not match:
                logger.warning("Xinpianchang page has no __NEXT_DATA__ for %s", self.article_id)
                return None
            detail = json.loads(match.group(1)).get("props", {}).get("pageProps", {}).get("detail")
        except Exception as exc:
            logger.warning("Xinpianchang page fallback failed for %s: %s", self.article_id, exc)
            return None
        return detail if isinstance(detail, dict) else None

    def _fetch_video_list(self, vid, app_key):
        mod_url = self.MEDIA_API.format(vid=vid, app_key=app_key)
        try:
            mod_resp = self.session.get(mod_url, headers=self.media_headers, timeout=10)
            if mod_resp.status_code != 200:
                logger.warning("Xinpianchang media API HTTP %s for vid %s", mod_resp.status_code, vid)
                return []
            mod_json = mod_resp.json()
        except Exception as exc:
            logger.warning("Xinpianchang media API failed for vid %s: %s", vid, exc)
            return []
        if mod_json.get("status") != 0 or not isinstance(mod_json.get("data"), dict):
            logger.warning("Xinpianchang media API returned error for vid %s: %s", vid, str(mod_json)[:200])
            return []
        progressive = (mod_json["data"].get("resource") or {}).get("progressive") or []
        urls = [
            p["url"]
            for p in progressive
            if isinstance(p, dict) and isinstance(p.get("url"), str) and p["url"].startswith("http")
        ]
        if not urls:
            logger.warning("Xinpianchang media API has no playable progressive url for vid %s", vid)
        return list(dict.fromkeys(urls))

    def _parse(self):
        if not self.article_id:
            logger.warning("Unable to extract Xinpianchang article_id from URL: %s", self.real_url)
            return

        data = self._fetch_article_from_api() or self._fetch_article_from_page()
        if not data:
            return

        self.title = data.get("title")
        self.cover_url = data.get("cover")

        author_info = (data.get("author") or {}).get("userinfo") or {}
        if isinstance(author_info, dict) and author_info:
            author_id = author_info.get("id")
            self.author = {
                "nickname": author_info.get("username") or "",
                "author_id": str(author_id) if author_id else "",
                "avatar": author_info.get("avatar") or "",
            }

        video = data.get("video") or {}
        vid = data.get("vid") or data.get("media_id") or video.get("vid")
        app_key = video.get("appKey") or self.DEFAULT_APP_KEY
        if not vid:
            logger.warning("Xinpianchang article %s has no vid", self.article_id)
            return

        self.video_list = self._fetch_video_list(vid, app_key)

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
