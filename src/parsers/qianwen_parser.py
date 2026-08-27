import json
import re

from configs.general_constants import USER_AGENT_M
from configs.logging_config import get_logger
from src.parsers.base_parser import BaseParser

logger = get_logger(__name__)


class QianwenParser(BaseParser):
    """通义千问（Qwen）AI 生成作品解析器。"""

    def __init__(self, real_url):
        super().__init__(real_url)
        self.headers = {
            "User-Agent": USER_AGENT_M[0],
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }
        self.title = None
        self.cover_url = None
        self.video_url = None
        self.video_list = []
        self.image_list = []
        self.author = None
        self._parse()

    def _parse(self):
        if not self.real_url:
            return
        try:
            resp = self.session.get(self.real_url, headers=self.headers, timeout=10)
            resp.raise_for_status()

            match = re.search(r"window\.__INITIAL_PROPS__\s*=\s*(\{.*?\});\s*</script>", resp.text, re.DOTALL)
            if not match:
                logger.warning("window.__INITIAL_PROPS__ not found in Qianwen page: %s", self.real_url)
                return

            data = json.loads(match.group(1))
            initial_data = data.get("initialData", {}).get("data", {})

            self.title = initial_data.get("title") or initial_data.get("shareSubtitle") or initial_data.get("shareTitle")

            creator = initial_data.get("creator") or initial_data.get("content", {}).get("creator", {})
            if isinstance(creator, dict) and creator:
                author_id = creator.get("authorId") or creator.get("uid")
                self.author = {
                    "nickname": creator.get("nick") or "",
                    "author_id": str(author_id) if author_id else "",
                    "avatar": creator.get("avatar") or "",
                }

            images_raw = initial_data.get("images") or []
            if not images_raw and initial_data.get("image"):
                images_raw = [initial_data["image"]]

            img_urls = []
            for img in images_raw:
                if isinstance(img, dict):
                    url = img.get("downloadUrl") or img.get("url")
                    if url:
                        img_urls.append(url)
                elif isinstance(img, str):
                    img_urls.append(img)

            self.image_list = list(dict.fromkeys(img_urls))
            if self.image_list:
                self.cover_url = self.image_list[0]

            play_info = initial_data.get("playInfo")
            if isinstance(play_info, dict):
                video_url = play_info.get("url") or play_info.get("downloadUrl")
                if video_url:
                    self.video_url = video_url
                    self.video_list = [video_url]

        except Exception as exc:
            logger.warning("Failed to parse Qianwen share page: %s", exc)

    def get_real_video_url(self):
        return self.video_url

    def get_video_list(self):
        return self.video_list

    def get_title_content(self):
        return self.title or ""

    def get_cover_photo_url(self):
        return self.cover_url

    def get_author_info(self):
        return self.author

    def get_image_list(self):
        return self.image_list
