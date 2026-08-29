from src.parser_factory import register_parser
# ======= 环境配置开始：将项目根目录添加到系统路径，当前脚本可测试 =======

from pathlib import Path
import sys
# 获取当前文件的绝对路径，并定位至向上推两级的项目根目录
root_dir = str(Path(__file__).resolve().parents[2])
# 如果根目录不在系统搜索路径中，则动态添加，以确保跨模块导入（Import）正常工作
if root_dir not in sys.path:
    sys.path.append(root_dir)

# ========================= 环境配置结束 =========================


import json
import urllib3
import warnings
import copy
from utils.web_fetcher import UrlParser
from utils.signer.bytedance.bogus_signer import BogusSigner
from configs.logging_config import get_logger
logger = get_logger(__name__)
from src.parsers.base_parser import BaseParser

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

    def fetch_html_data(self):
        # 尝试使用缓存的 ttwid，并在失败时重试一次（刷新 ttwid）
        for attempt in range(2):
            ttwid = self._get_ttwid()
            if not ttwid:
                ttwid = '1%7CvDWCB8tYdKPbdOlqwNTkDPhizBaV9i91KjYLKJbqurg%7C1723536402%7C314e63000decb79f46b8ff255560b29f4d8c57352dad465b41977db4830b4c7e'

            referer_url = f"https://www.douyin.com/video/{self.aweme_id}?previous_page=web_code_link"
            play_url = f"https://www.douyin.com/aweme/v1/web/aweme/detail/?device_platform=webapp&aid=6383&channel=channel_pc_web&aweme_id={self.aweme_id}&msToken={self.ms_token}"
            
            new_headers = copy.deepcopy(self.headers)
            new_headers['Referer'] = referer_url
            new_headers['Cookie'] = f"ttwid={ttwid}"
            
            abogus = self.signer.get_abogus(play_url, self.signer.user_agent)
            url = f"{play_url}&a_bogus={abogus}"
            
            try:
                response = self.session.get(url, headers=new_headers, verify=False, timeout=5)
                if response.status_code == 200 and response.text:
                    data = response.json()
                    # 如果返回结果中没有核心字段，说明 ttwid 可能在服务器端已失效，清空缓存重试
                    if not data.get('aweme_detail') and attempt == 0:
                        DouyinParser._TTWID_CACHE = None
                        continue
                    return data
                else:
                    if attempt == 0:
                        DouyinParser._TTWID_CACHE = None
                        continue
                    logger.warning(f"获取抖音视频详情失败: Status={response.status_code}")
                    return None
            except Exception as e:
                logger.error(f"请求抖音详情接口异常: {e}")
                if attempt == 0:
                    DouyinParser._TTWID_CACHE = None
                    continue
                return None
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
        1. 遍历 bit_rate 数组，提取有效流并按码率 (bit_rate) 降序排序；
        2. 优先选取 H.264 (is_h265 == 0) 的最高码率流，以保障跨平台及 Web 浏览器播放兼容性；
        3. 若无 H.264 则选取 H.265 的最高码率流；
        4. 若 bit_rate 为空或解析失败，无缝兜底到 video.play_addr / video.play_addr_h264 / video.play_addr_265。
        """
        try:
            data_dict = self.data
            if not data_dict or not data_dict.get('aweme_detail'):
                return None

            detail = data_dict.get('aweme_detail', {}) or {}
            video = detail.get('video', {}) or {}
            bit_rate_list = video.get('bit_rate', []) or []

            # 1. 尝试从 bit_rate 列表中选择最佳流
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

            # 2. 兜底方案：从 video.play_addr / play_addr_h264 / play_addr_265 提取
            for fallback_key in ('play_addr_h264', 'play_addr', 'play_addr_265'):
                fallback_play_addr = video.get(fallback_key)
                url = self._extract_best_url_from_play_addr(fallback_play_addr)
                if url:
                    return url

            return None
        except Exception as e:
            logger.warning(f"Failed to parse video URL: {e}")
            return None

    def get_video_list(self):
        """获取视频列表（单视频作品返回包含主视频的列表）"""
        video_url = self.get_real_video_url()
        return [video_url] if video_url else []

    def get_subtitles(self):
        """
        提取抖音原生 AI 生成字幕或多语言字幕列表。
        返回格式:
        [
            {
                "language_code": "zh-Hans",
                "url": "https://...",
                "format": "webvtt",
                "is_auto_generated": True,
                "sub_id": "123456"
            }
        ]
        若无字幕则返回 None。
        """
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

            subtitles = []
            for cap in caption_infos:
                if not isinstance(cap, dict):
                    continue

                url = cap.get('url')
                if not url:
                    url_list = cap.get('url_list') or []
                    if url_list:
                        url = url_list[0]

                if not url:
                    continue

                sub_item = {
                    'language_code': cap.get('language_code', ''),
                    'url': UrlParser.convert_to_https(url),
                    'format': cap.get('format', 'webvtt'),
                    'is_auto_generated': bool(cap.get('is_auto_generated', True)),
                }
                sub_id = cap.get('sub_id')
                if sub_id is not None:
                    sub_item['sub_id'] = str(sub_id)

                subtitles.append(sub_item)

            return subtitles if subtitles else None
        except Exception as e:
            logger.warning(f"Failed to parse Douyin subtitles: {e}")
            return None

    def get_title_content(self):
        try:
            data_dict = self.data
            if not data_dict or not data_dict.get('aweme_detail'):
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
            
            # 使用 or {} 确保 detail 不是 None
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
            if not data_dict or not data_dict.get('aweme_detail'):
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
            if not data_dict or not data_dict.get('aweme_detail'):
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

