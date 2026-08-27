"""小云雀AI (xiaoyunque.jianying.com) 分享解析器。"""

from urllib.parse import parse_qs, urlparse

from configs.logging_config import get_logger
from src.parsers.base_parser import BaseParser


logger = get_logger(__name__)


class XiaoyunqueParser(BaseParser):
    """通过小云雀官方接口解析 xiaoyunque.jianying.com 分享链接。"""

    API_URL = "https://xiaoyunque.jianying.com/luckycat/cn/jianying/campaign/v1/pippit/share/landing_page"
    USER_AGENT = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )

    def __init__(self, real_url):
        super().__init__(real_url)
        self.headers = {
            "Accept": "application/json, text/plain, */*",
            "Content-Type": "application/json",
            "User-Agent": self.USER_AGENT,
        }
        self.data = {
            "title": "",
            "video_url": None,
            "video_list": [],
            "cover_url": None,
            "author": None,
            "image_list": [],
        }
        self._parse_once()

    def _parse_once(self):
        try:
            url = self.real_url
            parsed = urlparse(url)
            qdict = {k: v[0] for k, v in parse_qs(parsed.query).items()}

            if not qdict and "/s/" in parsed.path:
                response = self.session.get(
                    url,
                    headers={"User-Agent": self.USER_AGENT},
                    allow_redirects=True,
                    timeout=15,
                )
                response.raise_for_status()
                parsed = urlparse(response.url)
                qdict = {k: v[0] for k, v in parse_qs(parsed.query).items()}

            if not qdict:
                logger.warning(f"Unable to extract Xiaoyunque query parameters from URL: {self.real_url}")
                return

            response = self.session.post(
                self.API_URL,
                headers=self.headers,
                json={"query_params": qdict},
                timeout=30,
            )
            response.raise_for_status()
            payload = response.json()
            if payload.get("err_no") != 0:
                raise ValueError(payload.get("err_tips") or "小云雀接口返回解析失败")

            self.data.update(self._format_data(payload.get("data") or {}))
        except Exception as exc:
            logger.exception(f"Failed to parse Xiaoyunque share: {exc}")

    @classmethod
    def _format_data(cls, data):
        page_info = data.get("page_info") or {}
        generate_page = page_info.get("generate_page") or {}
        user_info = generate_page.get("user_info") or {}
        item_info = generate_page.get("item_info") or {}

        title = item_info.get("desc") or item_info.get("title") or "小云雀AI 作品"

        # 图片列表
        image_info = item_info.get("image_info") or []
        image_list = []
        for img in image_info:
            if isinstance(img, dict) and img.get("image_url"):
                image_list.append(img["image_url"])
            elif isinstance(img, str):
                image_list.append(img)

        # 视频列表
        video_url = item_info.get("video_url") or item_info.get("video_play_url")
        video_info = item_info.get("video_info") or {}
        if not video_url and isinstance(video_info, dict):
            video_url = video_info.get("main_url") or video_info.get("video_url")

        video_list = [video_url] if video_url else []

        # 封面图
        cover_url = item_info.get("cover_url")
        if not cover_url and image_list:
            cover_url = image_list[0]

        author = {
            "nickname": user_info.get("nick_name") or "",
            "author_id": str(user_info.get("user_id") or user_info.get("sec_uid") or ""),
            "avatar": user_info.get("avatar_url") or "",
        }

        return {
            "title": title,
            "video_url": video_url,
            "video_list": video_list,
            "cover_url": cover_url,
            "author": author,
            "image_list": image_list,
        }

    def get_real_video_url(self):
        return self.data.get("video_url")

    def get_video_list(self):
        return self.data.get("video_list") or []

    def get_title_content(self):
        return self.data.get("title") or ""

    def get_cover_photo_url(self):
        return self.data.get("cover_url")

    def get_author_info(self):
        return self.data.get("author")

    def get_image_list(self):
        return self.data.get("image_list") or []
