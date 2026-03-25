import logging
from src.parsers.base_parser import BaseParser
from configs.logging_config import get_logger

logger = get_logger(__name__)

class InstagramParser(BaseParser):
    def __init__(self, real_url):
        super().__init__(real_url)
        self.post_data = self._fetch_post_data()

    def _fetch_post_data(self):
        try:
            import yt_dlp
        except ImportError:
            logger.error("yt-dlp not installed. run 'pip install yt-dlp'")
            return {}
            
        ydl_opts = {
            'quiet': True,
            'skip_download': True,
            'extract_flat': False,
            'nocheckcertificate': True,
            # For instagram, sometimes it returns a playlist for multi-image posts
        }
        
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(self.real_url, download=False)
                return info
        except Exception as e:
            logger.warning(f"yt-dlp extract failed for Instagram: {e}")
            
        return {}


    def get_real_video_url(self):
        try:
            entries = self.post_data.get('entries', [])
            if entries:
                # might be a playlist/carousel. Find the first video
                for entry in entries:
                     if entry.get('ext') == 'mp4' or 'video' in entry.get('formats', [{}])[0].get('vcodec', 'none'):
                          return entry.get('url')
                          
            url = self.post_data.get('url')
            # If the media is pure video, url is directly present
            if url and self.post_data.get('ext') == 'mp4':
                 return url
                 
        except Exception as e:
             logger.warning(f"Error extracting instagram video url: {e}")
        return None

    def get_title_content(self):
        title = self.post_data.get('title', '')
        desc = self.post_data.get('description', '')
        if desc and title not in desc:
            return f"{title}\n{desc[:200]}"
        return title or desc

    def get_cover_photo_url(self):
        entries = self.post_data.get('entries', [])
        if entries:
             return entries[0].get('thumbnail')
        return self.post_data.get('thumbnail', None)

    def get_image_list(self):
        images = []
        entries = self.post_data.get('entries', [])
        if entries:
             # It's a carousel, let's extract images (jpg/png)
             for entry in entries:
                 if entry.get('ext') != 'mp4':
                     img_url = entry.get('url')
                     if img_url:
                         images.append(img_url)
                         
        # If it's a single image post
        elif self.post_data.get('ext') != 'mp4':
             img = self.post_data.get('url')
             if img:
                 images.append(img)
        return images

    def get_author_info(self):
        nickname = self.post_data.get('uploader', '')
        author_id = self.post_data.get('uploader_id', '')
        return {
            "nickname": nickname,
            "author_id": author_id,
            "avatar": None
        }

if __name__ == '__main__':
    # Test will likely fail without cookies on local, but logic is sound
    real_url = 'https://www.instagram.com/p/C-UqV3YpU3Z/?hl=en'
    dl = InstagramParser(real_url)
    print("-" * 30)
    print(f"作者信息：{dl.get_author_info()}")
    print(f"标题内容：{dl.get_title_content()[:50]}...")
    print(f"封面图片：{dl.get_cover_photo_url()}")
    print(f"视频链接：{dl.get_real_video_url()}")
    print(f"图集数：{len(dl.get_image_list())}")
    print("-" * 30)
