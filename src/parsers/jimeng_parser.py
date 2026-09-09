from urllib.parse import parse_qs, urlparse

from configs.logging_config import get_logger
from src.parser_factory import register_parser
from src.parsers.base_parser import BaseParser


logger = get_logger(__name__)


@register_parser("即梦AI")
class JimengParser(BaseParser):
    """解析即梦AI 视频分享。

    """

    API_URL = "https://jimeng.jianying.com/mweb/v1/get_item_info"
    USER_AGENT = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/123.0.0.0 Safari/537.36"
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
            item_id = self._extract_item_id(self.real_url)
            if not item_id:
                response = self.session.get(
                    self.real_url,
                    headers={"User-Agent": self.USER_AGENT},
                    allow_redirects=True,
                    timeout=15,
                )
                response.raise_for_status()
                item_id = self._extract_item_id(response.url)
                if not item_id and response.text:
                    item_id = self._extract_item_id_from_html(response.text)

            if not item_id:
                logger.warning(f"Unable to extract Jimeng item ID: {self.real_url}")
                return

            response = self.session.post(
                self.API_URL,
                headers=self.headers,
                json={"published_item_id": item_id},
                timeout=30,
            )
            response.raise_for_status()
            payload = response.json()
            if str(payload.get("ret")) != "0":
                raise ValueError(payload.get("errmsg") or "即梦接口返回解析失败")

            self.data.update(self._format_data(payload.get("data") or {}))
        except Exception as exc:
            logger.exception(f"Failed to parse Jimeng share: {exc}")

    @classmethod
    def _format_data(cls, detail):
        common = detail.get("common_attr") or {}
        author = detail.get("author") or {}
        video = detail.get("video") or {}
        origin_video = video.get("origin_video") or {}
        transcoded = video.get("transcoded_video") or {}

        primary_video = None
        transcoded_origin = transcoded.get("origin")
        if isinstance(transcoded_origin, dict):
            primary_video = transcoded_origin.get("video_url")
        if not primary_video:
            primary_video = origin_video.get("video_url")
        if not primary_video:
            primary_video = cls._best_transcoded_url(transcoded)

        cover_map = common.get("cover_url_map") or {}
        cover_url = None
        if isinstance(cover_map, dict):
            for quality in ("4096", "2400", "1080", "720", "480", "360", "original"):
                if cover_map.get(quality):
                    cover_url = cover_map[quality]
                    break
            if not cover_url:
                cover_url = next((url for url in cover_map.values() if url), None)
        if not cover_url:
            cover_url = common.get("cover_url") or video.get("cover_url")

        # 提取即梦 AI 生图/图集图片
        image_list = []
        raw_images = detail.get("image_infos") or detail.get("image_list") or detail.get("images") or []
        if isinstance(raw_images, list):
            for img in raw_images:
                if isinstance(img, str) and img.startswith("http"):
                    image_list.append(img)
                elif isinstance(img, dict):
                    url_map = img.get("image_url_map") or img.get("cover_url_map") or {}
                    img_url = None
                    if isinstance(url_map, dict):
                        for quality in ("original", "4096", "2400", "1080", "720"):
                            if url_map.get(quality):
                                img_url = url_map[quality]
                                break
                        if not img_url:
                            img_url = next((u for u in url_map.values() if u), None)
                    if not img_url:
                        img_url = img.get("image_url") or img.get("url") or img.get("origin_url") or img.get("main_url")
                    if img_url:
                        image_list.append(img_url)

        image_list = list(dict.fromkeys(image_list))
        if not primary_video and not image_list and cover_url:
            image_list = [cover_url]

        author_id = author.get("uid") or author.get("sec_uid") or ""
        return {
            "title": common.get("title") or None,
            "desc": common.get("description") or None,
            "video_url": primary_video,
            "video_list": [primary_video] if primary_video else [],
            "cover_url": cover_url,
            "author": {
                "nickname": author.get("name") or "",
                "author_id": str(author_id) if author_id else "",
                "avatar": author.get("avatar_url") or "",
            },
            "image_list": image_list,
        }

    @staticmethod
    def _best_transcoded_url(transcoded):
        if not isinstance(transcoded, dict):
            return None
        candidates = []
        for item in transcoded.values():
            if not isinstance(item, dict) or not item.get("video_url"):
                continue
            score = (
                int(item.get("width") or 0) * int(item.get("height") or 0),
                int(item.get("br") or item.get("bitrate") or 0),
            )
            candidates.append((score, item["video_url"]))
        return max(candidates, default=(None, None))[1]

    @staticmethod
    def _extract_item_id(url):
        if not url:
            return None
        parsed = urlparse(url)
        query = parse_qs(parsed.query)
        for key in ("published_item_id", "item_id", "id", "work_id", "feed_id", "projectId"):
            value = query.get(key, [None])[0]
            if value and value.isdigit():
                return value

        path_parts = [part for part in parsed.path.split("/") if part]
        for part in reversed(path_parts):
            if part.isdigit() and len(part) >= 10:
                return part
        return None

    @staticmethod
    def _extract_item_id_from_html(html_text):
        if not html_text:
            return None
        import re
        patterns = [
            r'["\']published_item_id["\']\s*:\s*["\']?(\d{10,25})',
            r'["\']item_id["\']\s*:\s*["\']?(\d{10,25})',
            r'["\']itemId["\']\s*:\s*["\']?(\d{10,25})',
            r'["\']work_id["\']\s*:\s*["\']?(\d{10,25})',
            r'["\']feed_id["\']\s*:\s*["\']?(\d{10,25})',
            r'["\']id["\']\s*:\s*["\']?(\d{15,25})',
        ]
        for pattern in patterns:
            match = re.search(pattern, html_text)
            if match:
                return match.group(1)
        return None

    def get_real_video_url(self):
        return self.data.get("video_url")

    def get_video_list(self):
        return self.data.get("video_list") or []

    def get_title_content(self):
        return self.data.get("title") or None

    def get_description(self):
        return self.data.get("desc") or None

    def get_cover_photo_url(self):
        return self.data.get("cover_url")

    def get_author_info(self):
        return self.data.get("author")

    def get_image_list(self):
        return self.data.get("image_list") or []
