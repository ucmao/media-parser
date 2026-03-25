
from src.parsers.base_parser import BaseParser
from utils.web_fetcher import UrlParser

class ZuiyouParser(BaseParser):
    def fetch_html_data(self):
        video_id = UrlParser.get_video_id(self.real_url)
        try:
            int_video_id = int(video_id)
        except:
            int_video_id = 0
        req_url = "https://share.xiaochuankeji.cn/planck/share/post/detail_h5"
        post_data = {"h_av": "5.2.13.011", "pid": int_video_id}
        resp = self.session.post(req_url, headers=self.headers, json=post_data)
        return resp.json()
    def get_real_video_url(self):
        try:
            data = self.data["data"]["post"]
            video_key = str(data["imgs"][0]["id"])
            return data["videos"][video_key]["url"]
        except: return None
    def get_cover_photo_url(self): return None
    def get_title_content(self):
        try: return self.data["data"]["post"]["content"]
        except: return None
    def get_author_info(self):
        try:
            member = self.data["data"]["post"]["member"]
            return {"nickname": member["name"], "author_id": str(member["id"]), "avatar": member["avatar_urls"]["origin"]["urls"][0]}
        except: return {}
