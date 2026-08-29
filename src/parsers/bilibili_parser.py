from src.parser_factory import register_parser
import random
import re

import requests

from configs.general_constants import USER_AGENT_PC
from configs.logging_config import get_logger
from src.parsers.base_parser import BaseParser

logger = get_logger(__name__)


@register_parser("哔哩哔哩")
class BilibiliParser(BaseParser):
    """通过 B 站官方 API 获取可直接播放的单文件 MP4 地址。"""

    API_VIEW = "https://api.bilibili.com/x/web-interface/view"
    API_PLAYURL = "https://api.bilibili.com/x/player/playurl"

    def __init__(self, real_url):
        super().__init__(real_url)
        self.headers = {
            "User-Agent": random.choice(USER_AGENT_PC),
            "Referer": "https://www.bilibili.com/",
        }
        self.bvid = self._extract_bvid(real_url)
        self.video_info = self._fetch_video_info()
        self._play_info_by_cid = {}

    @staticmethod
    def _extract_bvid(url):
        """从 URL 中提取 BV 号，例如 ``BV1df421v7xm``。"""
        match = re.search(r"(BV[a-zA-Z0-9]+)", url or "")
        if match:
            return match.group(1)
        logger.error("无法从 URL 中提取 BV 号: %s", url)
        return None

    def _fetch_video_info(self):
        if not self.bvid:
            return {}
        try:
            response = self.session.get(
                self.API_VIEW,
                params={"bvid": self.bvid},
                headers=self.headers,
                timeout=10,
            )
            response.raise_for_status()
            result = response.json()
        except (requests.RequestException, ValueError) as error:
            logger.error("B站 API 视频信息请求失败: %s", error)
            return {}

        if result.get("code") == 0:
            return result.get("data") or {}
        logger.error(
            "B站 API 返回错误: code=%s, message=%s",
            result.get("code"),
            result.get("message"),
        )
        return {}

    def _fetch_play_info(self, cid):
        """获取包含音视频的 durl 单文件流，不下载或转封装媒体。"""
        if not self.bvid or not cid:
            return {}
        if cid in self._play_info_by_cid:
            return self._play_info_by_cid[cid]

        try:
            response = self.session.get(
                self.API_PLAYURL,
                params={
                    "otype": "json",
                    "fnver": 0,
                    "fnval": 3,
                    "player": 3,
                    "qn": 112,
                    "bvid": self.bvid,
                    "cid": cid,
                    "platform": "html5",
                    "high_quality": 1,
                },
                headers=self.headers,
                timeout=10,
            )
            response.raise_for_status()
            result = response.json()
        except (requests.RequestException, ValueError) as error:
            logger.error("B站 API 播放地址请求失败: %s", error)
            return {}

        if result.get("code") != 0:
            logger.error(
                "B站 API playurl 返回错误: code=%s, message=%s",
                result.get("code"),
                result.get("message"),
            )
            return {}

        play_info = result.get("data") or {}
        self._play_info_by_cid[cid] = play_info
        return play_info

    @staticmethod
    def _get_durl(play_info):
        durls = play_info.get("durl") or []
        if not durls:
            return None
        return durls[0].get("url")

    def _get_pages(self):
        return self.video_info.get("pages") or []

    def get_title_content(self):
        return self.video_info.get("title", "")

    def get_cover_photo_url(self):
        return self.video_info.get("pic", "")

    def get_author_info(self):
        owner = self.video_info.get("owner") or {}
        avatar = owner.get("face", "")
        if avatar.startswith("//"):
            avatar = "https:" + avatar
        return {
            "nickname": owner.get("name", ""),
            "author_id": str(owner.get("mid", "")),
            "avatar": avatar,
        }

    def get_real_video_url(self):
        """返回首个分 P 的 B 站 CDN MP4 直链；该文件已包含音轨。"""
        pages = self._get_pages()
        if not pages:
            return None
        return self._get_durl(self._fetch_play_info(pages[0].get("cid")))

    def get_video_list(self):
        """返回多分 P 视频的 CDN MP4 直链，单分 P 保持旧响应结构。"""
        pages = self._get_pages()
        if len(pages) <= 1:
            return []
        return [
            url
            for page in pages
            if (url := self._get_durl(self._fetch_play_info(page.get("cid"))))
        ]

    def get_audio_url(self):
        """durl 单文件已内嵌音轨，无需再下载 DASH 音频或调用 FFmpeg。"""
        return None
