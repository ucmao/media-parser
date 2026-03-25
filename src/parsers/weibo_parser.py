import re
import json
import random
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
        self.numeric_id = self._extract_id()
        self.post_data = self._fetch_post_data()

    def _extract_id(self):
        if not self.real_url:
            return None
            
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
        content = self.post_data.get('text_raw', '') or self.post_data.get('text', '')
        # Simple cleanup if there is HTML
        content = re.sub(r'<[^>]+>', '', content)
        return content

    def get_cover_photo_url(self):
        try:
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
            if not user:
                return None
            return {
                "nickname": user.get('screen_name', ''),
                "author_id": str(user.get('id', '')),
                "avatar": user.get('avatar_hd', '') or user.get('profile_image_url', '')
            }
        except:
            return None


if __name__ == '__main__':
    real_url = 'https://weibo.com/5756404150/QwnWJ1dtK'
    dl = WeiboParser(real_url)
    print("-" * 30)
    print(f"作者信息：{dl.get_author_info()}")
    print(f"标题内容：{dl.get_title_content()[:30]}...")
    print(f"封面图片：{dl.get_cover_photo_url()}")
    print(f"视频链接：{dl.get_real_video_url()}")
    print(f"图片列表：{dl.get_image_list()}")
    print("-" * 30)
