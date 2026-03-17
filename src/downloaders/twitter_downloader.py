import re
from src.downloaders.base_downloader import BaseDownloader
from configs.logging_config import get_logger

logger = get_logger(__name__)

class TwitterDownloader(BaseDownloader):
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
            'nocheckcertificate': True
        }
        
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(self.real_url, download=False)
                return info
        except Exception as e:
            logger.warning(f"yt-dlp extract failed for Twitter: {e}")
            
        return {}


    def get_real_video_url(self):
        try:
            url = self.post_data.get('url')
            # yt-dlp returns best format url directly for twitter
            if url and (self.post_data.get('ext') == 'mp4' or 'video' in self.post_data.get('formats', [{}])[0].get('vcodec', 'none')):
                 return url
                 
            # checking formats if direct url is missing or not optimal
            formats = self.post_data.get('formats', [])
            best_fmt = None
            max_height = -1
            for fmt in formats:
                 if fmt.get('ext') == 'mp4' and fmt.get('vcodec') != 'none':
                     height = fmt.get('height', 0) or 0
                     if height > max_height:
                          max_height = height
                          best_fmt = fmt.get('url')
            if best_fmt:
                 return best_fmt
                 
        except Exception as e:
             logger.warning(f"Error extracting Twitter video url: {e}")
        return None

    def get_title_content(self):
        title = self.post_data.get('title', '')
        desc = self.post_data.get('description', '')
        if desc and title not in desc:
            return f"{title}\n{desc[:200]}"
        return title or desc

    def get_cover_photo_url(self):
        return self.post_data.get('thumbnail', None)

    def get_image_list(self):
        images = []
        entries = self.post_data.get('entries', []) # rarely used for twitter in yt-dlp but just in case
        if entries:
             # Twitter might expose it as a gallery
             for entry in entries:
                 if entry.get('ext') != 'mp4':
                     img_url = entry.get('url')
                     if img_url:
                         images.append(img_url)
                         
        # If it's pure image
        elif self.post_data.get('url') and self.post_data.get('ext') in ['jpg', 'png', 'jpeg']:
             images.append(self.post_data.get('url'))
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
    # Test with a known tweet that contains a video (this is a random spacex video tweet just for placeholder)
    real_url = 'https://twitter.com/SpaceX/status/1768270529452372412' 
    dl = TwitterDownloader(real_url)
    print("-" * 30)
    print(f"作者信息：{dl.get_author_info()}")
    print(f"标题内容：{dl.get_title_content()[:50]}...")
    print(f"封面图片：{dl.get_cover_photo_url()}")
    print(f"视频链接：{dl.get_real_video_url()}")
    print(f"图集数：{len(dl.get_image_list())}")
    print("-" * 30)
