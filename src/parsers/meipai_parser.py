from src.parser_factory import register_parser
import base64
import json
import re

from configs.general_constants import USER_AGENT_M
from configs.logging_config import get_logger
from src.parsers.base_parser import BaseParser

logger = get_logger(__name__)


@register_parser("美拍")
class MeipaiParser(BaseParser):
    """美拍短视频解析器，通过 H5 页面的 window.PHPDATA 与嵌入式解密算法提取媒体信息。"""

    CDN_REDIRECT_API = "https://cracl.meitubase.com/resource/get_cdn_url?url={raw_url}"

    def __init__(self, real_url):
        super().__init__(real_url)
        self.headers = {
            "User-Agent": USER_AGENT_M[0],
            "Referer": "https://www.meipai.com/",
        }
        self.media_id = self._extract_media_id()
        self.title = None
        self.cover_url = None
        self.video_url = None
        self.author = None
        self._parse()

    def _extract_media_id(self):
        text = (self.real_url or "").strip()
        match = re.search(r"\d{15,}", text)
        if match:
            return match.group()
        return None

    def _decode_video_string(self, encoded):
        if not isinstance(encoded, str) or not encoded:
            return None
        try:
            hex_val = encoded[:4][::-1]
            e_dec = str(int(hex_val, 16))
            pre = [int(x) for x in e_dec[:2]]
            tail = [int(x) for x in e_dec[2:]]

            rest = encoded[4:]

            idx1, len1 = pre[0], pre[1]
            a1 = rest[idx1 : idx1 + len1]
            str1 = rest[:idx1] + rest[idx1:].replace(a1, "", 1)

            tail_idx = len(str1) - tail[0] - tail[1]
            tail_len = tail[1]
            a2 = str1[tail_idx : tail_idx + tail_len]
            str2 = str1[:tail_idx] + str1[tail_idx:].replace(a2, "", 1)

            raw_url = base64.b64decode(str2).decode("utf-8")
            if raw_url.startswith("//"):
                raw_url = "https:" + raw_url
            elif raw_url.startswith("http://"):
                raw_url = "https://" + raw_url[7:]

            cdn_url = self.CDN_REDIRECT_API.format(raw_url=raw_url)
            resp = self.session.get(cdn_url, headers=self.headers, allow_redirects=True, timeout=5)
            if resp.status_code == 200:
                return resp.url
            return raw_url
        except Exception as exc:
            logger.warning("Failed to decode Meipai video string: %s", exc)
            return None

    def _parse(self):
        if not self.media_id:
            logger.warning("Unable to extract Meipai media_id from URL: %s", self.real_url)
            return

        target_url = f"http://www.meipai.com/media/{self.media_id}"
        try:
            resp = self.session.get(target_url, headers=self.headers, timeout=10)
            resp.raise_for_status()

            start_idx = resp.text.find("window.PHPDATA = ")
            if start_idx == -1:
                logger.warning("window.PHPDATA not found in Meipai page: %s", target_url)
                return

            start_json = start_idx + len("window.PHPDATA = ")
            decoder = json.JSONDecoder()
            phpdata, _ = decoder.raw_decode(resp.text, start_json)

            media_info = phpdata.get("mediaInfo", {})
            raw_title = media_info.get("caption_origin") or media_info.get("caption")
            if raw_title:
                self.title = re.sub(r"<[^>]+>", "", raw_title).strip()

            cover = media_info.get("cover_pic")
            if cover:
                if cover.startswith("//"):
                    cover = "https:" + cover
                if "!" in cover:
                    cover = cover.split("!")[0]
                self.cover_url = cover

            user_info = media_info.get("user", {})
            if isinstance(user_info, dict) and user_info:
                avatar = user_info.get("avatar") or ""
                if avatar.startswith("//"):
                    avatar = "https:" + avatar
                author_id = user_info.get("id")
                self.author = {
                    "nickname": user_info.get("screen_name") or "",
                    "author_id": str(author_id) if author_id else "",
                    "avatar": avatar,
                }

            encoded_video = media_info.get("video")
            self.video_url = self._decode_video_string(encoded_video)
        except Exception as exc:
            logger.warning("Failed to parse Meipai media: %s", exc)

    def get_real_video_url(self):
        return self.video_url

    def get_title_content(self):
        return self.title or ""

    def get_cover_photo_url(self):
        return self.cover_url

    def get_author_info(self):
        return self.author
