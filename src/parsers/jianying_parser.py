from src.parser_factory import register_parser
"""剪映模板分享解析器。"""

import hashlib
import time
from urllib.parse import parse_qs, urlparse

from configs.logging_config import get_logger
from src.parsers.base_parser import BaseParser


logger = get_logger(__name__)


@register_parser("剪映")
class JianyingParser(BaseParser):
    """通过剪映公开模板接口解析 lv.ulikecam.com 分享链接。"""

    DETAIL_API = "https://lv-api.ulikecam.com/lv/v1/web/replicate/multi_get_templates"
    USER_AGENT = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )

    def __init__(self, real_url):
        super().__init__(real_url)
        self.template_id, self.item_type = self._extract_template_params(real_url)
        self.template = self._fetch_template()

    @staticmethod
    def _extract_template_params(url):
        query = parse_qs(urlparse(url).query)
        template_id = (query.get("template_id") or [""])[0]
        item_type = (query.get("item_type") or ["0"])[0]
        try:
            item_type = int(item_type)
        except (TypeError, ValueError):
            item_type = 0
        return template_id, item_type

    def _fetch_template(self):
        if not self.template_id:
            logger.warning("Unable to extract Jianying template_id from URL: %s", self.real_url)
            return {}
        timestamp = int(time.time())
        sign = hashlib.md5(
            f"9e2c|mplates|0||{timestamp}||11ac".encode("utf-8")
        ).hexdigest()
        headers = {
            "sign": sign,
            "pf": "0",
            "sign-ver": "1",
            "device-time": str(timestamp),
            "User-Agent": self.USER_AGENT,
            "Content-Type": "application/json",
            "Origin": "https://lv.ulikecam.com",
            "Referer": "https://lv.ulikecam.com/",
        }
        try:
            response = self.session.post(
                self.DETAIL_API,
                headers=headers,
                json={
                    "sdk_version": "100.0.0",
                    "id": [self.template_id],
                    "scene": "share",
                    "item_type": self.item_type,
                },
                timeout=15,
            )
            response.raise_for_status()
            templates = ((response.json().get("data") or {}).get("templates") or [])
            if templates and isinstance(templates[0], dict):
                return templates[0]
            logger.warning("Jianying API returned no template for %s", self.template_id)
        except Exception as exc:
            logger.warning("Failed to fetch Jianying template: %s", exc)
        return {}

    def get_real_video_url(self):
        return self.template.get("video_url")

    def get_title_content(self):
        return self.template.get("title") or self.template.get("short_title") or "剪映模板"

    def get_cover_photo_url(self):
        return self.template.get("cover_url") or self.template.get("cover")

    def get_author_info(self):
        author = self.template.get("author") or {}
        aweme_info = author.get("aweme_info") or {}
        return {
            "nickname": author.get("name") or aweme_info.get("name") or "",
            "author_id": str(
                author.get("uid") or author.get("id") or aweme_info.get("uid") or ""
            ),
            "avatar": (
                author.get("avatar")
                or author.get("avatar_url")
                or aweme_info.get("avatar_url")
                or ""
            ),
            "description": author.get("description") or "",
        }

    def get_audio_url(self):
        return ((self.template.get("music_info") or {}).get("play_url"))

    def get_image_list(self):
        return self.template.get("images") or []

    def get_video_list(self):
        video_url = self.get_real_video_url()
        return [video_url] if video_url else []
