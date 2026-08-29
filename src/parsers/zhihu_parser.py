from src.parser_factory import register_parser
"""知乎问答、文章、视频与 Pin 解析器。"""

import re
from urllib.parse import urlparse

from bs4 import BeautifulSoup

from configs.general_constants import USER_AGENT_M
from configs.logging_config import get_logger
from src.parsers.base_parser import BaseParser


logger = get_logger(__name__)


@register_parser("知乎")
class ZhihuParser(BaseParser):
    """通过知乎公开 API 解析问答、文章、zvideo 与 Pin 内容。"""

    API_ROOT = "https://api.zhihu.com"

    def __init__(self, real_url):
        super().__init__(real_url)
        self.headers = {"User-Agent": USER_AGENT_M[0], "Referer": "https://www.zhihu.com/"}
        self.content_type, self.content_id = self._extract_content_id()
        self.data = self._fetch_data()

    def _extract_content_id(self):
        path = urlparse(self.real_url).path
        patterns = (
            ("answer", r"question/\d+/answer/(\d+)"),
            ("answer", r"/answer/(\d+)"),
            ("zvideo", r"/zvideo/(\d+)"),
            ("pin", r"/pin/(\d+)"),
            ("article", r"(?:zhuanlan\.zhihu\.com/p/|/article/)(\d+)"),
        )
        for content_type, pattern in patterns:
            match = re.search(pattern, self.real_url if content_type == "article" else path)
            if match:
                return content_type, match.group(1)
        return "", ""

    def _fetch_data(self):
        if not self.content_id:
            logger.warning("Unable to extract Zhihu content ID: %s", self.real_url)
            return {}
        api_path = {
            "answer": "answers",
            "zvideo": "videos",
            "pin": "pins",
            "article": "articles",
        }.get(self.content_type)
        if not api_path:
            return {}
        try:
            response = self.session.get(
                f"{self.API_ROOT}/{api_path}/{self.content_id}",
                headers=self.headers,
                timeout=15,
            )
            response.raise_for_status()
            return response.json()
        except Exception as exc:
            logger.warning("Zhihu API fetch failed: %s", exc)
            return {}

    @staticmethod
    def _first_url(value):
        if isinstance(value, str) and value:
            return value
        if isinstance(value, dict):
            return next((value.get(key) for key in ("url", "play_url") if value.get(key)), None)
        if isinstance(value, list):
            return next((ZhihuParser._first_url(item) for item in value if ZhihuParser._first_url(item)), None)
        return None

    @staticmethod
    def _playlist_url(playlist):
        if isinstance(playlist, dict):
            candidates = playlist.values()
        elif isinstance(playlist, list):
            candidates = playlist
        else:
            return None
        candidates = [item for item in candidates if isinstance(item, dict)]
        candidates.sort(
            key=lambda item: (int(item.get("bitrate") or 0), int(item.get("width") or 0) * int(item.get("height") or 0)),
            reverse=True,
        )
        return next((item.get("play_url") or item.get("url") for item in candidates if item.get("play_url") or item.get("url")), None)

    def _pin_video(self):
        for item in self.data.get("content") or []:
            if isinstance(item, dict) and item.get("type") == "video":
                return item
        return {}

    def get_real_video_url(self):
        direct_url = self._playlist_url(self.data.get("playlist"))
        if direct_url:
            return direct_url
        pin_video = self._pin_video()
        direct_url = self._playlist_url(pin_video.get("playlist"))
        if direct_url:
            return direct_url
        lens_match = re.search(r'data-lens-id="(\d+)"', self.data.get("content") or "")
        if lens_match:
            try:
                response = self.session.get(
                    f"https://lens.zhihu.com/api/v4/videos/{lens_match.group(1)}",
                    headers=self.headers,
                    timeout=15,
                )
                response.raise_for_status()
                return self._playlist_url(response.json().get("playlist"))
            except Exception as exc:
                logger.warning("Zhihu Lens video fetch failed: %s", exc)
        return None

    def get_title_content(self):
        question = self.data.get("question") or {}
        title = question.get("title") or self.data.get("title") or self.data.get("excerpt_title") or ""
        excerpt = self.data.get("excerpt") or ""
        if title or excerpt:
            return "\n".join(part for part in (title, excerpt) if part).strip()
        content_html = self.data.get("content_html") or self.data.get("content") or ""
        if isinstance(content_html, str):
            text = BeautifulSoup(content_html, "html.parser").get_text(" ", strip=True)
            if text:
                return text
        return "知乎视频" if self._pin_video() else "知乎内容"

    def get_cover_photo_url(self):
        pin_video = self._pin_video()
        return (
            self._first_url(pin_video.get("thumbnail"))
            or self._first_url(self.data.get("thumbnail"))
            or self._first_url(self.data.get("image_url"))
            or self._first_url(self.get_image_list())
        )

    def get_image_list(self):
        images = []
        for item in self.data.get("content") or []:
            if isinstance(item, dict) and item.get("type") == "image":
                if url := self._first_url(item.get("url") or item.get("image")):
                    images.append(url)
        content_html = self.data.get("content") or self.data.get("content_html") or ""
        if isinstance(content_html, str):
            for image in BeautifulSoup(content_html, "html.parser").find_all("img"):
                if url := image.get("data-original") or image.get("data-actualsrc") or image.get("src"):
                    if url.startswith("http"):
                        images.append(url)
        return list(dict.fromkeys(images))

    def get_author_info(self):
        author = self.data.get("author") or {}
        return {
            "nickname": author.get("name") or "",
            "author_id": str(author.get("id") or ""),
            "avatar": author.get("avatar_url") or "",
        }
