"""松果时刻 AI 作品分享解析器。"""

from urllib.parse import parse_qs, urlparse

from configs.logging_config import get_logger
from src.parser_factory import register_parser
from src.parsers.base_parser import BaseParser


logger = get_logger(__name__)


@register_parser("松果时刻")
class PineconeMomentParser(BaseParser):
    """解析松果时刻公开故事、漫画及合成配音媒体。"""

    API_URL = "https://m.pineconemoment.com/share/item/detail"
    MOBILE_UA = (
        "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 "
        "Mobile/15E148 Safari/604.1"
    )

    def __init__(self, real_url):
        super().__init__(real_url)
        self.headers = {"User-Agent": self.MOBILE_UA, "Referer": "https://m.pineconemoment.com/"}
        self.title = ""
        self.cover_url = None
        self.author = {"nickname": "", "author_id": "", "avatar": ""}
        self.video_list = []
        self.image_list = []
        self.audio_url = None
        self._parse()

    @staticmethod
    def _params_from_url(url):
        parsed = urlparse(url or "")
        query = parse_qs(parsed.query)
        path_parts = [part for part in parsed.path.split("/") if part]
        story_id = (query.get("item_id") or query.get("story_id") or [None])[0]
        if not story_id and len(path_parts) >= 2 and path_parts[-2] == "story":
            story_id = path_parts[-1]
        params = {
            "item_type": (query.get("item_type") or query.get("story_type") or ["1"])[0],
            "item_id": story_id,
        }
        for key in ("sharer_id", "author_id", "channel", "version", "style_id", "share_id"):
            if value := (query.get(key) or [None])[0]:
                params[key] = value
        return params

    def _parse(self):
        params = self._params_from_url(self.real_url)
        if not params.get("item_id"):
            return
        try:
            response = self.session.get(self.API_URL, params=params, headers=self.headers, timeout=10)
            response.raise_for_status()
            payload = response.json()
        except Exception as exc:
            logger.warning("Failed to fetch Pinecone Moment detail: %s", exc)
            return
        if not isinstance(payload, dict) or payload.get("code") not in (0, 200):
            return
        data = payload.get("data") or {}
        story = data.get("story") or ((data.get("interactive_comic") or {}))
        if not isinstance(story, dict):
            return

        self.title = story.get("title") or ""
        creator = story.get("creator") or story.get("sharer") or {}
        self.author = {
            "nickname": creator.get("nickname") or "",
            "author_id": str(creator.get("user_id") or creator.get("short_id") or ""),
            "avatar": creator.get("avatar") or "",
        }
        images = story.get("images") or []
        self.image_list = [
            {"url": item["url"]} for item in images
            if isinstance(item, dict) and self._valid_url(item.get("url"))
        ]
        self.video_list = self._unique(
            item.get("video_url") for item in images if isinstance(item, dict)
        )
        first = images[0] if images and isinstance(images[0], dict) else {}
        self.cover_url = first.get("video_cover_url") or first.get("url") or story.get("cover_uri")
        dubbing = story.get("dubbing") or {}
        h5_audio = dubbing.get("h5_audio") or {}
        self.audio_url = h5_audio.get("audio_url") if self._valid_url(h5_audio.get("audio_url")) else None

    @staticmethod
    def _valid_url(url):
        return isinstance(url, str) and url.startswith(("http://", "https://"))

    @classmethod
    def _unique(cls, urls):
        return list(dict.fromkeys(url for url in urls if cls._valid_url(url)))

    def get_real_video_url(self):
        return self.video_list[0] if self.video_list else None

    def get_video_list(self):
        return self.video_list

    def get_image_list(self):
        return self.image_list

    def get_audio_url(self):
        return self.audio_url

    def get_title_content(self):
        return self.title

    def get_cover_photo_url(self):
        return self.cover_url

    def get_author_info(self):
        return self.author
