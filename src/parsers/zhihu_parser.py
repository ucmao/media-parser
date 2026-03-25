import re
import json
import random
import urllib.parse
from bs4 import BeautifulSoup
from src.parsers.base_parser import BaseParser
from configs.general_constants import USER_AGENT_PC, USER_AGENT_M
from configs.logging_config import get_logger

logger = get_logger(__name__)

class ZhihuParser(BaseParser):
    def __init__(self, real_url):
        super().__init__(real_url)
        self.headers = {
            'User-Agent': "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1",
            'referer': 'https://www.zhihu.com/'
        }
        self.question_id, self.answer_id, self.zvideo_id, self.pin_id, self.article_id = self._extract_ids()
        self.data = self._fetch_data()

    def _extract_ids(self):
        question_id, answer_id, zvideo_id, pin_id, article_id = None, None, None, None, None
        
        # Match answer
        ans_match = re.search(r'question/(\d+)/answer/(\d+)', self.real_url)
        if ans_match:
            question_id = ans_match.group(1)
            answer_id = ans_match.group(2)
            return question_id, answer_id, zvideo_id, pin_id, article_id
            
        # Match direct answer url
        ans2_match = re.search(r'/answer/(\d+)', self.real_url)
        if ans2_match:
            answer_id = ans2_match.group(1)
            
        # Match zvideo
        zvideo_match = re.search(r'/zvideo/(\d+)', self.real_url)
        if zvideo_match:
            zvideo_id = zvideo_match.group(1)
            
        # Match pin
        pin_match = re.search(r'/pin/(\d+)', self.real_url)
        if pin_match:
            pin_id = pin_match.group(1)
            
        # Match article (zhuanlan)
        article_match = re.search(r'(?:zhuanlan\.zhihu\.com/p/|/article/)(\d+)', self.real_url)
        if article_match:
            article_id = article_match.group(1)
            
        return question_id, answer_id, zvideo_id, pin_id, article_id

    def _fetch_data(self):
        data = {}
        headers = {
            'User-Agent': random.choice(USER_AGENT_M),
            'Accept': 'application/json, text/plain, */*',
        }
        
        try:
            if self.answer_id:
                url = f"https://api.zhihu.com/answers/{self.answer_id}"
                resp = self.session.get(url, headers=headers, timeout=5)
                if resp.status_code == 200:
                    data = resp.json()
                    
            elif self.zvideo_id:
                url = f"https://api.zhihu.com/videos/{self.zvideo_id}"
                resp = self.session.get(url, headers=headers, timeout=5)
                if resp.status_code == 200:
                    data = resp.json()
                    
            elif self.pin_id:
                url = f"https://api.zhihu.com/pins/{self.pin_id}"
                resp = self.session.get(url, headers=headers, timeout=5)
                if resp.status_code == 200:
                    data = resp.json()
                    
            elif self.article_id:
                url = f"https://api.zhihu.com/articles/{self.article_id}"
                resp = self.session.get(url, headers=headers, timeout=5)
                if resp.status_code == 200:
                    data = resp.json()
                    
        except Exception as e:
            logger.warning(f"ZhihuParser fetch API error: {e}")
            
        return data

    def _get_lens_video_url(self, lens_id):
        if not lens_id: return None
        url = f"https://lens.zhihu.com/api/v4/videos/{lens_id}"
        headers = {
            'User-Agent': random.choice(USER_AGENT_M),
            'Referer': 'https://v.vzuu.com/',
            'Origin': 'https://v.vzuu.com'
        }
        try:
            resp = self.session.get(url, headers=headers, timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                playlist = data.get('playlist', {})
                # Try to get highest quality
                for quality in ['HD', 'SD', 'LD']:
                    if quality in playlist and playlist[quality].get('play_url'):
                        return playlist[quality]['play_url']
        except Exception as e:
            logger.warning(f"ZhihuParser lens video error: {e}")
        return None

    def get_real_video_url(self):
        # 1. Direct from API data (zvideo)
        try:
            if 'playlist' in self.data:
                playlist = self.data['playlist']
                for quality in ['HD', 'SD', 'LD']:
                    if quality in playlist and playlist[quality].get('play_url'):
                        return playlist[quality]['play_url']
        except: pass
        
        # 2. Extract from content (answer/article HTML)
        content = self.data.get('content', '')
        if content:
            # Look for lens video ID in data-lens-id
            lens_match = re.search(r'data-lens-id="(\d+)"', content)
            if lens_match:
                lens_id = lens_match.group(1)
                video_url = self._get_lens_video_url(lens_id)
                if video_url: return video_url
                
            # If there's an internal video link fallback
            video_match = re.search(r'a\s+href="([^"]+\.mp4[^"]*)"', content)
            if video_match:
                return video_match.group(1)
                
        return None

    def get_title_content(self):
        try:
            if 'question' in self.data and 'title' in self.data['question']:
                title = self.data['question']['title']
                excerpt = self.data.get('excerpt', '')
                return f"{title}\n{excerpt}".strip()
            elif 'title' in self.data:
                title = self.data['title']
                excerpt = self.data.get('excerpt', '')
                return f"{title}\n{excerpt}".strip()
            # For Pins, content might be in content list
            elif 'content' in self.data and isinstance(self.data['content'], list):
                text_parts = []
                for item in self.data['content']:
                    if item.get('type') == 'text' and item.get('content'):
                        text = re.sub(r'<[^>]+>', '', item['content']) # plain text
                        text_parts.append(text)
                return "\n".join(text_parts).strip()
        except: pass
        
        # Fallback raw html cleanup
        content = self.data.get('excerpt') or self.data.get('content', '')
        clean_content = re.sub(r'<[^>]+>', '', content)
        return clean_content[:100]

    def get_cover_photo_url(self):
        try:
            # From thumbnail or cover
            if 'thumbnail' in self.data and self.data['thumbnail']:
                return self.data['thumbnail']
            if 'image_url' in self.data and self.data['image_url']:
                return self.data['image_url']
            
            # Extract first image from HTML content
            content = self.data.get('content', '')
            if content and isinstance(content, str):
                img_match = re.search(r'<img[^>]+src="([^"]+)"', content)
                if img_match:
                    src = img_match.group(1)
                    # Filter out base64 or small icons if necessary, but take first usually
                    if src.startswith('http'):
                        return src
        except: pass
        return None

    def get_image_list(self):
        images = []
        try:
            # From Pins
            if 'content' in self.data and isinstance(self.data['content'], list):
                for item in self.data['content']:
                    if item.get('type') == 'image' and item.get('url'):
                        images.append(item['url'])
                if images:
                    return list(set(images))
            
            # Extract all images from HTML content (Answers/Articles)
            content = self.data.get('content', '')
            if content and isinstance(content, str):
                soup = BeautifulSoup(content, 'html.parser')
                for img in soup.find_all('img'):
                    src = img.get('data-original') or img.get('data-actualsrc') or img.get('src')
                    if src and src.startswith('http'):
                        # Zhihu often saves _hd, _r, _b variants, _r is original size
                        if '_hd' in src or '_hq' in src:
                            src = src.replace('_hd', '_r').replace('_hq', '_r')
                        images.append(src)
                # Keep unique and return
                return list(dict.fromkeys(images))
        except: pass
        return images

    def get_author_info(self):
        try:
            author = self.data.get('author', {})
            if author:
                # Handle cases where author might just be a string ID or dict
                if isinstance(author, dict):
                    return {
                        "nickname": author.get('name', ''),
                        "author_id": author.get('id', ''),
                        "avatar": author.get('avatar_url', '')
                    }
        except: pass
        return None


if __name__ == '__main__':
    real_url = 'https://www.zhihu.com/question/441253090/answer/1703034136'
    dl = ZhihuParser(real_url)
    print("-" * 30)
    print(f"作者信息：{dl.get_author_info()}")
    print(f"标题内容：{dl.get_title_content()[:50]}...")
    print(f"封面图片：{dl.get_cover_photo_url()}")
    print(f"视频链接：{dl.get_real_video_url()}")
    print(f"图片列表：{dl.get_image_list()[:2] if dl.get_image_list() else []}")
    print("-" * 30)
