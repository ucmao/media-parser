"""可灵AI 分享作品解析器。"""

import re
from urllib.parse import parse_qs, urlparse

from configs.general_constants import USER_AGENT_M
from configs.logging_config import get_logger
from src.parsers.base_parser import BaseParser


logger = get_logger(__name__)


class KlingParser(BaseParser):
    """通过可灵公开分享接口提取作品媒体信息。"""

    DETAIL_API = "https://klingai-share.kuaishou.com/app/creatives/query"

    def __init__(self, real_url):
        super().__init__(real_url)
        self.headers = {
            "User-Agent": USER_AGENT_M[-4],
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh",
            "Referer": "https://klingai-share.kuaishou.com/",
        }
        self.creative_id, self.creative_type = self._extract_creative()
        self.detail = self._fetch_detail()

    def _extract_creative(self):
        text = (self.real_url or "").strip()
        if "://" in text:
            query_params = parse_qs(urlparse(text).query)
            creative_id = (
                query_params.get("creative_id") or query_params.get("work_id") or [""]
            )[0]
            creative_type = (query_params.get("creative_type") or ["WORK"])[0]
            if creative_id:
                return creative_id, creative_type

        match = re.fullmatch(r"\d+", text)
        if match:
            return match.group(), "WORK"
        return "", "WORK"

    def _fetch_detail(self):
        if not self.creative_id:
            logger.warning("Unable to extract Kling creative_id from URL: %s", self.real_url)
            return {}
        try:
            response = self.session.get(
                self.DETAIL_API,
                params={
                    "creativeId": self.creative_id,
                    "creativeType": self.creative_type,
                },
                headers=self.headers,
                timeout=15,
            )
            response.raise_for_status()
            result = response.json()
            data = result.get("data")
            if result.get("status") == 200 and result.get("result") == 1 and isinstance(data, dict):
                return data
            logger.warning("Kling API returned error: %s", result)
        except Exception as exc:
            logger.warning("Failed to fetch Kling data: %s", exc)
        return {}

    @staticmethod
    def _resource_url(value):
        if isinstance(value, dict) and value.get("resource"):
            return str(value["resource"]).replace("\\/", "/")
        return None

    def get_real_video_url(self):
        return self._resource_url(self.detail.get("resource"))

    def get_title_content(self):
        return self.detail.get("introduction") or "可灵AI 作品"

    def get_cover_photo_url(self):
        return self._resource_url(self.detail.get("cover")) or self._resource_url(
            self.detail.get("firstFrame")
        )

    def get_author_info(self):
        profile = self.detail.get("userProfile") or {}
        author_id = profile.get("userId")
        return {
            "nickname": profile.get("userName") or "",
            "author_id": str(author_id) if author_id else "",
            "avatar": self._resource_url(profile.get("avatar")) or "",
            "description": "",
        }
