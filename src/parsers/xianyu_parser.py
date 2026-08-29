from src.parser_factory import register_parser
import re
from urllib.parse import parse_qs, urlparse

from configs.general_constants import USER_AGENT_M
from configs.logging_config import get_logger
from src.parsers.base_parser import BaseParser

logger = get_logger(__name__)


@register_parser("闲鱼")
class XianyuParser(BaseParser):
    """闲鱼/淘宝短链解析器，提取商品 ID、标价与真实目标链接。"""

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
        self.cover_url = None
        self.video_url = None
        self.image_list = []
        self.author = None
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
                self.item_id = (params.get("id") or [None])[0]
                self.price = (params.get("price") or [None])[0]

            if not self.item_id:
                parsed_real = urlparse(self.real_url)
                params_real = parse_qs(parsed_real.query)
                self.item_id = (params_real.get("id") or [None])[0]

            if self.target_url:
                self.image_list = [self.target_url]
                self.cover_url = self.target_url

            if self.item_id:
                if self.price:
                    self.title = f"闲鱼商品 (商品ID: {self.item_id}, 标价: ¥{self.price})"
                else:
                    self.title = f"闲鱼商品 (商品ID: {self.item_id})"

        except Exception as exc:
            logger.warning("Failed to parse Xianyu share URL: %s", exc)

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
