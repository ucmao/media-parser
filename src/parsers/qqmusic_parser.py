"""QQ 音乐 MV 与分享视频解析器。"""

import json
import re
from urllib.parse import parse_qs, urlparse

from configs.logging_config import get_logger
from src.parser_factory import register_parser
from src.parsers.base_parser import BaseParser


logger = get_logger(__name__)


@register_parser("QQ音乐")
class QQMusicParser(BaseParser):
    """解析 QQ 音乐公开 MV 页面，并返回所有可用 MP4 清晰度。"""

    API_URL = "https://u.y.qq.com/cgi-bin/musicu.fcg"
    MOBILE_UA = (
        "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 "
        "Mobile/15E148 Safari/604.1"
    )

    def __init__(self, real_url):
        super().__init__(real_url)
        self.headers = {
            "User-Agent": self.MOBILE_UA,
            "Referer": "https://y.qq.com/",
        }
        self.vid = self._extract_vid(real_url)
        self.title = ""
        self.cover_url = None
        self.author = {"nickname": "", "author_id": "", "avatar": ""}
        self.video_list = []
        self._parse_page()
        self._fetch_mv_data()

    @staticmethod
    def _extract_vid(url):
        parsed = urlparse(url or "")
        if vid := (parse_qs(parsed.query).get("vid") or [None])[0]:
            return vid
        match = re.search(r"/(?:mv|mvDetail)/([A-Za-z0-9]+)(?:/|$)", parsed.path)
        return match.group(1) if match else None

    def _parse_page(self):
        """从 SSR 数据补充上传者信息；接口仍是媒体地址的权威来源。"""
        if not self.vid:
            return
        try:
            response = self.session.get(
                self.real_url,
                headers=self.headers,
                allow_redirects=True,
                timeout=10,
            )
            response.raise_for_status()
            self.html_content = response.text
            self.vid = self.vid or self._extract_vid(response.url)
        except Exception as exc:
            logger.warning("Failed to fetch QQMusic page: %s", exc)
            return

        match = re.search(
            r"window\.__ssrFirstPageData__\s*=\s*(\"(?:\\.|[^\"\\])*\")",
            self.html_content or "",
            re.DOTALL,
        )
        if not match:
            return
        try:
            encoded_payload = json.loads(match.group(1))
            payload = json.loads(encoded_payload)
            data = payload.get("data") or {}
            video = data.get("video") or {}
            self._apply_metadata(video)

            creators = data.get("creator") or []
            if creators and isinstance(creators[0], dict):
                creator = creators[0]
                self.author = {
                    "nickname": creator.get("nick") or creator.get("name") or "",
                    "author_id": str(creator.get("mid") or creator.get("uin") or ""),
                    "avatar": creator.get("avatar") or creator.get("headurl") or "",
                }
        except (json.JSONDecodeError, TypeError) as exc:
            logger.warning("Failed to parse QQMusic SSR payload: %s", exc)

    def _fetch_mv_data(self):
        if not self.vid:
            return
        payload = {
            "comm": {"ct": 24, "cv": 0},
            "mvInfo": {
                "module": "video.VideoDataServer",
                "method": "get_video_info_batch",
                "param": {
                    "vidlist": [self.vid],
                    "required": [
                        "vid",
                        "type",
                        "sid",
                        "cover_pic",
                        "duration",
                        "singers",
                        "video_pay",
                        "hint",
                        "code",
                        "msg",
                        "name",
                        "desc",
                        "playcnt",
                        "pubdate",
                        "isfav",
                        "gmid",
                    ],
                },
            },
            "mvUrl": {
                "module": "gosrf.Stream.MvUrlProxy",
                "method": "GetMvUrls",
                "param": {"vids": [self.vid], "request_typet": 10001},
            },
        }
        try:
            response = self.session.post(
                self.API_URL,
                json=payload,
                headers={**self.headers, "Content-Type": "application/json"},
                timeout=10,
            )
            response.raise_for_status()
            result = response.json()
        except Exception as exc:
            logger.warning("Failed to fetch QQMusic MV data: %s", exc)
            return

        metadata = (((result.get("mvInfo") or {}).get("data") or {}).get(self.vid) or {})
        self._apply_metadata(metadata)
        stream_data = (((result.get("mvUrl") or {}).get("data") or {}).get(self.vid) or {})
        self.video_list = self._extract_streams(stream_data)

    def _apply_metadata(self, video):
        if not isinstance(video, dict):
            return
        self.title = self.title or video.get("name") or video.get("raw_name") or ""
        self.cover_url = self.cover_url or video.get("cover_pic") or video.get("first_frame_pic")

        singers = video.get("singers") or video.get("related_singers") or []
        if singers and isinstance(singers[0], dict) and not self.author["nickname"]:
            singer = singers[0]
            self.author = {
                "nickname": singer.get("name") or singer.get("title") or "",
                "author_id": str(singer.get("mid") or singer.get("id") or ""),
                "avatar": singer.get("picurl") or singer.get("avatar") or "",
            }

        if not self.author["nickname"] and video.get("uploader_nick"):
            self.author = {
                "nickname": video.get("uploader_nick") or "",
                "author_id": str(video.get("uploader_encuin") or video.get("uploader_uin") or ""),
                "avatar": video.get("uploader_headurl") or "",
            }

    @staticmethod
    def _extract_streams(stream_data):
        streams = []
        for kind in ("mp4", "hls"):
            for item in stream_data.get(kind) or []:
                if not isinstance(item, dict) or item.get("code") not in (None, 0):
                    continue
                candidates = item.get("url") or item.get("freeflow_url") or item.get("comm_url") or []
                if isinstance(candidates, str):
                    candidates = [candidates]
                url = next(
                    (value for value in candidates if isinstance(value, str) and value.startswith(("http://", "https://"))),
                    None,
                )
                if not url and isinstance(item.get("m3u8"), str) and item["m3u8"].startswith(("http://", "https://")):
                    url = item["m3u8"]
                if url:
                    quality = item.get("filetype") or item.get("newFileType") or item.get("fileSize") or 0
                    streams.append((quality, url))

        streams.sort(key=lambda value: value[0], reverse=True)
        return list(dict.fromkeys(url for _, url in streams))

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
