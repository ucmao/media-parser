"""酷狗音乐 MV 与歌曲分享解析器。"""

import hashlib
import json
import re
import time
from urllib.parse import parse_qs, urlparse

from configs.logging_config import get_logger
from src.parser_factory import register_parser
from src.parsers.base_parser import BaseParser


logger = get_logger(__name__)


@register_parser("酷狗音乐")
class KugouMusicParser(BaseParser):
    """解析酷狗移动端公开 MV，以及未受限歌曲分享页。"""

    MV_API_URL = "https://m3ws.kugou.com/api/v1/mv/infov2"
    SIGNATURE_SALT = "NVPh5oo715z5DIWAeQlhMDsWXXQV4hwt"
    MOBILE_UA = (
        "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 "
        "Mobile/15E148 Safari/604.1"
    )

    def __init__(self, real_url):
        super().__init__(real_url)
        self.headers = {"User-Agent": self.MOBILE_UA, "Referer": "https://m.kugou.com/"}
        self.title = ""
        self.cover_url = None
        self.author = {"nickname": "", "author_id": "", "avatar": ""}
        self.video_list = []
        self.audio_url = None
        self.media_type, self.content_id = self._detect_media(real_url)
        self._parse()

    @staticmethod
    def _detect_media(url):
        parsed = urlparse(url or "")
        params = parse_qs(parsed.query)
        path = parsed.path.lower()
        desktop_mv = re.search(r"/mvweb/html/mv_([0-9a-f]{32})\.html", path)
        if desktop_mv:
            return "mv", desktop_mv.group(1)
        if "/mv" in path or "/mv/" in path:
            return "mv", (params.get("hash") or [None])[0]
        if "/share/song" in path or "/song" in path:
            return "song", (params.get("chain") or [None])[0]
        return None, None

    def _parse(self):
        if self.media_type == "mv" and self.content_id:
            self._parse_mv()
        elif self.media_type == "song":
            self._parse_song_page()

    def _parse_mv(self):
        timestamp = str(int(time.time() * 1000))
        params = {
            "cmd": "100",
            "hash": self.content_id,
            "ext": "mp4",
            "ismp3": "1",
            "ssl": "1",
            "srcappid": "2919",
            "clientver": "20000",
            "clienttime": timestamp,
            "mid": timestamp,
            "uuid": timestamp,
            "dfid": "-",
        }
        source = self.SIGNATURE_SALT + "".join(
            f"{key}={params[key]}" for key in sorted(params)
        ) + self.SIGNATURE_SALT
        params["signature"] = hashlib.md5(source.encode()).hexdigest()
        try:
            response = self.session.get(
                self.MV_API_URL, params=params, headers=self.headers, timeout=10
            )
            response.raise_for_status()
            payload = response.json()
        except Exception as exc:
            logger.warning("Failed to fetch Kugou MV data: %s", exc)
            return
        if not isinstance(payload, dict) or payload.get("errcode") not in (None, 0):
            return

        self.title = payload.get("songname") or ""
        cover = payload.get("mvicon")
        self.cover_url = cover.replace("{size}", "400") if isinstance(cover, str) else cover
        self.author = {
            "nickname": payload.get("singer") or "",
            "author_id": str(payload.get("id") or ""),
            "avatar": "",
        }
        self.video_list = self._extract_mv_streams(payload.get("mvdata") or {})

    def _parse_song_page(self):
        try:
            response = self.session.get(self.real_url, headers=self.headers, timeout=10)
            response.raise_for_status()
            self.html_content = response.text
        except Exception as exc:
            logger.warning("Failed to fetch Kugou song page: %s", exc)
            return
        match = re.search(r"var\s+phpParam\s*=\s*(\{.*?\});", self.html_content, re.DOTALL)
        if not match:
            return
        try:
            payload = json.loads(match.group(1))
        except json.JSONDecodeError:
            return
        data = ((payload.get("song_info") or {}).get("data") or {})
        self.title = data.get("songName") or data.get("fileName") or ""
        cover = data.get("album_img") or data.get("imgUrl")
        self.cover_url = cover.replace("{size}", "400") if isinstance(cover, str) else cover
        authors = data.get("authors") or []
        if authors and isinstance(authors[0], dict):
            author = authors[0]
            self.author = {
                "nickname": author.get("author_name") or author.get("name") or "",
                "author_id": str(author.get("author_id") or author.get("id") or ""),
                "avatar": (author.get("avatar") or "").replace("{size}", "400"),
            }
        elif data.get("singerName"):
            self.author["nickname"] = data["singerName"]

        # 付费、试听或平台明确报错的地址不能作为完整音频返回。
        if data.get("error") or data.get("pay_type") not in (None, 0, "0"):
            return
        url = data.get("url")
        if self._valid_url(url):
            self.audio_url = url

    @staticmethod
    def _extract_mv_streams(mvdata):
        streams = []
        for rank, key in enumerate(("sq", "rq", "le", "sd")):
            item = mvdata.get(key) or {}
            if not isinstance(item, dict):
                continue
            candidates = [item.get("downurl"), *(item.get("backupdownurl") or [])]
            url = next((value for value in candidates if KugouMusicParser._valid_url(value)), None)
            if url:
                streams.append((rank, url))
        return [url for _, url in sorted(streams, key=lambda item: item[0])]

    @staticmethod
    def _valid_url(url):
        return isinstance(url, str) and url.startswith(("http://", "https://"))

    def get_real_video_url(self):
        return self.video_list[0] if self.video_list else None

    def get_video_list(self):
        return self.video_list

    def get_audio_url(self):
        return self.audio_url

    def get_title_content(self):
        return self.title

    def get_cover_photo_url(self):
        return self.cover_url

    def get_author_info(self):
        return self.author
