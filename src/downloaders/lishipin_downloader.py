import re
import random
from bs4 import BeautifulSoup
from utils.web_fetcher import UrlParser
from src.downloaders.base_downloader import BaseDownloader
from configs.general_constants import USER_AGENT_PC
from configs.logging_config import get_logger

logger = get_logger(__name__)


class LishipinDownloader(BaseDownloader):
    def __init__(self, real_url):
        super().__init__(real_url)
        self.headers = {
            "content-type": "application/json; charset=UTF-8",
            'User-Agent': random.choice(USER_AGENT_PC),
            'referer': self.real_url
        }
        self.video_id = UrlParser.get_video_id(self.real_url)
        self.data = self.fetch_html_data()
        self.html_content = self.fetch_html_content()

    def fetch_html_data(self):
        jsp_url = "https://www.pearvideo.com/videoStatus.jsp"
        params = {
            "contId": f"{''.join(filter(str.isdigit, self.video_id))}",
            "mrd": random.random()
        }
        try:
            response = self.session.get(jsp_url, params=params, headers=self.headers, timeout=5)
            if response.status_code == 200:
                return response.json()
            else:
                logger.warning(f"Lishipin API request failed: {response.status_code}")
                return None
        except Exception as e:
            logger.error(f"Lishipin API error: {e}")
            return None

    def get_real_video_url(self):
        try:
            if not self.data: return None
            video_url = self.data.get('videoInfo', {}).get('videos', {}).get('srcUrl')
            if not video_url: return None

            new_value = f"cont-{self.video_id}"
            pattern = r'(\d+)-(\d+-hd\.mp4)'
            return re.sub(pattern, new_value + r'-\2', video_url)
        except (KeyError, TypeError) as e:
            logger.warning(f"Failed to parse Lishipin video URL: {e}")
            return None

    def get_title_content(self):
        try:
            if not self.html_content: return ""
            soup = BeautifulSoup(self.html_content, 'html.parser')
            summary_div = soup.find('div', class_='summary')
            return summary_div.get_text(strip=True) if summary_div else ""
        except Exception as e:
            logger.warning(f"Failed to parse Lishipin title: {e}")
            return ""

    def get_cover_photo_url(self):
        try:
            if not self.data: return ""
            return self.data.get('videoInfo', {}).get('video_image', '')
        except Exception as e:
            logger.warning(f"Failed to parse Lishipin cover URL: {e}")
            return ""

    def get_author_info(self):
        try:
            soup = BeautifulSoup(self.html_content, 'html.parser')

            # 定位到包含作者信息的父级 div
            author_node = soup.find('div', class_='thiscat')

            if not author_node:
                logger.warning("未找到作者信息节点")
                return {}

            # 1. 提取昵称 (col-name 包含一个 i 标签和文本，get_text 会直接提取出文本)
            name_node = author_node.find('div', class_='col-name')
            nickname = name_node.get_text(strip=True) if name_node else ''

            # 2. 提取头像
            avatar_node = author_node.find('img')
            avatar = avatar_node['src'] if avatar_node and 'src' in avatar_node.attrs else ''

            # 3. 提取 unique_id (可以从 data-userid 获取，或者从 href="author_xxx" 提取)
            unique_id = ''
            subscribe_node = author_node.find('div', class_='column-subscribe')
            if subscribe_node and 'data-userid' in subscribe_node.attrs:
                unique_id = subscribe_node['data-userid']
            else:
                # 备用方案：通过正则从 href 提取
                a_node = author_node.find('a', href=re.compile(r'author_(\d+)'))
                if a_node:
                    match = re.search(r'author_(\d+)', a_node['href'])
                    if match:
                        unique_id = match.group(1)

            author_info = {
                'nickname': nickname,
                'author_id': unique_id,
                'avatar': avatar
            }
            return author_info

        except Exception as e:
            logger.warning(f"Failed to parse author info: {e}")
            return {}


if __name__ == '__main__':
    real_url = 'https://www.pearvideo.com/video_1805408'

    dl = LishipinDownloader(real_url)

    print("-" * 30)
    print(f"作者信息：{dl.get_author_info()}")
    print(f"标题内容：{dl.get_title_content()[:30]}...")  # 仅打印前30字
    print(f"封面图片：{dl.get_cover_photo_url()}")
    print(f"视频链接：{dl.get_real_video_url()}")
    print("-" * 30)
