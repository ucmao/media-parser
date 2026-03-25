import re
import json
import random
from src.parsers.base_parser import BaseParser
from configs.general_constants import USER_AGENT_PC, USER_AGENT_M
from configs.logging_config import get_logger

logger = get_logger(__name__)

class XiguaParser(BaseParser):
    def __init__(self, real_url):
        super().__init__(real_url)
        self.headers = {
            'User-Agent': random.choice(USER_AGENT_M),
        }
        self.video_id = self._extract_video_id()
        self.post_data = self._fetch_post_data()

    def _extract_video_id(self):
        if not self.real_url:
            return None
            
        # PC URL, like: ixigua.com/7123456789012345678
        # Or Mobile URL: m.ixigua.com/video/7123456789012345678/
        match = re.search(r'ixigua\.com/(?:video/)?(\d+)', self.real_url)
        if match:
            return match.group(1)
            
        return None

    def _fetch_post_data(self):
        if not self.video_id:
            logger.error("XiguaParser: Could not extract video ID.")
            return {}
            
        req_url = (
            f"https://m.ixigua.com/douyin/share/video/{self.video_id}"
            f"?aweme_type=107&schema_type=1&utm_source=copy"
            f"&utm_campaign=client_share&utm_medium=android&app=aweme"
        )
        
        try:
            resp = self.session.get(req_url, headers=self.headers, timeout=10)
            
            # Using _ROUTER_DATA
            pattern = re.compile(
                pattern=r"window\._ROUTER_DATA\s*=\s*(.*?)</script>",
                flags=re.DOTALL,
            )
            find_res = pattern.search(resp.text)

            if find_res and find_res.group(1):
                json_data = json.loads(find_res.group(1).strip())
                original_video_info = json_data.get("loaderData", {}).get("video_(id)/page", {}).get("videoInfoRes", {})
                
                item_list = original_video_info.get("item_list", [])
                if item_list:
                    return item_list[0]
                    
            # Fallback for PC SSR hydration data
            ssr_pattern = re.compile(r"window\._SSR_HYDRATED_DATA\s*=\s*(.*?)</script>", re.DOTALL)
            ssr_res = ssr_pattern.search(resp.text)
            if ssr_res:
                data_str = ssr_res.group(1).replace('undefined', 'null')
                json_data = json.loads(data_str)
                # Parse structure from SSR
                if "anyVideo" in json_data and "item_info" in json_data["anyVideo"]:
                    return json_data["anyVideo"]["item_info"]
                
        except Exception as e:
            logger.warning(f"Xigua API fetch failed: {e}")
            
        return {}


    def get_real_video_url(self):
        try:
            video = self.post_data.get('video', {})
            play_addr = video.get('play_addr', {})
            url_list = play_addr.get('url_list', [])
            
            if url_list:
                # convert playwm to play if we want watermark-free, although usually url_list contains WM-free endpoints in Douyin APIs
                return url_list[0].replace("playwm", "play")
                
            # If from SSR SSR_HYDRATED_DATA AnyVideo Structure:
            if "video_list" in video:
                # get max resolution
                resolutions = ["video_4", "video_3", "video_2", "video_1"]
                for res in resolutions:
                    if res in video["video_list"]:
                        v_info = video["video_list"][res]
                        if v_info.get("main_url"):
                            import base64
                            return base64.b64decode(v_info["main_url"]).decode("utf-8")
        except Exception as e:
            logger.warning(f"Failed to extract real video url: {e}")
            
        return None

    def get_title_content(self):
        # 'desc' is used in _ROUTER_DATA, 'title' might be in others
        content = self.post_data.get('desc', '') or self.post_data.get('title', '')
        return content

    def get_cover_photo_url(self):
        try:
            video = self.post_data.get('video', {})
            cover = video.get('cover', {})
            url_list = cover.get('url_list', [])
            if url_list:
                return url_list[0]
                
            # SSR fallback
            poster_url = video.get('poster_url', '')
            if poster_url:
                return poster_url
        except:
            pass
        return None

    def get_image_list(self):
        return []

    def get_author_info(self):
        try:
            author = self.post_data.get('author', {})
            if not author:
                # SSR fallback uses user_info
                author = self.post_data.get('user_info', {})
                
            if author:
                nickname = author.get('nickname', '') or author.get('name', '')
                uid = author.get('unique_id', '') or author.get('user_id', '')
                
                avatar = ""
                avatar_thumb = author.get('avatar_thumb', {})
                if 'url_list' in avatar_thumb and avatar_thumb['url_list']:
                    avatar = avatar_thumb['url_list'][0]
                else:
                    avatar = author.get('avatar_url', '')
                    
                return {
                    "nickname": nickname,
                    "author_id": str(uid),
                    "avatar": avatar
                }
        except:
            pass
        return None


if __name__ == '__main__':
    # Test
    real_url = 'https://www.ixigua.com/7123456789012345678'
    dl = XiguaParser(real_url)
    print("-" * 30)
    print(f"作者信息：{dl.get_author_info()}")
    print(f"标题内容：{dl.get_title_content()[:30]}...")
    print(f"封面图片：{dl.get_cover_photo_url()}")
    print(f"视频链接：{dl.get_real_video_url()}")
    print("-" * 30)
