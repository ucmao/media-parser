from src.parser_factory import register_parser
"""剪映与 CapCut 模板及项目分享解析器。"""

import hashlib
import re
import time
from urllib.parse import parse_qs, urlparse

from configs.logging_config import get_logger
from src.parsers.base_parser import BaseParser


logger = get_logger(__name__)


@register_parser("剪映")
class JianyingParser(BaseParser):
    """支持剪映移动端模板分享 (lv.ulikecam.com) 及 CapCut 网页/协作分享 (capcut.cn)。"""

    DETAIL_API = "https://lv-api.ulikecam.com/lv/v1/web/replicate/multi_get_templates"
    CAPCUT_CLUSTER_API = "https://www.capcut.cn/lv/v1/coordination/cluster_list"
    CAPCUT_DETAIL_API = "https://www.capcut.cn/lv/v1/coordination/share_detail_query"
    USER_AGENT = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )

    def __init__(self, real_url):
        super().__init__(real_url)
        self.share_type, self.target_id, self.item_type = self._extract_params(real_url)
        self.template = self._fetch_media_data()

    @staticmethod
    def _extract_params(url):
        parsed = urlparse(url)
        # 1. 检查是否为 CapCut 网页/协作分享 (如 capcut.cn/share/:id)
        if "capcut" in parsed.netloc or "/share/" in parsed.path:
            match = re.search(r"/share/(\d+)", parsed.path)
            share_id = match.group(1) if match else ""
            return "capcut", share_id, 0

        # 2. 剪映标准模板分享 (如 lv.ulikecam.com/.../?template_id=xxx)
        query = parse_qs(parsed.query)
        template_id = (query.get("template_id") or [""])[0]
        item_type = (query.get("item_type") or ["0"])[0]
        try:
            item_type = int(item_type)
        except (TypeError, ValueError):
            item_type = 0
        return "jianying_template", template_id, item_type

    def _fetch_media_data(self):
        if self.share_type == "capcut":
            return self._fetch_capcut_share()
        return self._fetch_jianying_template()

    def _fetch_capcut_share(self):
        """解析 CapCut Web 端协作审阅分享 (两阶段 Cluster -> ShareDetail)。"""
        if not self.target_id:
            logger.warning("Unable to extract CapCut share_id from URL: %s", self.real_url)
            return {}

        timestamp = int(time.time())
        inner_share_id = self.target_id

        # 阶段 1：查询 Cluster 版本聚合列表
        try:
            url_path1 = "/lv/v1/coordination/cluster_list"
            sign1 = hashlib.md5(
                f"9e2c|{url_path1[-7:]}|7||{timestamp}||11ac".encode("utf-8")
            ).hexdigest().lower()
            headers1 = {
                "sign": sign1,
                "device-time": str(timestamp),
                "pf": "7",
                "sign-ver": "1",
                "User-Agent": self.USER_AGENT,
                "Content-Type": "application/json",
                "Origin": "https://www.capcut.cn",
                "Referer": self.real_url,
            }
            r1 = self.session.post(
                self.CAPCUT_CLUSTER_API,
                headers=headers1,
                json={"share_id": self.target_id, "password": ""},
                timeout=12,
            )
            if r1.status_code == 200:
                data1 = (r1.json().get("data") or {})
                share_list = data1.get("share_info_list") or []
                if share_list and isinstance(share_list[0], dict):
                    inner_share_id = share_list[0].get("share_id") or self.target_id
        except Exception as exc:
            logger.warning("CapCut cluster_list query failed: %s", exc)

        # 阶段 2：查询实际媒体详情并提取未加密的 normal_video 直链
        try:
            url_path2 = "/lv/v1/coordination/share_detail_query"
            sign2 = hashlib.md5(
                f"9e2c|{url_path2[-7:]}|7||{timestamp}||11ac".encode("utf-8")
            ).hexdigest().lower()
            headers2 = {
                "sign": sign2,
                "device-time": str(timestamp),
                "pf": "7",
                "sign-ver": "1",
                "User-Agent": self.USER_AGENT,
                "Content-Type": "application/json",
                "Origin": "https://www.capcut.cn",
                "Referer": self.real_url,
            }
            r2 = self.session.post(
                self.CAPCUT_DETAIL_API,
                headers=headers2,
                json={"share_id": inner_share_id},
                timeout=12,
            )
            r2.raise_for_status()
            data2 = (r2.json().get("data") or {})
            if not data2:
                return {}

            # 优先提取未加密的 normal_video 免防盗链流
            normal_v = data2.get("normal_video") or {}
            video_url = (
                (normal_v.get("player_720p") or {}).get("main_url")
                or (normal_v.get("player_480p") or {}).get("main_url")
                or (normal_v.get("player_360p") or {}).get("main_url")
            )
            # 降级尝试标准 video 字段
            if not video_url:
                v_obj = data2.get("video") or {}
                video_url = (
                    (v_obj.get("player_720p") or {}).get("main_url")
                    or (v_obj.get("player_480p") or {}).get("main_url")
                    or (v_obj.get("player_360p") or {}).get("main_url")
                )

            cover_obj = data2.get("cover_image") or {}
            cover_url = (
                cover_obj.get("preview_1080p_url")
                or cover_obj.get("preview_720p_url")
                or cover_obj.get("preview_360p_url")
                or ""
            )

            return {
                "video_url": video_url,
                "title": data2.get("file_name") or data2.get("share_name") or "CapCut视频",
                "cover_url": cover_url,
                "author": {
                    "name": data2.get("uploader_name", ""),
                    "id": str(data2.get("uploader_id", "")),
                    "avatar": "",
                },
                "duration": int(data2.get("duration", 0)) // 1000 if str(data2.get("duration", "0")).isdigit() else 0,
            }
        except Exception as exc:
            logger.warning("CapCut share_detail_query failed: %s", exc)
        return {}

    def _fetch_jianying_template(self):
        """解析剪映 App 移动端模板分享。"""
        if not self.target_id:
            logger.warning("Unable to extract Jianying template_id from URL: %s", self.real_url)
            return {}
        timestamp = int(time.time())
        sign = hashlib.md5(
            f"9e2c|mplates|0||{timestamp}||11ac".encode("utf-8")
        ).hexdigest()
        headers = {
            "sign": sign,
            "pf": "0",
            "sign-ver": "1",
            "device-time": str(timestamp),
            "User-Agent": self.USER_AGENT,
            "Content-Type": "application/json",
            "Origin": "https://lv.ulikecam.com",
            "Referer": "https://lv.ulikecam.com/",
        }
        try:
            response = self.session.post(
                self.DETAIL_API,
                headers=headers,
                json={
                    "sdk_version": "100.0.0",
                    "id": [self.target_id],
                    "scene": "share",
                    "item_type": self.item_type,
                },
                timeout=15,
            )
            response.raise_for_status()
            templates = ((response.json().get("data") or {}).get("templates") or [])
            if templates and isinstance(templates[0], dict):
                return templates[0]
            logger.warning("Jianying API returned no template for %s", self.target_id)
        except Exception as exc:
            logger.warning("Failed to fetch Jianying template: %s", exc)
        return {}

    def get_real_video_url(self):
        return self.template.get("video_url")

    def get_title_content(self):
        return self.template.get("title") or self.template.get("short_title") or "剪映模板"

    def get_cover_photo_url(self):
        return self.template.get("cover_url") or self.template.get("cover")

    def get_author_info(self):
        author = self.template.get("author") or {}
        aweme_info = author.get("aweme_info") or {}
        return {
            "nickname": author.get("name") or author.get("nickname") or aweme_info.get("name") or "",
            "author_id": str(
                author.get("uid") or author.get("id") or aweme_info.get("uid") or ""
            ),
            "avatar": (
                author.get("avatar")
                or author.get("avatar_url")
                or aweme_info.get("avatar_url")
                or ""
            ),
            "description": author.get("description") or "",
        }

    def get_audio_url(self):
        return ((self.template.get("music_info") or {}).get("play_url"))

    def get_image_list(self):
        return self.template.get("images") or []

    def get_video_list(self):
        video_url = self.get_real_video_url()
        return [video_url] if video_url else []

