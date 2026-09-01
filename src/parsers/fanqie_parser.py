import random
from src.parsers.base_parser import BaseParser
from src.parser_factory import register_parser
from utils.html_video_extractor import HtmlVideoExtractor
from configs.general_constants import USER_AGENT_M
from configs.logging_config import get_logger

logger = get_logger(__name__)


@register_parser("番茄短剧", "红果短剧", "畅读短剧", "鱼跃短剧")
class FanqieParser(BaseParser):
    """番茄短剧 / 畅读短剧 / 鱼跃短剧 推广页解析器"""

    def __init__(self, real_url):
        super().__init__(real_url)
        self.headers = {
            "content-type": "application/json; charset=UTF-8",
            "User-Agent": random.choice(USER_AGENT_M)
        }
        self.parsed_data = self._parse_html()

    def _parse_html(self):
        try:
            html = self.fetch_html_content()
            return HtmlVideoExtractor.parse_page(html)
        except Exception as e:
            logger.error(f"Failed to fetch or parse HTML for {self.real_url}: {e}")
            return {'title': None, 'video_url': None, 'cover_url': None, 'author': None}

    def get_real_video_url(self):
        return self.parsed_data.get('video_url')

    def get_title_content(self):
        return self.parsed_data.get('title') or ""

    def get_cover_photo_url(self):
        return self.parsed_data.get('cover_url') or ""

    def get_author_info(self):
        author_name = self.parsed_data.get('author')
        if author_name:
            return {'nickname': author_name}
        return {}
