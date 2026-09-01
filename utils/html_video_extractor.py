import re
import json
from html import unescape
from typing import Dict, Any, Optional
from configs.logging_config import get_logger

logger = get_logger(__name__)


class HtmlVideoExtractor:
    """通用网页 HTML 视频及元数据提取助手类"""

    @classmethod
    def parse_page(cls, html: str) -> Dict[str, Any]:
        """解析页面 HTML，返回统一的元数据字典:
        {
            'title': str or None,
            'video_url': str or None,
            'cover_url': str or None,
            'author': str or None
        }
        """
        result = {
            'title': None,
            'video_url': None,
            'cover_url': None,
            'author': None
        }

        if not html or not isinstance(html, str):
            return result

        # 1. 优先从 window._ROUTER_DATA 或 window._SSR_DATA 等 JSON 数据块提取
        json_data = cls._extract_router_json(html)
        if json_data:
            extracted = cls._extract_from_json_dict(json_data)
            result.update({k: v for k, v in extracted.items() if v})

        # 2. 从 HTML Meta 标签提取补全
        meta_data = cls._extract_from_meta(html)
        for k, v in meta_data.items():
            if not result.get(k) and v:
                result[k] = v

        # 3. 规范化并清洗 URL
        if result['video_url']:
            result['video_url'] = cls._clean_url(result['video_url'])
        if result['cover_url']:
            result['cover_url'] = cls._clean_url(result['cover_url'])

        return result

    @classmethod
    def _extract_router_json(cls, html: str) -> Optional[Dict[str, Any]]:
        """从 script 标签提取 window._ROUTER_DATA 或 window._SSR_DATA 对象"""
        patterns = [
            r'window\._ROUTER_DATA\s*=\s*(\{.*?\});\s*</script>',
            r'window\._ROUTER_DATA\s*=\s*(\{.*?\});',
            r'window\._SSR_DATA\s*=\s*(\{.*?\});\s*</script>',
            r'window\._SSR_DATA\s*=\s*(\{.*?\});'
        ]
        for pattern in patterns:
            match = re.search(pattern, html, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group(1))
                except Exception as e:
                    logger.debug(f"JSON loads failed for pattern {pattern}: {e}")

        # 备选：查找 script 内包含 play_url 的 JSON 对象
        json_matches = re.findall(r'<script[^>]*>\s*(?:var\s+)?(?:window\.\w+\s*=\s*)?(\{.*?\})\s*;?\s*</script>', html, re.DOTALL)
        for jstr in json_matches:
            if 'play_url' in jstr or 'video_url' in jstr or 'series_data' in jstr:
                try:
                    return json.loads(jstr)
                except Exception:
                    continue

        return None

    @classmethod
    def _extract_from_json_dict(cls, data: Any) -> Dict[str, Any]:
        """递归检索 JSON 字典获取视频关键字段"""
        result = {'title': None, 'video_url': None, 'cover_url': None, 'author': None}

        def search_dict(obj):
            if isinstance(obj, dict):
                # 匹配标题
                if not result['title']:
                    for key in ('title', 'series_title', 'video_title', 'share_title', 'name'):
                        if isinstance(obj.get(key), str) and obj[key].strip():
                            result['title'] = obj[key].strip()
                            break

                # 匹配播放链接
                if not result['video_url']:
                    for key in ('play_url', 'video_url', 'video_play_url', 'url', 'mp4_url'):
                        val = obj.get(key)
                        if isinstance(val, str) and ('http://' in val or 'https://' in val or '.mp4' in val or '/tos-cn-' in val):
                            result['video_url'] = val
                            break

                # 匹配封面
                if not result['cover_url']:
                    for key in ('cover_url', 'poster_url', 'cover', 'image_url', 'og:image'):
                        val = obj.get(key)
                        if isinstance(val, str) and ('http://' in val or 'https://' in val):
                            result['cover_url'] = val
                            break

                # 匹配作者
                if not result['author']:
                    for key in ('author', 'author_name', 'user_name', 'nick_name', 'nickname'):
                        val = obj.get(key)
                        if isinstance(val, str) and val.strip():
                            result['author'] = val.strip()
                            break

                for v in obj.values():
                    search_dict(v)
            elif isinstance(obj, list):
                for item in obj:
                    search_dict(item)

        search_dict(data)
        return result

    @classmethod
    def _extract_from_meta(cls, html: str) -> Dict[str, Any]:
        """从 Meta 标签提取描述、图片、视频链接"""
        result = {'title': None, 'video_url': None, 'cover_url': None, 'author': None}

        # 匹配 <meta property="..." content="..."> 或 <meta name="..." content="...">
        meta_matches = re.findall(r'<meta\s+[^>]*?(?:name|property)\s*=\s*["\']([^"\']+)["\'][^>]*?content\s*=\s*["\']([^"\']+)["\']', html, re.IGNORECASE)
        meta_matches += re.findall(r'<meta\s+[^>]*?content\s*=\s*["\']([^"\']+)["\'][^>]*?(?:name|property)\s*=\s*["\']([^"\']+)["\']', html, re.IGNORECASE)

        for name, content in meta_matches:
            name_lower = name.lower()
            content = unescape(content)

            if name_lower in ('og:url', 'twitter:player', 'video:url') and ('mime_type=video' in content or '.mp4' in content or '/tos-cn-' in content or 'play' in content):
                if not result['video_url']:
                    result['video_url'] = content
            elif name_lower in ('og:image', 'twitter:image'):
                if not result['cover_url']:
                    result['cover_url'] = content
            elif name_lower in ('og:description', 'description', 'og:title', 'twitter:title'):
                if not result['title']:
                    result['title'] = content

        # 标签兜底
        if not result['title']:
            title_match = re.search(r'<title>(.*?)</title>', html, re.IGNORECASE | re.DOTALL)
            if title_match:
                result['title'] = unescape(title_match.group(1)).strip()

        # HTML5 <video src="..."> 兜底
        if not result['video_url']:
            video_match = re.search(r'<video[^>]+src=["\']([^"\']+)["\']', html, re.IGNORECASE)
            if video_match:
                result['video_url'] = unescape(video_match.group(1))

        return result

    @staticmethod
    def _clean_url(url: str) -> Optional[str]:
        if not url or not isinstance(url, str):
            return None
        cleaned = url.replace(r'\u002F', '/').replace('\\/', '/')
        cleaned = unescape(cleaned).strip()
        if cleaned.startswith('//'):
            cleaned = 'https:' + cleaned
        return cleaned
