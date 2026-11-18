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

            if "环境异常" in html and ("secitptpage/verify" in html or "完成验证后即可继续访问" in html):
                self.terminal_error = {
                    "error_code": "WECHAT_MP_VERIFY_REQUIRED",
                    "detail_msg": "微信公众号访问触发安全验证，请稍后重试",
                }
                return {"title": None, "desc": None, "video_url": None, "video_list": [], "cover_url": None, "author": None, "image_list": []}

            if any(kw in html for kw in ("该内容已被发布者删除", "此内容因违规无法查看", "此内容已被发布者删除", "该内容因违规无法查看")):
                self.terminal_error = {
                    "error_code": "MEDIA_DELETED_OR_PRIVATE",
                    "detail_msg": "该公众号文章已被作者删除或违规下架",
                }
                return {"title": None, "desc": None, "video_url": None, "video_list": [], "cover_url": None, "author": None, "image_list": []}

            soup = BeautifulSoup(html, "html.parser")

            # 1. 标题提取 (优先 JS 变量，其次 meta，再次 h1)
            title = ""
            m_title = re.search(r"(?:var msg_title\s*=\s*|msg_title\s*:\s*|title\s*:\s*(?:xml\s*\?\s*getXmlValue\([^)]*\)\s*:\s*)?)['\"](.*?)['\"]", html)
            if m_title:
                title = unescape(m_title.group(1).replace("\\x26amp;", "&").replace("&amp;", "&"))
            if not title:
                meta_t = soup.find("meta", property="og:title")
                title = meta_t["content"] if meta_t else ""
            if not title:
                h1 = soup.find("h1", id="activity-name")
                title = h1.text.strip() if h1 else "微信公众号文章"

            # 2. 公众号作者、ID 与 头像提取
            author_name = ""
            m_author = re.search(r"(?:var nickname\s*=\s*|nick_name\s*:\s*)['\"](.*?)['\"]", html)
            if m_author:
                author_name = unescape(m_author.group(1))
            if not author_name:
                meta_a = soup.find("meta", property="og:article:author") or soup.find("meta", attrs={"name": "author"})
                author_name = meta_a["content"] if meta_a else ""
            if not author_name:
                js_name = soup.find("a", id="js_name")
                author_name = js_name.text.strip() if js_name else ""

            author_id = ""
            m_user = re.search(r"(?:var user_name\s*=\s*|user_name\s*:\s*)['\"](.*?)['\"]", html)
            if m_user:
                author_id = m_user.group(1)

            author_avatar = ""
            m_avatar = re.search(r"(?:round_head_img|ori_head_img_url)\s*:\s*['\"](.*?)['\"]", html)
            if m_avatar:
                author_avatar = m_avatar.group(1).replace(r"\x26amp;", "&").replace("&amp;", "&")

            # 3. 封面图提取
            cover_url = ""
            m_cover = re.search(r"(?:var msg_cdn_url\s*=\s*|cdn_url\s*:\s*)['\"](.*?)['\"]", html)
            if m_cover:
                cover_url = m_cover.group(1).replace(r"\x26amp;", "&").replace("&amp;", "&")
            if not cover_url:
                meta_c = soup.find("meta", property="og:image")
                cover_url = meta_c["content"] if meta_c else ""

            # 4. 正文高清全量插图 (将 /640? 或 /300? 升级为原始画质 /0?)
            image_list = []
            content_box = soup.find("div", id="js_content") or soup
            description = content_box.get_text("\n", strip=True) or None
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

            # 6. 视频提取 (mpvideo / 视频消息 / 正文内嵌多视频)
            video_url = None
            video_list = []
            video_groups = {}
            for block in re.finditer(
                r"\{[^{}]*?url\s*:\s*['\"`](https?://mpvideo\.qpic\.cn/[^'\"`]+)['\"`][^{}]*?\}",
                html,
                re.DOTALL,
            ):
                b_text = block.group(0)
                raw_vurl = block.group(1).replace(r"\x26amp;", "&").replace("&amp;", "&")
                width_m = re.search(r"width\s*:\s*['\"`]?(\d+)", b_text)
                height_m = re.search(r"height\s*:\s*['\"`]?(\d+)", b_text)
                filesize_m = re.search(r"filesize\s*:\s*['\"`]?(\d+)", b_text)
                quality_m = re.search(r"video_quality_level\s*:\s*['\"`]?(\d+)", b_text)

                width = int(width_m.group(1)) if width_m else 0
                height = int(height_m.group(1)) if height_m else 0
                filesize = int(filesize_m.group(1)) if filesize_m else 0
                quality = int(quality_m.group(1)) if quality_m else 0

                item = {
                    "url": raw_vurl,
                    "width": width,
                    "height": height,
                    "filesize": filesize,
                    "quality": quality,
                }

                # 依据视频唯一标识分组（如 mpvideo.qpic.cn/{file_id}.f10002.mp4 中的 file_id）
                m_f = re.search(r"mpvideo\.qpic\.cn/([a-zA-Z0-9_-]+)\.f\d+", raw_vurl)
                if m_f:
                    group_key = m_f.group(1)
                else:
                    m_prefix = re.search(r"mpvideo\.qpic\.cn/([a-zA-Z0-9_-]+)", raw_vurl)
                    group_key = m_prefix.group(1) if m_prefix else raw_vurl.split("?")[0]

                if group_key not in video_groups:
                    video_groups[group_key] = []
                video_groups[group_key].append(item)

            # 单视频文章（如 video_page_info）场景保护
            if "video_page_info" in html and "video_page_infos" not in html and "videoPageInfos" not in html:
                all_items = [item for items in video_groups.values() for item in items]
                if all_items:
                    best_video = max(
                        all_items,
                        key=lambda v: (v["quality"], v["width"] * v["height"], v["filesize"]),
                    )
                    video_list = [best_video["url"]]
            elif video_groups:
                for items in video_groups.values():
                    best_video = max(
                        items,
                        key=lambda v: (v["quality"], v["width"] * v["height"], v["filesize"]),
                    )
                    if best_video["url"] not in video_list:
                        video_list.append(best_video["url"])
            else:
                # 备选匹配任意 mpvideo.qpic.cn 链接
                direct_matches = re.findall(
                    r"https?://mpvideo\.qpic\.cn/[^\s'\"`]+",
                    html,
                )
                seen_keys = set()
                for dm in direct_matches:
                    clean_vurl = dm.replace(r"\x26amp;", "&").replace("&amp;", "&")
                    m_prefix = re.search(r"mpvideo\.qpic\.cn/([a-zA-Z0-9_-]+)", clean_vurl)
                    key = m_prefix.group(1) if m_prefix else clean_vurl.split("?")[0]
                    if key not in seen_keys:
                        seen_keys.add(key)
                        video_list.append(clean_vurl)

            video_url = video_list[0] if video_list else None

            return {
                "title": title,
                "desc": description,
                "author": {
                    "nickname": author_name,
                    "author_id": author_id,
                    "avatar": author_avatar,
                },
                "cover_url": cover_url,
                "image_list": image_list,
                "audio_url": audio_url,
                "video_url": video_url,
                "video_list": video_list,
            }
        except Exception as exc:
            logger.warning("Failed to fetch WeChat MP article: %s", exc)
        return {}

    def get_real_video_url(self):
        """提取首个视频直链（如文章内嵌视频源）。"""
        return self.article_data.get("video_url")

    def get_title_content(self):
        """提取文章标题。"""
        return self.article_data.get("title") or "微信公众号文章"

    def get_description(self):
        """提取已去除 HTML 标记的文章正文。"""
        return self.article_data.get("desc") or None

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
        """提取文章内嵌的所有视频直链列表。"""
        return self.article_data.get("video_list") or []
