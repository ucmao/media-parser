import json
import os
import random
import re
import string
from urllib.parse import parse_qs, unquote, urlparse

from configs.general_constants import USER_AGENT_M
from configs.logging_config import get_logger
from src.parser_factory import register_parser
from src.parsers.base_parser import BaseParser
from utils.signer.pinduoduo.anti_signer import AntiSigner

logger = get_logger(__name__)


@register_parser("拼多多")
class PinduoduoParser(BaseParser):
    """拼多多 / 多多视频 / 商品与评价秀解析器。

    支持：
    1. 多多视频 (feed_id) 原画视频与作者、封面提取（支持 PINDUODUO_COOKIE 配置）。
    2. 商品分享与评价秀短链 (_oak_share_url, goods_id, review_id) 高清实物图与元数据提取。
    3. 商品页面 SSR window.rawData 数据解析。
    """

    def __init__(self, real_url):
        super().__init__(real_url)
        cookie = os.getenv("PINDUODUO_COOKIE", "").strip()

        self.headers = {
            "User-Agent": USER_AGENT_M[0],
            "Referer": "https://mobile.yangkeduo.com/",
            "Accept": "application/json, text/plain, */*",
        }
        if cookie:
            self.headers["Cookie"] = cookie

        self.video_url = None
        self.video_list = []
        self.cover_url = None
        self.title = None
        self.author = None
        self.image_list = []
        self.audio_url = None

        self.feed_id = None
        self.goods_id = None
        self.review_id = None
        self.ps = None
        self._oak_share_url = None

        self._parse()

    def _parse(self):
        if not self.real_url:
            return

        parsed = urlparse(self.real_url)
        params = parse_qs(parsed.query)

        self.feed_id = (params.get("feed_id") or [None])[0]
        self.goods_id = (params.get("goods_id") or [None])[0]
        self.review_id = (params.get("review_id") or [None])[0]
        self.ps = (params.get("ps") or [None])[0]
        raw_oak = (params.get("_oak_share_url") or [None])[0]
        if raw_oak:
            self._oak_share_url = unquote(raw_oak)

        # 1. 优先提取链接中携带的实物/商品高清图片素材
        if self._oak_share_url:
            self.image_list.append(self._oak_share_url)
            self.cover_url = self._oak_share_url
            if self.goods_id:
                if self.review_id:
                    self.title = f"拼多多评价分享 (商品ID: {self.goods_id}, 评价ID: {self.review_id})"
                else:
                    self.title = f"拼多多商品 (商品ID: {self.goods_id})"

        # 2. 如果包含 feed_id，按多多视频 (Duoduo Video) 进行解析
        if self.feed_id:
            self._parse_duoduo_video()

        # 3. 若仍无视频或图集，尝试解析商品详情与页面 SSR 数据
        if not self.video_url and not self.image_list:
            self._parse_goods_detail()

        # 4. 保障默认兜底字段
        if self.image_list and not self.cover_url:
            self.cover_url = self.image_list[0]

        if not self.title:
            if self.goods_id:
                if self.review_id:
                    self.title = f"拼多多评价分享 (商品ID: {self.goods_id}, 评价ID: {self.review_id})"
                else:
                    self.title = f"拼多多商品 (商品ID: {self.goods_id})"
            elif self.feed_id:
                self.title = f"多多视频 (FeedID: {self.feed_id})"
            elif self.ps:
                self.title = f"拼多多分享 (短链: {self.ps})"

    def _parse_duoduo_video(self):
        """调用多多视频 API 获取视频播放地址、封面、标题与作者。"""
        signer = AntiSigner()
        anti_content = signer.get_anti_content()
        cookie = os.getenv("PINDUODUO_COOKIE", "").strip()

        list_id = "".join(random.choices(string.ascii_letters + string.digits, k=10))
        payload = {
            "base": {
                "scene_id": "55",
                "mode": 0,
                "direction": 0,
                "list_id": list_id,
                "ext": json.dumps({
                    "feed_id_list": [self.feed_id],
                    "page_from": "602100",
                    "load_author": True,
                    "load_data": True,
                    "url": self.real_url,
                }),
            },
            "anti_content": anti_content,
        }

        api_headers = {
            "Content-Type": "application/json;charset=UTF-8",
            "User-Agent": self.headers["User-Agent"],
            "Referer": self.real_url,
            "Origin": "https://mobile.yangkeduo.com",
            "anti-content": anti_content,
        }
        if cookie:
            api_headers["Cookie"] = cookie

        endpoints = [
            "https://mobile.yangkeduo.com/proxy/api/api/hub/dsp_detail/weak/list/get",
            "https://api.pinduoduo.com/api/hub/dsp_detail/weak/list/get",
        ]

        for endpoint in endpoints:
            try:
                resp = self.session.post(endpoint, json=payload, headers=api_headers, timeout=10)
                if resp.status_code == 200 and resp.text:
                    data = resp.json()
                    feeds = data.get("result", {}).get("feeds", [])
                    if feeds:
                        feed_data = feeds[0].get("data", {})
                        title = (
                            feed_data.get("feedTitle")
                            or feed_data.get("title")
                            or feed_data.get("feedDesc")
                            or feed_data.get("desc")
                            or feed_data.get("goods_v2", {}).get("goods_info", {}).get("goods_name")
                        )
                        if title:
                            self.title = str(title).strip()

                        # 从 feedMedia 提取视频与封面
                        for media in feed_data.get("feedMedia", []):
                            media_type = media.get("mediaType")
                            url = media.get("url") or media.get("playUrl")
                            if media_type == 1 and url and not self.video_url:
                                self.video_url = url
                            elif media_type == 2 and url and not self.cover_url:
                                self.cover_url = url

                        # 字段兜底（兼容实际 API 字段 h5_auto_play_url / native_auto_play_url / playUrl / linkUrl）
                        if not self.video_url:
                            self.video_url = (
                                feed_data.get("h5_auto_play_url")
                                or feed_data.get("native_auto_play_url")
                                or feed_data.get("playUrl")
                                or feed_data.get("linkUrl")
                            )
                        if not self.cover_url:
                            self.cover_url = (
                                feed_data.get("cover")
                                or feed_data.get("blur_cover")
                                or feed_data.get("thumbUrl")
                            )

                        # 作者信息（兼容 author_info 及 authorInfo）
                        author_info = feed_data.get("author_info") or feed_data.get("authorInfo") or {}
                        if author_info:
                            self.author = {
                                "nickname": author_info.get("authorName") or author_info.get("nickname") or "",
                                "avatar": author_info.get("avatar") or "",
                                "author_id": str(
                                    author_info.get("authorId")
                                    or author_info.get("mallId")
                                    or author_info.get("room_id")
                                    or ""
                                ),
                            }
                        return
                elif resp.status_code in (403, 424):
                    logger.warning(
                        f"Pinduoduo dsp_detail API requires authentication (HTTP {resp.status_code})."
                    )
            except Exception as e:
                logger.warning(f"Failed to request dsp_detail endpoint {endpoint}: {e}")

    def _parse_goods_detail(self):
        """解析页面内可能注入的 SSR 数据 (window.rawData) 或调用商品渲染 API。"""
        html = self.fetch_html_content()
        if html:
            match = re.search(r"window\.rawData\s*=\s*(\{.*?\});\s*</script>", html, re.DOTALL)
            if match:
                try:
                    raw_data = json.loads(match.group(1))
                    init_data = raw_data.get("store", {}).get("initDataObj", {})
                    goods = init_data.get("goods", {})
                    if goods:
                        if not self.title and goods.get("goods_name"):
                            self.title = goods.get("goods_name")
                        banner = goods.get("banner") or goods.get("gallery") or goods.get("top_gallery") or []
                        for item in banner:
                            img_url = item if isinstance(item, str) else (item.get("url") if isinstance(item, dict) else None)
                            if img_url and img_url not in self.image_list:
                                self.image_list.append(img_url)
                        video = goods.get("video")
                        if video:
                            if isinstance(video, dict):
                                self.video_url = video.get("url") or video.get("play_url")
                            elif isinstance(video, str):
                                self.video_url = video
                        if not self.cover_url:
                            self.cover_url = goods.get("hd_thumb_url") or goods.get("thumb_url")
                except Exception as exc:
                    logger.debug(f"Failed to parse rawData in goods HTML: {exc}")

    def get_real_video_url(self):
        return self.video_url

    def get_title_content(self):
        return self.title or ""

    def get_cover_photo_url(self):
        return self.cover_url

    def get_author_info(self):
        return self.author

    def get_image_list(self):
        return self.image_list

    def get_audio_url(self):
        return self.audio_url

    def get_video_list(self):
        if self.video_url:
            return [self.video_url]
        return self.video_list
