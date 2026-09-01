"""配音秀作品分享页解析器。"""

import html
import re

from bs4 import BeautifulSoup

from configs.logging_config import get_logger
from src.parser_factory import register_parser
from src.parsers.base_parser import BaseParser


logger = get_logger(__name__)


@register_parser("配音秀")
class PeiyinxiuParser(BaseParser):
    """解析配音秀公开作品页中的原始 MP4 与作品元数据。"""

    MOBILE_UA = (
        "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 "
        "Mobile/15E148 Safari/604.1"
    )

    def __init__(self, real_url):
        super().__init__(real_url)
        self.headers = {"User-Agent": self.MOBILE_UA, "Referer": "https://www.peiyinxiu.com/"}
        self.title = ""
        self.cover_url = None
        self.author = {"nickname": "", "author_id": "", "avatar": ""}
        self.video_list = []
        self._parse_page()

    def _parse_page(self):
        try:
            response = self.session.get(self.real_url, headers=self.headers, timeout=10)
            response.raise_for_status()
            self.html_content = response.text
        except Exception as exc:
            logger.warning("Failed to fetch Peiyinxiu share page: %s", exc)
            return

        soup = BeautifulSoup(self.html_content, "lxml")
        root = soup.select_one("#wlui")
        author_id = root.get("data-uid", "") if root else ""
        title_tag = soup.select_one(".filmName")
        self.title = (
            (title_tag.get("data-title") if title_tag else None)
            or (title_tag.get_text(strip=True) if title_tag else "")
            or self._meta_content(soup, "og:title")
            or ""
        )
        author_tag = soup.select_one(".athorName span")
        avatar_tag = soup.select_one(".userHead")
        self.author = {
            "nickname": author_tag.get_text(strip=True).lstrip("@") if author_tag else "",
            "author_id": str(author_id),
            "avatar": self._absolute_url(avatar_tag.get("src")) if avatar_tag else "",
        }
        self.video_list = self._unique(self._script_value("filmurl"))
        self.cover_url = self._script_value("filmimg") or self._meta_content(soup, "og:image")

    def _script_value(self, key):
        match = re.search(
            rf"\b{key}\s*:\s*['\"]([^'\"]+)['\"]", self.html_content or "", re.I
        )
        return self._absolute_url(html.unescape(match.group(1))) if match else None

    @staticmethod
    def _meta_content(soup, property_name):
        tag = soup.find("meta", attrs={"property": property_name})
        return tag.get("content") if tag else None

    @staticmethod
    def _absolute_url(url):
        if not isinstance(url, str) or not url:
            return None
        if url.startswith("//"):
            return f"https:{url}"
        return url if url.startswith(("http://", "https://")) else None

    @staticmethod
    def _unique(url):
        return [url] if url else []

    def get_real_video_url(self):
        return self.video_list[0] if self.video_list else None

    def get_video_list(self):
        return self.video_list

    def get_title_content(self):
        return self.title

    def get_cover_photo_url(self):
        return self.cover_url

    def get_author_info(self):
        return self.author
