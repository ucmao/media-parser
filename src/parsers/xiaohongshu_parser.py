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

        # 优先使用 PC 端 UA 请求以获得无水印高品质音视频流与原图，若失败再回退至移动端 UA
        candidate_uas = [pc_ua, mobile_ua]

        for i, ua in enumerate(candidate_uas):
            is_last = (i == len(candidate_uas) - 1)
            headers = {
                "User-Agent": ua,
                "Referer": "https://www.xiaohongshu.com/",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            }
            try:
                resp = self.session.get(self.real_url, headers=headers, timeout=6)
                if resp.status_code == 404:
                    if is_last:
                        self.terminal_error = {"detail_msg": "该小红书笔记已被作者删除或不存在"}
                    continue
                if resp.status_code != 200:
                    continue
                if "xiaohongshu.com/404" in resp.url or "undertake_note_error" in resp.url:
                    if is_last:
                        self.terminal_error = {"detail_msg": "该小红书笔记已被作者删除或不存在"}
                    continue
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

    def _clean_image_url(self, img_obj_or_url):
        """
        清洗并获取无水印、浏览器原生兼容（JPG 格式）的小红书原图地址
        """
        if not img_obj_or_url:
            return None

        file_id = None
        url = None

        if isinstance(img_obj_or_url, dict):
            file_id = img_obj_or_url.get('fileId')
            url = img_obj_or_url.get('urlDefault') or img_obj_or_url.get('url')
            if not url:
                info_list = img_obj_or_url.get('infoList', [])
                if info_list and isinstance(info_list, list):
                    url = info_list[-1].get('url') or info_list[0].get('url', '')
        elif isinstance(img_obj_or_url, str):
            url = img_obj_or_url

        if file_id:
            return f"https://sns-img-qc.xhscdn.com/{file_id}?imageView2/2/w/1920/format/jpg"

        if not url:
            return None

        url = url.replace("\\u002F", "/")
        match = re.search(r'/[0-9a-f]{32}/(.+?)(?:!|$)', url)
        if match:
            extracted_file_id = match.group(1)
            return f"https://sns-img-qc.xhscdn.com/{extracted_file_id}?imageView2/2/w/1920/format/jpg"

        clean_url = re.sub(r'![^?]*', '', url)
        return clean_url

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

    def _ensure_https(self, url):
        if not url or not isinstance(url, str):
            return url
        url = url.replace("\\u002F", "/")
        if url.startswith("http://"):
            return "https://" + url[7:]
        return url

    def get_real_video_url(self):
        try:
            video_info = self.note_data.get('video', {})
            if not isinstance(video_info, dict):
                return None

            # 1. 优先提取 consumer 中的 originVideoKey（无水印原画视频 Key）
            consumer = video_info.get('consumer', {})
            origin_key = None
            if isinstance(consumer, dict):
                origin_key = consumer.get('originVideoKey') or consumer.get('origin_video_key')
            if not origin_key:
                origin_key = video_info.get('originVideoKey') or video_info.get('origin_video_key')

            if origin_key:
                if origin_key.startswith(('http://', 'https://')):
                    return self._ensure_https(origin_key)
                else:
                    return f"https://sns-video-bd.xhscdn.com/{origin_key.lstrip('/')}"

            # 2. 优先提取 mediaV2 中的 screencast 原画/高清无水印流
            media_v2_str = video_info.get('mediaV2')
            if media_v2_str and isinstance(media_v2_str, str):
                try:
                    mv2 = json.loads(media_v2_str)
                    opaque1 = mv2.get('video', {}).get('opaque1', {})
                    hd_screencast = opaque1.get('hd_screencast_stream')
                    if hd_screencast:
                        return self._ensure_https(hd_screencast)
                    default_screencast = opaque1.get('default_screencast_stream')
                    if default_screencast:
                        return self._ensure_https(default_screencast)

                    mv2_consumer = mv2.get('video', {}).get('consumer', {}) or mv2.get('consumer', {})
                    if isinstance(mv2_consumer, dict):
                        mv2_origin_key = mv2_consumer.get('originVideoKey') or mv2_consumer.get('origin_video_key')
                        if mv2_origin_key:
                            if mv2_origin_key.startswith(('http://', 'https://')):
                                return self._ensure_https(mv2_origin_key)
                            else:
                                return f"https://sns-video-bd.xhscdn.com/{mv2_origin_key.lstrip('/')}"
                except Exception as e:
                    logger.debug(f"解析 mediaV2 失败: {e}")

            # 3. 检查 h264/h265/av1 中的 stream，优先使用无水印流（如 streamType 258 或 301，或 streamDesc X264_MP4）
            stream = video_info.get('media', {}).get('stream', {}) or video_info.get('stream', {})
            unwatermarked_candidates = []
            fallback_candidates = []

            for codec in ('h264', 'h265', 'av1'):
                codec_list = stream.get(codec, [])
                if not isinstance(codec_list, list):
                    continue
                for item in codec_list:
                    if not isinstance(item, dict):
                        continue
                    master_url = item.get('masterUrl', '')
                    if not master_url:
                        continue
                    clean_url = self._ensure_https(master_url)
                    stream_type = item.get('streamType')
                    stream_desc = item.get('streamDesc', '')

                    if stream_type in (258, 301) or "X264_MP4" in stream_desc:
                        unwatermarked_candidates.append(clean_url)
                    elif stream_type not in (259, 309):
                        unwatermarked_candidates.append(clean_url)
                    else:
                        fallback_candidates.append(clean_url)

            if unwatermarked_candidates:
                return unwatermarked_candidates[0]
            if fallback_candidates:
                return fallback_candidates[0]
            return None
        except Exception as e:
            logger.error(f"获取小红书视频真实地址异常: {e}")
            return None

    def get_title_content(self):
        return self.note_data.get('title', '') or None

    def get_description(self):
        return self.note_data.get('desc', '') or None

    def get_cover_photo_url(self):
        cover = self.note_data.get('cover')
        if cover:
            clean_url = self._clean_image_url(cover)
            if clean_url:
                return clean_url

        # 兜底从 imageList 中获取首图作为封面
        image_list = self.note_data.get('imageList', [])
        if image_list and isinstance(image_list, list):
            first_img = image_list[0]
            clean_url = self._clean_image_url(first_img)
            if clean_url:
                return clean_url
        return None

    def get_image_list(self):
        image_url_list = []
        image_list = self.note_data.get('imageList', [])
        if not isinstance(image_list, list):
            return image_url_list

        for image in image_list:
            if not isinstance(image, dict):
                continue
            clean_url = self._clean_image_url(image)
            if clean_url:
                img_data = clean_url
                # 检查是否有 livePhoto
                if image.get('livePhoto', False):
                    stream = image.get('stream', {})
                    h264_data = stream.get('h264', [])
                    if h264_data and isinstance(h264_data, list):
                        master_url = h264_data[0].get('masterUrl', '')
                        if master_url:
                            img_data = {
                                'url': clean_url,
                                'live_photo_url': self._ensure_https(master_url)
                            }
                image_url_list.append(img_data)
        return image_url_list
