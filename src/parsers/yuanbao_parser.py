import html
import json
import os
import re
from urllib.parse import parse_qs, urlparse

from bs4 import BeautifulSoup

from configs.general_constants import USER_AGENT_M
from configs.logging_config import get_logger
from src.parser_factory import register_parser
from src.parsers.base_parser import BaseParser


logger = get_logger(__name__)


@register_parser("腾讯元宝")
class YuanbaoParser(BaseParser):
    """腾讯元宝公开对话、AI 生图和 AI 视频分享解析器。"""

    GENERAL_SHARE_DETAIL_API = "https://yb.tencent.com/api/share/general_share_detail"

    def __init__(self, real_url):
        super().__init__(real_url)
        self.headers = {
            "User-Agent": USER_AGENT_M[0],
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }
        cookie = os.getenv("YUANBAO_COOKIE", "").strip()
        if cookie:
            self.headers["Cookie"] = cookie

        self.title = ""
        self.cover_url = None
        self.video_url = None
        self.video_list = []
        self.image_list = []
        self.author = None
        self._parse()

    def _parse(self):
        if not self.real_url:
            return
        try:
            response = self.session.get(
                self.real_url,
                headers=self.headers,
                timeout=15,
            )
            response.raise_for_status()
            self.real_url = response.url

            payload = self._load_next_data(response.text)
            page_props = payload.get("props", {}).get("pageProps", {})
            self._parse_page_props(page_props, response.text)

            if not self.video_list and not self.image_list:
                detail = self._fetch_standalone_share_detail(page_props)
                if detail:
                    self._parse_share_detail(detail)
        except Exception as exc:
            logger.warning("Failed to parse Yuanbao share page: %s", exc)

    @staticmethod
    def _load_next_data(page_html):
        soup = BeautifulSoup(page_html or "", "lxml")
        script = soup.select_one("script#__NEXT_DATA__")
        if not script or not script.string:
            return {}
        try:
            return json.loads(script.string)
        except (TypeError, json.JSONDecodeError):
            return {}

    def _parse_page_props(self, page_props, page_html=""):
        if not isinstance(page_props, dict):
            return

        full_share = page_props.get("fullChatShareData")
        if isinstance(full_share, dict):
            self._parse_chat_share(full_share)

        detail = page_props.get("shareDetailData")
        if isinstance(detail, dict):
            self._parse_share_detail(detail)

        if not isinstance(full_share, dict) and not isinstance(detail, dict):
            self._collect_direct_media(page_props)

        if not self.title:
            soup = BeautifulSoup(page_html or "", "lxml")
            if soup.title and soup.title.string:
                self.title = soup.title.string.strip()

        self.video_list = self._unique(self.video_list)
        self.image_list = self._unique(self.image_list)
        self.video_url = self.video_list[0] if self.video_list else None
        if not self.cover_url:
            self.cover_url = self.image_list[0] if self.image_list else None

    def _parse_chat_share(self, payload):
        chat = payload.get("chat") or {}
        card = chat.get("shareCardInfo") or {}
        conversations = chat.get("convs") or []

        self.title = self._clean_title(card.get("title"))
        self.author = self._extract_author(chat, conversations)

        for conversation in conversations:
            if not isinstance(conversation, dict) or conversation.get("speaker") != "ai":
                continue
            for speech in conversation.get("speechesV2") or []:
                if not isinstance(speech, dict):
                    continue
                extra = speech.get("extra") or {}
                for replace in extra.get("replaces") or []:
                    if not isinstance(replace, dict):
                        continue
                    for media in replace.get("multimedias") or []:
                        self._collect_multimedia(media)

        if not self.title:
            self.title = self._find_prompt(conversations)

        card_media_type = str(card.get("imageFrom") or "").lower()
        card_image = self._valid_url(card.get("coverUrl") or card.get("imageUrl"))
        if card_image:
            if "video" in card_media_type:
                self.cover_url = self.cover_url or card_image
            elif not self.image_list:
                self.image_list.append(card_image)
                self.cover_url = self.cover_url or card_image

    def _collect_multimedia(self, media):
        if not isinstance(media, dict):
            return

        media_type = " ".join(
            str(media.get(key) or "").lower()
            for key in ("type", "mediaType", "mimeType", "display")
        )
        is_video = "video" in media_type
        is_image = "image" in media_type or not is_video

        primary = self._first_url(
            media.get("downloadUrl"),
            media.get("url"),
            media.get("resourceUrl"),
            media.get("playUrl"),
            media.get("videoUrl"),
        )
        if is_video and primary:
            self.video_list.append(primary)
        elif is_image and primary:
            self.image_list.append(primary)

        cover = self._first_url(
            media.get("downloadCoverUrl"),
            media.get("cover"),
            media.get("coverUrl"),
            media.get("thumbnailUrl"),
            media.get("previewUrl"),
        )
        if cover and (is_video or not self.cover_url):
            self.cover_url = cover

    def _parse_share_detail(self, detail):
        if not isinstance(detail, dict):
            return
        self.title = self.title or self._clean_title(
            detail.get("title") or detail.get("prompt")
        )

        extra = detail.get("extra")
        if isinstance(extra, str):
            try:
                extra = json.loads(extra)
            except json.JSONDecodeError:
                extra = {}
        if isinstance(extra, dict):
            self._collect_direct_media(extra)
        self._collect_direct_media(detail)

        if not self.author:
            self.author = self._author_from_dict(
                detail.get("userInfo") or detail.get("author") or {}
            )

    def _collect_direct_media(self, data):
        """兼容独立图片/视频分享页及字段变体。"""
        if isinstance(data, dict):
            for key, value in data.items():
                key_lower = str(key).lower()
                if isinstance(value, str):
                    url = self._valid_url(value)
                    if not url:
                        continue
                    if any(token in key_lower for token in ("avatar", "icon", "logo", "target")):
                        continue
                    if "video" in key_lower or "playurl" in key_lower:
                        self.video_list.append(url)
                    elif "cover" in key_lower or "poster" in key_lower or "thumbnail" in key_lower:
                        self.cover_url = self.cover_url or url
                    elif key_lower in {"downloadurl", "imageurl", "image_url"}:
                        self.image_list.append(url)
                elif isinstance(value, (dict, list)):
                    self._collect_direct_media(value)
        elif isinstance(data, list):
            for item in data:
                self._collect_direct_media(item)

    def _fetch_standalone_share_detail(self, page_props):
        path = urlparse(self.real_url).path
        if "/bot/app/share/" not in path:
            return {}

        share_id = page_props.get("shareId") or path.rstrip("/").split("/")[-1]
        user_id = parse_qs(urlparse(self.real_url).query).get("userId", [""])[0]
        if not share_id:
            return {}

        headers = {
            "User-Agent": self.headers["User-Agent"],
            "Accept": "application/json, text/plain, */*",
            "Content-Type": "application/json",
            "Origin": "https://yb.tencent.com",
            "Referer": self.real_url,
            "X-Requested-With": "XMLHttpRequest",
            "x-source": "web",
            "x-verify-flag": "1",
        }
        if self.headers.get("Cookie"):
            headers["Cookie"] = self.headers["Cookie"]

        try:
            response = self.session.post(
                self.GENERAL_SHARE_DETAIL_API,
                headers=headers,
                json={
                    "shareType": "videoWeb",
                    "shareId": share_id,
                    "userId": user_id,
                },
                timeout=10,
            )
            if response.status_code != 200:
                return {}
            payload = response.json()
            return payload if isinstance(payload, dict) and not payload.get("error") else {}
        except Exception as exc:
            logger.debug("Yuanbao standalone share API failed: %s", exc)
            return {}

    @staticmethod
    def _extract_author(chat, conversations):
        author = YuanbaoParser._author_from_dict(chat.get("userInfo") or {})
        for conversation in conversations:
            if not isinstance(conversation, dict) or conversation.get("speaker") != "human":
                continue
            role = conversation.get("role") or {}
            candidate = YuanbaoParser._author_from_dict(role)
            if candidate:
                if not candidate.get("author_id") and conversation.get("userId"):
                    candidate["author_id"] = str(conversation["userId"])
                if not author:
                    return candidate
                for key in ("nickname", "author_id", "avatar"):
                    if not author.get(key) and candidate.get(key):
                        author[key] = candidate[key]
                return author
        return author

    @staticmethod
    def _author_from_dict(data):
        if not isinstance(data, dict) or not data:
            return None
        nickname = data.get("name") or data.get("nickname") or data.get("nick") or ""
        author_id = data.get("userId") or data.get("id") or data.get("uid") or ""
        avatar = data.get("imageUrl") or data.get("avatar") or data.get("avatarUrl") or ""
        if not any((nickname, author_id, avatar)):
            return None
        return {
            "nickname": str(nickname),
            "author_id": str(author_id),
            "avatar": avatar,
        }

    @staticmethod
    def _find_prompt(conversations):
        for conversation in conversations:
            if not isinstance(conversation, dict) or conversation.get("speaker") != "human":
                continue
            prompt = conversation.get("displayPrompt") or conversation.get("speech")
            if isinstance(prompt, str) and prompt.strip():
                return YuanbaoParser._clean_title(prompt)
        return "腾讯元宝分享"

    @staticmethod
    def _clean_title(value):
        if not isinstance(value, str):
            return ""
        value = html.unescape(value).strip()
        value = re.sub(r"^\[(?:图片|视频)\]\s*", "", value)
        return value

    @staticmethod
    def _valid_url(value):
        if not isinstance(value, str) or not value.startswith(("http://", "https://")):
            return None
        return html.unescape(value).replace("\\u0026", "&")

    @classmethod
    def _first_url(cls, *values):
        for value in values:
            url = cls._valid_url(value)
            if url:
                return url
        return None

    @staticmethod
    def _unique(values):
        return list(dict.fromkeys(value for value in values if value))

    def get_real_video_url(self):
        return self.video_url

    def get_video_list(self):
        return self.video_list

    def get_title_content(self):
        return self.title

    def get_cover_photo_url(self):
        return self.cover_url

    def get_author_info(self):
        return self.author

    def get_image_list(self):
        return self.image_list
