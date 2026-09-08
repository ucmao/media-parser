import base64
import json
import re
import urllib.parse
from bs4 import BeautifulSoup

from configs.logging_config import get_logger
from src.parser_factory import register_parser
from src.parsers.douyin_parser import DouyinParser

logger = get_logger(__name__)


@register_parser("今日头条")
class ToutiaoParser(DouyinParser):
    """今日头条分享解析器，支持移动端 SSR + ByteDance VOD 调度及抖音链路兜底。"""

    MOBILE_HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) "
            "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh-Hans;q=0.9",
    }

    @staticmethod
    def _clean_description(content):
        """将头条 SSR 返回的富文本正文转换为保留段落的纯文本。"""
        if not isinstance(content, str):
            return None

        soup = BeautifulSoup(content, "html.parser")
        for tag in soup.find_all(["script", "style", "template"]):
            tag.decompose()
        for tag in soup.find_all("br"):
            tag.replace_with("\n")
        for tag in soup.find_all(
            ["address", "article", "blockquote", "div", "h1", "h2", "h3", "h4", "h5", "h6", "li", "p", "section"]
        ):
            tag.append("\n")

        lines = []
        for line in soup.get_text().replace("\xa0", " ").splitlines():
            normalized = re.sub(r"[\t\f\v ]+", " ", line).strip()
            if normalized:
                lines.append(normalized)
        return "\n".join(lines) or None

    def _fetch_toutiao_mobile_ssr(self, item_id: str):
        """通过今日头条移动端 SSR 渲染数据及 VOD 接口提取视频详情。"""
        if not item_id:
            return None

        candidate_urls = [
            f"https://m.toutiao.com/video/{item_id}/",
            f"https://m.toutiao.com/i{item_id}/",
            f"https://m.toutiao.com/group/{item_id}/",
            f"https://m.toutiao.com/item/{item_id}/",
        ]

        for target_url in candidate_urls:
            try:
                resp = self.session.get(target_url, headers=self.MOBILE_HEADERS, timeout=5, allow_redirects=True)
                if resp.status_code != 200 or not resp.text:
                    continue

                soup = BeautifulSoup(resp.text, "lxml")
                script = soup.find("script", id="RENDER_DATA")
                if not script or not script.string:
                    continue

                text = urllib.parse.unquote(script.string.strip())
                raw_json = json.loads(text)
                article_info = raw_json.get("articleInfo")
                if not article_info or not isinstance(article_info, dict):
                    continue

                token_v2 = article_info.get("playAuthTokenV2")
                vod_data = None
                if token_v2:
                    try:
                        token_obj = json.loads(base64.b64decode(token_v2).decode("utf-8"))
                        query_str = token_obj.get("GetPlayInfoToken")
                        if query_str:
                            vod_url = f"https://vod.bytedanceapi.com/?{query_str}"
                            vod_resp = self.session.get(vod_url, timeout=5)
                            if vod_resp.status_code == 200:
                                vod_data = vod_resp.json().get("Result", {}).get("Data", {})
                    except Exception as e:
                        logger.warning(f"Failed to fetch Toutiao VOD data: {e}")

                logger.info(f"Successfully extracted Toutiao mobile SSR data for {item_id}")
                return {
                    "toutiao_article_info": article_info,
                    "vod_data": vod_data,
                }
            except Exception as e:
                logger.debug(f"Failed to fetch Toutiao mobile SSR from {target_url}: {e}")
                continue

        return None

    def fetch_html_data(self):
        # 1. 优先尝试今日头条移动端 SSR + ByteDance VOD 链路
        toutiao_data = self._fetch_toutiao_mobile_ssr(self.aweme_id)
        if toutiao_data:
            return toutiao_data

        # 2. 兜底回退到抖音核心链路（移动 Feed、Web a_bogus API、抖音 SSR）
        return super().fetch_html_data()

    def get_real_video_url(self):
        if self.data and isinstance(self.data, dict) and "vod_data" in self.data:
            vod_data = self.data.get("vod_data") or {}
            play_list = vod_data.get("PlayInfoList") or []
            if play_list:
                # 优先按码率降序选择最高清晰度流
                valid_streams = [p for p in play_list if isinstance(p, dict) and (p.get("MainPlayUrl") or p.get("BackupPlayUrl"))]
                if valid_streams:
                    valid_streams.sort(key=lambda x: x.get("Bitrate", 0), reverse=True)
                    best = valid_streams[0]
                    return best.get("MainPlayUrl") or best.get("BackupPlayUrl")

            article_info = self.data.get("toutiao_article_info") or {}
            play_url_list = article_info.get("playUrlList") or []
            if play_url_list:
                return play_url_list[0].get("mainUrl") or play_url_list[0].get("backupUrl")

        return super().get_real_video_url()

    def get_title_content(self):
        if self.data and isinstance(self.data, dict) and "toutiao_article_info" in self.data:
            article_info = self.data["toutiao_article_info"]
            return article_info.get("title") or None

        return super().get_title_content()

    def get_description(self):
        if self.data and isinstance(self.data, dict) and "toutiao_article_info" in self.data:
            content = self.data["toutiao_article_info"].get("content")
            return self._clean_description(content)
        return super().get_description()

    def get_cover_photo_url(self):
        if self.data and isinstance(self.data, dict) and "toutiao_article_info" in self.data:
            article_info = self.data["toutiao_article_info"]
            return (
                article_info.get("posterUrl")
                or (self.data.get("vod_data") or {}).get("CoverUrl")
            )

        return super().get_cover_photo_url()

    def get_author_info(self):
        if self.data and isinstance(self.data, dict) and "toutiao_article_info" in self.data:
            article_info = self.data["toutiao_article_info"]
            user = article_info.get("mediaUser") or {}
            name = user.get("screenName") or article_info.get("userName") or article_info.get("source")
            avatar = user.get("avatarUrl")
            if name or avatar:
                return {"author": name, "avatar": avatar}
            return None

        return super().get_author_info()

    def get_video_list(self):
        if self.data and isinstance(self.data, dict) and "vod_data" in self.data:
            url = self.get_real_video_url()
            return [url] if url else []

        return super().get_video_list()
