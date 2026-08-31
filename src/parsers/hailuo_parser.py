from src.parser_factory import register_parser
"""海螺AI（Hailuo AI / MiniMax）视频与作品分享解析器。"""

import json
import re

from configs.general_constants import USER_AGENT_PC
from configs.logging_config import get_logger
from src.parsers.base_parser import BaseParser

logger = get_logger(__name__)


@register_parser("海螺AI")
class HailuoParser(BaseParser):
    """海螺AI（MiniMax）视频与作品分享解析器。

    支持解析 https://hailuoai.com/share/ai-video/{id} 等公开分享链接。
    优先提取去除品牌大标的水印优化直链（downloadURLWithAIWatermark / downloadURL）。
    """

    def __init__(self, real_url):
        super().__init__(real_url)
        self.headers = {
            "User-Agent": USER_AGENT_PC[0],
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
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
        html_content = self.fetch_html_content()
        if not html_content:
            return

        # 1. 优先从 Next.js Flight SSR 数据流中提取 videoAsset
        asset = self._extract_flight_video_asset(html_content)
        if asset:
            self._apply_video_asset(asset)
            return

        # 2. 兜底从 JSON-LD (application/ld+json) 中提取 VideoObject
        ld_video = self._extract_ld_json_video(html_content)
        if ld_video:
            self._apply_ld_video(ld_video)

    def _extract_flight_video_asset(self, html_content):
        # 匹配 self.__next_f.push([1, "..."])
        pushes = re.findall(r"self\.__next_f\.push\(\[1,\s*\"(.*?)\"\]\)", html_content, re.DOTALL)
        for chunk in pushes:
            try:
                decoded = json.loads(f'"{chunk}"')
                if "videoAsset" in decoded:
                    idx = decoded.find(":")
                    if idx != -1:
                        json_str = decoded[idx + 1 :]
                        try:
                            data = json.loads(json_str)
                            asset = self._find_key_in_tree(data, "videoAsset")
                            if isinstance(asset, dict):
                                return asset
                        except Exception:
                            pass
            except Exception:
                continue

        # 兜底：直接在 HTML 中用正则匹配提取 videoAsset JSON 块
        match = re.search(r"\"videoAsset\":\s*(\{.+?\})(?:,\s*\"[a-zA-Z0-9_-]+\":|\]|\})", html_content)
        if match:
            try:
                asset_str = match.group(1).encode("utf-8").decode("unicode_escape", errors="ignore")
                return json.loads(asset_str)
            except Exception:
                pass

        return None

    def _find_key_in_tree(self, obj, target_key):
        if isinstance(obj, dict):
            for k, v in obj.items():
                if k == target_key and isinstance(v, dict):
                    return v
                res = self._find_key_in_tree(v, target_key)
                if res is not None:
                    return res
        elif isinstance(obj, list):
            for item in obj:
                res = self._find_key_in_tree(item, target_key)
                if res is not None:
                    return res
        return None

    def _apply_video_asset(self, asset):
        # 1. 提取标题 / 描述
        self.title = asset.get("title") or asset.get("desc") or "海螺AI 作品"

        # 2. 提取视频直链（优先提取去除品牌大标的直链）
        video_urls_obj = asset.get("videoURLs") or {}
        candidate_video = (
            video_urls_obj.get("downloadURLWithAIWatermark")
            or asset.get("downloadURL")
            or asset.get("videoURL")
            or video_urls_obj.get("downloadURLWithHailuoWatermark")
        )
        if candidate_video:
            self.video_url = candidate_video
            self.video_list = [candidate_video]

        # 3. 提取封面
        self.cover_url = asset.get("coverURL") or asset.get("promptImgURL")

        # 4. 提取作者信息
        user_id = asset.get("userIDStr") or asset.get("userID")
        if user_id:
            self.author = {
                "nickname": "",
                "author_id": str(user_id),
                "avatar": "",
                "description": "",
            }

        # 5. 提取参考图/素材图
        origin_files = asset.get("originFiles") or []
        images = []
        for item in origin_files:
            if isinstance(item, dict):
                url = item.get("url") or item.get("coverUrl")
                if url and url not in images:
                    images.append(url)
        self.image_list = images

    def _extract_ld_json_video(self, html_content):
        matches = re.finditer(
            r"<script[^>]*type=[\"']application/ld\+json[\"'][^>]*>(.*?)</script>",
            html_content,
            re.DOTALL,
        )
        for m in matches:
            raw = m.group(1).strip()
            # 兼容嵌套在 next_s push 中的场景
            if "children" in raw:
                c_match = re.search(r"\"children\":\s*(\".*?\")\s*\}\]\)", raw)
                if c_match:
                    try:
                        raw = json.loads(c_match.group(1))
                    except Exception:
                        pass
            try:
                data = json.loads(raw)
                graph = data.get("@graph", [data]) if isinstance(data, dict) else [data]
                for item in graph:
                    if isinstance(item, dict) and item.get("@type") == "VideoObject":
                        return item
            except Exception:
                continue
        return None

    def _apply_ld_video(self, ld_video):
        self.title = ld_video.get("description") or ld_video.get("name") or "海螺AI 作品"
        self.video_url = ld_video.get("contentUrl")
        if self.video_url:
            self.video_list = [self.video_url]
        self.cover_url = ld_video.get("thumbnailUrl")
        author_data = ld_video.get("author")
        if isinstance(author_data, dict):
            self.author = {
                "nickname": (author_data.get("name") or "").strip(),
                "author_id": "",
                "avatar": "",
                "description": "",
            }

    def get_real_video_url(self):
        return self.video_url

    def get_title_content(self):
        return self.title or "海螺AI 作品"

    def get_cover_photo_url(self):
        return self.cover_url

    def get_author_info(self):
        return self.author

    def get_image_list(self):
        return self.image_list

    def get_video_list(self):
        return self.video_list
