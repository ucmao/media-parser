import logging
import re
import json
from src.parsers.base_parser import BaseParser
from configs.logging_config import get_logger

logger = get_logger(__name__)

class YoutubeParser(BaseParser):
    def __init__(self, real_url):
        super().__init__(real_url)
        self.headers = {
            'User-Agent': "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36",
            'Accept-Language': 'en-US,en;q=0.9',
        }
        self.post_data = self._fetch_post_data()

    def _fetch_post_data(self):
        try:
            resp = self.session.get(self.real_url, headers=self.headers, timeout=10)
            if resp.status_code == 200:
                match = re.search(r'ytInitialPlayerResponse\s*=\s*({.+?});', resp.text)
                if match:
                    player_res = json.loads(match.group(1))
                    return player_res
        except Exception as e:
            logger.warning(f"Youtube raw fetch failed: {e}")
            
        return {}


    def get_real_video_url(self):
        try:
            streamingData = self.post_data.get('streamingData', {})
            formats = streamingData.get('formats', [])
            
            # YouTube format with Audio and Video multiplexed
            for fmt in formats:
                # Prioritize 720p or 1080p multiplexed
                url = fmt.get('url')
                if url:
                    return url

        except Exception as e:
            logger.warning(f"Youtube URL extraction error: {e}")

        return None

    def get_audio_url(self):
        try:
            streamingData = self.post_data.get('streamingData', {})
            adaptiveFormats = streamingData.get('adaptiveFormats', [])
            
            # Prioritize m4a (audio/mp4) or webm audio
            for fmt in adaptiveFormats:
                mime = fmt.get('mimeType', '')
                if 'audio/' in mime:
                    url = fmt.get('url')
                    if url:
                        return url

        except Exception as e:
            logger.warning(f"Youtube audio URL extraction error: {e}")

        return None

    def get_title_content(self):
        details = self.post_data.get('videoDetails', {})
        title = details.get('title', '')
        desc = details.get('shortDescription', '')
        if desc:
            return f"{title}\n{desc[:200]}"
        return title

    def get_cover_photo_url(self):
        try:
            thumbnails = self.post_data.get('videoDetails', {}).get('thumbnail', {}).get('thumbnails', [])
            if thumbnails:
                # get max resolution thumbnail
                return thumbnails[-1].get('url')
        except:
             pass
        return None

    def get_image_list(self):
        return []

    def get_author_info(self):
        details = self.post_data.get('videoDetails', {})
        author_name = details.get('author', '')
        channel_id = details.get('channelId', '')
        
        avatar = None
        try:
             micro = self.post_data.get('microformat', {}).get('playerMicroformatRenderer', {})
             avatar = micro.get('ownerProfileUrl', '') 
        except:
             pass
             
        return {
            "nickname": author_name,
            "author_id": channel_id,
            "avatar": avatar
        }

if __name__ == '__main__':
    real_url = 'https://www.youtube.com/watch?v=kffacxfA7G4'
    dl = YoutubeParser(real_url)
    print("-" * 30)
    print(f"作者信息：{dl.get_author_info()}")
    print(f"标题内容：{dl.get_title_content()[:50]}...")
    print(f"封面图片：{dl.get_cover_photo_url()}")
    print(f"视频链接：{dl.get_real_video_url()}")
    print(f"音频链接：{dl.get_audio_url()} ")
    print("-" * 30)
