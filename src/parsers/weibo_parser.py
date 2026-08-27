import re
import json
import random
from urllib.parse import parse_qs, urlparse
from src.parsers.base_parser import BaseParser
from configs.general_constants import USER_AGENT_PC, USER_AGENT_M
from configs.logging_config import get_logger

logger = get_logger(__name__)

ALPHABET = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"

def base62_decode(s):
    res = 0
    for char in s:
        res = res * 62 + ALPHABET.index(char)
    return res

def mid_to_id(mid):
    mid = str(mid)[::-1]
    size = len(mid) // 4 if len(mid) % 4 == 0 else len(mid) // 4 + 1
    res = []
    for i in range(size):
        s = mid[i*4 : (i+1)*4][::-1]
        part = str(base62_decode(s))
        if i != size - 1:
            part = part.zfill(7)
        res.append(part)
    res.reverse()
    return str(int(''.join(res)))

class WeiboParser(BaseParser):
    def __init__(self, real_url):
        super().__init__(real_url)
        self.headers = {
            'User-Agent': random.choice(USER_AGENT_PC),
            'referer': 'https://weibo.com/'
        }
        self.video_oid = self._extract_video_oid()
        self.numeric_id = self._extract_id()
        self.post_data = self._fetch_post_data()

    def _extract_video_oid(self):
        """提取微博视频页使用的 ``1034:<media_id>`` 标识。"""
        if not self.real_url:
            return None

        fid = (parse_qs(urlparse(self.real_url).query).get("fid") or [""])[0]
        if re.fullmatch(r"\d+:\d+", fid):
            return fid
        if match := re.search(r"/(?:tv/)?show/(\d+:\d+)", urlparse(self.real_url).path):
            return match.group(1)
        return None

    def _extract_id(self):
        if not self.real_url:
            return None

        fid = (parse_qs(urlparse(self.real_url).query).get("fid") or [""])[0]
        if match := re.fullmatch(r"\d+:(\d+)", fid):
            return match.group(1)

        # 视频页会从 video.weibo.com/show?fid=1034:... 跳转到
        # weibo.com/tv/show/1034:...，两种 URL 都使用同一个数字微博 ID。
        if match := re.search(r"/(?:tv/)?show/\d+:(\d+)", urlparse(self.real_url).path):
            return match.group(1)
            
        # PC URL, like: weibo.com/123456789/O8yqz0I8Q
        match = re.search(r'weibo\.com/\d+/([a-zA-Z0-9]+)', self.real_url)
        if match:
            return mid_to_id(match.group(1))
            
        # Mobile URL, like: m.weibo.cn/status/4921612...
        match = re.search(r'weibo\.cn/(?:status/|detail/|statuses/show\?id=)(\d+)', self.real_url)
        if match:
            return match.group(1)
            
        # Query parameter fallback
        match = re.search(r'id=(\d+)', self.real_url)
        if match:
            return match.group(1)
            
        # Base62 Query parameter fallback
        match = re.search(r'id=([a-zA-Z0-9]+)', self.real_url)
        if match:
            return mid_to_id(match.group(1))

        # Check for /O8yqz0I8Q in general
        match = re.search(r'/([a-zA-Z0-9]{9})\b', self.real_url)
        if match:
            return mid_to_id(match.group(1))

        return None

    def _fetch_post_data(self):
        if self.video_oid:
            data = self._fetch_video_page_data()
            if data:
                return data

        if not self.numeric_id:
            logger.error("WeiboParser: Could not extract numeric ID.")
            return {}
            
        url = f"https://m.weibo.cn/statuses/show?id={self.numeric_id}"
        headers = {
            'User-Agent': random.choice(USER_AGENT_M),
            'Accept': 'application/json, text/plain, */*',
            'MWeibo-Pwa': '1',
            'X-Requested-With': 'XMLHttpRequest',
            'Referer': f'https://m.weibo.cn/detail/{self.numeric_id}'
        }
        try:
            resp = self.session.get(url, headers=headers, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                if data.get('ok') == 1:
                    return data.get('data', {})
        except Exception as e:
            logger.warning(f"Weibo API fetch failed: {e}")
            
        return self._fallback_fetch_ajax()

    @staticmethod
    def _parse_jsonp(text):
        try:
            return json.loads(text[text.index("(") + 1:text.rindex(")")])
        except (ValueError, json.JSONDecodeError):
            return {}

    def _initialize_visitor_session(self):
        """初始化微博公开页所需的临时访客会话。"""
        fingerprint = {
            "os": "1",
            "browser": "Chrome",
            "fonts": "undefined",
            "screenInfo": "1440*900*24",
            "plugins": "",
            "ls": "undefined",
            "wh": "",
            "version": "1.0.0",
            "vendor": "Google Inc.",
            "ua": "Mozilla/5.0",
        }
        headers = {**self.headers, "Referer": "https://weibo.com/"}
        try:
            response = self.session.get(
                "https://passport.weibo.com/visitor/genvisitor",
                params={"cb": "parser_callback", "fp": json.dumps(fingerprint, separators=(",", ":"))},
                headers=headers,
                timeout=10,
            )
            tid = self._parse_jsonp(response.text).get("data", {}).get("tid")
            if not tid:
                return False
            response = self.session.get(
                "https://passport.weibo.com/visitor/visitor",
                params={
                    "a": "incarnate", "t": tid, "w": "2", "c": "095", "gc": "",
                    "cb": "parser_callback", "from": "weibo", "_rand": str(random.random()),
                },
                headers=headers,
                timeout=10,
            )
            return self._parse_jsonp(response.text).get("retcode") == 20000000
        except Exception as exc:
            logger.warning(f"Weibo visitor initialization failed: {exc}")
            return False

    def _fetch_video_page_data(self):
        if not self._initialize_visitor_session():
            return {}

        path = urlparse(self.real_url).path
        headers = {
            **self.headers,
            "Referer": self.real_url,
            "PAGE-REFERER": path,
            "Content-Type": "application/x-www-form-urlencoded",
        }
        payload = {"Component_Play_Playinfo": {"oid": self.video_oid}}
        try:
            response = self.session.post(
                "https://weibo.com/tv/api/component",
                data={"data": json.dumps(payload, separators=(",", ":"))},
                headers=headers,
                timeout=10,
            )
            data = response.json()
            if data.get("code") == "100000":
                return data.get("data", {}).get("Component_Play_Playinfo", {})
        except Exception as exc:
            logger.warning(f"Weibo video component fetch failed: {exc}")
        return {}

    def _fallback_fetch_ajax(self):
        url = f"https://m.weibo.cn/detail/{self.numeric_id}"
        headers = {
             'User-Agent': random.choice(USER_AGENT_M),
             'Accept': 'text/html,application/xhtml+xml,application/xml;'
        }
        try:
            resp = self.session.get(url, headers=headers, timeout=10)
            match = re.search(r'\$render_data\s*=\s*\[(.*?)\]\[0\]\s*\|\|', resp.text, re.DOTALL)
            if match:
                data = match.group(1)
                j = json.loads(data)
                return j.get('status', {})
        except Exception as e:
            logger.warning(f"Weibo chunk fallback fetch failed: {e}")
            
        # Fallback to PC Ajax API
        url_pc = f"https://weibo.com/ajax/statuses/show?id={self.numeric_id}"
        headers_pc = {
            'User-Agent': random.choice(USER_AGENT_PC),
            'Referer': 'https://weibo.com/',
        }
        try:
            resp = self.session.get(url_pc, headers=headers_pc, timeout=10)
            if resp.status_code == 200:
                return resp.json()
        except Exception as e:
            logger.error(f"Weibo PC Ajax fetch failed: {e}")
            
        return {}

    def get_real_video_url(self):
        try:
            urls = self.post_data.get("urls", {})
            if urls:
                url = next((value for value in urls.values() if value), None)
                if url:
                    return f"https:{url}" if url.startswith("//") else url

            # First try m.weibo.cn format
            page_info = self.post_data.get('page_info', {})
            media_info = page_info.get('media_info', {})
            
            url = media_info.get('mp4_hd_url') or media_info.get('mp4_sd_url') or media_info.get('stream_url_hd') or media_info.get('stream_url')
            if url:
                return url
                
            playback_list = media_info.get('playback_list', [])
            for pb in playback_list:
                if 'play_info' in pb and pb['play_info'].get('url'):
                    return pb['play_info']['url']
                    
        except Exception:
            pass
            
        return None

    def get_title_content(self):
        content = (
            self.post_data.get('text_raw', '')
            or self.post_data.get('text', '')
            or self.post_data.get('content', '')
            or self.post_data.get('title', '')
        )
        # Simple cleanup if there is HTML
        content = re.sub(r'<[^>]+>', '', content)
        return content

    def get_cover_photo_url(self):
        try:
            cover = self.post_data.get("cover_image")
            if cover:
                return f"https:{cover}" if cover.startswith("//") else cover
            page_info = self.post_data.get('page_info', {})
            if page_info.get('page_pic') and page_info['page_pic'].get('url'):
                return page_info['page_pic']['url']
        except:
            pass
        return None

    def get_image_list(self):
        try:
            pics = self.post_data.get('pics', [])
            return [p.get('large', {}).get('url') for p in pics if p.get('large', {}).get('url')]
        except:
            return []

    def get_author_info(self):
        try:
            user = self.post_data.get('user', {})
            if not user and not self.post_data.get("author"):
                return None
            return {
                "nickname": user.get('screen_name', '') or self.post_data.get("author", ""),
                "author_id": str(user.get('id', '') or self.post_data.get("author_id", "")),
                "avatar": user.get('avatar_hd', '') or user.get('profile_image_url', '') or self.post_data.get("avatar", "")
            }
        except:
            return None
