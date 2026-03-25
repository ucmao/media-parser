
from src.parsers.base_parser import BaseParser
from utils.web_fetcher import UrlParser

class PipixiaParser(BaseParser):
    def fetch_html_data(self):
        resp = self.session.get(self.real_url, headers=self.headers, allow_redirects=False)
        location_url = resp.headers.get("location", "")
        if not location_url: location_url = self.real_url
        video_id = location_url.split("?")[0].split("/")[-1]
        req_url = f"https://api.pipix.com/bds/cell/cell_comment/?offset=0&cell_type=1&api_version=1&cell_id={video_id}&ac=wifi&channel=huawei_1319_64&aid=1319&app_name=super"
        resp = self.session.get(req_url, headers=self.headers)
        return resp.json()
    def get_real_video_url(self):
        try:
            data = self.data["data"]["cell_comments"][0]["comment_info"]["item"]
            if data.get("video") is not None:
                return data["video"]["video_high"]["url_list"][0]["url"]
            return None
        except: return None
    def get_image_list(self):
        try:
            data = self.data["data"]["cell_comments"][0]["comment_info"]["item"]
            images = []
            if data.get("note") is not None:
                for img in data["note"]["multi_image"]:
                    images.append(img["url_list"][0]["url"])
            return images
        except: return []
    def get_cover_photo_url(self):
        try: return self.data["data"]["cell_comments"][0]["comment_info"]["item"]["cover"]["url_list"][0]["url"]
        except: return None
    def get_title_content(self):
        try: return self.data["data"]["cell_comments"][0]["comment_info"]["item"]["content"]
        except: return None
    def get_author_info(self):
        try:
            author = self.data["data"]["cell_comments"][0]["comment_info"]["item"]["author"]
            return {"nickname": author["name"], "author_id": str(author["id"]), "avatar": author["avatar"]["download_list"][0]["url"]}
        except: return {}
