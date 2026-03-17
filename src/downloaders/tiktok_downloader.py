import re
import json
import random
from src.downloaders.base_downloader import BaseDownloader
from configs.general_constants import USER_AGENT_PC, USER_AGENT_M
from configs.logging_config import get_logger

logger = get_logger(__name__)

class TiktokDownloader(BaseDownloader):
    def __init__(self, real_url):
        super().__init__(real_url)
        self.headers = {
            'User-Agent': random.choice(USER_AGENT_PC),
        }
        self.video_id = self._extract_id()
        self.post_data = self._fetch_post_data()

    def _extract_id(self):
        if not self.real_url:
            return None
            
        # Match URL patterns like:
        # https://www.tiktok.com/@username/video/7106594312292453675
        # https://m.tiktok.com/v/7106594312292453675.html
        # https://vt.tiktok.com/ZSdQXXXXX/ -> redirect
        
        match = re.search(r'/video/(\d+)', self.real_url)
        if match:
            return match.group(1)
            
        match = re.search(r'/v/(\d+)', self.real_url)
        if match:
            return match.group(1)
            
        return None

    def _fetch_post_data(self):
        if not self.video_id:
            logger.error("TiktokDownloader: Could not extract video ID.")
            return {}
            
        # Using tikwm API as primary, since TikTok's own web download addresses
        # are protected by rigid browser fingerprints and Akamai WAF
        url = "https://www.tikwm.com/api/"
        params = {
            'url': self.real_url,
            'count': 12,
            'cursor': 0,
            'web': 1,
            'hd': 1
        }
        try:
            resp = self.session.get(url, params=params, headers=self.headers, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                if data.get('code') == 0:
                     return data.get('data', {})
        except Exception as e:
            logger.warning(f"Tiktok API fetch failed: {e}")
            
        return {}

    def get_real_video_url(self):
        try:
            # prefer hdplay then play
            play_addr = self.post_data.get('hdplay') or self.post_data.get('play')
            if play_addr:
                if play_addr.startswith('/'):
                     return f"https://www.tikwm.com{play_addr}"
                return play_addr
        except Exception as e:
            logger.warning(f"Failed to extract real video url: {e}")
            
        return None

    def get_title_content(self):
        return self.post_data.get('title', '')

    def get_cover_photo_url(self):
        try:
            cover = self.post_data.get('cover')
            if cover:
                 if cover.startswith('/'):
                     return f"https://www.tikwm.com{cover}"
                 return cover
        except:
            pass
        return None

    def get_image_list(self):
        images = []
        try:
            # TikWM supports photo mode as well in the "images" field array
            if 'images' in self.post_data and isinstance(self.post_data['images'], list):
                for img in self.post_data['images']:
                    images.append(img)
        except:
            pass
        return images

    def get_author_info(self):
        try:
            author = self.post_data.get('author', {})
            if author:
                uid = author.get('unique_id', '') or author.get('id', '')
                nickname = author.get('nickname', '')
                avatar = author.get('avatar', '')
                if avatar.startswith('/'):
                     avatar = f"https://www.tikwm.com{avatar}"
                
                return {
                    "nickname": nickname,
                    "author_id": str(uid),
                    "avatar": avatar
                }
        except:
            pass
        return None


if __name__ == '__main__':
    real_url = 'https://www.tiktok.com/@tiktok/video/7106594312292453675'
    dl = TiktokDownloader(real_url)
    print("-" * 30)
    print(f"作者信息：{dl.get_author_info()}")
    print(f"标题内容：{dl.get_title_content()[:30]}...")
    print(f"封面图片：{dl.get_cover_photo_url()}")
    print(f"视频链接：{dl.get_real_video_url()}")
    print(f"图片列表：{dl.get_image_list()}")
    print("-" * 30)
