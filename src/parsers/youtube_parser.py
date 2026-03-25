import logging
import re
import json
import urllib.parse
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
                    
            # If no direct URL, it might have a signature cipher
            for fmt in formats:
                 s_cipher = fmt.get('signatureCipher')
                 if s_cipher:
                     # fallback to yt-dlp if raw extraction fails or needs decipher
                     return self._fallback_ytdlp_url()
                     
        except Exception as e:
            logger.warning(f"Youtube URL extraction error: {e}")
            
        return self._fallback_ytdlp_url()
        
    def _fallback_ytdlp_url(self):
        try:
            import yt_dlp
            # We want to extract specifically format with both audio and video, up to 1080p
            ydl_opts = {
                'quiet': True,
                'skip_download': True,
                'extract_flat': False,
                'nocheckcertificate': True,
                'format': 'best[ext=mp4]',
                'extractor_args': {'youtube': {'player_client': ['web_creator', 'web']}},
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(self.real_url, download=False)
                return info.get('url')
        except Exception as e:
             logger.warning(f"yt-dlp fallback failed: {e}")
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
                        
            # If no direct URL, it might have a signature cipher
            for fmt in adaptiveFormats:
                 if 'audio/' in fmt.get('mimeType', ''):
                     s_cipher = fmt.get('signatureCipher')
                     if s_cipher:
                         return self._fallback_ytdlp_audio_url()
                         
        except Exception as e:
            logger.warning(f"Youtube audio URL extraction error: {e}")
            
        return self._fallback_ytdlp_audio_url()

    def _fallback_ytdlp_audio_url(self):
        try:
            import yt_dlp
            ydl_opts = {
                'quiet': True,
                'skip_download': True,
                'extract_flat': False,
                'nocheckcertificate': True,
                'format': 'bestaudio[ext=m4a]/bestaudio',
                'extractor_args': {'youtube': {'player_client': ['web_creator', 'web']}},
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(self.real_url, download=False)
                return info.get('url')
        except Exception as e:
             logger.warning(f"yt-dlp audio fallback failed: {e}")
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
    # Try a video with signatureCipher (e.g. music video)
    real_url = 'https://www.youtube.com/watch?v=kffacxfA7G4' # Justin Bieber - Baby
    dl = YoutubeParser(real_url)
    print("-" * 30)
    print(f"作者信息：{dl.get_author_info()}")
    print(f"标题内容：{dl.get_title_content()[:50]}...")
    print(f"封面图片：{dl.get_cover_photo_url()}")
    url = dl.get_real_video_url()
    print(f"视频链接长度：{len(url) if url else 'None'} ")
    audio_url = dl.get_audio_url()
    print(f"音频链接长度：{len(audio_url) if audio_url else 'None'} ")
    print("-" * 30)
