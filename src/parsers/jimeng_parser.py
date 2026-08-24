from pathlib import Path
import sys
from urllib.parse import parse_qs, urlparse

root_dir = str(Path(__file__).resolve().parents[2])
if root_dir not in sys.path:
    sys.path.append(root_dir)

from configs.logging_config import get_logger
from src.parsers.base_parser import BaseParser


logger = get_logger(__name__)


class JimengParser(BaseParser):
    """解析即梦 AI 视频分享。

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
            if not item_id and "/s/" in urlparse(self.real_url).path:
                response = self.session.get(
                    self.real_url,
                    headers={"User-Agent": self.USER_AGENT},
                    allow_redirects=True,
                    timeout=15,
                )
                response.raise_for_status()
                item_id = self._extract_item_id(response.url)

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

        author_id = author.get("uid") or author.get("sec_uid") or ""
        return {
            "title": common.get("description") or "即梦 AI 视频",
            "video_url": primary_video,
            "video_list": [primary_video] if primary_video else [],
            "cover_url": cover_url,
            "author": {
                "nickname": author.get("name") or "",
                "author_id": str(author_id) if author_id else "",
                "avatar": author.get("avatar_url") or "",
            },
            "image_list": [],
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
        parsed = urlparse(url)
        query = parse_qs(parsed.query)
        for key in ("item_id", "id"):
            value = query.get(key, [None])[0]
            if value:
                return value

        path_parts = [part for part in parsed.path.split("/") if part]
        if path_parts and path_parts[-1].isdigit():
            return path_parts[-1]
        return None

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


if __name__ == "__main__":
    test_url = "https://jimeng.jianying.com/s/rdloCrYi2wc/?t=8011"
    parser = JimengParser(test_url)
    print("-" * 30)
    print(f"标题内容：{parser.get_title_content()}")
    print(f"作者信息：{parser.get_author_info()}")
    print(f"封面图片：{parser.get_cover_photo_url()}")
    print(f"视频链接：{parser.get_real_video_url()}")
    print(f"视频列表：{parser.get_video_list()}")
    print(f"图片列表：{parser.get_image_list()}")
