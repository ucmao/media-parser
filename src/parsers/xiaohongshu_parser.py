from src.parser_factory import register_parser
import re
import json
from src.parsers.base_parser import BaseParser
from configs.logging_config import get_logger
from configs.general_constants import USER_AGENT_PC, USER_AGENT_M
import requests

logger = get_logger(__name__)


@register_parser("小红书")
class XiaohongshuParser(BaseParser):
    def __init__(self, real_url):
        super().__init__(real_url)
        self.note_data = {}
        self.fetch_and_parse()

    def fetch_and_parse(self):
        pc_ua = USER_AGENT_PC[0] if USER_AGENT_PC else "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
        mobile_ua = USER_AGENT_M[0] if USER_AGENT_M else "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"

        # 根据链接特征选择优先尝试的 UA
        if "app_platform" in self.real_url or "app_share" in self.real_url or "xhslink" in self.real_url:
            candidate_uas = [mobile_ua, pc_ua]
        else:
            candidate_uas = [pc_ua, mobile_ua]

        for ua in candidate_uas:
            headers = {
                "User-Agent": ua,
                "Referer": "https://www.xiaohongshu.com/",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            }
            try:
                resp = self.session.get(self.real_url, headers=headers, timeout=6)
                if resp.status_code == 404:
                    self.terminal_error = {"detail_msg": "该小红书笔记已被作者删除或不存在"}
                    return
                if resp.status_code != 200:
                    continue
                if "xiaohongshu.com/404" in resp.url or "undertake_note_error" in resp.url:
                    self.terminal_error = {"detail_msg": "该小红书笔记已被作者删除或不存在"}
                    return
                if "xiaohongshu.com/login" in resp.url:
                    continue

                self.html_content = resp.text
                note = self._extract_note_from_html(self.html_content)
                if note:
                    self.note_data = note
                    return
                if self.terminal_error:
                    return
            except requests.RequestException as e:
                logger.warning(f"小红书请求失败 (UA: {ua[:30]}...): {e}")
                continue
            except Exception as e:
                logger.error(f"解析小红书页面异常: {e}")
                continue

        if not self.note_data and not self.terminal_error:
            logger.error(f"未能解析出小红书笔记数据: {self.real_url}")

    def _extract_note_from_html(self, html_content):
        if not html_content:
            return None
        pattern = re.compile(r'window\.__INITIAL_STATE__\s*=\s*(\{.*?\})</script>', re.DOTALL)
        match = pattern.search(html_content)
        if not match:
            pattern = re.compile(r'window\.__INITIAL_STATE__\s*=\s*(\{.*\})', re.DOTALL)
            match = pattern.search(html_content)
        if not match:
            return None

        json_str = match.group(1)
        json_str = re.sub(r':\s*undefined\b', ':null', json_str)
        try:
            full_data = json.loads(json_str)
        except json.JSONDecodeError as e:
            logger.error(f"小红书 JSON 解析失败: {e}")
            return None

        # 1. PC 端结构: full_data['note']['noteDetailMap'][first_note_id]['note']
        first_note_id = full_data.get('note', {}).get('firstNoteId')
        if first_note_id:
            note_item = full_data.get('note', {}).get('noteDetailMap', {}).get(first_note_id)
            if isinstance(note_item, dict):
                note = note_item.get('note')
                if isinstance(note, dict) and note:
                    return note
                if note == {}:
                    self.terminal_error = {"detail_msg": "该小红书笔记已被作者删除或设置为私密不可见"}
                    return None

        # 2. 移动端 H5 结构: full_data['noteData']['data']['noteData']
        note = full_data.get('noteData', {}).get('data', {}).get('noteData', {})
        if note:
            return note

        # 3. 兜底回退结构
        return full_data.get('noteData', {}).get('note', {}) or full_data.get('note', {}).get('note', {}) or None

    def get_author_info(self):
        """
        获取作者信息，返回固定格式字典
        """
        user = self.note_data.get('user', {})
        return {
            'nickname': user.get('nickname') or user.get('nickName', ''),
            'author_id': user.get('userId') or user.get('author_id') or user.get('id', ''),
            'avatar': user.get('avatar', '')
        }

    def get_real_video_url(self):
        try:
            video_info = self.note_data.get('video', {})
            if not isinstance(video_info, dict):
                return None
            stream = video_info.get('media', {}).get('stream', {}) or video_info.get('stream', {})
            h264_data = stream.get('h264', [])
            if h264_data and isinstance(h264_data, list):
                master_url = h264_data[0].get('masterUrl', '')
                if master_url:
                    return master_url.replace("\\u002F", "/")
            for codec in ('h265', 'av1'):
                codec_data = stream.get(codec, [])
                if codec_data and isinstance(codec_data, list):
                    master_url = codec_data[0].get('masterUrl', '')
                    if master_url:
                        return master_url.replace("\\u002F", "/")
            return None
        except (KeyError, IndexError, AttributeError):
            return None

    def get_title_content(self):
        return self.note_data.get('title', '') or None

    def get_description(self):
        return self.note_data.get('desc', '') or None

    def get_cover_photo_url(self):
        cover = self.note_data.get('cover')
        if isinstance(cover, dict):
            url = cover.get('urlDefault') or cover.get('url')
            if url:
                return url.replace("\\u002F", "/")
            info_list = cover.get('infoList', [])
            if info_list and isinstance(info_list, list):
                url = info_list[0].get('url')
                if url:
                    return url.replace("\\u002F", "/")
        elif isinstance(cover, str) and cover:
            return cover.replace("\\u002F", "/")

        # 兜底从 imageList 中获取首图作为封面
        image_list = self.note_data.get('imageList', [])
        if image_list and isinstance(image_list, list):
            first_img = image_list[0]
            if isinstance(first_img, dict):
                url = first_img.get('urlDefault') or first_img.get('url')
                if url:
                    return url.replace("\\u002F", "/")
                info_list = first_img.get('infoList', [])
                if info_list and isinstance(info_list, list):
                    url = info_list[0].get('url')
                    if url:
                        return url.replace("\\u002F", "/")
        return None

    def get_image_list(self):
        image_url_list = []
        image_list = self.note_data.get('imageList', [])
        if not isinstance(image_list, list):
            return image_url_list

        for image in image_list:
            if not isinstance(image, dict):
                continue
            url = image.get('urlDefault') or image.get('url')
            if not url:
                info_list = image.get('infoList', [])
                if info_list and isinstance(info_list, list):
                    url = info_list[-1].get('url') or info_list[0].get('url', '')
            if url:
                img_data = url.replace("\\u002F", "/")
                # 检查是否有 livePhoto
                if image.get('livePhoto', False):
                    stream = image.get('stream', {})
                    h264_data = stream.get('h264', [])
                    if h264_data and isinstance(h264_data, list):
                        master_url = h264_data[0].get('masterUrl', '')
                        if master_url:
                            img_data = {
                                'url': img_data,
                                'live_photo_url': master_url.replace("\\u002F", "/")
                            }
                image_url_list.append(img_data)
        return image_url_list
