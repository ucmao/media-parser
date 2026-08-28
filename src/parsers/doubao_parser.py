import base64
import hashlib
import html
import json
import os
from pathlib import Path
import re
import sys
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

from bs4 import BeautifulSoup
from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad

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
    PLAY_INFO_API = "https://www.doubao.com/samantha/media/get_play_info"
    GET_VIDEO_MODEL_API = "https://www.doubao.com/alice/resource/get_video_model"
    FPLAY_KDF_SALT = "TdTC5rgxYgkOUrPHpnM7pByyRiuCmrWKGWs521cXdST0m69/COjWjSanLjfBqVovHwWlGJKu8pSXMrYqOKrdWA=="
    USER_AGENT = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/145.0.0.0 Safari/537.36"
    )


    def __init__(self, real_url):
        super().__init__(real_url)
        cookie = os.getenv("DOUBAO_COOKIE", "").strip()
        self.headers = {
            "Accept": "application/json, text/plain, */*",
            "User-Agent": self.USER_AGENT,
        }
        if cookie:
            self.headers["Cookie"] = cookie
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
            headers=self.headers,
            timeout=15,
        )
        response.raise_for_status()

        roots = self._load_script_payloads(response.text)
        creations = []
        image_urls = []
        video_urls = []
        cover_urls = []

        for root in roots:
            self._collect_creations(root, creations)
            self._collect_all_images(root, image_urls)

        for creation in creations:
            image = creation.get("image") or {}
            image_url = self._extract_image_url_from_dict(image)
            if image_url:
                image_urls.append(image_url)
                cover_urls.append(image_url)

            video = creation.get("video") or {}
            if video:
                vid = video.get("vid") or video.get("video_id")
                clean_urls = []
                if vid:
                    # 1. 优先通过 alice/resource/get_video_model + FPLAY 解密获取 1080p 原画无水印视频
                    clean_urls, clean_poster = self._fetch_unwatermarked_video_by_vid(vid)
                    if clean_urls:
                        video_urls.extend(clean_urls)
                    if clean_poster:
                        cover_urls.append(clean_poster)

                    # 2. 次选 samantha/media/get_play_info
                    if not clean_urls:
                        play_url, play_poster = self._fetch_play_info(vid)
                        if play_url:
                            video_urls.append(play_url)
                        if play_poster:
                            cover_urls.append(play_poster)

                if not clean_urls:
                    video_urls.extend(self._extract_thread_video_urls(video))

                poster = (
                    video.get("poster_url")
                    or self._nested_get(video, "cover", "url")
                    or self._nested_get(video, "poster", "url")
                )
                if poster:
                    cover_urls.append(poster)

        if image_urls:
            cover_urls.extend(image_urls)

        image_urls = self._unique(image_urls)
        video_urls = self._unique(video_urls)
        cover_urls = self._unique(cover_urls)

        clean_video_urls = [u for u in video_urls if not self._is_watermarked_video_url(u)]
        if clean_video_urls:
            video_urls = clean_video_urls

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

        # 1. 优先通过 alice/resource/get_video_model + FPLAY 解密获取 1080p 原画无水印视频
        unwatermarked_urls, unwatermarked_poster = self._fetch_unwatermarked_video_by_vid(video_id)
        original_video_url = unwatermarked_urls[0] if unwatermarked_urls else None
        play_poster_url = unwatermarked_poster

        # 2. 次选 samantha/media/get_play_info
        if not original_video_url:
            try:
                play_resp = self.session.post(
                    self.PLAY_INFO_API,
                    params=params,
                    headers=headers,
                    json={"key": video_id},
                    timeout=10,
                )
                if play_resp.status_code == 200:
                    play_json = play_resp.json()
                    if play_json.get("code") == 0 and play_json.get("data"):
                        pdata = play_json["data"]
                        orig_info = pdata.get("original_media_info") or {}
                        raw_orig = orig_info.get("main_url")
                        if raw_orig:
                            original_video_url = self._sanitize_video_url(raw_orig)
                        if pdata.get("poster_url"):
                            play_poster_url = pdata["poster_url"]
            except Exception as err:
                logger.debug(f"Doubao samantha get_play_info request failed: {err}")

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
        if payload.get("code") != 0 and not original_video_url:
            raise ValueError(payload.get("msg") or "豆包接口返回解析失败")

        detail = payload.get("data") or {}
        play_info = detail.get("play_info") or {}
        raw_main = play_info.get("main") or play_info.get("backup")
        share_url = self._sanitize_video_url(raw_main) if raw_main else None
        user_info = detail.get("user_info") or {}
        nickname = user_info.get("nickname") or user_info.get("user_name") or ""
        author_id = user_info.get("user_id")

        final_video_url = original_video_url or share_url
        final_video_list = unwatermarked_urls if unwatermarked_urls else ([final_video_url] if final_video_url else [])
        final_cover_url = play_poster_url or play_info.get("poster_url")

        return {
            "title": detail.get("prompt") or "豆包 AI 视频",
            "video_url": final_video_url,
            "video_list": final_video_list,
            "cover_url": final_cover_url,
            "author": {
                "nickname": nickname,
                "author_id": str(author_id) if author_id is not None else "",
                "avatar": user_info.get("avatar") or user_info.get("avatar_url") or "",
            },
            "image_list": [],
        }

    @classmethod
    def _decipher_fplay_url(cls, url_raw: str, key_seed: str) -> str:
        if not url_raw or not key_seed:
            return ""
        try:
            s = url_raw.replace("-", "+").replace("_", "/")
            pad = (4 - len(s) % 4) % 4
            encrypted = base64.b64decode(s + "=" * pad)

            s_seed = key_seed.replace("-", "+").replace("_", "/")
            pad_seed = (4 - len(s_seed) % 4) % 4
            seed = base64.b64decode(s_seed + "=" * pad_seed)

            ciphertext = encrypted[4:]
            first_hash = hashlib.sha512(seed).digest()
            salt = base64.b64decode(cls.FPLAY_KDF_SALT)
            key_material = first_hash + salt
            derived = hashlib.sha512(key_material).digest()

            key_bytes = derived[:16]
            iv = derived[16:32]

            cipher = AES.new(key_bytes, AES.MODE_CBC, iv)
            decrypted = unpad(cipher.decrypt(ciphertext), AES.block_size)
            return decrypted.decode("utf-8").strip()
        except Exception as err:
            logger.debug(f"Failed to decipher fplay url: {err}")
            return ""

    def _fetch_unwatermarked_videos_from_fallback_api(self, fallback_api: str) -> list:
        if not fallback_api:
            return []
        try:
            parsed = urlparse(fallback_api)
            qs = parse_qs(parsed.query)
            if "key_seed" not in qs:
                return []

            candidates = [
                {"force_fids": [base64.b64encode(b"original").decode()], "codec_type": ["5"]},
                {"codec_type": ["1"]},
            ]

            headers = {
                "User-Agent": self.USER_AGENT,
                "Referer": "https://www.doubao.com/",
            }

            for cand in candidates:
                test_qs = dict(qs)
                test_qs.pop("logo_type", None)
                test_qs.pop("force_fids", None)
                test_qs.update(cand)
                clean_query = urlencode(test_qs, doseq=True)
                clean_url = urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, clean_query, parsed.fragment))

                resp = self.session.get(clean_url, headers=headers, timeout=10)
                if resp.status_code != 200:
                    continue
                info_data = resp.json().get("video_info", {}).get("data", {})
                key_seed = info_data.get("key_seed")
                if not key_seed:
                    continue

                urls = []
                video_list = info_data.get("video_list", {})
                for v_info in video_list.values():
                    for key in ("main_url", "backup_url_1"):
                        raw_url = v_info.get(key)
                        if raw_url:
                            dec = self._decipher_fplay_url(raw_url, key_seed)
                            if dec and dec not in urls:
                                urls.append(dec)
                if urls:
                    return urls
        except Exception as err:
            logger.debug(f"Failed to fetch unwatermarked video from fallback_api: {err}")
        return []

    def _fetch_unwatermarked_video_by_vid(self, vid: str):
        if not vid:
            return [], None
        headers = dict(self.headers)
        headers.update({
            "Content-Type": "application/json",
            "Origin": "https://www.doubao.com",
            "Referer": self.real_url,
        })
        try:
            resp = self.session.post(
                self.GET_VIDEO_MODEL_API,
                json={"params": [{"uri": vid}]},
                headers=headers,
                timeout=10,
            )
            if resp.status_code == 200:
                data = resp.json()
                if data.get("code") == 0 and data.get("data", {}).get("results"):
                    res0 = data["data"]["results"][0]
                    v_res = res0.get("video_model_result", {})
                    v_model_raw = v_res.get("video_model")
                    poster = res0.get("video_url_result", {}).get("poster_url")
                    if v_model_raw:
                        v_model = json.loads(v_model_raw)
                        fb_api = v_model.get("fallback_api")
                        poster = poster or v_model.get("poster_url")
                        if fb_api:
                            unwatermarked_urls = self._fetch_unwatermarked_videos_from_fallback_api(fb_api)
                            if unwatermarked_urls:
                                return unwatermarked_urls, poster
        except Exception as err:
            logger.debug(f"Failed to fetch video model for vid {vid}: {err}")
        return [], None

    def _fetch_play_info(self, vid):
        if not vid:
            return None, None
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
        headers = dict(self.headers)
        headers.update({
            "Content-Type": "application/json",
            "Origin": "https://www.doubao.com",
            "Referer": self.real_url,
        })
        try:
            resp = self.session.post(
                self.PLAY_INFO_API,
                params=params,
                headers=headers,
                json={"key": vid},
                timeout=10,
            )
            if resp.status_code == 200:
                pjson = resp.json()
                if pjson.get("code") == 0 and pjson.get("data"):
                    pdata = pjson["data"]
                    orig_info = pdata.get("original_media_info") or {}
                    raw_orig = orig_info.get("main_url")
                    poster = pdata.get("poster_url")
                    sanitized = self._sanitize_video_url(raw_orig) if raw_orig else None
                    return sanitized, poster
        except Exception as err:
            logger.debug(f"Doubao get_play_info failed for vid {vid}: {err}")
        return None, None

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

        # 当前线程页把完整会话载荷放在 data-fn-name="r" 的脚本属性中。
        # 其中的嵌套转义会使部分 HTML 解析器无法将该 script 识别为标签，
        # 因此直接从原始页面提取该属性后再按 JSON 解码。
        router_pattern = re.compile(
            r'<script\b[^>]*\bdata-fn-name="r"[^>]*\bdata-fn-args="(?P<args>.*?)"\s+nonce=',
            re.DOTALL,
        )
        for match in router_pattern.finditer(html_content):
            try:
                roots.append(cls._expand_json_strings(
                    json.loads(html.unescape(match.group("args")))
                ))
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
            # 线程页的 message.content 会经过两层 HTML/JSON 转义；先还原
            # HTML 实体，才能把其中的 creation_block 当作 JSON 展开。
            stripped = html.unescape(value).strip()
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
    def _extract_image_url_from_dict(cls, img_item):
        if not isinstance(img_item, dict):
            return None
        return (
            cls._nested_get(img_item, "image_ori_raw", "url")
            or cls._nested_get(img_item, "image_raw", "url")
            or cls._nested_get(img_item, "image_ori", "url")
            or cls._nested_get(img_item, "image_origin", "url")
            or img_item.get("raw_url")
            or img_item.get("origin_url")
            or img_item.get("url")
        )

    @classmethod
    def _collect_all_images(cls, node, output):
        if isinstance(node, dict):
            ref_images = node.get("ref_images")
            if isinstance(ref_images, list):
                for item in ref_images:
                    url = cls._extract_image_url_from_dict(item)
                    if url:
                        output.append(url)

            ref_resources = node.get("ref_resources")
            if isinstance(ref_resources, list):
                for item in ref_resources:
                    if isinstance(item, dict):
                        url = cls._extract_image_url_from_dict(item.get("image"))
                        if url:
                            output.append(url)

            image = node.get("image")
            if isinstance(image, dict):
                url = cls._extract_image_url_from_dict(image)
                if url:
                    output.append(url)

            for value in node.values():
                cls._collect_all_images(value, output)
        elif isinstance(node, list):
            for value in node:
                cls._collect_all_images(value, output)

    @classmethod
    def _extract_thread_video_urls(cls, video):
        urls = []
        fallback_urls = []
        direct_url = video.get("download_url")
        if direct_url:
            sanitized = cls._sanitize_video_url(direct_url)
            if sanitized:
                if not cls._is_watermarked_video_url(sanitized):
                    urls.append(sanitized)
                else:
                    fallback_urls.append(sanitized)

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
                if sanitized:
                    if not cls._is_watermarked_video_url(sanitized):
                        urls.append(sanitized)
                    else:
                        fallback_urls.append(sanitized)

        final_urls = cls._unique(urls)
        if not final_urls and fallback_urls:
            final_urls = cls._unique(fallback_urls)
        return final_urls

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
