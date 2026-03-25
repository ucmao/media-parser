
from src.parsers.base_parser import BaseParser
from utils.web_fetcher import UrlParser

class QuanminParser(BaseParser):
    def fetch_html_data(self):
        video_id = UrlParser.get_video_id(self.real_url)
        req_url = f"https://haokan.baidu.com/haokan/ui-web/video/info?vid={video_id}"
        resp = self.session.get(req_url, headers=self.headers)
        return resp.json()
    def get_real_video_url(self):
        try: return self.data["data"]["meta"]["video_info"]["clarityUrl"][1]["url"]
        except: return None
    def get_cover_photo_url(self):
        try: return self.data["data"]["meta"]["image"]
        except: return None
    def get_title_content(self):
        try:
            video_title = self.data["data"]["meta"]["title"]
            if len(video_title) == 0: video_title = self.data["data"]["shareInfo"]["title"]
            return video_title
        except: return None
    def get_author_info(self):
        try:
            author = self.data["data"]["author"]
            return {"nickname": author["name"], "author_id": str(author["id"]), "avatar": author["icon"]}
        except: return {}
