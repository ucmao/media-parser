import hashlib
import json
import re
import time
from urllib.parse import parse_qs, urlparse

from configs.general_constants import USER_AGENT_M
from configs.logging_config import get_logger
from src.parser_factory import register_parser
from src.parsers.base_parser import BaseParser

logger = get_logger(__name__)


@register_parser("闲鱼")
class XianyuParser(BaseParser):
    """闲鱼/淘宝短链解析器，提取商品 ID、标题、描述、标价、原画图片列表与视频。"""

    def __init__(self, real_url):
        super().__init__(real_url)
        self.headers = {
            "User-Agent": USER_AGENT_M[0],
            "Referer": "https://e.tb.cn/",
        }
        self.item_id = None
        self.price = None
        self.target_url = None
        self.title = None
        self.desc = None
        self.cover_url = None
        self.video_url = None
        self.video_list = []
        self.image_list = []
        self.author = None
        self.terminal_detail = None
        self._parse()

    def _parse(self):
        if not self.real_url:
            return
        try:
            resp = self.session.get(self.real_url, headers=self.headers, timeout=10)
            resp.raise_for_status()

            match = re.search(r"var\s+url\s*=\s*'([^']+)'", resp.text)
            if match:
                self.target_url = match.group(1)
                parsed = urlparse(self.target_url)
                params = parse_qs(parsed.query)
                self.item_id = (params.get("id") or params.get("itemId") or [None])[0]
                self.price = (params.get("price") or [None])[0]

            if not self.item_id:
                parsed_real = urlparse(self.real_url)
                params_real = parse_qs(parsed_real.query)
                self.item_id = (
                    params_real.get("itemId")
                    or params_real.get("id")
                    or params_real.get("item_id")
                    or [None]
                )[0]
                if not self.price:
                    self.price = (params_real.get("price") or [None])[0]

            if not self.target_url and self.item_id:
                self.target_url = f"https://www.goofish.com/item?itemId={self.item_id}"

            if self.item_id:
                if self.price:
                    self.title = f"闲鱼商品 (商品ID: {self.item_id}, 标价: ¥{self.price})"
                else:
                    self.title = f"闲鱼商品 (商品ID: {self.item_id})"

            if self.item_id:
                self._fetch_item_detail(self.item_id)

        except Exception as exc:
            logger.warning("Failed to parse Xianyu share URL: %s", exc)

    def _fetch_item_detail(self, item_id):
        """调用闲鱼 H5 MTOP 接口获取商品真实媒体与图文元数据。"""
        # 1. 优先调用轻量级、免风控的 item.info 接口获取核心商品详情与原图相册
        self._fetch_via_item_info(item_id)

        # 2. 尝试从 awesome.detail 补充卖家昵称与视频直链（若触发风控静默忽略，不影响主流程）
        if not self.author or not self.video_url:
            self._try_fetch_awesome_detail(item_id)

    def _fetch_via_item_info(self, item_id):
        """调用闲鱼官方公共商品详情接口，提取高清图片、标题、描述与标价。"""
        app_key = "12574478"
        mtop_url = "https://h5api.m.goofish.com/h5/mtop.taobao.idle.item.info/1.0/"
        mtop_headers = {
            "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1",
            "Referer": "https://h5.m.goofish.com/",
            "Accept": "application/json",
        }
        data_str = json.dumps({"itemId": str(item_id)}, separators=(",", ":"))

        try:
            t = str(int(time.time() * 1000))
            self.session.get(
                mtop_url,
                params={
                    "jsv": "2.7.3",
                    "appKey": app_key,
                    "t": t,
                    "sign": "dummy",
                    "api": "mtop.taobao.idle.item.info",
                    "v": "1.0",
                    "type": "originaljson",
                    "dataType": "json",
                    "data": data_str,
                },
                headers=mtop_headers,
                timeout=5,
            )

            token_cookie = self.session.cookies.get("_m_h5_tk", "")
            token = token_cookie.split("_")[0] if token_cookie else ""
            t2 = str(int(time.time() * 1000))
            sign = hashlib.md5(f"{token}&{t2}&{app_key}&{data_str}".encode("utf-8")).hexdigest()

            req_params = {
                "jsv": "2.7.3",
                "appKey": app_key,
                "t": t2,
                "sign": sign,
                "api": "mtop.taobao.idle.item.info",
                "v": "1.0",
                "type": "originaljson",
                "dataType": "json",
                "data": data_str,
            }
            resp = self.session.get(mtop_url, params=req_params, headers=mtop_headers, timeout=10)
            try:
                result = resp.json()
            except Exception:
                return

            if not isinstance(result, dict):
                return

            ret = result.get("ret", [])
            ret_code = ret[0] if isinstance(ret, list) and ret else ""

            if "FAIL_BIZ_ITEM_DEL_NOT_FOUND" in ret_code or "FAIL_BIZ_ITEM_QUERY_FAILED" in ret_code:
                self.terminal_error = {
                    "detail_msg": "该宝贝不存在或已被卖家删除/下架",
                    "error_code": "ITEM_NOT_FOUND",
                }
                self.terminal_detail = self.terminal_error
                return

            if "RGV587_ERROR" in ret_code:
                from src.utils.parser_transport import report_cookie_required
                report_cookie_required()
                return

            data = result.get("data", {})
            if isinstance(data, dict):
                if data.get("title"):
                    self.title = data.get("title")
                if data.get("description"):
                    self.desc = data.get("description")
                if data.get("reservePrice"):
                    self.price = str(data.get("reservePrice"))

                images = []
                for img_info in data.get("imageInfos", []):
                    if isinstance(img_info, dict):
                        img_url = img_info.get("url")
                        if img_url:
                            if img_url.startswith("//"):
                                img_url = "https:" + img_url
                            elif img_url.startswith("http://"):
                                img_url = "https://" + img_url[7:]
                            img_url = re.sub(r"_[0-9]+x[0-9]+[a-z0-9]*\.(jpg|png|webp)$", "", img_url, flags=re.IGNORECASE)
                            images.append(img_url)

                if images:
                    self.image_list = images
                    self.cover_url = images[0]

                major_pic = data.get("absoluteMajorPicture")
                if major_pic:
                    if major_pic.startswith("//"):
                        major_pic = "https:" + major_pic
                    elif major_pic.startswith("http://"):
                        major_pic = "https://" + major_pic[7:]
                    self.cover_url = major_pic

        except Exception as exc:
            logger.warning("Failed to fetch Xianyu item.info via MTOP: %s", exc)

    def _try_fetch_awesome_detail(self, item_id):
        """尝试从 awesome.detail 补充卖家昵称与视频直链（若受风控限制静默忽略）。"""
        app_key = "12574478"
        mtop_url = "https://h5api.m.goofish.com/h5/mtop.taobao.idle.awesome.detail/1.0/"
        mtop_headers = {
            "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1",
            "Referer": "https://h5.m.goofish.com/",
            "Accept": "application/json",
        }
        data_str = json.dumps({"itemId": str(item_id)}, separators=(",", ":"))

        try:
            t = str(int(time.time() * 1000))
            self.session.get(
                mtop_url,
                params={
                    "jsv": "2.7.3",
                    "appKey": app_key,
                    "t": t,
                    "sign": "dummy",
                    "api": "mtop.taobao.idle.awesome.detail",
                    "v": "1.0",
                    "type": "originaljson",
                    "dataType": "json",
                    "data": data_str,
                },
                headers=mtop_headers,
                timeout=5,
            )

            token_cookie = self.session.cookies.get("_m_h5_tk", "")
            token = token_cookie.split("_")[0] if token_cookie else ""
            t2 = str(int(time.time() * 1000))
            sign = hashlib.md5(f"{token}&{t2}&{app_key}&{data_str}".encode("utf-8")).hexdigest()

            req_params = {
                "jsv": "2.7.3",
                "appKey": app_key,
                "t": t2,
                "sign": sign,
                "api": "mtop.taobao.idle.awesome.detail",
                "v": "1.0",
                "type": "originaljson",
                "dataType": "json",
                "data": data_str,
            }
            resp = self.session.get(mtop_url, params=req_params, headers=mtop_headers, timeout=5)
            result = resp.json()
            data = result.get("data", {})
            if isinstance(data, dict):
                seller_nick = self._extract_seller_nick(data)
                if seller_nick:
                    self.author = seller_nick

                video_url = self._extract_video_url(data)
                if video_url:
                    self.video_url = video_url
                    self.video_list = [video_url]

        except Exception:
            pass

    def _extract_seller_nick(self, data):
        """提取闲鱼卖家昵称，优先未脱敏昵称。"""
        seller_do = data.get("sellerDO", {})
        fallback_nick = seller_do.get("nick") if isinstance(seller_do, dict) else None

        flow_data = data.get("flowData", {})
        if isinstance(flow_data, dict):
            floating = flow_data.get("floating", {})
            if isinstance(floating, dict):
                for comp in floating.get("components", []):
                    if isinstance(comp, dict):
                        comp_data = comp.get("data", {})
                        if isinstance(comp_data, dict):
                            nick = comp_data.get("nick") or comp_data.get("userNick")
                            if nick and isinstance(nick, str) and "*" not in nick:
                                return nick

        return fallback_nick

    def _extract_video_url(self, data):
        """递归查找返回数据中的视频直链。"""
        def _search(obj):
            if isinstance(obj, dict):
                for k, v in obj.items():
                    if k in ("videoUrl", "mainVideoUrl", "video_url", "video") and isinstance(v, str) and v.startswith("http"):
                        return v
                    res = _search(v)
                    if res:
                        return res
            elif isinstance(obj, list):
                for item in obj:
                    res = _search(item)
                    if res:
                        return res
            return None

        video = _search(data)
        if video:
            if video.startswith("//"):
                video = "https:" + video
            elif video.startswith("http://"):
                video = "https://" + video[7:]
        return video

    def get_real_video_url(self):
        return self.video_url

    def get_video_list(self):
        return self.video_list

    def get_title_content(self):
        return self.title or ""

    def get_description(self):
        return self.desc

    def get_cover_photo_url(self):
        return self.cover_url

    def get_author_info(self):
        return self.author

    def get_image_list(self):
        return self.image_list

    def get_terminal_detail(self):
        return self.terminal_error or self.terminal_detail
