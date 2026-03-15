import random
from utils.web_fetcher import UrlParser
from src.downloaders.base_downloader import BaseDownloader
from configs.general_constants import USER_AGENT_PC
from configs.logging_config import get_logger

logger = get_logger(__name__)


class PipigaoxiaoDownloader(BaseDownloader):
    def __init__(self, url):
        super().__init__(url)
        self.headers = {
            "content-type": "application/json; charset=UTF-8",
            'User-Agent': random.choice(USER_AGENT_PC),
            'referer': self.real_url
        }
        self.video_pid = UrlParser.get_video_id(self.real_url)
        self.data = self.fetch_html_data()

    def fetch_html_data(self):
        jsp_url = "https://h5.pipigx.com/ppapi/share/fetch_content"
        params = {
            'mid': 'null',
            'pid': int(self.video_pid),
            'type': "post"
        }
        try:
            response = self.session.post(jsp_url, json=params, headers=self.headers, timeout=5)
            if response.status_code == 200:
                return response.json()
            else:
                logger.warning(f"Pipigaoxiao API request failed: {response.status_code}")
                return None
        except Exception as e:
            logger.error(f"Pipigaoxiao API error: {e}")
            return None

    def get_real_video_url(self):
        try:
            if not self.data: return None
            post = self.data.get('data', {}).get('post', {})
            imgs = post.get('imgs', [])
            if not imgs: return None

            imgs_id = imgs[0].get('id')
            videos = post.get('videos', {})
            video_info = videos.get(str(imgs_id))
            return video_info.get('url') if video_info else None
        except Exception as e:
            logger.warning(f"Failed to parse Pipigaoxiao video URL: {e}")
            return None

    def get_title_content(self):
        try:
            if not self.data: return ""
            return self.data.get('data', {}).get('post', {}).get('content', '')
        except Exception as e:
            logger.warning(f"Failed to parse Pipigaoxiao title content: {e}")
            return ""

    def get_cover_photo_url(self):
        try:
            if not self.data: return ""
            imgs = self.data.get('data', {}).get('post', {}).get('imgs', [])
            if imgs:
                imgs_id = imgs[0].get('id')
                return f'https://file.ippzone.com/img/view/id/{imgs_id}'
            return ""
        except Exception as e:
            logger.warning(f"Failed to parse Pipigaoxiao cover URL: {e}")
            return ""

    def get_author_info(self):
        try:
            data_dict = self.data
            post_info = data_dict.get('data', {}).get('post', {})
            # 尝试获取外层的 user 节点（有时接口会返回）
            user_info = data_dict.get('data', {}).get('user', {})

            # 提取唯一标识 (mid)，优先从 user 取，没有则从 post 取
            unique_id = str(user_info.get('mid') or post_info.get('mid', ''))

            # 提取昵称
            nickname = user_info.get('name', '')

            # 提取头像：皮皮搞笑的 avatar 通常是图片 ID，如果是数字则拼接为完整链接
            avatar_val = user_info.get('avatar', '')
            if str(avatar_val).isdigit() and avatar_val:
                avatar = f'https://file.ippzone.com/img/view/id/{avatar_val}'
            else:
                avatar = str(avatar_val)

            author_info = {
                'nickname': nickname,
                'author_id': unique_id,
                'avatar_url': avatar
            }
            return author_info

        except Exception as e:
            logger.warning(f"Failed to parse author info: {e}")
            return {}


if __name__ == '__main__':
    real_url = 'https://h5.pipigx.com/pp/post/815491325984?pid=815491325984&type=post'

    dl = PipigaoxiaoDownloader(real_url)

    print("-" * 30)
    print(f"作者信息：{dl.get_author_info()}")
    print(f"标题内容：{dl.get_title_content()[:30]}...")  # 仅打印前30字
    print(f"封面图片：{dl.get_cover_photo_url()}")
    print(f"视频链接：{dl.get_real_video_url()}")
    print("-" * 30)