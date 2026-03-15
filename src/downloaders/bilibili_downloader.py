import re
import json
import random
from src.downloaders.base_downloader import BaseDownloader
from configs.general_constants import USER_AGENT_PC
from configs.logging_config import get_logger
logger = get_logger(__name__)


class BilibiliDownloader(BaseDownloader):
    def __init__(self, real_url):
        super().__init__(real_url)
        self.headers = {
            "content-type": "application/json; charset=UTF-8",
            'User-Agent': random.choice(USER_AGENT_PC),
            'referer': self.real_url
        }
        self.data, self.data2 = self.fetch_html_data()

    def fetch_html_data(self):
        self.html_content = self.fetch_html_content()
        pattern_playinfo = re.compile(r'window\.__playinfo__\s*=\s*(\{.*\})', re.DOTALL)
        json_data = BaseDownloader.parse_html_data(self.html_content, pattern_playinfo)
        pattern_initial = re.compile(r'window\.__INITIAL_STATE__\s*=\s*(\{.*\});', re.DOTALL)
        json_data2 = BaseDownloader.parse_html_data(self.html_content, pattern_initial)
        return json_data, json_data2

    def get_real_video_url(self):
        try:
            data_dict = json.loads(self.data)
            videos = data_dict.get('data', {}).get('dash', {}).get('video', [])
            if videos:
                return videos[0].get('baseUrl')
            return None
        except (KeyError, json.JSONDecodeError, TypeError) as e:
            logger.warning(f"Failed to parse Bilibili video URL: {e}")
            return None

    def get_title_content(self):
        try:
            data_dict = json.loads(self.data2)
            return data_dict.get('videoData', {}).get('title', '')
        except (KeyError, json.JSONDecodeError, TypeError) as e:
            logger.warning(f"Failed to parse Bilibili title: {e}")
            return ""

    def get_cover_photo_url(self):
        try:
            data_dict = json.loads(self.data2)
            return data_dict.get('videoData', {}).get('pic', '')
        except (KeyError, json.JSONDecodeError, TypeError) as e:
            logger.warning(f"Failed to parse Bilibili cover URL: {e}")
            return ""

    def get_audio_url(self):
        try:
            data_dict = json.loads(self.data)
            audios = data_dict.get('data', {}).get('dash', {}).get('audio', [])
            if audios:
                return audios[0].get('baseUrl')
            return None
        except (KeyError, json.JSONDecodeError, TypeError) as e:
            logger.warning(f"Failed to parse Bilibili audio URL: {e}")
            return None

    def get_author_info(self):
        try:
            data_dict = json.loads(self.data2)
            # 定位到作者信息节点
            owner_info = data_dict.get('videoData', {}).get('owner', {})

            # 如果 videoData 中没有，可以尝试从 upData 节点获取作为备用
            if not owner_info:
                owner_info = data_dict.get('upData', {})

            # 提取并格式化为你需要的字典结构
            author_info = {
                'nickname': owner_info.get('name', ''),
                # B站的核心唯一ID是 mid
                'author_id': str(owner_info.get('mid', '')),
                'avatar': owner_info.get('face', '')
            }

            # B站的头像 URL 经常以 // 开头，缺少 http: 或 https: 协议头，这里做个兼容处理
            if author_info['avatar'] and author_info['avatar'].startswith('//'):
                author_info['avatar'] = 'https:' + author_info['avatar']

            return author_info
        except (KeyError, json.JSONDecodeError, AttributeError) as e:
            logger.warning(f"Failed to parse author info: {e}")
            return {}


if __name__ == '__main__':
    real_url = 'https://www.bilibili.com/video/BV1df421v7xm/?share_source=copy_web&vd_source=5ac2e55972f5e2fd96b63d01ee42ff01'

    dl = BilibiliDownloader(real_url)

    print("-" * 30)
    print(f"作者信息：{dl.get_author_info()}")
    print(f"标题内容：{dl.get_title_content()[:30]}...")  # 仅打印前30字
    print(f"封面图片：{dl.get_cover_photo_url()}")
    print("\nB站采用 DASH 流媒体技术，将视频画面与音频音轨分开存储和传输（通常为两个 .m4s 文件），需要通过 FFmpeg 等工具无损合并才能得到完整的 MP4。")
    print(f"视频链接：{dl.get_real_video_url()}")
    print(f"音频链接：{dl.get_audio_url()}")
    print("-" * 30)
