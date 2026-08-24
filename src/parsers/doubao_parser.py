import base64
import html
import json
import os
from pathlib import Path
import sys
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

from bs4 import BeautifulSoup

root_dir = str(Path(__file__).resolve().parents[2])
if root_dir not in sys.path:
    sys.path.append(root_dir)

from configs.logging_config import get_logger
from src.parsers.base_parser import BaseParser


logger = get_logger(__name__)


class DoubaoParser(BaseParser):
    """解析豆包对话分享和独立 AI 视频分享。

    """

    VIDEO_API = "https://www.doubao.com/creativity/share/get_video_share_info"
    USER_AGENT = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/145.0.0.0 Safari/537.36"
    )

    def __init__(self, real_url):
        super().__init__(real_url)
        self.headers = {
            "Accept": "application/json, text/plain, */*",
            "User-Agent": self.USER_AGENT,
        }
        self.data = {
            "title": "",
            "video_url": None,
            "video_list": [],
            "cover_url": None,
            "author": None,
            "image_list": [],
        }
        self._parse_once()

    def _parse_once(self):
        path = urlparse(self.real_url).path.rstrip("/")
        try:
            if path.startswith("/thread/"):
                self.data.update(self._parse_thread())
            elif path == "/video-sharing":
                self.data.update(self._parse_video_sharing())
            else:
                logger.warning(f"Unsupported Doubao share URL: {self.real_url}")
        except Exception as exc:
            logger.exception(f"Failed to parse Doubao share: {exc}")

    def _parse_thread(self):
        response = self.session.get(
            self.real_url,
            headers={"User-Agent": self.USER_AGENT},
            timeout=15,
        )
        response.raise_for_status()

        roots = self._load_script_payloads(response.text)
        creations = []
        for root in roots:
            self._collect_creations(root, creations)

        image_urls = []
        video_urls = []
        cover_urls = []
        for creation in creations:
            image = creation.get("image") or {}
            image_url = self._nested_get(image, "image_ori_raw", "url")
            if image_url:
                image_urls.append(image_url)
                cover_urls.append(image_url)

            video = creation.get("video") or {}
            if video:
                video_urls.extend(self._extract_thread_video_urls(video))
                poster = (
                    video.get("poster_url")
                    or self._nested_get(video, "cover", "url")
                    or self._nested_get(video, "poster", "url")
                )
                if poster:
                    cover_urls.append(poster)

        image_urls = self._unique(image_urls)
        video_urls = self._unique(video_urls)
        cover_urls = self._unique(cover_urls)

        return {
            "title": self._find_title(roots) or "豆包对话分享",
            "video_url": video_urls[0] if video_urls else None,
            "video_list": video_urls,
            "cover_url": cover_urls[0] if cover_urls else None,
            "author": self._find_author(roots),
            "image_list": image_urls,
        }

    def _parse_video_sharing(self):
        query = parse_qs(urlparse(self.real_url).query)
        share_id = self._first(query.get("share_id"))
        video_id = self._first(query.get("video_id"))
        if not share_id or not video_id:
            logger.warning("Doubao video-sharing URL is missing share_id or video_id")
            return {}

        headers = dict(self.headers)
        headers.update({
            "Content-Type": "application/json",
            "Origin": "https://www.doubao.com",
            "Referer": self.real_url,
        })
        cookie = os.getenv("DOUBAO_COOKIE", "").strip()
        if cookie:
            headers["Cookie"] = cookie

        params = {
            "version_code": "20800",
            "language": "zh-CN",
            "device_platform": "web",
            "aid": "497858",
            "real_aid": "497858",
            "pkg_type": "release_version",
            "samantha_web": "1",
            "use-olympus-account": "1",
        }
        response = self.session.post(
            self.VIDEO_API,
            params=params,
            headers=headers,
            json={
                "share_id": share_id,
                "vid": video_id,
                "creation_id": "",
            },
            timeout=15,
        )
        response.raise_for_status()
        payload = response.json()
        if payload.get("code") != 0:
            raise ValueError(payload.get("msg") or "豆包接口返回解析失败")

        detail = payload.get("data") or {}
        play_info = detail.get("play_info") or {}
        main_url = play_info.get("main") or play_info.get("backup")
        user_info = detail.get("user_info") or {}
        nickname = user_info.get("nickname") or user_info.get("user_name") or ""
        author_id = user_info.get("user_id")

        return {
            "title": detail.get("prompt") or "豆包 AI 视频",
            "video_url": main_url,
            # main/backup 是同一作品的 CDN 备选，只对外返回主地址。
            "video_list": [main_url] if main_url else [],
            "cover_url": play_info.get("poster_url"),
            "author": {
                "nickname": nickname,
                "author_id": str(author_id) if author_id is not None else "",
                "avatar": user_info.get("avatar") or user_info.get("avatar_url") or "",
            },
            "image_list": [],
        }

    @classmethod
    def _load_script_payloads(cls, html_content):
        soup = BeautifulSoup(html_content, "lxml")
        roots = []
        for script in soup.find_all("script", attrs={"data-fn-args": True}):
            raw = script.get("data-fn-args")
            if not raw:
                continue
            try:
                roots.append(cls._expand_json_strings(json.loads(html.unescape(raw))))
            except (TypeError, json.JSONDecodeError):
                continue
        return roots

    @classmethod
    def _expand_json_strings(cls, value):
        if isinstance(value, dict):
            return {key: cls._expand_json_strings(item) for key, item in value.items()}
        if isinstance(value, list):
            return [cls._expand_json_strings(item) for item in value]
        if isinstance(value, str):
            stripped = value.strip()
            if stripped.startswith(("{", "[")):
                try:
                    return cls._expand_json_strings(json.loads(stripped))
                except json.JSONDecodeError:
                    pass
        return value

    @classmethod
    def _collect_creations(cls, node, output):
        if isinstance(node, dict):
            creation_block = node.get("creation_block")
            if isinstance(creation_block, dict):
                creations = creation_block.get("creations")
                if isinstance(creations, list):
                    output.extend(item for item in creations if isinstance(item, dict))

            creations = node.get("creations")
            if isinstance(creations, list):
                output.extend(item for item in creations if isinstance(item, dict))

            for value in node.values():
                cls._collect_creations(value, output)
        elif isinstance(node, list):
            for value in node:
                cls._collect_creations(value, output)

    @classmethod
    def _extract_thread_video_urls(cls, video):
        urls = []
        direct_url = video.get("download_url")
        if direct_url:
            sanitized = cls._sanitize_video_url(direct_url)
            if not cls._is_watermarked_video_url(sanitized):
                urls.append(sanitized)

        model = video.get("video_model")
        if isinstance(model, str):
            try:
                model = json.loads(model)
            except json.JSONDecodeError:
                model = None

        for item in cls._walk_dicts(model):
            for key in ("main_url", "backup_url_1"):
                encoded = item.get(key)
                if not encoded:
                    continue
                try:
                    decoded = base64.b64decode(encoded, validate=True).decode("utf-8")
                except (ValueError, UnicodeDecodeError):
                    continue
                sanitized = cls._sanitize_video_url(decoded)
                if sanitized and not cls._is_watermarked_video_url(sanitized):
                    urls.append(sanitized)

        return cls._unique(urls)

    @staticmethod
    def _sanitize_video_url(url):
        if not isinstance(url, str) or not url:
            return ""
        parsed = urlparse(url)
        if not parsed.scheme or not parsed.netloc:
            return url
        query = parse_qs(parsed.query, keep_blank_values=True)
        for key in ("lr", "logo_type", "download"):
            query.pop(key, None)
        # 豆包 CDN 的签名参数必须保留。只有明确的水印控制参数会被移除。
        return urlunparse(parsed._replace(query=urlencode(query, doseq=True)))

    @staticmethod
    def _is_watermarked_video_url(url):
        lower = (url or "").lower()
        return any(marker in lower for marker in (
            "video_gen_watermark",
            "watermark_dyn",
            "logo_type=video_gen_watermark",
        ))

    @classmethod
    def _find_title(cls, roots):
        preferred_keys = ("title", "prompt", "description")
        for key in preferred_keys:
            for item in cls._walk_dicts(roots):
                value = item.get(key)
                if isinstance(value, str) and value.strip() and not value.lstrip().startswith(("{", "[")):
                    return value.strip()
        return ""

    @classmethod
    def _find_author(cls, roots):
        for item in cls._walk_dicts(roots):
            nickname = item.get("nickname") or item.get("user_name")
            if not isinstance(nickname, str) or not nickname.strip():
                continue
            author_id = item.get("user_id") or item.get("uid") or item.get("id") or ""
            avatar = item.get("avatar") or item.get("avatar_url") or ""
            return {
                "nickname": nickname.strip(),
                "author_id": str(author_id) if author_id else "",
                "avatar": avatar if isinstance(avatar, str) else "",
            }
        return None

    @classmethod
    def _walk_dicts(cls, node):
        if isinstance(node, dict):
            yield node
            for value in node.values():
                yield from cls._walk_dicts(value)
        elif isinstance(node, list):
            for value in node:
                yield from cls._walk_dicts(value)

    @staticmethod
    def _nested_get(value, *keys):
        current = value
        for key in keys:
            if not isinstance(current, dict):
                return None
            current = current.get(key)
        return current

    @staticmethod
    def _unique(values):
        return list(dict.fromkeys(value for value in values if value))

    @staticmethod
    def _first(values):
        return values[0] if values else None

    def get_real_video_url(self):
        return self.data.get("video_url")

    def get_video_list(self):
        return self.data.get("video_list") or []

    def get_title_content(self):
        return self.data.get("title") or ""

    def get_cover_photo_url(self):
        return self.data.get("cover_url")

    def get_author_info(self):
        return self.data.get("author")

    def get_image_list(self):
        return self.data.get("image_list") or []


if __name__ == "__main__":
    test_urls = {
        "独立 AI 视频": (
            "https://www.doubao.com/video-sharing?"
            "share_id=41356597786354690&source_type=mobile&"
            "video_id=v0d69cg10004d6978e2ljht0i4fdpp00&"
            "share_scene=video_viewer"
        ),
        "对话图片": "https://www.doubao.com/thread/a7c085916a92a",
    }

    for test_name, test_url in test_urls.items():
        parser = DoubaoParser(test_url)
        print("-" * 30)
        print(f"测试类型：{test_name}")
        print(f"标题内容：{parser.get_title_content()}")
        print(f"作者信息：{parser.get_author_info()}")
        print(f"封面图片：{parser.get_cover_photo_url()}")
        print(f"视频链接：{parser.get_real_video_url()}")
        print(f"视频列表：{parser.get_video_list()}")
        print(f"图片列表：{parser.get_image_list()}")
