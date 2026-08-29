from src.parser_factory import register_parser
"""Soul 分享帖解析器。"""

import json
import random
from urllib.parse import parse_qs, urlparse

from configs.general_constants import USER_AGENT_M
from configs.logging_config import get_logger
from src.parsers.base_parser import BaseParser


logger = get_logger(__name__)


@register_parser("Soul")
class SoulParser(BaseParser):
    """通过 Soul H5 公开接口提取帖子媒体和作者信息。"""

    POST_DETAIL_API = "https://api-h5.soulapp.cn/html/v3/post/detail"
    USER_INFO_API = "https://api-h5.soulapp.cn/html/v2/user/info"
    REQUIRED_PARAMS = ("postIdEcpt", "sign", "signVersion")

    def __init__(self, real_url):
        super().__init__(real_url)
        self.headers = {
            "User-Agent": random.choice(USER_AGENT_M),
            "Accept": "application/json, text/plain, */*",
            "Referer": "https://w13.soulsmile.cn/",
            "Origin": "https://w13.soulsmile.cn",
        }
        self.page_params = self._parse_page_params()
        self.post = self._fetch_post_detail()
        self.user = self._fetch_user_info(self.post.get("authorIdEcpt"))

    def _parse_page_params(self):
        parsed = urlparse(self.real_url)
        query_params = parse_qs(parsed.query)
        fragment_params = {}
        if "?" in parsed.fragment:
            fragment_params = parse_qs(parsed.fragment.split("?", 1)[1])

        params = {
            key: (query_params.get(key, [None])[0] or fragment_params.get(key, [None])[0])
            for key in self.REQUIRED_PARAMS
        }
        missing = [key for key, value in params.items() if not value]
        if missing:
            raise ValueError(f"Soul URL 缺少必要参数: {', '.join(missing)}")
        return params

    def _fetch_json(self, api_url, params):
        try:
            response = self.session.get(api_url, params=params, headers=self.headers, timeout=15)
            response.raise_for_status()
            return response.json()
        except Exception as exc:
            logger.warning("Failed to fetch Soul API %s: %s", api_url, exc)
            return {}

    def _fetch_post_detail(self):
        result = self._fetch_json(self.POST_DETAIL_API, self.page_params)
        post = (result.get("data") or {}).get("post") or {}
        if result.get("success") and isinstance(post, dict):
            return post
        logger.warning("Soul post detail API returned error: %s", result)
        return {}

    def _fetch_user_info(self, author_id_ecpt):
        if not author_id_ecpt:
            return {}
        result = self._fetch_json(self.USER_INFO_API, {"userIdEcpt": author_id_ecpt})
        data = result.get("data") or {}
        if result.get("success") and isinstance(data, dict):
            return data
        logger.warning("Soul user info API returned error: %s", result)
        return {}

    @staticmethod
    def _normalize_url(url):
        return str(url).replace("\\/", "/") if url else None

    def _get_attachments(self):
        attachments = self.post.get("attachments")
        return attachments if isinstance(attachments, list) else []

    def _get_primary_video(self):
        attachments = self._get_attachments()
        return next(
            (item for item in attachments if isinstance(item, dict) and item.get("type") == "VIDEO"),
            {},
        )

    def get_real_video_url(self):
        return self._normalize_url(self._get_primary_video().get("fileUrl"))

    def get_title_content(self):
        return self.post.get("content") or "Soul 帖子"

    def get_cover_photo_url(self):
        attachment = self._get_primary_video()
        ext = attachment.get("ext")
        try:
            ext = json.loads(ext) if ext else {}
        except (TypeError, json.JSONDecodeError):
            ext = {}
        return self._normalize_url(attachment.get("videoCoverUrl") or ext.get("videoCoverUrl"))

    def get_author_info(self):
        return {
            "nickname": self.user.get("nickName") or "",
            "author_id": self.post.get("authorIdEcpt") or "",
            "avatar": self._normalize_url(self.user.get("headImgurl")) or "",
            "description": self.user.get("signature") or self.post.get("signature") or "",
        }

    def get_image_list(self):
        images = []
        for attachment in self._get_attachments():
            if not isinstance(attachment, dict) or attachment.get("type") == "VIDEO":
                continue
            url = next(
                (
                    attachment.get(key)
                    for key in ("fileUrl", "imageUrl", "imageOriginUrl", "pictureUrl")
                    if attachment.get(key)
                ),
                None,
            )
            if normalized := self._normalize_url(url):
                images.append(normalized)
        return images
