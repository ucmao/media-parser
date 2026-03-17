import re
import json
import random
import urllib.parse
from src.downloaders.base_downloader import BaseDownloader
from configs.general_constants import USER_AGENT_PC, USER_AGENT_M
from configs.logging_config import get_logger

logger = get_logger(__name__)

class AcfunDownloader(BaseDownloader):
    def __init__(self, real_url):
        super().__init__(real_url)
        self.headers = {
            'User-Agent': random.choice(USER_AGENT_PC),
        }
        self.video_id = self._extract_video_id()
        self.post_data = self._fetch_post_data()

    def _extract_video_id(self):
        if not self.real_url:
            return None
            
        # PC URL, like: acfun.cn/v/ac43445963
        match = re.search(r'acfun\.cn/v/(ac\d+)', self.real_url)
        if match:
            return match.group(1)
            
        return None

    def _fetch_post_data(self):
        try:
            resp = self.session.get(self.real_url, headers=self.headers, timeout=10)
            if resp.status_code == 200:
                # Find window.pageInfo
                match = re.search(r'window\.pageInfo\s*=\s*(?:window\.videoInfo\s*=\s*)?({.*?});', resp.text)
                if match:
                    json_data = json.loads(match.group(1))
                    return json_data
        except Exception as e:
            logger.warning(f"AcFun fetch failed: {e}")
            
        return {}


    def get_real_video_url(self):
        try:
            js_info = self.post_data.get('currentVideoInfo', {})
            ksPlayJson = js_info.get('ksPlayJson')
            if ksPlayJson:
                play_data = json.loads(ksPlayJson)
                adaptationSet = play_data.get('adaptationSet', [])
                if adaptationSet and isinstance(adaptationSet, list):
                     representation = adaptationSet[0].get('representation', [])
                     if representation and isinstance(representation, list):
                          # AcFun uses m3u8 for HLS streaming instead of direct MP4 sometimes, 
                          # but `url` provides the manifest format which we can return.
                          url = representation[0].get('url')
                          return url
                          
        except Exception as e:
            logger.warning(f"Failed to extract real video url: {e}")
            
        return None

    def get_title_content(self):
        return self.post_data.get('title', '')

    def get_cover_photo_url(self):
        return self.post_data.get('coverUrl', None)

    def get_image_list(self):
        return []

    def get_author_info(self):
        try:
            author = self.post_data.get('user', {})
            if author:
                return {
                    "nickname": author.get('name', ''),
                    "author_id": str(author.get('id', '')),
                    "avatar": author.get('headUrl', '')
                }
        except:
             pass
        return None


if __name__ == '__main__':
    real_url = 'https://www.acfun.cn/v/ac43445963'
    dl = AcfunDownloader(real_url)
    print("-" * 30)
    print(f"作者信息：{dl.get_author_info()}")
    print(f"标题内容：{dl.get_title_content()[:50]}...")
    print(f"封面图片：{dl.get_cover_photo_url()}")
    print(f"视频链接：{dl.get_real_video_url()}")
    print("-" * 30)
