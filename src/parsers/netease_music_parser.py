"""网易云音乐歌曲、MV、Mlog 与动态分享解析器。"""

import html
import json
import re
from urllib.parse import parse_qs, urlencode, urlparse

from configs.logging_config import get_logger
from src.parser_factory import register_parser
from src.parsers.base_parser import BaseParser


logger = get_logger(__name__)


@register_parser("网易云音乐")
class NeteaseMusicParser(BaseParser):
    MOBILE_UA = (
        "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1"
    )
    DESKTOP_UA = (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0 Safari/537.36"
    )

    def __init__(self, real_url):
        super().__init__(real_url)
        self.headers = {"User-Agent": self.MOBILE_UA, "Referer": "https://music.163.com/"}
        self.title = ""
        self.cover_url = None
        self.video_list = []
        self.audio_url = None
        self.image_list = []
        self.subtitles = None
        self.author = {"nickname": "", "author_id": "", "avatar": ""}
        self.media_type, self.media_id = self._detect_media(real_url)
        self._parse()

    @staticmethod
    def _detect_media(url):
        parsed = urlparse(url or "")
        params = parse_qs(parsed.query)
        path = parsed.path.lower()
        media_id = (params.get("id") or [None])[0]
        if "/landing/mlog" in path:
            return "mlog", media_id
        if "/landing/mv" in path or re.search(r"/(?:mv|mvdetail)(?:/|$)", path):
            return "mv", media_id or parsed.path.rstrip("/").split("/")[-1]
        if "/event" in path:
            return "event", media_id
        if "/song" in path:
            return "song", media_id
        return None, media_id

    def _parse(self):
        if self.media_type == "mv":
            self._parse_mv()
        elif self.media_type == "mlog":
            self._parse_mlog()
        elif self.media_type == "event":
            self._parse_event()
        elif self.media_type == "song":
            self._parse_song(self.media_id)

    def _request_json(self, url, params=None):
        try:
            response = self.session.get(url, params=params, headers=self.headers, timeout=10)
            response.raise_for_status()
            payload = response.json()
            return payload if isinstance(payload, dict) else {}
        except Exception as exc:
            logger.warning("Failed to fetch NetEase Music API %s: %s", url, exc)
            return {}

    def _parse_mv(self):
        if not self.media_id:
            return
        payload = self._request_json(
            "https://music.163.com/api/mv/detail",
            {"id": self.media_id},
        )
        data = payload.get("data") or {}
        self.title = data.get("name") or ""
        self.cover_url = data.get("cover")
        artists = data.get("artists") or []
        if artists and isinstance(artists[0], dict):
            artist = artists[0]
            self.author = {
                "nickname": artist.get("name") or data.get("artistName") or "",
                "author_id": str(artist.get("id") or data.get("artistId") or ""),
                "avatar": artist.get("img1v1Url") or "",
            }
        elif data.get("artistName"):
            self.author["nickname"] = data["artistName"]
            self.author["author_id"] = str(data.get("artistId") or "")

        streams = []
        for quality, url in (data.get("brs") or {}).items():
            if self._valid_url(url):
                try:
                    rank = int(quality)
                except (TypeError, ValueError):
                    rank = 0
                streams.append((rank, url))
        streams.sort(key=lambda item: item[0], reverse=True)
        self.video_list = self._unique(url for _, url in streams)

    def _parse_mlog(self):
        payload = self._fetch_initial_props(self.real_url, self.MOBILE_UA)
        info = payload.get("mlogInfo") or {}
        resource = info.get("resource") or {}
        content = resource.get("content") or {}
        profile = resource.get("profile") or {}
        video = content.get("video") or {}

        self._set_author(profile)
        self.title = (
            content.get("title")
            or content.get("text")
            or (f"{self.author['nickname']}的音乐动态" if self.author["nickname"] else "网易云音乐动态")
        )
        self.cover_url = (
            video.get("coverUrl")
            or video.get("frameUrl")
            or ((video.get("frameImage") or {}).get("imageUrl"))
        )
        self.video_list = self._ranked_urls(video.get("urlInfos") or [])
        if not self.video_list:
            fallback = ((video.get("urlInfo") or {}).get("url"))
            self.video_list = [fallback] if self._valid_url(fallback) else []
        self.image_list = self._extract_images(content.get("image") or [])

        song = content.get("song") or resource.get("song") or {}
        if song.get("id") and not self.video_list:
            self._parse_song(song["id"], fallback=song)

    def _parse_event(self):
        if not self.media_id:
            return
        parsed = urlparse(self.real_url)
        params = parse_qs(parsed.query)
        query = {"id": self.media_id}
        if uid := (params.get("uid") or params.get("userid") or [None])[0]:
            query["uid"] = uid
        url = f"https://music.163.com/event?{urlencode(query)}"
        payload = self._fetch_event_data(url)
        if not payload:
            return

        user = payload.get("user") or {}
        self._set_author(user)
        try:
            content = json.loads(payload.get("json") or "{}")
        except json.JSONDecodeError:
            content = {}

        song = content.get("song") or {}
        self.title = content.get("title") or content.get("msg") or song.get("name") or ""
        self.image_list = self._extract_event_images(payload.get("pics") or [])
        if self.image_list:
            first = self.image_list[0]
            self.cover_url = first.get("url") if isinstance(first, dict) else first

        video_data = content.get("videoData") or {}
        self.video_list = self._extract_nested_video_urls(video_data)
        if song.get("id"):
            self._parse_song(song["id"], fallback=song, preserve_title=True)

    def _parse_song(self, song_id, fallback=None, preserve_title=False):
        if not song_id:
            return
        try:
            numeric_id = int(song_id)
        except (TypeError, ValueError):
            return
        detail = self._request_json(
            "https://music.163.com/api/song/detail/",
            {"id": numeric_id, "ids": json.dumps([numeric_id])},
        )
        songs = detail.get("songs") or []
        song = songs[0] if songs and isinstance(songs[0], dict) else (fallback or {})
        if not preserve_title or not self.title:
            self.title = song.get("name") or self.title
        album = song.get("album") or {}
        self.cover_url = self.cover_url or album.get("picUrl") or album.get("blurPicUrl")
        artists = song.get("artists") or []
        if artists and isinstance(artists[0], dict) and not self.author["nickname"]:
            artist = artists[0]
            self.author = {
                "nickname": artist.get("name") or "",
                "author_id": str(artist.get("id") or ""),
                "avatar": artist.get("img1v1Url") or artist.get("picUrl") or "",
            }

        player = self._request_json(
            "https://music.163.com/api/song/enhance/player/url",
            {"id": numeric_id, "ids": json.dumps([numeric_id]), "br": 320000},
        )
        entries = player.get("data") or []
        if entries and isinstance(entries[0], dict) and self._valid_url(entries[0].get("url")):
            self.audio_url = entries[0]["url"]
        self._parse_lyrics(numeric_id)

    def _parse_lyrics(self, song_id):
        payload = self._request_json(
            "https://music.163.com/api/song/lyric",
            {"id": song_id, "lv": 1, "kv": 1, "tv": -1},
        )
        lyric = ((payload.get("lrc") or {}).get("lyric"))
        if not isinstance(lyric, str):
            return
        subtitles = []
        for line in lyric.splitlines():
            match = re.match(r"\[(\d+):(\d+(?:\.\d+)?)\](.*)", line.strip())
            if match and match.group(3).strip():
                start = int(match.group(1)) * 60 + float(match.group(2))
                subtitles.append({"start": round(start, 3), "text": match.group(3).strip()})
        self.subtitles = subtitles or None

    def _fetch_initial_props(self, url, user_agent):
        try:
            response = self.session.get(
                url,
                headers={"User-Agent": user_agent, "Referer": "https://music.163.com/"},
                allow_redirects=True,
                timeout=10,
            )
            response.raise_for_status()
            self.html_content = response.text
        except Exception as exc:
            logger.warning("Failed to fetch NetEase Music share page: %s", exc)
            return {}
        match = re.search(
            r"window\.__INITIAL_PROPS__\s*=\s*(\{.*?\})\s*</script>",
            self.html_content or "",
            re.DOTALL,
        )
        if not match:
            return {}
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError as exc:
            logger.warning("Failed to parse NetEase Music initial props: %s", exc)
            return {}

    def _fetch_event_data(self, url):
        try:
            response = self.session.get(
                url,
                headers={"User-Agent": self.DESKTOP_UA, "Referer": "https://music.163.com/"},
                timeout=10,
            )
            response.raise_for_status()
        except Exception as exc:
            logger.warning("Failed to fetch NetEase Music event: %s", exc)
            return {}
        match = re.search(
            r'<textarea[^>]+id="event-data"[^>]*>\s*(.*?)\s*</textarea>',
            response.text or "",
            re.DOTALL,
        )
        if not match:
            return {}
        try:
            return json.loads(html.unescape(match.group(1)))
        except json.JSONDecodeError as exc:
            logger.warning("Failed to parse NetEase Music event data: %s", exc)
            return {}

    def _set_author(self, profile):
        if not isinstance(profile, dict):
            return
        self.author = {
            "nickname": profile.get("nickname") or profile.get("name") or "",
            "author_id": str(profile.get("userId") or profile.get("id") or ""),
            "avatar": profile.get("avatarUrl") or profile.get("avatar") or "",
        }

    @classmethod
    def _ranked_urls(cls, entries):
        ranked = []
        for entry in entries:
            if not isinstance(entry, dict) or not cls._valid_url(entry.get("url")):
                continue
            quality = entry.get("resolution") or entry.get("r") or 0
            ranked.append((quality if isinstance(quality, (int, float)) else 0, entry["url"]))
        ranked.sort(key=lambda item: item[0], reverse=True)
        return cls._unique(url for _, url in ranked)

    @classmethod
    def _extract_images(cls, entries):
        images = []
        for entry in entries:
            if isinstance(entry, str) and cls._valid_url(entry):
                images.append(entry)
            elif isinstance(entry, dict):
                url = entry.get("originUrl") or entry.get("url") or entry.get("imageUrl") or entry.get("picUrl")
                if cls._valid_url(url):
                    images.append(url)
        return cls._unique(images)

    @classmethod
    def _extract_event_images(cls, entries):
        images = []
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            url = entry.get("originUrl") or entry.get("pcRectangleUrl") or entry.get("rectangleUrl")
            if not cls._valid_url(url):
                continue
            live_url = entry.get("videoOriginalUrl") or entry.get("videoUrl")
            images.append(
                {"url": url, "live_photo_url": live_url if cls._valid_url(live_url) else None}
            )
        return images

    @classmethod
    def _extract_nested_video_urls(cls, value):
        found = []
        if isinstance(value, dict):
            for key, child in value.items():
                if "url" in key.lower() and cls._valid_url(child) and child.lower().split("?", 1)[0].endswith((".mp4", ".mov", ".m3u8")):
                    found.append(child)
                else:
                    found.extend(cls._extract_nested_video_urls(child))
        elif isinstance(value, list):
            for child in value:
                found.extend(cls._extract_nested_video_urls(child))
        return cls._unique(found)

    @staticmethod
    def _valid_url(value):
        return isinstance(value, str) and value.startswith(("http://", "https://"))

    @staticmethod
    def _unique(values):
        return list(dict.fromkeys(value for value in values if value))

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

    def get_image_list(self):
        return self.image_list

    def get_subtitles(self):
        return self.subtitles
