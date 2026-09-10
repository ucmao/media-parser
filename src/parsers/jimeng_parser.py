from urllib.parse import parse_qs, urlparse

from configs.logging_config import get_logger
from src.parser_factory import register_parser
from src.parsers.base_parser import BaseParser


logger = get_logger(__name__)


@register_parser("即梦AI")
class JimengParser(BaseParser):
    """解析即梦AI 视频分享。

    """

    API_URL = "https://jimeng.jianying.com/mweb/v1/get_item_info"
    CAMPAIGN_API_URL = (
        "https://jimeng.jianying.com/luckycat/cn/jianying/campaign/v1/dreamina/share/landing_page"
    )
    USER_AGENT = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/123.0.0.0 Safari/537.36"
    )

    def __init__(self, real_url):
        super().__init__(real_url)
        self.headers = {
            "Accept": "application/json, text/plain, */*",
            "Content-Type": "application/json",
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
        try:
            target_url = self.real_url
            item_id = self._extract_item_id(target_url)

            # 若为短链或尚未提取到 ID，跟随重定向获取真实落地页长链与页面内容
            if not item_id or "/s/" in target_url:
                response = self.session.get(
                    target_url,
                    headers={"User-Agent": self.USER_AGENT},
                    allow_redirects=True,
                    timeout=15,
                )
                response.raise_for_status()
                target_url = str(response.url) if hasattr(response, "url") and isinstance(response.url, str) else target_url
                if not item_id:
                    item_id = self._extract_item_id(target_url)
                if not item_id and response.text:
                    item_id = self._extract_item_id_from_html(response.text)

            # 1. 活动/回流/同款链接优先调用官方 campaign landing_page 接口
            if "reflux" in target_url or "mproject" in target_url:
                if self._try_parse_campaign_api(target_url, item_id):
                    return

            # 2. 标准已发布社区作品调用官方 mweb get_item_info 接口
            if item_id:
                response = self.session.post(
                    self.API_URL,
                    headers=self.headers,
                    json={"published_item_id": item_id},
                    timeout=30,
                )
                response.raise_for_status()
                payload = response.json()
                if str(payload.get("ret")) == "0":
                    self.data.update(self._format_data(payload.get("data") or {}))
                    return

                # 若提示 itemId 不存在或非社区公开作品，自动降级至 campaign landing_page 接口
                errmsg = str(payload.get("errmsg") or "")
                if "itemId not exist" in errmsg or str(payload.get("ret")) in ("2032", "1000"):
                    if self._try_parse_campaign_api(target_url, item_id):
                        return
                raise ValueError(errmsg or "即梦接口返回解析失败")
            else:
                logger.warning(f"Unable to extract Jimeng item ID: {self.real_url}")
        except Exception as exc:
            logger.exception(f"Failed to parse Jimeng share: {exc}")

    def _try_parse_campaign_api(self, url, item_id):
        try:
            parsed = urlparse(url)
            qs = parse_qs(parsed.query)
            query_params = {k: v[0] for k, v in qs.items() if v}
            sec_uid = query_params.get("share_sec_uid") or query_params.get("author_id")

            headers = {**self.headers, "appid": "581595"}
            payload = {
                "query_params": query_params,
            }
            if item_id:
                payload["item_id"] = str(item_id)
            if sec_uid:
                payload["sec_uid"] = str(sec_uid)

            res = self.session.post(
                self.CAMPAIGN_API_URL,
                headers=headers,
                json=payload,
                timeout=30,
            )
            res.raise_for_status()
            res_json = res.json()

            if res_json.get("err_no") != 0 or not res_json.get("data"):
                if "item_id" in payload and query_params:
                    payload.pop("item_id", None)
                    res = self.session.post(
                        self.CAMPAIGN_API_URL,
                        headers=headers,
                        json=payload,
                        timeout=30,
                    )
                    res.raise_for_status()
                    res_json = res.json()

            if res_json.get("err_no") == 0 and res_json.get("data"):
                formatted = self._format_campaign_data(res_json["data"])
                if formatted.get("video_url") or formatted.get("image_list"):
                    self.data.update(formatted)
                    return True
        except Exception as e:
            logger.warning(f"Jimeng campaign API parse failed: {e}")
        return False

    @classmethod
    def _format_data(cls, detail):
        common = detail.get("common_attr") or {}
        author = detail.get("author") or {}
        video = detail.get("video") or {}
        origin_video = video.get("origin_video") or {}
        transcoded = video.get("transcoded_video") or {}

        primary_video = None
        transcoded_origin = transcoded.get("origin")
        if isinstance(transcoded_origin, dict):
            primary_video = transcoded_origin.get("video_url")
        if not primary_video:
            primary_video = origin_video.get("video_url")
        if not primary_video:
            primary_video = cls._best_transcoded_url(transcoded)

        cover_map = common.get("cover_url_map") or {}
        cover_url = None
        if isinstance(cover_map, dict):
            for quality in ("4096", "2400", "1080", "720", "480", "360", "original"):
                if cover_map.get(quality):
                    cover_url = cover_map[quality]
                    break
            if not cover_url:
                cover_url = next((url for url in cover_map.values() if url), None)
        if not cover_url:
            cover_url = common.get("cover_url") or video.get("cover_url")

        # 提取即梦 AI 生图/图集图片
        image_list = []
        raw_images = detail.get("image_infos") or detail.get("image_list") or detail.get("images") or []
        if isinstance(raw_images, list):
            for img in raw_images:
                if isinstance(img, str) and img.startswith("http"):
                    image_list.append(img)
                elif isinstance(img, dict):
                    url_map = img.get("image_url_map") or img.get("cover_url_map") or {}
                    img_url = None
                    if isinstance(url_map, dict):
                        for quality in ("original", "4096", "2400", "1080", "720"):
                            if url_map.get(quality):
                                img_url = url_map[quality]
                                break
                        if not img_url:
                            img_url = next((u for u in url_map.values() if u), None)
                    if not img_url:
                        img_url = img.get("image_url") or img.get("url") or img.get("origin_url") or img.get("main_url")
                    if img_url:
                        image_list.append(img_url)

        image_list = list(dict.fromkeys(image_list))
        if not primary_video and not image_list and cover_url:
            image_list = [cover_url]

        primary_video = cls._sanitize_video_url(primary_video)
        video_list = []
        if primary_video:
            video_list.append(primary_video)
        if isinstance(transcoded, dict):
            for item in transcoded.values():
                if isinstance(item, dict) and item.get("video_url"):
                    u = cls._sanitize_video_url(item["video_url"])
                    if u and u not in video_list:
                        video_list.append(u)

        author_id = author.get("uid") or author.get("sec_uid") or ""
        return {
            "title": common.get("title") or None,
            "desc": common.get("description") or None,
            "video_url": primary_video,
            "video_list": video_list,
            "cover_url": cover_url,
            "author": {
                "nickname": author.get("name") or "",
                "author_id": str(author_id) if author_id else "",
                "avatar": author.get("avatar_url") or "",
            },
            "image_list": image_list,
        }

    @classmethod
    def _format_campaign_data(cls, data):
        page_info = data.get("page_info") or {}
        creation = page_info.get("creation") or {}
        meta = creation.get("metadata") or {}
        user_info = page_info.get("user_info") or creation.get("author") or {}

        raw_video = meta.get("video_url") or creation.get("video_url")
        download_info = meta.get("download_info")
        watermark_ending_url = None
        download_url = None
        if isinstance(download_info, dict):
            watermark_ending_url = download_info.get("watermark_ending_url")
            download_url = download_info.get("url")

        candidate_videos = []
        for candidate in (watermark_ending_url, raw_video, download_url):
            if candidate and isinstance(candidate, str) and candidate.startswith("http"):
                cleaned = cls._sanitize_video_url(candidate)
                if cleaned not in candidate_videos:
                    candidate_videos.append(cleaned)

        primary_video = candidate_videos[0] if candidate_videos else None
        video_list = candidate_videos

        cover_url = meta.get("cover_url") or creation.get("cover_url") or page_info.get("cover_url")

        image_list = []
        raw_images = creation.get("image_list") or meta.get("image_list") or creation.get("images") or []
        if isinstance(raw_images, list):
            for img in raw_images:
                if isinstance(img, str) and img.startswith("http"):
                    image_list.append(img)
                elif isinstance(img, dict):
                    u = img.get("image_url") or img.get("url") or img.get("origin_url")
                    if u:
                        image_list.append(u)
        image_list = list(dict.fromkeys(image_list))
        if not primary_video and not image_list and cover_url:
            image_list = [cover_url]

        title = meta.get("title") or creation.get("prompt") or page_info.get("title") or None
        desc = meta.get("description") or creation.get("desc") or page_info.get("desc") or None

        primary_video = cls._sanitize_video_url(primary_video)
        author_name = user_info.get("name") or user_info.get("nickname") or ""
        author_id = user_info.get("uid") or user_info.get("sec_uid") or user_info.get("author_id") or ""
        avatar = user_info.get("avatar_url") or user_info.get("avatar") or ""

        return {
            "title": title,
            "desc": desc,
            "video_url": primary_video,
            "video_list": video_list,
            "cover_url": cover_url,
            "author": {
                "nickname": author_name,
                "author_id": str(author_id) if author_id else "",
                "avatar": avatar,
            },
            "image_list": image_list,
        }

    @classmethod
    def _sanitize_video_url(cls, url):
        if not url or not isinstance(url, str):
            return url
        import re
        url = re.sub(r'&lr=[^&]+', '', url)
        url = re.sub(r'\?lr=[^&]+&', '?', url)
        url = url.replace('cd=0%7C0%7C1%7C3', 'cd=0%7C0%7C0%7C3').replace('cd=0|0|1|3', 'cd=0|0|0|3')
        return url

    @staticmethod
    def _best_transcoded_url(transcoded):
        if not isinstance(transcoded, dict):
            return None
        candidates = []
        for item in transcoded.values():
            if not isinstance(item, dict) or not item.get("video_url"):
                continue
            score = (
                int(item.get("width") or 0) * int(item.get("height") or 0),
                int(item.get("br") or item.get("bitrate") or 0),
            )
            candidates.append((score, item["video_url"]))
        return max(candidates, default=(None, None))[1]

    @staticmethod
    def _extract_item_id(url):
        if not url or not isinstance(url, str):
            return None
        parsed = urlparse(url)
        query = parse_qs(parsed.query)
        for key in ("published_item_id", "item_id", "id", "work_id", "feed_id", "projectId"):
            value = query.get(key, [None])[0]
            if value and value.isdigit():
                return value

        path_parts = [part for part in parsed.path.split("/") if part]
        for part in reversed(path_parts):
            if part.isdigit() and len(part) >= 10:
                return part
        return None

    @staticmethod
    def _extract_item_id_from_html(html_text):
        if not html_text or not isinstance(html_text, str):
            return None
        import re
        patterns = [
            r'["\']published_item_id["\']\s*:\s*["\']?(\d{10,25})',
            r'["\']item_id["\']\s*:\s*["\']?(\d{10,25})',
            r'["\']itemId["\']\s*:\s*["\']?(\d{10,25})',
            r'["\']work_id["\']\s*:\s*["\']?(\d{10,25})',
            r'["\']feed_id["\']\s*:\s*["\']?(\d{10,25})',
            r'["\']id["\']\s*:\s*["\']?(\d{15,25})',
        ]
        for pattern in patterns:
            match = re.search(pattern, html_text)
            if match:
                return match.group(1)
        return None

    def get_real_video_url(self):
        return self.data.get("video_url")

    def get_video_list(self):
        return self.data.get("video_list") or []

    def get_title_content(self):
        return self.data.get("title") or None

    def get_description(self):
        return self.data.get("desc") or None

    def get_cover_photo_url(self):
        return self.data.get("cover_url")

    def get_author_info(self):
        return self.data.get("author")

    def get_image_list(self):
        return self.data.get("image_list") or []
