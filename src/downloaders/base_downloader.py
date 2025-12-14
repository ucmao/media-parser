import os
import uuid
import requests
from requests.adapters import HTTPAdapter
from requests.exceptions import RequestException, ChunkedEncodingError
from bs4 import BeautifulSoup
from urllib3.util.retry import Retry
from configs.general_constants import SAVE_VIDEO_PATH, SAVE_IMAGE_PATH
from configs.logging_config import logger


class BaseDownloader:
    def __init__(self, real_url):
        self.real_url = real_url
        self.headers = None
        self.html_content = None

    def get_real_video_url(self):
        raise NotImplementedError

    def get_title_content(self):
        raise NotImplementedError

    def get_cover_photo_url(self):
        raise NotImplementedError

    def fetch_html_content(self):
        try:
            resp = requests.get(self.real_url, headers=self.headers, timeout=5)
            resp.raise_for_status()
            return resp.text
        except requests.RequestException as e:
            logger.error(f"Failed to get the page: {e}")
        except Exception as e:
            logger.error(f"An error occurred: {e}")

    @staticmethod
    def parse_html_data(html_content, pattern):
        page_obj = BeautifulSoup(html_content, 'lxml')
        script_tags = page_obj.find_all('script')
        for script in script_tags:
            if script.string:
                match = pattern.search(script.string)
                if match:
                    json_data = match.group(1)
                    json_data = json_data.rstrip(';')  # 部分需要去除分号
                    json_data = json_data.replace('undefined', 'null')  # 小红书需要这步骤
                    return json_data
        logger.error("Video object not found")

    @staticmethod
    def mkdir(folder):
        if not os.path.exists(folder):
            os.makedirs(folder, 0o777)
            return True
        return False

    def download_and_save(self, folder, url, file_extension):
        BaseDownloader.mkdir(folder)
        retries = Retry(total=5, backoff_factor=1, status_forcelist=[500, 502, 503, 504])
        session = requests.Session()
        session.mount('http://', HTTPAdapter(max_retries=retries))
        session.mount('https://', HTTPAdapter(max_retries=retries))
        try:
            response = session.get(url, headers=self.headers, stream=True)
            response.raise_for_status()
        except RequestException as e:
            logger.error(f"Failed to download the resource: {e}")
        _filename = os.path.join(folder, f'{str(uuid.uuid4())}.{file_extension}')
        full_name = os.path.abspath(_filename)
        try:
            with open(full_name, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
        except ChunkedEncodingError as e:
            logger.error(f"Failed to save the resource: {e}")
        except IOError as e:
            logger.error(f"Failed to save the resource: {e}")
        return full_name

    def download_and_save_video(self):
        video_url = self.get_real_video_url()
        logger.debug(f'视频下载地址：{video_url}')
        return self.download_and_save(SAVE_VIDEO_PATH, video_url, 'mp4')

    def download_and_save_image(self):
        photo_url = self.get_cover_photo_url()
        if photo_url:
            logger.debug(f'封面下载地址：{photo_url}')
            return self.download_and_save(SAVE_IMAGE_PATH, photo_url, 'jpg')
        else:
            logger.debug(f'未获取到封面下载地址')
            return None
