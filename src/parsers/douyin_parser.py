import copy
import json
import re
import urllib.parse
import urllib3
import warnings

from bs4 import BeautifulSoup

from configs.logging_config import get_logger
from src.parser_factory import register_parser
from src.parsers.base_parser import BaseParser
from utils.signer.bytedance.bogus_signer import BogusSigner
from utils.web_fetcher import UrlParser

logger = get_logger(__name__)

warnings.filterwarnings("ignore", category=urllib3.exceptions.InsecureRequestWarning)


@register_parser("抖音")
class DouyinParser(BaseParser):
    def __init__(self, real_url):
        super().__init__(real_url)
        self.signer = BogusSigner()
        self.headers = {
            'sec-ch-ua': '"Google Chrome";v="123", "Not:A-Brand";v="8", "Chromium";v="123"',
            'Accept': 'application/json, text/plain, */*',
            'sec-ch-ua-mobile': '?0',
            'User-Agent': self.signer.user_agent,
            'sec-ch-ua-platform': '"Windows"',
            'Sec-Fetch-Site': 'same-origin',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Dest': 'empty',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        }
        self.ms_token = self.signer.get_ms_token()
        self.ttwid = '1%7CvDWCB8tYdKPbdOlqwNTkDPhizBaV9i91KjYLKJbqurg%7C1723536402%7C314e63000decb79f46b8ff255560b29f4d8c57352dad465b41977db4830b4c7e'
        self.webid = '7307457174287205926'
        self.is_music = bool(self.real_url and ('/music/' in self.real_url or '/share/music/' in self.real_url))
        self.is_collection = bool(self.real_url and ('/collection/' in self.real_url or '/mix/' in self.real_url or '/mix/detail/' in self.real_url))
        self.fetch_html_content()
        self.aweme_id = UrlParser.get_video_id(self.real_url)
        self.data = self.fetch_html_data()

    _TTWID_CACHE = None

    def _get_ttwid(self):
        """
        动态获取 ttwid，增加了类级别的缓存以减少重复请求
        """
        if DouyinParser._TTWID_CACHE:
            return DouyinParser._TTWID_CACHE

        try:
            url = "https://ttwid.bytedance.com/ttwid/union/register/"
            data = {
                "region": "cn",
                "aid": 6383,
                "need_t": 1,
                "service": "www.douyin.com",
                "migrate_priority": 0,
                "cb_url_protocol": "https",
                "domain": ".douyin.com"
            }
            # 使用 instance session
            resp = self.session.post(url, data=json.dumps(data), timeout=5)
            ttwid = resp.cookies.get('ttwid')
            if ttwid:
                DouyinParser._TTWID_CACHE = ttwid
            return ttwid
        except Exception as e:
            logger.warning(f"Failed to get dynamic ttwid: {e}")
            return None

    @staticmethod
    def _find_music_info(data, target_id=None):
        """
        递归查找嵌套字典或列表中的 music_info / musicInfo 节点。
        """
        if not data:
            return None

        if isinstance(data, dict):
            if "music_info" in data and isinstance(data["music_info"], dict):
                return data["music_info"]
            if "musicInfo" in data and isinstance(data["musicInfo"], dict):
                return data["musicInfo"]
            if "music" in data and isinstance(data["music"], dict) and ("play_url" in data["music"] or "title" in data["music"]):
                return data["music"]
            if "play_url" in data and ("author" in data or "owner_nickname" in data or "title" in data):
                return data
            for _, v in data.items():
                if isinstance(v, (dict, list)):
                    found = DouyinParser._find_music_info(v, target_id)
                    if found:
                        return found
        elif isinstance(data, list):
            for item in data:
                if isinstance(item, (dict, list)):
                    found = DouyinParser._find_music_info(item, target_id)
                    if found:
                        return found
        return None

    @staticmethod
    def _find_aweme_detail(data, target_id=None):
        """
        递归查找嵌套字典或列表中的 aweme_detail 或 itemStruct 节点。
        """
        if not data:
            return None

        if isinstance(data, dict):
            # 1. 直接包含标准 aweme_detail 键
            if "aweme_detail" in data and isinstance(data["aweme_detail"], dict):
                detail = data["aweme_detail"]
                if target_id is None or str(detail.get("aweme_id", "")) == str(target_id) or str(detail.get("id", "")) == str(target_id):
                    return detail

            # 2. 直接包含 itemStruct（现代 Web 端常见结构）
            if "itemStruct" in data and isinstance(data["itemStruct"], dict):
                detail = data["itemStruct"]
                if target_id is None or str(detail.get("aweme_id", "")) == str(target_id) or str(detail.get("id", "")) == str(target_id):
                    return detail

            # 3. 自身就是一个合法的 aweme 对象（包含 video/images/desc 等标志字段）
            if ("video" in data or "images" in data) and ("desc" in data or "author" in data):
                if target_id is None or str(data.get("aweme_id", "")) == str(target_id) or str(data.get("id", "")) == str(target_id):
                    return data

            # 4. 递归遍历字典的所有子项
            for _, v in data.items():
                if isinstance(v, (dict, list)):
                    found = DouyinParser._find_aweme_detail(v, target_id)
                    if found:
                        return found

        elif isinstance(data, list):
            for item in data:
                if isinstance(item, (dict, list)):
                    found = DouyinParser._find_aweme_detail(item, target_id)
                    if found:
                        return found

        return None

    def _parse_ssr_data(self, html_content):
        """
        从抖音 PC 网页端 HTML 提取内嵌的 SSR 数据作为免签名兜底方案。
        支持结构：
        1. <script id="__UNIVERSAL_DATA_FOR_REHYDRATION__" ...>
        2. <script id="RENDER_DATA" ...> (支持 URL 编码解码)
        3. window._ROUTER_DATA / window._SSR_DATA 正则匹配
        """
        if not html_content or not isinstance(html_content, str):
            return None

        soup = BeautifulSoup(html_content, 'lxml')

        # 策略 1: __UNIVERSAL_DATA_FOR_REHYDRATION__ (现代抖音主流)
        universal_script = soup.find('script', id='__UNIVERSAL_DATA_FOR_REHYDRATION__')
        if universal_script and universal_script.string:
            try:
                raw_json = json.loads(universal_script.string.strip())
                if self.is_music:
                    music_info = self._find_music_info(raw_json, self.aweme_id)
                    if music_info:
                        logger.info("Successfully extracted Douyin music detail from __UNIVERSAL_DATA_FOR_REHYDRATION__")
                        return {"music_info": music_info}
                detail = self._find_aweme_detail(raw_json, self.aweme_id)
                if detail:
                    logger.info("Successfully extracted Douyin detail from __UNIVERSAL_DATA_FOR_REHYDRATION__")
                    return {"aweme_detail": detail}
            except Exception as e:
                logger.debug(f"Failed to parse __UNIVERSAL_DATA_FOR_REHYDRATION__: {e}")

        # 策略 2: RENDER_DATA (经典版本)
        render_script = soup.find('script', id='RENDER_DATA')
        if render_script and render_script.string:
            try:
                content = render_script.string.strip()
                if '%' in content:
                    content = urllib.parse.unquote(content)
                raw_json = json.loads(content)
                if self.is_music:
                    music_info = self._find_music_info(raw_json, self.aweme_id)
                    if music_info:
                        logger.info("Successfully extracted Douyin music detail from RENDER_DATA")
                        return {"music_info": music_info}
                detail = self._find_aweme_detail(raw_json, self.aweme_id)
                if detail:
                    logger.info("Successfully extracted Douyin detail from RENDER_DATA")
                    return {"aweme_detail": detail}
            except Exception as e:
                logger.debug(f"Failed to parse RENDER_DATA: {e}")

        # 策略 3: 正则匹配 _ROUTER_DATA / _SSR_DATA / __INIT_PROPS__
        patterns = [
            re.compile(r'_ROUTER_DATA\s*=\s*(\{.*?\});', re.DOTALL),
            re.compile(r'window\._SSR_DATA\s*=\s*(\{.*?\});', re.DOTALL),
            re.compile(r'window\.__INIT_PROPS__\s*=\s*(\{.*?\});', re.DOTALL),
        ]
        for pattern in patterns:
            match = pattern.search(html_content)
            if match:
                try:
                    raw_json = json.loads(match.group(1).strip())
                    if self.is_music:
                        music_info = self._find_music_info(raw_json, self.aweme_id)
                        if music_info:
                            logger.info("Successfully extracted Douyin music detail from regex SSR script")
                            return {"music_info": music_info}
                    detail = self._find_aweme_detail(raw_json, self.aweme_id)
                    if detail:
                        logger.info("Successfully extracted Douyin detail from regex SSR script")
                        return {"aweme_detail": detail}
                except Exception as e:
                    logger.debug(f"Failed to parse regex SSR data: {e}")

        return None

    def fetch_html_data(self):
        """
        获取抖音作品元数据（支持单视频、图文、音乐原声、合集与 SSR HTML 免签名多级容灾兜底）。
        """
        # 0. 针对音乐 / 原声独立链接 (/music/)
        if self.is_music:
            for attempt in range(2):
                ttwid = self._get_ttwid() or '1%7CvDWCB8tYdKPbdOlqwNTkDPhizBaV9i91KjYLKJbqurg%7C1723536402%7C314e63000decb79f46b8ff255560b29f4d8c57352dad465b41977db4830b4c7e'
                music_api = f"https://www.douyin.com/aweme/v1/web/music/detail/?music_id={self.aweme_id}&device_platform=webapp&aid=6383&channel=channel_pc_web&msToken={self.ms_token}"
                new_headers = copy.deepcopy(self.headers)
                new_headers['Referer'] = f"https://www.douyin.com/music/{self.aweme_id}"
                new_headers['Cookie'] = f"ttwid={ttwid}"
                try:
                    abogus = self.signer.get_abogus(music_api, self.signer.user_agent)
                    url = f"{music_api}&a_bogus={abogus}"
                    response = self.session.get(url, headers=new_headers, verify=False, timeout=5)
                    if response.status_code == 200 and response.text:
                        data = response.json()
                        if data.get('music_info'):
                            return data
                except Exception as e:
                    logger.debug(f"抖音音乐 API 异常: {e}")

            if not self.html_content:
                self.fetch_html_content()
            if self.html_content:
                ssr_data = self._parse_ssr_data(self.html_content)
                if ssr_data and ssr_data.get('music_info'):
                    return ssr_data
            return None

        # 0. 针对合集链接 (/collection/ 或 /mix/)
        if self.is_collection:
            for attempt in range(2):
                ttwid = self._get_ttwid() or '1%7CvDWCB8tYdKPbdOlqwNTkDPhizBaV9i91KjYLKJbqurg%7C1723536402%7C314e63000decb79f46b8ff255560b29f4d8c57352dad465b41977db4830b4c7e'
                mix_api = f"https://www.douyin.com/aweme/v1/web/mix/aweme/?mix_id={self.aweme_id}&cursor=0&count=20&device_platform=webapp&aid=6383&channel=channel_pc_web&msToken={self.ms_token}"
                new_headers = copy.deepcopy(self.headers)
                new_headers['Referer'] = f"https://www.douyin.com/collection/{self.aweme_id}"
                new_headers['Cookie'] = f"ttwid={ttwid}"
                try:
                    abogus = self.signer.get_abogus(mix_api, self.signer.user_agent)
                    url = f"{mix_api}&a_bogus={abogus}"
                    response = self.session.get(url, headers=new_headers, verify=False, timeout=5)
                    if response.status_code == 200 and response.text:
                        data = response.json()
                        aweme_list = data.get('aweme_list', [])
                        if aweme_list or data.get('mix_info'):
                            if 'aweme_detail' not in data and aweme_list:
                                data['aweme_detail'] = aweme_list[0]
                            return data
                except Exception as e:
                    logger.debug(f"抖音合集 API 异常: {e}")

            if not self.html_content:
                self.fetch_html_content()
            if self.html_content:
                ssr_data = self._parse_ssr_data(self.html_content)
                if ssr_data and (ssr_data.get('aweme_detail') or ssr_data.get('mix_info')):
                    return ssr_data
            return None

        # 1. 尝试使用缓存的 ttwid 调用普通作品 API，并在失败时重试一次（刷新 ttwid）
        for attempt in range(2):
            ttwid = self._get_ttwid()
            if not ttwid:
                ttwid = '1%7CvDWCB8tYdKPbdOlqwNTkDPhizBaV9i91KjYLKJbqurg%7C1723536402%7C314e63000decb79f46b8ff255560b29f4d8c57352dad465b41977db4830b4c7e'

            referer_url = f"https://www.douyin.com/video/{self.aweme_id}?previous_page=web_code_link"
            play_url = f"https://www.douyin.com/aweme/v1/web/aweme/detail/?device_platform=webapp&aid=6383&channel=channel_pc_web&aweme_id={self.aweme_id}&msToken={self.ms_token}"
            
            new_headers = copy.deepcopy(self.headers)
            new_headers['Referer'] = referer_url
            new_headers['Cookie'] = f"ttwid={ttwid}"
            
            try:
                abogus = self.signer.get_abogus(play_url, self.signer.user_agent)
                url = f"{play_url}&a_bogus={abogus}"
            except Exception as e:
                logger.warning(f"生成 a_bogus 签名异常: {e}")
                break

            try:
                response = self.session.get(url, headers=new_headers, verify=False, timeout=5)
                if response.status_code == 200 and response.text:
                    data = response.json()
                    # 如果返回结果中包含核心字段，说明 API 抓取成功
                    if data.get('aweme_detail'):
                        return data
                    if attempt == 0:
                        DouyinParser._TTWID_CACHE = None
                        continue
                else:
                    if attempt == 0:
                        DouyinParser._TTWID_CACHE = None
                        continue
                    logger.warning(f"获取抖音视频详情失败: Status={response.status_code}")
            except Exception as e:
                logger.error(f"请求抖音详情接口异常: {e}")
                if attempt == 0:
                    DouyinParser._TTWID_CACHE = None
                    continue

        # 2. 多级容灾降级：当 API 失败时，从页面 SSR HTML 提取数据
        logger.info(f"抖音 a_bogus API 未返回有效详情，触发 SSR HTML 兜底解析: {self.real_url}")
        if not self.html_content:
            self.fetch_html_content()

        if self.html_content:
            ssr_data = self._parse_ssr_data(self.html_content)
            if ssr_data and ssr_data.get('aweme_detail'):
                return ssr_data

        return None

    @staticmethod
    def _extract_best_url_from_play_addr(play_addr_dict):
        """
        从 play_addr 字典中提取最佳播放链接。
        play_addr_list 结构通常为：[主CDN节点, 备用CDN节点, 抖音官方源站URL]
        优先取源站 URL（如列表中有 3 个或更多元素，取 index 2），否则取第 1 个。
        """
        if not play_addr_dict or not isinstance(play_addr_dict, dict):
            return None
        url_list = play_addr_dict.get('url_list') or []
        if not url_list:
            return None
        if len(url_list) >= 3 and url_list[2]:
            return url_list[2]
        return url_list[0] if url_list else None

    def get_real_video_url(self):
        """
        获取最高清晰度视频播放地址。
        优化策略：
        1. 图文作品（包含 images 列表或 media_type=2 且无 bit_rate）直接返回 None；
        2. 遍历 bit_rate 数组，提取有效流并按码率 (bit_rate) 降序排序；
        3. 优先选取 H.264 (is_h265 == 0) 的最高码率流，以保障跨平台及 Web 浏览器播放兼容性；
        4. 若无 H.264 则选取 H.265 的最高码率流；
        5. 若 bit_rate 为空或解析失败，无缝兜底到 video.play_addr / video.play_addr_h264 / video.play_addr_265（严格过滤音频流）。
        """
        if self.is_music:
            return None

        try:
            data_dict = self.data
            if not data_dict:
                return None

            detail = data_dict.get('aweme_detail', {}) or {}
            if not detail and self.is_collection and data_dict.get('aweme_list'):
                detail = data_dict['aweme_list'][0]

            video = detail.get('video', {}) or {}
            bit_rate_list = video.get('bit_rate', []) or []
            images = detail.get('images') or detail.get('image_list') or []
            media_type = detail.get('media_type')

            # 1. 图文作品识别：如果存在 images 列表或 media_type=2，且没有视频码率流，则为纯图文作品，不返回视频地址
            if (images or media_type == 2) and not bit_rate_list:
                return None

            # 2. 尝试从 bit_rate 列表中选择最佳流
            valid_streams = []
            for item in bit_rate_list:
                if not isinstance(item, dict):
                    continue
                play_addr = item.get('play_addr')
                url = self._extract_best_url_from_play_addr(play_addr)
                if url:
                    rate = item.get('bit_rate') or 0
                    is_h265 = item.get('is_h265', 0)
                    valid_streams.append({
                        'bit_rate': rate,
                        'is_h265': is_h265,
                        'url': url
                    })

            if valid_streams:
                # 优先筛选 H.264 流
                h264_streams = [s for s in valid_streams if not s.get('is_h265')]
                if h264_streams:
                    # 按码率降序，选最高画质
                    h264_streams.sort(key=lambda s: s['bit_rate'], reverse=True)
                    return h264_streams[0]['url']

                # 若仅有 H.265，则按码率降序选最高画质
                valid_streams.sort(key=lambda s: s['bit_rate'], reverse=True)
                return valid_streams[0]['url']

            # 3. 兜底方案：从 video.play_addr / play_addr_h264 / play_addr_265 提取（严格过滤音频流）
            for fallback_key in ('play_addr_h264', 'play_addr', 'play_addr_265'):
                fallback_play_addr = video.get(fallback_key)
                url = self._extract_best_url_from_play_addr(fallback_play_addr)
                if url:
                    clean_url = url.split('?')[0].lower()
                    if clean_url.endswith(('.mp3', '.m4a', '.aac', '.wav')) or 'ies-music' in url:
                        continue
                    return url

            return None
        except Exception as e:
            logger.warning(f"Failed to parse video URL: {e}")
            return None

    def get_video_list(self):
        """获取视频列表（单视频作品返回包含主视频的列表；合集返回所有分集视频列表）"""
        if self.is_music:
            return []

        if self.is_collection and self.data and self.data.get('aweme_list'):
            video_urls = []
            for item in self.data['aweme_list']:
                video_item = item.get('video') or {}
                bit_rate_list = video_item.get('bit_rate') or []
                url = None
                if bit_rate_list:
                    for b in bit_rate_list:
                        if not b.get('is_h265'):
                            url = self._extract_best_url_from_play_addr(b.get('play_addr'))
                            if url:
                                break
                    if not url and bit_rate_list:
                        url = self._extract_best_url_from_play_addr(bit_rate_list[0].get('play_addr'))
                if not url:
                    url = self._extract_best_url_from_play_addr(video_item.get('play_addr'))
                if url:
                    video_urls.append(url)
            if video_urls:
                return video_urls

        video_url = self.get_real_video_url()
        return [video_url] if video_url else []

    @staticmethod
    def _parse_timestamp_to_seconds(ts_str: str) -> float:
        """将 WebVTT / SRT 时间戳 (如 00:01:23.456 或 01:23.456) 转换为秒数"""
        try:
            ts_str = ts_str.strip().replace(',', '.')
            parts = ts_str.split(':')
            if len(parts) == 3:
                hours = float(parts[0])
                minutes = float(parts[1])
                seconds = float(parts[2])
                return round(hours * 3600 + minutes * 60 + seconds, 2)
            elif len(parts) == 2:
                minutes = float(parts[0])
                seconds = float(parts[1])
                return round(minutes * 60 + seconds, 2)
            elif len(parts) == 1:
                return round(float(parts[0]), 2)
        except (ValueError, TypeError):
            pass
        return 0.0

    @staticmethod
    def _parse_webvtt_to_segments(vtt_text: str):
        """
        解析 WebVTT / SRT 文本为统一的结构化字幕片段数组:
        [
            {"start": 0.64, "end": 2.12, "text": "第一句文案"},
            ...
        ]
        """
        if not vtt_text or not isinstance(vtt_text, str):
            return None

        time_cue_pattern = re.compile(
            r'((?:\d+:)?\d+:\d+(?:[\.,]\d+)?)\s*-->\s*((?:\d+:)?\d+:\d+(?:[\.,]\d+)?)'
        )

        lines = vtt_text.splitlines()
        segments = []
        current_start = None
        current_end = None
        current_text_lines = []

        def flush_segment():
            nonlocal current_start, current_end, current_text_lines
            if current_start is not None and current_text_lines:
                text = " ".join([l.strip() for l in current_text_lines if l.strip()])
                # 过滤 WebVTT 内置样式标签，如 <c>, <v>, <b>, <i> 等
                text = re.sub(r'<[^>]+>', '', text).strip()
                if text:
                    segments.append({
                        "start": current_start,
                        "end": current_end,
                        "text": text
                    })
            current_start = None
            current_end = None
            current_text_lines = []

        for line in lines:
            stripped = line.strip()
            if not stripped:
                flush_segment()
                continue

            if stripped.startswith("WEBVTT") or stripped.startswith("NOTE") or stripped.startswith("STYLE"):
                continue

            match = time_cue_pattern.search(stripped)
            if match:
                flush_segment()
                start_str, end_str = match.group(1), match.group(2)
                current_start = DouyinParser._parse_timestamp_to_seconds(start_str)
                current_end = DouyinParser._parse_timestamp_to_seconds(end_str)
                current_text_lines = []
            elif current_start is not None:
                current_text_lines.append(stripped)

        flush_segment()
        return segments if segments else None

    def get_subtitles(self):
        """
        提取抖音原生字幕并自动下载解析为结构化时间轴文本数组。
        返回格式:
        [
            {"start": 0.64, "end": 2.12, "text": "第一句文案"},
            {"start": 2.20, "end": 4.50, "text": "第二句文案"}
        ]
        若无字幕则返回 None。
        """
        if self.is_music:
            return None

        try:
            data_dict = self.data
            if not data_dict or not data_dict.get('aweme_detail'):
                return None

            detail = data_dict.get('aweme_detail', {}) or {}
            video = detail.get('video', {}) or {}

            # 1. 优先从 video.cla_info 中提取
            cla_info = video.get('cla_info') or {}
            caption_infos = cla_info.get('caption_infos') or cla_info.get('captions') or []

            # 2. 兜底从 video.subtitle_infos 提取
            if not caption_infos:
                caption_infos = video.get('subtitle_infos') or []

            if not caption_infos or not isinstance(caption_infos, list):
                return None

            # 3. 优先选择中文字幕 (zh-Hans / zh / zh-CN / cmn-Hans)，兜底选择第一个可用字幕
            target_cap = None
            for cap in caption_infos:
                if isinstance(cap, dict) and cap.get('language_code') in ('zh-Hans', 'zh', 'zh-CN', 'cmn-Hans'):
                    target_cap = cap
                    break
            if not target_cap and caption_infos:
                for cap in caption_infos:
                    if isinstance(cap, dict) and (cap.get('url') or cap.get('url_list')):
                        target_cap = cap
                        break

            if not target_cap:
                return None

            url = target_cap.get('url')
            if not url:
                url_list = target_cap.get('url_list') or []
                if url_list:
                    url = url_list[0]

            if not url:
                return None

            sub_url = UrlParser.convert_to_https(url)
            resp = self.session.get(sub_url, headers=self.headers, timeout=5)
            if resp.status_code == 200 and resp.text:
                return self._parse_webvtt_to_segments(resp.text)

            return None
        except Exception as e:
            logger.warning(f"Failed to parse Douyin subtitles: {e}")
            return None

    def get_title_content(self):
        try:
            data_dict = self.data
            if not data_dict:
                return None

            if self.is_music:
                music_info = data_dict.get('music_info') or {}
                return music_info.get('title', '')

            if self.is_collection:
                mix_info = data_dict.get('mix_info') or {}
                mix_name = mix_info.get('mix_name')
                if mix_name:
                    return f"【合集】{mix_name}"

            if not data_dict.get('aweme_detail'):
                return None
            title_content = data_dict['aweme_detail'].get('desc', '')
            return title_content
        except (KeyError, json.JSONDecodeError, TypeError) as e:
            logger.warning(f"Failed to parse title content: {e}")
            return None

    def get_cover_photo_url(self):
        try:
            data_dict = self.data
            if not data_dict:
                return None

            if self.is_music:
                music_info = data_dict.get('music_info') or {}
                for k in ('cover_large', 'cover_hd', 'cover_medium', 'cover_thumb'):
                    url_list = (music_info.get(k) or {}).get('url_list') or []
                    if url_list:
                        return url_list[0]
                return None

            if self.is_collection:
                mix_info = data_dict.get('mix_info') or {}
                cover_obj = mix_info.get('cover_url') or {}
                url_list = cover_obj.get('url_list') or []
                if url_list:
                    return url_list[0]
            
            detail = data_dict.get('aweme_detail') or {}
            
            # 1. 尝试获取视频动态封面
            video_cover = None
            video_data = detail.get('video') or {}
            if video_data and 'dynamic_cover' in video_data:
                url_list = video_data['dynamic_cover'].get('url_list') or []
                if url_list:
                    video_cover = url_list[0]
            
            # 2. 尝试获取图集封面 (如果视频封面不存在)
            images_cover = None
            images_list = detail.get('images') or []
            if images_list and len(images_list) > 0:
                first_img = images_list[0] or {}
                url_list = first_img.get('url_list') or []
                if url_list:
                    images_cover = url_list[0]
            
            # 3. 优先级逻辑：有视频封面优先用视频，否则用图集封面
            play_cover = video_cover or images_cover
            
            if not play_cover:
                logger.info("No cover URL found in both video and images.")
            
            return play_cover
            
        except Exception as e:
            logger.warning(f"Failed to parse cover URL: {e}")
            return None

    def get_audio_url(self):
        try:
            data_dict = self.data
            if not data_dict:
                return None

            if self.is_music:
                music_info = data_dict.get('music_info') or {}
                play_url = music_info.get('play_url') or {}
                url_list = play_url.get('url_list') or []
                if url_list:
                    return url_list[0]
                return None

            if not data_dict.get('aweme_detail'):
                return None
            detail = data_dict.get('aweme_detail') or {}
            music = detail.get('music') or {}
            play_url = music.get('play_url') or {}
            url_list = play_url.get('url_list') or []
            if url_list:
                return url_list[0]
            return None
        except (KeyError, json.JSONDecodeError, TypeError) as e:
            logger.warning(f"Failed to parse background music: {e}")
            return None

    def get_author_info(self):
        try:
            data_dict = self.data
            if not data_dict:
                return None

            if self.is_music:
                music_info = data_dict.get('music_info') or {}
                avatar_list = (music_info.get('avatar_large') or music_info.get('avatar_medium') or {}).get('url_list') or [None]
                return {
                    "nickname": music_info.get('author') or music_info.get('owner_nickname', ''),
                    "author_id": str(music_info.get('owner_id') or music_info.get('sec_uid') or ''),
                    "avatar": avatar_list[0]
                }

            if self.is_collection:
                mix_info = data_dict.get('mix_info') or {}
                author = mix_info.get('author') or (data_dict.get('aweme_detail', {}).get('author') or {})
                if author:
                    avatar_thumb = author.get('avatar_thumb') or {}
                    avatar_url_list = avatar_thumb.get('url_list') or [None]
                    return {
                        "nickname": author.get('nickname', ''),
                        "author_id": author.get('unique_id') or author.get('short_id', ''),
                        "avatar": avatar_url_list[0]
                    }

            if not data_dict.get('aweme_detail'):
                return None
                
            author = (data_dict['aweme_detail'].get('author') or {})
            if not author:
                return None
                
            # 1. 抖音号逻辑：优先取 unique_id (自定义号)，没有则取 short_id
            # 2. 头像逻辑：安全取 url_list 的第一个元素
            avatar_thumb = author.get('avatar_thumb') or {}
            avatar_url_list = avatar_thumb.get('url_list') or [None]
            
            return {
                "nickname": author.get('nickname', ''),
                "author_id": author.get('unique_id') or author.get('short_id', ''),
                "avatar": avatar_url_list[0]
            }
        except Exception as e:
            logger.warning(f"Failed to parse author info: {e}")
            return None

    def get_image_list(self):
        """
        针对 aweme_type 68 的图文笔记，提取所有高清图片链接
        """
        if self.is_music:
            return []

        try:
            data_dict = self.data
            if not data_dict or 'aweme_detail' not in data_dict:
                return []

            # 1. 抖音图文笔记的图片存储在 images 字段中
            images = data_dict['aweme_detail'].get('images') or []
            if not images:
                # 兜底：有些版本可能在 image_list 字段
                images = data_dict['aweme_detail'].get('image_list') or []

            image_urls = []
            for img in images:
                if not img:
                    continue
                # ⚠️ 注意：download_url_list 包含带水印的图片！
                # url_list 才是无水印的原始图片链接（已通过 f2 等主流项目验证）
                # url_list 中最后一个元素通常是最高质量的 CDN 链接
                urls = img.get('url_list')

                if urls and isinstance(urls, list) and len(urls) > 0:
                    # 优先取最后一个 URL（通常是最高质量的源站 CDN）
                    img_data = urls[-1]
                    # 检查是否有 livePhoto
                    if 'video' in img and 'play_addr' in img['video']:
                        live_urls = img['video']['play_addr'].get('url_list')
                        if live_urls and isinstance(live_urls, list) and len(live_urls) > 0:
                            img_data = {
                                'url': img_data,
                                'live_photo_url': live_urls[0]
                            }
                    image_urls.append(img_data)

            return image_urls

        except Exception as e:
            logger.warning(f"Failed to parse image list: {e}")
            return []


