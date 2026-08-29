from src.parser_factory import register_parser

import json
import random
import re
from urllib.parse import parse_qs, urlparse
from src.parsers.base_parser import BaseParser
from configs.general_constants import USER_AGENT_PC

@register_parser("全民K歌")
class QuanminkgeParser(BaseParser):
    def __init__(self, real_url):
        super().__init__(real_url)
        self.headers = {
            "User-Agent": random.choice(USER_AGENT_PC),
            "Referer": "https://kg.qq.com/",
        }
        self.data = self.fetch_html_data()

    def fetch_html_data(self):
        video_id = parse_qs(urlparse(self.real_url).query).get("s", [None])[0]
        if not video_id:
            return {}
        req_url = f"https://kg.qq.com/node/play?s={video_id}"
        try:
            resp = self.session.get(req_url, headers=self.headers, timeout=10)
            resp.raise_for_status()
        except Exception:
            return {}

        pattern = re.compile(r"window\.__DATA__\s*=\s*({.*?})\s*;\s*</script>", re.DOTALL)
        match = pattern.search(resp.text)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                return {}
        return {}
    def get_real_video_url(self):
        try: return self.data["detail"]["playurl_video"]
        except: return None
    def get_cover_photo_url(self):
        try: return self.data["detail"]["cover"]
        except: return None
    def get_title_content(self):
        try: return self.data["detail"]["content"]
        except: return None
