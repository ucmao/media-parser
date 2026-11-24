from src.parser_factory import register_parser
import json
import random
import requests
from urllib.parse import urlparse
from utils.web_fetcher import UrlParser
from src.parsers.base_parser import BaseParser
from src.utils.cookie_manager import get_platform_cookie
from src.utils.parser_transport import report_cookie_required
from configs.general_constants import USER_AGENT_M, USER_AGENT_PC
from configs.logging_config import get_logger

logger = get_logger(__name__)


@register_parser("快手")
class KuaishouParser(BaseParser):
    def __init__(self, real_url):
        super().__init__(real_url)
        # 独立请求原本不共享 Cookie，统一传输后继续保持此行为。
        self.session.isolate_cookies = True

        custom_cookie = get_platform_cookie("kuaishou")
        self.custom_cookie = custom_cookie or ""

        self.headers = {
            "content-type": "application/json; charset=UTF-8",
            'User-Agent': random.choice(USER_AGENT_PC),
            'referer': 'https://www.kuaishou.com/',
        }
        if self.custom_cookie:
            self.headers['cookie'] = self.custom_cookie

        self.video_id = UrlParser.get_video_id(self.real_url)
        self.page_type = "UNKNOWN"
        self.structured_data = {}
        self.client = {}
        self.cookie_required = False
        self.terminal_error = None

        # 快手不同公开路由的稳定性差异较大，命中风控时自动切换备用路由重试。
        self._load_page_with_fallbacks()

        # 提取核心数据客户端对象
        self.client = self.structured_data.get('defaultClient',
                                               {}) if self.page_type == "VIDEO" else self.structured_data

    @staticmethod
    def _is_blocked_payload(html_content):
        if not html_content:
            return False
        try:
            payload = json.loads(html_content)
            result = payload.get("result") or payload.get("data", {}).get("result")
            if result in (2, 400002) or payload.get("bizName") == "ANTICRAWL_DEFAULT":
                return True
        except (TypeError, json.JSONDecodeError):
            return False
        return False

    def _candidate_urls(self):
        candidates = [self.real_url]
        if self.video_id:
            if not self._is_fw_photo_url(self.real_url):
                candidates.append(f"https://v.m.chenzhongtech.com/fw/photo/{self.video_id}")
            candidates.append(f"https://www.kuaishou.com/short-video/{self.video_id}")

        deduped = []
        for url in candidates:
            if url and url not in deduped:
                deduped.append(url)
        return deduped

    @staticmethod
    def _is_fw_photo_url(url):
        if not url:
            return False
        path = urlparse(url).path.rstrip("/")
        return path.startswith("/fw/photo/")

    def _build_mobile_headers(self):
        headers = {
            "User-Agent": random.choice(USER_AGENT_M),
            "referer": "https://v.m.chenzhongtech.com/",
            "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }
        if self.custom_cookie:
            headers["cookie"] = self.custom_cookie
        return headers

    def _fetch_html_with_headers(self, url, headers):
        try:
            resp = self.session.get(url, headers=headers, timeout=5)
            resp.raise_for_status()
            return resp.text
        except requests.RequestException as e:
            logger.error(f"Failed to get the page: {url}, Error: {e}")
            return None
        except Exception as e:
            logger.error(f"An unexpected error occurred while fetching {url}: {e}")
            return None

    def _is_valid_video_state(self, page_type, structured_data):
        if not structured_data:
            return False

        if page_type == "ATLAS":
            payload = self._find_nested_dict(structured_data, ("photo",))
            if not payload:
                return False
            photo = payload.get("photo", {})
            if not isinstance(photo, dict):
                return False
            return bool(
                photo.get("caption")
                or photo.get("coverUrls")
                or photo.get("webpCoverUrls")
                or photo.get("mainMvUrls")
                or photo.get("manifest")
                or payload.get("atlas")
            )

        if page_type != "VIDEO":
            return True

        default_client = structured_data.get("defaultClient", {})
        if not isinstance(default_client, dict):
            return False

        if default_client.get("VisionVideoSetRepresentation:1"):
            return True

        for key in default_client.keys():
            if "visionVideoDetail" in key or "VisionVideoDetailPhoto:" in key:
                return True

        return False

    def _try_parse_candidate(self, candidate_url, headers):
        self.real_url = candidate_url
        self.html_content = self._fetch_html_with_headers(candidate_url, headers)
        if self._is_blocked_payload(self.html_content):
            logger.warning(f"Kuaishou blocked route {candidate_url}, trying fallback")
            self.cookie_required = True
            report_cookie_required()
            return False

        page_type, structured_data = self._identify_and_parse_data()
        if page_type == "UNKNOWN" or not structured_data:
            return False
        if not self._is_valid_video_state(page_type, structured_data):
            logger.warning(f"Kuaishou route {candidate_url} returned incomplete video state, trying fallback")
            return False

        self.page_type = page_type
        self.structured_data = structured_data
        return True

    def _try_graphql_api(self, video_id):
        if not video_id:
            return False
        graphql_url = "https://www.kuaishou.com/graphql"
        headers = dict(self.headers)
        headers["Referer"] = f"https://www.kuaishou.com/short-video/{video_id}"
        payload = {
            "operationName": "visionVideoDetail",
            "variables": {"photoId": video_id, "page": "detail"},
            "query": """query visionVideoDetail($photoId: String, $type: String, $page: String, $webPageArea: String) {
  visionVideoDetail(photoId: $photoId, type: $type, page: $page, webPageArea: $webPageArea) {
    status
    type
    author {
      id
      name
      headerUrl
    }
    photo {
      id
      caption
      coverUrl
      photoUrl
      mainMvUrls {
        url
      }
      manifest {
        adaptationSet {
          representation {
            url
            backupUrl
          }
        }
      }
      atlas {
        cdn
        cdnList
        list
      }
    }
  }
}"""
        }
        try:
            resp = self.session.post(graphql_url, json=payload, headers=headers, timeout=5)
            if resp.status_code == 200:
                if self._is_blocked_payload(resp.text):
                    self.cookie_required = True
                    report_cookie_required()
                    return False
                data = resp.json()
                detail = data.get("data", {}).get("visionVideoDetail")
                if isinstance(detail, dict) and detail.get("photo"):
                    self.page_type = "GRAPHQL"
                    self.structured_data = detail
                    return True
        except Exception as e:
            logger.debug(f"Kuaishou GraphQL request failed: {e}")
        return False

    def _load_page_with_fallbacks(self):
        blocked = False
        for candidate_url in self._candidate_urls():
            # 快手移动端页面优先返回完整的 INIT_STATE；桌面端页面仅作为兼容兜底。
            if self._try_parse_candidate(candidate_url, self._build_mobile_headers()):
                return
            if self.cookie_required:
                blocked = True
            if self._try_parse_candidate(candidate_url, self.headers):
                return
            if self.cookie_required:
                blocked = True

        if self.video_id and self._try_graphql_api(self.video_id):
            return

        if blocked or self.cookie_required:
            self.cookie_required = True
            self.terminal_error = {
                "detail_msg": "解析失败：该链接触发快手安全校验，请在配置中提供有效快手 Cookie 后重试",
                "error_code": "KUAISHOU_COOKIE_REQUIRED",
            }

        self.page_type = "UNKNOWN"
        self.structured_data = {}

    def _extract_json_object(self, text, start_index):
        """稳健提取 JSON 对象：通过括号匹配解决额外数据报错"""
        if start_index == -1 or not text:
            return None

        bracket_count = 0
        in_string = False
        escape_next = False
        quote_char = ""

        for i in range(start_index, len(text)):
            char = text[i]
            if in_string:
                if escape_next:
                    escape_next = False
                elif char == "\\":
                    escape_next = True
                elif char == quote_char:
                    in_string = False
                continue

            if char in ("'", '"'):
                in_string = True
                quote_char = char
            elif char == '{':
                bracket_count += 1
            elif char == '}':
                bracket_count -= 1
                if bracket_count == 0:
                    return text[start_index:i + 1]
        return None

    def _find_nested_dict(self, data, required_keys):
        """在快手扁平状态里查找同时具备指定字段的节点。"""
        stack = [data]
        while stack:
            current = stack.pop()
            if isinstance(current, dict):
                if all(key in current for key in required_keys):
                    return current
                stack.extend(
                    value for value in current.values()
                    if isinstance(value, (dict, list))
                )
            elif isinstance(current, list):
                stack.extend(
                    item for item in current
                    if isinstance(item, (dict, list))
                )
        return {}

    def _get_atlas_payload(self):
        if self.page_type not in ("ATLAS", "VIDEO"):
            return {}

        payload = self._find_nested_dict(self.structured_data, ("atlas", "photo"))
        if payload:
            return payload

        payload = self._find_nested_dict(self.structured_data, ("photo",))
        if payload:
            return payload

        return {}

    def _get_atlas_variants(self):
        payload = self._get_atlas_payload()
        photo = payload.get("photo", {})

        variants = []
        ext_atlas = photo.get("ext_params", {}).get("atlas")
        if isinstance(ext_atlas, dict):
            variants.append(ext_atlas)

        atlas = payload.get("atlas")
        if isinstance(atlas, dict):
            variants.append(atlas)

        return variants

    @staticmethod
    def _atlas_is_webp(atlas):
        image_paths = atlas.get("list") or []
        return any(str(path).lower().endswith(".webp") for path in image_paths)

    @staticmethod
    def _normalize_url(url):
        if not url:
            return None
        url = str(url).replace("\\u002F", "/")
        if url.startswith("//"):
            return f"https:{url}"
        return url

    def _first_url(self, candidates):
        if isinstance(candidates, str):
            return self._normalize_url(candidates)
        if not isinstance(candidates, list):
            return None

        for item in candidates:
            if isinstance(item, str):
                return self._normalize_url(item)
            if isinstance(item, dict) and item.get("url"):
                return self._normalize_url(item.get("url"))
        return None

    @staticmethod
    def _first_cdn(atlas):
        cdn_list = atlas.get("cdn") or []
        if not cdn_list:
            cdn_list = [
                item.get("cdn") for item in atlas.get("cdnList", [])
                if isinstance(item, dict) and item.get("cdn")
            ]
        if isinstance(cdn_list, str):
            return cdn_list
        return cdn_list[0] if cdn_list else None

    def _build_resource_url(self, cdn, path):
        path = self._normalize_url(path)
        if not path:
            return None
        if path.startswith("http://") or path.startswith("https://"):
            return path
        if path.startswith("//"):
            return f"https:{path}"
        if not cdn:
            return path

        cdn = self._normalize_url(cdn).rstrip("/")
        if not cdn.startswith("http://") and not cdn.startswith("https://"):
            cdn = f"https://{cdn}"
        return f"{cdn}/{path.lstrip('/')}"

    def _identify_and_parse_data(self):
        """识别快手不同的数据载体（Apollo 或 InitState）"""
        if not self.html_content:
            return "UNKNOWN", {}

        # 1. 视频详情页 (Apollo)
        if "window.__APOLLO_STATE__" in self.html_content:
            marker = "window.__APOLLO_STATE__"
            start_pos = self.html_content.find(marker) + len(marker)
            start_pos = self.html_content.find("{", start_pos)
            json_str = self._extract_json_object(self.html_content, start_pos)
            if json_str:
                try:
                    return "VIDEO", json.loads(json_str)
                except json.JSONDecodeError as e:
                    logger.warning(f"Failed to decode Kuaishou Apollo data: {e}")

        # 2. 某些图文或移动端适配页 (INIT_STATE)
        if "window.INIT_STATE" in self.html_content:
            marker = "window.INIT_STATE"
            start_pos = self.html_content.find(marker) + len(marker)
            start_pos = self.html_content.find("{", start_pos)
            json_str = self._extract_json_object(self.html_content, start_pos)
            if json_str:
                try:
                    return "ATLAS", json.loads(json_str, strict=False)
                except json.JSONDecodeError as e:
                    logger.warning(f"Failed to decode Kuaishou INIT_STATE data: {e}")

        return "UNKNOWN", {}

    def get_real_video_url(self):
        try:
            if self.page_type == "GRAPHQL":
                photo = self.structured_data.get("photo", {})
                video_url = (
                    self._first_url(photo.get("mainMvUrls"))
                    or self._normalize_url(photo.get("photoUrl"))
                )
                if video_url:
                    return video_url
                manifest = photo.get("manifest", {})
                for adaptation_set in manifest.get("adaptationSet", []):
                    for representation in adaptation_set.get("representation", []):
                        backup_urls = representation.get("backupUrl") or []
                        if backup_urls:
                            return self._first_url(backup_urls)
                        rep_url = representation.get("url")
                        if rep_url:
                            return self._normalize_url(rep_url)
                return None

            if self.page_type == "VIDEO":
                # 优先从标准表示层获取
                video_url = self.client.get('VisionVideoSetRepresentation:1', {}).get('url')
                # 兜底：直接从 Photo 对象获取
                if not video_url:
                    photo_key = f"VisionVideoDetailPhoto:{self.video_id}"
                    video_url = self.client.get(photo_key, {}).get('photoUrl')

                return video_url.replace("\u002F", "/") if video_url else None

            payload = self._get_atlas_payload()
            photo = payload.get("photo", {})
            video_url = (
                self._first_url(photo.get("mainMvUrls"))
                or self._first_url(photo.get("photoUrls"))
            )

            if video_url:
                return video_url

            manifest = photo.get("manifest", {})
            for adaptation_set in manifest.get("adaptationSet", []):
                for representation in adaptation_set.get("representation", []):
                    backup_urls = representation.get("backupUrl") or []
                    if backup_urls:
                        return self._first_url(backup_urls)
                    m3u8_slice = representation.get("m3u8Slice")
                    if m3u8_slice and "http" in m3u8_slice:
                        for line in m3u8_slice.splitlines():
                            line = line.strip()
                            if line.startswith("http://") or line.startswith("https://"):
                                return line
        except Exception as e:
            logger.warning(f"Failed to parse video URL: {e}")
            return None

        return None

    def get_title_content(self):
        return None

    def get_description(self):
        try:
            if self.page_type == "GRAPHQL":
                return self.structured_data.get("photo", {}).get("caption") or None
            photo_key = f"VisionVideoDetailPhoto:{self.video_id}"
            if self.page_type == "VIDEO":
                caption = self.client.get(photo_key, {}).get('caption', '')
                if caption:
                    return caption
            if self.page_type in ("ATLAS", "VIDEO"):
                payload = self._get_atlas_payload()
                return payload.get("photo", {}).get("caption") or None
        except Exception as e:
            logger.warning(f"Failed to parse Kuaishou description: {e}")
        return None

    def get_cover_photo_url(self):
        try:
            if self.page_type == "GRAPHQL":
                cover = self.structured_data.get("photo", {}).get("coverUrl")
                if cover:
                    return self._normalize_url(cover)
                return ""

            photo_key = f"VisionVideoDetailPhoto:{self.video_id}"
            if self.page_type == "VIDEO":
                cover_url = self.client.get(photo_key, {}).get('coverUrl', '')
                if cover_url:
                    return cover_url

            if self.page_type in ("ATLAS", "VIDEO"):
                payload = self._get_atlas_payload()
                photo = payload.get("photo", {})
                cover_url = (
                        self._first_url(photo.get("coverUrls"))
                        or self._first_url(photo.get("webpCoverUrls"))
                        or self._first_url(self.get_image_list())
                )
                return cover_url or ""
        except Exception as e:
            logger.warning(f"Failed to parse cover URL: {e}")
            pass
        return ""

    def get_author_info(self):
        """
        核心修正：通过引用 ID 在扁平化的状态机中进行二次索引
        """
        try:
            if self.page_type == "GRAPHQL":
                author = self.structured_data.get("author", {})
                if author:
                    return {
                        "nickname": author.get("name"),
                        "unique_id": author.get("id"),
                        "avatar": author.get("headerUrl")
                    }
                return None

            if self.page_type == "VIDEO":
                # 1. 定位视频对象中的作者引用
                photo_key = f"VisionVideoDetailPhoto:{self.video_id}"
                author_ref = self.client.get(photo_key, {}).get('author')

                # 2. 模糊匹配兜底（防止 Key 中带有复杂参数）
                if not author_ref:
                    for k in self.client.keys():
                        if f'photoId":"{self.video_id}"' in k:
                            author_ref = self.client[k].get('author')
                            break

                # 3. 提取详情
                if author_ref and author_ref.get('id') in self.client:
                    author_detail = self.client[author_ref['id']]
                    return {
                        "nickname": author_detail.get('name'),
                        "unique_id": author_detail.get('id'),
                        "avatar": author_detail.get('headerUrl')
                    }
            if self.page_type in ("ATLAS", "VIDEO"):
                payload = self._get_atlas_payload()
                photo = payload.get("photo", {})
                if photo:
                    author_id = photo.get("kwaiId") or photo.get("userEid") or photo.get("userId") or photo.get("eid")
                    return {
                        "nickname": photo.get("userName", "") or photo.get("user_name", ""),
                        "author_id": str(author_id) if author_id else "",
                        "unique_id": str(author_id) if author_id else "",
                        "avatar": self._first_url(photo.get("headUrls")) or photo.get("headUrl", "") or photo.get("headurl", "")
                    }

                # 图文页通常直接在某个 Profile 节点下
                for val in self.structured_data.values():
                    if isinstance(val, dict) and "userProfile" in val:
                        p = val['userProfile']['profile']
                        return {
                            "nickname": p.get('user_name'),
                            "unique_id": p.get('user_id'),
                            "avatar": p.get('headurl')
                        }
        except Exception as e:
            logger.error(f"Author parse error: {e}")
        return None

    def get_audio_url(self):
        """
        获取独立的音频链接。
        支持从创作者原声 (soundTrack)、背景音乐 (music) 及图集音乐 (atlas.music) 提取音频直链。
        """
        try:
            if self.page_type == "GRAPHQL":
                photo = self.structured_data.get("photo", {})
                for key in ("soundTrack", "sound_track", "music"):
                    music_obj = photo.get(key)
                    if isinstance(music_obj, dict):
                        audio_url = (
                            self._first_url(music_obj.get("audioUrls"))
                            or self._normalize_url(music_obj.get("url"))
                        )
                        if audio_url:
                            return audio_url
                return None

            if self.page_type in ("ATLAS", "VIDEO"):
                payload = self._get_atlas_payload()
                photo = payload.get("photo", {}) if isinstance(payload, dict) else {}
                for key in ("soundTrack", "sound_track", "music"):
                    music_obj = photo.get(key)
                    if isinstance(music_obj, dict):
                        audio_url = (
                            self._first_url(music_obj.get("audioUrls"))
                            or self._normalize_url(music_obj.get("url"))
                        )
                        if audio_url:
                            return audio_url

                atlas = payload.get("atlas", {}) if isinstance(payload, dict) else {}
                return self._build_resource_url(
                    self._first_cdn({"cdnList": atlas.get("musicCdnList", [])}),
                    atlas.get("music")
                )
        except Exception as e:
            logger.warning(f"Failed to parse atlas audio URL: {e}")
            return None
        return None

    def get_image_list(self):
        try:
            if self.page_type == "GRAPHQL":
                atlas = self.structured_data.get("photo", {}).get("atlas")
                if isinstance(atlas, dict):
                    image_urls = []
                    cdn = self._first_cdn(atlas)
                    for image_path in atlas.get("list") or []:
                        image_url = self._build_resource_url(cdn, image_path)
                        if image_url:
                            image_urls.append(image_url)
                    if image_urls:
                        return image_urls
                return []

            if self.page_type not in ("ATLAS", "VIDEO"):
                return []

            payload = self._get_atlas_payload()
            atlas_variants = self._get_atlas_variants()
            preferred_atlas = next(
                (atlas for atlas in atlas_variants if self._atlas_is_webp(atlas)),
                atlas_variants[0] if atlas_variants else {}
            )

            image_urls = []
            for image_path in preferred_atlas.get("list") or []:
                image_url = self._build_resource_url(self._first_cdn(preferred_atlas), image_path)
                if image_url:
                    image_urls.append(image_url)

            if image_urls:
                return image_urls

            return [
                url for url in (
                    self._first_url(payload.get("photo", {}).get("coverUrls")),
                    self._first_url(payload.get("photo", {}).get("webpCoverUrls"))
                )
                if url
            ]
        except Exception as e:
            logger.warning(f"Failed to parse image list: {e}")
            return []
