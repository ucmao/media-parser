from src.parser_factory import register_parser
"""微信公众号 (WeChat Official Accounts) 文章图文与媒体解析器。"""

from html import unescape
import re

from bs4 import BeautifulSoup

from configs.logging_config import get_logger
from src.parsers.base_parser import BaseParser


logger = get_logger(__name__)


@register_parser("微信公众号")
class WechatMpParser(BaseParser):
    """通过 SSR 页面结构解析 mp.weixin.qq.com 公众号文章、原画图集与音频。"""

    USER_AGENT = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )

    def __init__(self, real_url):
        super().__init__(real_url)
        self.article_data = self._fetch_article()

    def _fetch_article(self):
        """抓取并解析公众号文章 HTML 内容。"""
        headers = {
            "User-Agent": self.USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }
        try:
            response = self.session.get(self.real_url, headers=headers, timeout=12)
            response.raise_for_status()
            html = response.text
            soup = BeautifulSoup(html, "html.parser")

            # 1. 标题提取 (优先 JS 变量，其次 meta，再次 h1)
            title = ""
            m_title = re.search(r"var msg_title = ['\"](.*?)['\"]", html)
            if m_title:
                title = unescape(m_title.group(1).replace("\\x26amp;", "&").replace("&amp;", "&"))
            if not title:
                meta_t = soup.find("meta", property="og:title")
                title = meta_t["content"] if meta_t else ""
            if not title:
                h1 = soup.find("h1", id="activity-name")
                title = h1.text.strip() if h1 else "微信公众号文章"

            # 2. 公众号作者与 ID 提取
            author_name = ""
            m_author = re.search(r"var nickname = ['\"](.*?)['\"]", html)
            if m_author:
                author_name = unescape(m_author.group(1))
            if not author_name:
                meta_a = soup.find("meta", property="og:article:author") or soup.find("meta", attrs={"name": "author"})
                author_name = meta_a["content"] if meta_a else ""
            if not author_name:
                js_name = soup.find("a", id="js_name")
                author_name = js_name.text.strip() if js_name else ""

            author_id = ""
            m_user = re.search(r"var user_name = ['\"](.*?)['\"]", html)
            if m_user:
                author_id = m_user.group(1)

            # 3. 封面图提取
            cover_url = ""
            m_cover = re.search(r"var msg_cdn_url = ['\"](.*?)['\"]", html)
            if m_cover:
                cover_url = m_cover.group(1)
            if not cover_url:
                meta_c = soup.find("meta", property="og:image")
                cover_url = meta_c["content"] if meta_c else ""

            # 4. 正文高清全量插图 (将 /640? 或 /300? 升级为原始画质 /0?)
            image_list = []
            content_box = soup.find("div", id="js_content") or soup
            for img in content_box.find_all("img"):
                src = img.get("data-src") or img.get("src")
                if src and src.startswith("http") and "qpic.cn" in src:
                    full_res = re.sub(r"/(?:640|300|0)\?", "/0?", src)
                    if full_res not in image_list:
                        image_list.append(full_res)

            # 如果正文无图但有封面，将封面加入图集
            if not image_list and cover_url:
                image_list.append(cover_url)

            # 5. 音频提取 (mpvoice)
            audio_url = None
            voice_tag = soup.find("mpvoice")
            if voice_tag and voice_tag.get("voice_encode_fileid"):
                audio_url = f"https://res.wx.qq.com/voice/getvoice?mediaid={voice_tag.get('voice_encode_fileid')}"

            return {
                "title": title,
                "author": {
                    "nickname": author_name,
                    "author_id": author_id,
                    "avatar": "",
                },
                "cover_url": cover_url,
                "image_list": image_list,
                "audio_url": audio_url,
                "video_url": None,
            }
        except Exception as exc:
            logger.warning("Failed to fetch WeChat MP article: %s", exc)
        return {}

    def get_real_video_url(self):
        """提取视频直链（如文章内嵌视频源）。"""
        return self.article_data.get("video_url")

    def get_title_content(self):
        """提取文章标题。"""
        return self.article_data.get("title") or "微信公众号文章"

    def get_cover_photo_url(self):
        """提取文章封面图。"""
        return self.article_data.get("cover_url")

    def get_author_info(self):
        """提取公众号名称及 gh_ 标识。"""
        author = self.article_data.get("author") or {}
        return {
            "nickname": author.get("nickname") or "",
            "author_id": author.get("author_id") or "",
            "avatar": author.get("avatar") or "",
        }

    def get_audio_url(self):
        """提取语音播报或内嵌音频直链。"""
        return self.article_data.get("audio_url")

    def get_image_list(self):
        """提取正文所有原画高清插图。"""
        return self.article_data.get("image_list") or []

    def get_video_list(self):
        video_url = self.get_real_video_url()
        return [video_url] if video_url else []
