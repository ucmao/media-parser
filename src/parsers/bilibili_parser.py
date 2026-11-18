from src.parser_factory import register_parser
import random
import re

import requests

from configs.general_constants import USER_AGENT_PC
from configs.logging_config import get_logger
from src.parsers.base_parser import BaseParser
from utils.web_fetcher import UrlParser

logger = get_logger(__name__)


@register_parser("哔哩哔哩")
class BilibiliParser(BaseParser):
    """通过 B 站官方 API 获取可直接播放的单文件 MP4 地址及动态内容。"""

    API_VIEW = "https://api.bilibili.com/x/web-interface/view"
    API_PLAYURL = "https://api.bilibili.com/x/player/playurl"
    API_PGC_PLAYURL = "https://api.bilibili.com/pgc/player/web/playurl"
    API_DYNAMIC_DETAIL = "https://api.bilibili.com/x/polymer/web-dynamic/v1/detail"
    API_SEASON_VIEW = "https://api.bilibili.com/pgc/view/web/season"

    def __init__(self, real_url):
        super().__init__(real_url)
        self.headers = {
            "User-Agent": random.choice(USER_AGENT_PC),
            "Referer": "https://www.bilibili.com/",
        }
        # B站 web-interface/view 接口对浏览器标识在特定网络环境下会返回 412，单独使用客户端标识
        self.view_headers = {
            "User-Agent": "okhttp/4.9.3",
            "Referer": "https://www.bilibili.com/",
        }
        self.bvid = self._extract_bvid(real_url)
        self.aid = self._extract_aid(real_url) if not self.bvid else None
        self.ep_id = self._extract_ep_id(real_url)
        self.season_id = self._extract_season_id(real_url) if not self.ep_id else None
        self.dynamic_id = None if (self.bvid or self.aid or self.ep_id or self.season_id) else self._extract_dynamic_id(real_url)
        self.dynamic_info = {}
        self.season_info = {}
        self.bangumi_ep_info = {}

        if self.ep_id or self.season_id:
            self.season_info = self._fetch_season_info(self.ep_id, self.season_id)
            if self.season_info:
                all_eps = list(self.season_info.get("episodes", []))
                for sec in self.season_info.get("section", []):
                    all_eps.extend(sec.get("episodes", []))
                if self.ep_id:
                    self.bangumi_ep_info = next((e for e in all_eps if str(e.get("id")) == str(self.ep_id)), {})
                if not self.bangumi_ep_info and all_eps:
                    self.bangumi_ep_info = all_eps[0]
                if self.bangumi_ep_info.get("bvid"):
                    self.bvid = self.bangumi_ep_info.get("bvid")

        if not self.bvid and self.dynamic_id:
            self.dynamic_info = self._fetch_dynamic_info(self.dynamic_id)
            if bvid := self._extract_bvid_from_dynamic(self.dynamic_info):
                self.bvid = bvid

        self.video_info = self._fetch_video_info() if (self.bvid or self.aid) else {}
        self._play_info_by_cid = {}

    @staticmethod
    def _extract_bvid(url):
        """从 URL 中提取 BV 号，例如 ``BV1df421v7xm``。"""
        match = re.search(r"(BV[a-zA-Z0-9]+)", url or "")
        if match:
            return match.group(1)
        return None

    @staticmethod
    def _extract_aid(url):
        """从 URL 中提取 AV 号，例如 ``av117586188636547`` 或 ``aid=123``。"""
        match = re.search(r"(?:/video/av|aid=)(\d+)", url or "", re.IGNORECASE)
        if match:
            return match.group(1)
        return None

    @staticmethod
    def _extract_ep_id(url):
        """从 URL 中提取番剧/剧集 EP 号，例如 ``ep1231565``。"""
        match = re.search(r"(?:bangumi/play/ep|b23\.tv/ep|ep_id=)(\d+)", url or "")
        if match:
            return match.group(1)
        return None

    @staticmethod
    def _extract_season_id(url):
        """从 URL 中提取番剧 Season ID，例如 ``ss12345``。"""
        match = re.search(r"(?:bangumi/play/ss|season_id=)(\d+)", url or "")
        if match:
            return match.group(1)
        return None

    def _fetch_season_info(self, ep_id=None, season_id=None):
        """通过 PGC API 获取番剧/剧集 Season 详情。"""
        params = {}
        if ep_id:
            params["ep_id"] = ep_id
        elif season_id:
            params["season_id"] = season_id
        else:
            return {}

        try:
            response = self.session.get(
                self.API_SEASON_VIEW,
                params=params,
                headers=self.headers,
                timeout=10,
            )
            response.raise_for_status()
            result = response.json()
            if result.get("code") == 0:
                return result.get("result") or {}
            logger.warning("B站 PGC 接口返回错误: %s", result)
        except Exception as error:
            logger.error("B站 PGC 接口请求失败: %s", error)
        return {}

    @staticmethod
    def _extract_dynamic_id(url):
        """从 URL 中提取动态/Opus ID。"""
        match = re.search(r"(?:t\.bilibili\.com/|opus/|dynamic_id=)(\d{17,20})", url or "")
        if match:
            return match.group(1)
        logger.error("无法从 URL 中提取 BV 号或动态 ID: %s", url)
        return None

    def _fetch_dynamic_info(self, dynamic_id):
        """通过动态 API 获取动态详情。"""
        if not dynamic_id:
            return {}
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Referer": "https://t.bilibili.com/",
            }
            response = self.session.get(
                self.API_DYNAMIC_DETAIL,
                params={"id": dynamic_id},
                headers=headers,
                timeout=10,
            )
            response.raise_for_status()
            result = response.json()
        except (requests.RequestException, ValueError) as error:
            logger.error("B站动态 API 请求失败: %s", error)
            return {}

        if result.get("code") == 0:
            return result.get("data", {}).get("item") or {}
        code = result.get("code")
        msg = result.get("message") or ""
        if code in (4101152, 4101153) or "不可见" in msg or "不存在" in msg:
            self.terminal_error = {
                "error_code": "MEDIA_DELETED_OR_PRIVATE",
                "detail_msg": "该B站动态不存在、已被删除或不可见",
            }
        logger.error(
            "B站动态 API 返回错误: code=%s, message=%s",
            result.get("code"),
            result.get("message"),
        )
        return {}

    @staticmethod
    def _extract_bvid_from_dynamic(dynamic_info):
        """从动态详情数据中提取关联的视频 BV 号。"""
        major = (
            dynamic_info.get("modules", {})
            .get("module_dynamic", {})
            .get("major", {})
        )
        if major.get("type") == "MAJOR_TYPE_ARCHIVE":
            return major.get("archive", {}).get("bvid")
        return None

    def _fetch_video_info(self):
        if not self.bvid and not getattr(self, "aid", None):
            return {}
        params = {"bvid": self.bvid} if self.bvid else {"aid": self.aid}
        try:
            response = self.session.get(
                self.API_VIEW,
                params=params,
                headers=self.view_headers,
                timeout=10,
            )
            response.raise_for_status()
            result = response.json()
        except (requests.RequestException, ValueError) as error:
            logger.error("B站 API 视频信息请求失败: %s", error)
            return {}

        if result.get("code") == 0:
            data = result.get("data") or {}
            if not self.bvid and data.get("bvid"):
                self.bvid = data["bvid"]
            return data

        code = result.get("code")
        msg = result.get("message") or ""
        if code in (62002, 62004, -404) or "不可见" in msg or "不存在" in msg:
            self.terminal_error = {
                "error_code": "MEDIA_DELETED_OR_PRIVATE",
                "detail_msg": "该B站稿件不存在、已被作者删除或不可见",
            }
        logger.error(
            "B站 API 返回错误: code=%s, message=%s",
            code,
            msg,
        )
        return {}

    def _fetch_play_info(self, cid):
        """获取包含音视频的 durl 单文件流，不下载或转封装媒体。"""
        if not cid:
            return {}
        if cid in self._play_info_by_cid:
            return self._play_info_by_cid[cid]

        # 1. 优先尝试番剧 / PGC 播放地址接口
        if self.bangumi_ep_info or self.season_info:
            try:
                ep_id = self.bangumi_ep_info.get("id") or self.ep_id
                params = {
                    "otype": "json",
                    "qn": 80,
                    "fnval": 1,
                    "cid": cid,
                }
                if ep_id:
                    params["ep_id"] = ep_id
                if self.bvid:
                    params["bvid"] = self.bvid
                response = self.session.get(
                    self.API_PGC_PLAYURL,
                    params=params,
                    headers=self.headers,
                    timeout=10,
                )
                response.raise_for_status()
                result = response.json()
                if result.get("code") == 0:
                    play_info = result.get("result") or result.get("data") or {}
                    if play_info.get("durl"):
                        self._play_info_by_cid[cid] = play_info
                        return play_info
            except Exception as error:
                logger.warning("B站 PGC 播放接口请求失败: %s", error)

        # 2. 常规 UGC 视频播放接口
        if not self.bvid:
            return {}

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
            code = result.get("code")
            if code == 87008 or "充电" in str(result.get("message")):
                self.terminal_error = {
                    "error_code": "MEDIA_DELETED_OR_PRIVATE",
                    "detail_msg": "该视频为B站充电专属或付费视频，无法直接提取",
                }
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
        if self.bangumi_ep_info and self.bangumi_ep_info.get("cid"):
            return [{"cid": self.bangumi_ep_info["cid"], "page": 1, "part": self.bangumi_ep_info.get("title") or ""}]
        return self.video_info.get("pages") or []

    def _get_dynamic_pics(self):
        if not self.dynamic_info:
            return []
        major = (
            self.dynamic_info.get("modules", {})
            .get("module_dynamic", {})
            .get("major", {})
        )
        pics = []
        if opus := major.get("opus"):
            for pic in opus.get("pics") or []:
                if url := pic.get("url"):
                    pics.append(url)
        elif draw := major.get("draw"):
            for item in draw.get("items") or []:
                if url := item.get("src"):
                    pics.append(url)
        return pics

    def get_title_content(self):
        if self.season_info and self.bangumi_ep_info:
            s_title = self.season_info.get("title", "")
            ep_title = self.bangumi_ep_info.get("title", "")
            ep_long = self.bangumi_ep_info.get("long_title", "")
            full_title = f"{s_title} {ep_title} {ep_long}".strip()
            if full_title:
                return full_title
        if self.video_info:
            return self.video_info.get("title") or None
        if self.dynamic_info:
            modules = self.dynamic_info.get("modules", {})
            dynamic_mod = modules.get("module_dynamic", {})
            major = dynamic_mod.get("major", {})
            if opus := major.get("opus"):
                return opus.get("title") or None
        return None

    def get_description(self):
        if self.season_info:
            return self.season_info.get("evaluate") or self.season_info.get("subtitle") or self.video_info.get("desc") or None
        if self.video_info:
            return self.video_info.get("desc") or None
        if self.dynamic_info:
            dynamic_mod = self.dynamic_info.get("modules", {}).get("module_dynamic", {})
            major = dynamic_mod.get("major", {})
            if opus := major.get("opus"):
                return opus.get("summary", {}).get("text") or dynamic_mod.get("desc", {}).get("text") or None
            return dynamic_mod.get("desc", {}).get("text") or None
        return None

    def get_cover_photo_url(self):
        if self.bangumi_ep_info:
            cover = self.bangumi_ep_info.get("cover") or self.season_info.get("cover", "")
            if cover:
                return cover
        if self.video_info:
            return self.video_info.get("pic", "")
        if self.dynamic_info:
            pics = self._get_dynamic_pics()
            if pics:
                return pics[0]
        return ""

    def get_author_info(self):
        if self.season_info and self.season_info.get("up_info"):
            up = self.season_info["up_info"]
            avatar = up.get("avatar", "")
            if avatar.startswith("//"):
                avatar = "https:" + avatar
            return {
                "nickname": up.get("uname", ""),
                "author_id": str(up.get("mid", "")),
                "avatar": avatar,
            }
        if self.video_info:
            owner = self.video_info.get("owner") or {}
            avatar = owner.get("face", "")
            if avatar.startswith("//"):
                avatar = "https:" + avatar
            return {
                "nickname": owner.get("name", ""),
                "author_id": str(owner.get("mid", "")),
                "avatar": avatar,
            }
        if self.dynamic_info:
            author = (
                self.dynamic_info.get("modules", {})
                .get("module_author", {})
            )
            avatar = author.get("face", "")
            if avatar.startswith("//"):
                avatar = "https:" + avatar
            return {
                "nickname": author.get("name", ""),
                "author_id": str(author.get("mid", "")),
                "avatar": avatar,
            }
        return {"nickname": "", "author_id": "", "avatar": ""}

    def get_real_video_url(self):
        """返回首个分 P 的 B 站 CDN MP4 直链；该文件已包含音轨。"""
        pages = self._get_pages()
        if not pages:
            return None
        return self._get_durl(self._fetch_play_info(pages[0].get("cid")))

    def get_video_list(self):
        """返回多分 P 视频的 CDN MP4 直链，单分 P 保持旧响应结构。"""
        if self.video_info:
            pages = self._get_pages()
            if len(pages) <= 1:
                return []
            return [
                url
                for page in pages
                if (url := self._get_durl(self._fetch_play_info(page.get("cid"))))
            ]
        return []

    def get_image_list(self):
        """返回动态或 Opus 帖中的原始图片列表。"""
        return self._get_dynamic_pics()

    def get_audio_url(self):
        """durl 单文件已内嵌音轨，无需再下载 DASH 音频或调用 FFmpeg。"""
        return None
