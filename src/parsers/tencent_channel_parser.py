from src.parser_factory import register_parser
"""腾讯频道分享视频解析器。"""

import html
import json
import random
import re

from configs.general_constants import USER_AGENT_PC
from configs.logging_config import get_logger
from src.parsers.base_parser import BaseParser


logger = get_logger(__name__)

from py_mini_racer._mini_racer import MiniRacer


@register_parser("腾讯频道")
class TencentChannelParser(BaseParser):
    """解析腾讯频道页面，并处理 EdgeOne 的 JavaScript 挑战。"""

    def __init__(self, real_url):
        super().__init__(real_url)
        self.headers = {
            "User-Agent": random.choice(USER_AGENT_PC),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Referer": "https://pd.qq.com/",
        }
        self.title = ""
        self.video_url = None
        self.cover_url = None
        self.author = {"nickname": "", "author_id": "", "avatar": "", "guild_name": ""}
        self._parse_page()

    def _parse_page(self):
        try:
            response = self.session.get(
                self.real_url, headers=self.headers, allow_redirects=True, timeout=15
            )
            self.html_content = self._solve_waf_if_needed(response.text)
            self._extract_metadata()
        except Exception as exc:
            logger.warning("Failed to parse Tencent Channel page %s: %s", self.real_url, exc)

    def _solve_waf_if_needed(self, html_text):
        if not ("EO-Bot-Js-Token" in html_text or "Qua7lMrVs" in html_text):
            return html_text
        scripts = re.findall(r"<script[^>]*>(.*?)</script>", html_text, re.DOTALL)
        if not scripts:
            return html_text
        try:
            context = MiniRacer()
            location = json.dumps(self.real_url)
            stub = f"""
                var window = this;
                var location = {{href: {location}, search: '?b=2', pathname: '/s'}};
                var document = {{
                    createElement: function() {{ return {{setAttribute: function(){{}}, appendChild: function(){{}}}}; }},
                    getElementsByTagName: function() {{ return [{{appendChild: function(){{}}}}]; }},
                    head: {{appendChild: function(){{}}}}, body: {{appendChild: function(){{}}}}, cookie: ''
                }};
            """
            context.eval(stub + scripts[0])
            token = context.eval("r.token")
            cookie_name = context.eval("c") or "EO-Bot-Js-Token"
            if not token:
                return html_text
            response = self.session.get(
                self.real_url,
                headers=self.headers,
                cookies={str(cookie_name): str(token)},
                timeout=15,
            )
            return response.text if len(response.text) > len(html_text) else html_text
        except Exception as exc:
            logger.warning("Failed to bypass Tencent Channel WAF challenge: %s", exc)
            return html_text

    def _extract_metadata(self):
        for raw_data in re.findall(
            r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
            self.html_content,
            re.DOTALL,
        ):
            try:
                data = json.loads(raw_data)
            except json.JSONDecodeError:
                continue
            if not isinstance(data, dict):
                continue
            self.title = self.title or self._text(data.get("headline") or data.get("text"))
            author = data.get("author") or {}
            if isinstance(author, dict):
                self.author["nickname"] = self.author["nickname"] or self._text(author.get("name"))
                self.author["avatar"] = self.author["avatar"] or self._url(author.get("url")) or ""
            video = data.get("video") or {}
            if isinstance(video, dict):
                self.video_url = self.video_url or self._url(video.get("contentUrl"))
                self.cover_url = self.cover_url or self._url(video.get("thumbnailUrl"))

        self.title = self.title or self._text(self._match(r'<meta[^>]+property=["\']og:title["\'][^>]+content=["\'](.*?)["\']'))
        self.cover_url = self.cover_url or self._url(self._match(r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\'](.*?)["\']'))
        self.video_url = self.video_url or self._url(self._match_any([
            r"<video[^>]+src=[\"']([^\"']+)[\"']",
            r'"contentUrl"\s*:\s*"([^\"]+qchannelvideo[^\"]+)"',
            r'(https?://qchannelvideo\.photo\.qq\.com/[^"\'< >\s]+\.mp4[^"\'< >\s]*)',
        ]))
        self.author["nickname"] = self.author["nickname"] or self._text(self._match_any([
            r'"poster":\{.*?"nick":"([^\"]+)"', r"发帖作者:([^,，]+)",
        ]))
        self.author["avatar"] = self.author["avatar"] or self._url(self._match(r'"poster":\{.*?"avatar":"([^\"]+)"')) or ""
        self.author["author_id"] = self.author["author_id"] or self._text(self._match_any([
            r'"poster":\{.*?"str_tiny_id":"([^\"]+)"', r'"poster":\{.*?"tiny_id":([0-9]+)',
        ]))
        if self.title:
            guild = re.search(r"｜([^｜]+)｜腾讯频道", self.title)
            if guild:
                self.author["guild_name"] = guild.group(1).strip()

    def _match(self, pattern):
        match = re.search(pattern, self.html_content, re.I | re.S)
        return match.group(1) if match else None

    def _match_any(self, patterns):
        return next((value for pattern in patterns if (value := self._match(pattern))), None)

    @staticmethod
    def _text(value):
        return html.unescape(str(value)).strip() if value is not None else ""

    @classmethod
    def _url(cls, value):
        value = cls._text(value)
        return value.replace("\\/", "/").replace("&amp;", "&") if value else None

    def get_real_video_url(self):
        return self.video_url

    def get_title_content(self):
        return self.title

    def get_cover_photo_url(self):
        return self.cover_url

    def get_author_info(self):
        return self.author

    def get_video_list(self):
        return [self.video_url] if self.video_url else []
