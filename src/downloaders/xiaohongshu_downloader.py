import re
import json
from src.downloaders.base_downloader import BaseDownloader
from configs.logging_config import logger


class XiaohongshuDownloader(BaseDownloader):
    def __init__(self, real_url):
        super().__init__(real_url)
        self.headers = {
            "content-type": "application/json; charset=UTF-8",
            'User-Agent': "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
            'referer': 'https://www.xiaohongshu.com/'
        }
        self.data = self.fetch_html_data()

    def fetch_html_data(self):
        self.html_content = self.fetch_html_content()
        pattern = re.compile(r'window\.__INITIAL_STATE__\s*=\s*(\{.*\})', re.DOTALL)
        json_data = BaseDownloader.parse_html_data(self.html_content, pattern)
        return json_data

    def get_real_video_url(self):
        try:
            data_dict = json.loads(self.data)
            first_note_id = data_dict['note']['firstNoteId']
            origin_video_key = data_dict['note']['noteDetailMap'][first_note_id]['note']['video']['consumer']['originVideoKey']
            if not origin_video_key:
                raise Exception("Failed to find originVideoKey in response")
            video_key = origin_video_key.replace("\\u002F", "/")
            video_url = "http://sns-video-bd.xhscdn.com/" + video_key
            return video_url
        except (KeyError, json.JSONDecodeError) as e:
            logger.warning(f"Failed to parse video URL: {e}")

    def get_title_content(self):
        try:
            data_dict = json.loads(self.data)
            first_note_id = data_dict['note']['firstNoteId']
            title_content = data_dict['note']['noteDetailMap'][first_note_id]['note']['title']
            desc_content = data_dict['note']['noteDetailMap'][first_note_id]['note']['desc']
            return title_content + desc_content
        except (KeyError, json.JSONDecodeError) as e:
            logger.warning(f"Failed to parse title content: {e}")

    def get_cover_photo_url(self):
        try:
            data_dict = json.loads(self.data)
            first_note_id = data_dict['note']['firstNoteId']
            cover_url = data_dict['note']['noteDetailMap'][first_note_id]['note']['imageList'][0]['urlDefault']
            cover_url = cover_url.replace("\\u002F", "/")
            return cover_url
        except (KeyError, json.JSONDecodeError) as e:
            logger.warning(f"Failed to parse cover URL: {e}")


if __name__ == '__main__':
    real_url = 'https://www.xiaohongshu.com/explore/66265ead000000000d030c3f?xsec_token=ABClLfS3dCR8EaYcL9WW7xzrqPoYH4oOildl5Xg1vGjMo=&xsec_source=pc_search'
    xhs_dl = XiaohongshuDownloader(real_url)
    print(xhs_dl.get_title_content())
    print(xhs_dl.get_cover_photo_url())
    print(xhs_dl.get_real_video_url())
