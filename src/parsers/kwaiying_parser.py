from src.parser_factory import register_parser
"""快影 (Kwaiying) 模板与作品分享解析器。"""

import hashlib
import random
import re
import time
from urllib.parse import parse_qs, urlparse

from configs.logging_config import get_logger
from src.parsers.base_parser import BaseParser


logger = get_logger(__name__)


@register_parser("快影")
class KwaiyingParser(BaseParser):
    """通过快影 OpenAPI 接口解析 share.kwaiying.com 分享链接。"""

    DETAIL_API = "https://api.kmovie.gifshow.com/rest/n/kmovie/app/resource/getTemplateById"
    SIGN_KEY = "yiuhjkbvhbjisjchgdnx38uejd"
    USER_AGENT = (
        "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 "
        "(KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1"
    )

    def __init__(self, real_url):
        super().__init__(real_url)
        self.template_id = self._extract_template_id(real_url)
        self.resource_data = self._fetch_template()

    @staticmethod
    def _extract_template_id(url):
        """从 URL query 或 path 中提取 templateId / id。"""
        parsed = urlparse(url)
        query = parse_qs(parsed.query)
        template_id = (query.get("id") or query.get("templateId") or [""])[0]
        if not template_id:
            match = re.search(r"(?:id|templateId|template_id)=(\d+)", url)
            if match:
                template_id = match.group(1)
        return template_id

    @classmethod
    def _generate_sign_params(cls):
        """生成快影 API 签名与 nonce 校验参数。"""
        now_ms = int(time.time() * 1000)
        nonce = random.randint(100000000000, 999999999999)
        hex_str = "".join([hex(ord(c))[2:] for c in cls.SIGN_KEY])
        digits_only = re.sub(r"[a-fA-F]", "", hex_str)[:16]
        a = int(digits_only) if digits_only else 0
        s = (a ^ now_ms) | a
        sign_val = hashlib.md5(str(nonce ^ s).encode("utf-8")).hexdigest()
        return {
            "timestamp": now_ms,
            "nonce": nonce,
            "sign": sign_val,
        }

    def _fetch_template(self):
        """请求快影 API 获取模板及媒体数据。"""
        if not self.template_id:
            logger.warning("Unable to extract Kwaiying template_id from URL: %s", self.real_url)
            return {}

        params = self._generate_sign_params()
        params["templateId"] = self.template_id

        headers = {
            "User-Agent": self.USER_AGENT,
            "Origin": "https://share.kwaiying.com",
            "Referer": self.real_url,
        }

        try:
            response = self.session.get(
                self.DETAIL_API,
                headers=headers,
                params=params,
                timeout=12,
            )
            response.raise_for_status()
            res_json = response.json()
            if res_json.get("result") == 1 and res_json.get("resource"):
                return res_json.get("resource") or {}
            logger.warning("Kwaiying API returned error: %s", res_json.get("errorMsg"))
        except Exception as exc:
            logger.warning("Failed to fetch Kwaiying template: %s", exc)
        return {}

    def get_real_video_url(self):
        """提取无水印高清 MP4 视频直链。"""
        return self.resource_data.get("videoUrl")

    def get_title_content(self):
        """提取模板标题或文案描述。"""
        return (
            self.resource_data.get("name")
            or (self.resource_data.get("templateBean") or {}).get("description")
            or "快影模板"
        )

    def get_cover_photo_url(self):
        """提取封面图地址。"""
        template_bean = self.resource_data.get("templateBean") or {}
        return template_bean.get("coverUrl") or template_bean.get("coverWebPUrl")

    def get_author_info(self):
        """提取创作者昵称、ID 及头像。"""
        user = self.resource_data.get("user") or {}
        icon_list = user.get("iconUrlList") or []
        avatar = icon_list[0] if icon_list else ""
        return {
            "nickname": user.get("nickName") or "",
            "author_id": str(user.get("userId") or user.get("ksUserId") or ""),
            "avatar": avatar,
        }

    def get_audio_url(self):
        """提取音频地址。"""
        music = self.resource_data.get("music") or {}
        return music.get("url") or music.get("playUrl")

    def get_image_list(self):
        """提取图集资源。"""
        return []

    def get_video_list(self):
        video_url = self.get_real_video_url()
        return [video_url] if video_url else []
