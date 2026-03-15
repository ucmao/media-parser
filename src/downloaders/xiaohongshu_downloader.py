import re
import json
from src.downloaders.base_downloader import BaseDownloader
from configs.logging_config import get_logger
logger = get_logger(__name__)


class XiaohongshuDownloader(BaseDownloader):
    def __init__(self, real_url):
        super().__init__(real_url)
        self.headers = {
            "content-type": "application/json; charset=UTF-8",
            'User-Agent': "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
            'referer': 'https://www.xiaohongshu.com/'
        }
        # 获取 HTML 并解析 JSON 状态
        html_content = self.fetch_html_content()
        pattern = re.compile(r'window\.__INITIAL_STATE__\s*=\s*(\{.*\})', re.DOTALL)
        json_str = BaseDownloader.parse_html_data(html_content, pattern)

        # 初始化数据容器
        self.note_data = {}
        try:
            if json_str:
                full_data = json.loads(json_str)
                first_note_id = full_data.get('note', {}).get('firstNoteId')
                if first_note_id:
                    self.note_data = full_data['note']['noteDetailMap'].get(first_note_id, {}).get('note', {})
        except (json.JSONDecodeError, KeyError) as e:
            logger.error(f"初始化解析数据失败: {e}")

    def get_author_info(self):
        """
        获取作者信息，返回固定格式字典
        """
        user = self.note_data.get('user', {})
        return {
            'nickname': user.get('nickname', ''),
            'author_id': user.get('userId', ''),
            'avatar': user.get('avatar', '')
        }

    def get_real_video_url(self):
        try:
            video_info = self.note_data.get('video', {})
            master_url = video_info['media']['stream']['h264'][0].get('masterUrl', '')
            return master_url.replace("\\u002F", "/") if master_url else None
        except (KeyError, IndexError):
            return None

    def get_title_content(self):
        title = self.note_data.get('title', '')
        desc = self.note_data.get('desc', '')
        return f"{title}\n{desc}".strip()

    def get_cover_photo_url(self):
        try:
            image_list = self.note_data.get('imageList', [])
            if image_list:
                cover_url = image_list[0].get('urlDefault', '')
                return cover_url.replace("\\u002F", "/")
            return None
        except (KeyError, IndexError):
            return None

    def get_image_list(self):
        image_url_list = []
        image_list = self.note_data.get('imageList', [])
        for image in image_list:
            url = image.get('urlDefault', '')
            if url:
                image_url_list.append(url.replace("\\u002F", "/"))
        return image_url_list


if __name__ == '__main__':
    real_url = 'https://www.xiaohongshu.com/discovery/item/699ec585000000002602eb4c?xsec_token=ABxyNDjNzyo7x607F-O1PLIKtfYSPsQPi8ZscMk3c8JCI='

    dl = XiaohongshuDownloader(real_url)

    print("-" * 30)
    print(f"作者信息：{dl.get_author_info()}")
    print(f"标题内容：{dl.get_title_content()[:30]}...")  # 仅打印前30字
    print(f"封面图片：{dl.get_cover_photo_url()}")
    print(f"视频链接：{dl.get_real_video_url()}")
    print(f"图片列表：{dl.get_image_list()}")
    print("-" * 30)