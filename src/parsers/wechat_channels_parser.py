import os
import random
import re
from urllib.parse import parse_qs, quote, urlencode, urlparse

from configs.logging_config import get_logger
from src.parsers.base_parser import BaseParser


logger = get_logger(__name__)


class WeChatChannelsParser(BaseParser):
    """解析微信视频号分享链接，优先匿名请求，必要时使用元宝登录态兜底。"""

    FEED_INFO_API = "https://channels.weixin.qq.com/finder-preview/api/feed/get_feed_info"
    FEED_PAGE = "https://channels.weixin.qq.com/finder-preview/pages/feed"
    SPH_PAGE = "https://channels.weixin.qq.com/finder-preview/pages/sph"
    YUANBAO_API = "https://yuanbao.tencent.com/api/weixin/get_parse_result"
    USER_AGENT = (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"
    )
    def __init__(self, real_url):
        super().__init__(real_url)
        self.headers = {"User-Agent": self.USER_AGENT}
        self.data = self._empty_data()
        self._parse_once()

    @staticmethod
    def _empty_data():
        return {
            "title": "",
            "video_url": None,
            "video_list": [],
            "cover_url": None,
            "author": None,
            "image_list": [],
        }

    def _parse_once(self):
        try:
            cookie = os.getenv("YUANBAO_COOKIE", "").strip()
            if cookie:
                try:
                    self.data.update(self._parse_with_yuanbao(cookie))
                    return
                except Exception as exc:
                    # Cookie 过期时仍可返回无需鉴权的公开视频号数据。
                    logger.warning("视频号元宝解析失败，尝试匿名解析：%s", exc)

            self.data.update(self._parse_public())
        except Exception as exc:
            logger.warning("视频号解析失败：%s", exc)

    def _short_uri(self):
        match = re.search(r"(?:^|/)sph/([A-Za-z0-9]+)", urlparse(self.real_url).path)
        if match:
            return match.group(1)

        parsed = urlparse(self.real_url)
        short_uri = parse_qs(parsed.query).get("id", [""])[0]
        if short_uri:
            return short_uri

        response = self.session.get(self.real_url, headers=self.headers, allow_redirects=True, timeout=15)
        response.raise_for_status()
        short_uri = parse_qs(urlparse(response.url).query).get("id", [""])[0]
        if not short_uri:
            raise ValueError("链接不是可识别的视频号分享链接")
        return short_uri

    def _parse_public(self):
        short_uri = self._short_uri()
        result = self._feed_info(
            {"baseReq": {"generalToken": ""}, "shortUri": short_uri},
            referer=f"{self.SPH_PAGE}?id={quote(short_uri, safe='')}",
            page_url=self.SPH_PAGE,
        )
        return self._normalize_feed(result)

    def _parse_with_yuanbao(self, cookie):
        response = self.session.post(
            self.YUANBAO_API,
            json={"type": "video_channel_url", "url": self.real_url, "scene": 1},
            headers={
                "Accept": "application/json, text/plain, */*",
                "Content-Type": "application/json",
                "Origin": "https://yuanbao.tencent.com",
                "Referer": "https://yuanbao.tencent.com/chat",
                "User-Agent": self.USER_AGENT,
                "Cookie": cookie,
                "x-source": "web",
            },
            timeout=20,
        )
        response.raise_for_status()
        response_data = response.json()
        playable_url = (response_data.get("data") or {}).get("playable_url")
        if not playable_url:
            raise RuntimeError(response_data.get("msg") or "元宝未返回可播放地址")

        query = parse_qs(urlparse(playable_url).query)
        token = query.get("token", [""])[0]
        export_id = query.get("eid", [""])[0]
        if not token or not export_id:
            raise RuntimeError("元宝响应缺少视频号临时凭证")

        referer = self.FEED_PAGE + "?" + urlencode({
            "entry_card_type": 48,
            "comment_scene": 39,
            "appid": 0,
            "token": token,
            "entry_scene": 0,
            "eid": export_id,
        })
        result = self._feed_info(
            {"baseReq": {"generalToken": token}, "exportId": export_id},
            referer=referer,
            page_url=self.FEED_PAGE,
        )
        return self._normalize_feed(result)

    def _feed_info(self, payload, referer, page_url):
        request_id = f"{random.randrange(16**8):08x}"
        response = self.session.post(
            f"{self.FEED_INFO_API}?_rid={request_id}&_pageUrl={quote(page_url, safe='')}",
            json=payload,
            headers={
                "Accept": "application/json, text/plain, */*",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                "Content-Type": "application/json",
                "Origin": "https://channels.weixin.qq.com",
                "Referer": referer,
                "User-Agent": self.USER_AGENT,
            },
            timeout=20,
        )
        response.raise_for_status()
        result = response.json()
        if result.get("errCode") not in (0, None):
            raise RuntimeError(result.get("errMsg") or "视频号接口返回错误")
        return result

    @staticmethod
    def _normalize_feed(result):
        data = result.get("data") or {}
        feed = data.get("feedInfo") or {}
        author = data.get("authorInfo") or {}
        video_url = (
            feed.get("videoUrl")
            or (feed.get("h264VideoInfo") or {}).get("videoUrl")
            or (feed.get("h265VideoInfo") or {}).get("videoUrl")
        )
        return {
            "title": feed.get("description") or "视频号",
            "video_url": video_url,
            "video_list": [video_url] if video_url else [],
            "cover_url": feed.get("coverUrl"),
            "author": {
                "nickname": author.get("nickname") or "",
                "avatar": author.get("headImgUrl") or "",
                "author_id": author.get("id") or "",
            },
            "image_list": [],
        }

    def get_real_video_url(self):
        return self.data["video_url"]

    def get_video_list(self):
        return self.data["video_list"]

    def get_title_content(self):
        return self.data["title"]

    def get_cover_photo_url(self):
        return self.data["cover_url"]

    def get_author_info(self):
        return self.data["author"]
