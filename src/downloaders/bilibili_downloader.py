import re
import os
import uuid
import random
import requests
import subprocess
import concurrent.futures
from src.downloaders.base_downloader import BaseDownloader
from configs.general_constants import USER_AGENT_PC, SAVE_VIDEO_PATH, DOMAIN
from configs.logging_config import get_logger
logger = get_logger(__name__)


class BilibiliDownloader(BaseDownloader):
    """
    B站下载器 —— 通过官方 API 获取视频信息和 DASH 流地址。

    调用链路：
    1. 从 URL 中提取 BV 号
    2. 调用 /x/web-interface/view 接口获取视频元信息（标题、封面、作者、cid）
    3. 调用 /x/player/playurl 接口获取 DASH 视频流和音频流的下载地址
    4. 并发下载 video.m4s + audio.m4s，使用 FFmpeg 合并为 mp4

    相比旧版爬取网页 HTML 的方案，API 方案的优势：
    - 不受 B 站针对数据中心 IP 的网页 WAF (412) 拦截
    - 返回结构化 JSON，无需 BeautifulSoup 解析 HTML
    - 更稳定，不受前端页面结构变化影响
    """

    # B站官方 API 端点
    API_VIEW = 'https://api.bilibili.com/x/web-interface/view'
    API_PLAYURL = 'https://api.bilibili.com/x/player/playurl'

    def __init__(self, real_url):
        super().__init__(real_url)
        self.headers = {
            'User-Agent': random.choice(USER_AGENT_PC),
            'referer': 'https://www.bilibili.com/'
        }
        self.bvid = self._extract_bvid(real_url)
        # 通过 API 获取视频元信息
        self.video_info = self._fetch_video_info()
        # 通过 API 获取 DASH 流地址
        self.play_info = self._fetch_play_info()

    @staticmethod
    def _extract_bvid(url):
        """从 URL 中提取 BV 号，如 BV1df421v7xm"""
        match = re.search(r'(BV[a-zA-Z0-9]+)', url)
        if match:
            return match.group(1)
        logger.error(f"无法从 URL 中提取 BV 号: {url}")
        return None

    def _fetch_video_info(self):
        """
        调用 /x/web-interface/view 接口获取视频元信息。
        返回 data 字典，包含 title、pic、owner、pages（含 cid）等。
        """
        if not self.bvid:
            return {}
        try:
            resp = self.session.get(
                self.API_VIEW,
                params={'bvid': self.bvid},
                headers=self.headers,
                timeout=10
            )
            resp.raise_for_status()
            result = resp.json()
            if result.get('code') == 0:
                logger.debug(f"B站 API 视频信息获取成功: {self.bvid}")
                return result.get('data', {})
            else:
                logger.error(f"B站 API 返回错误: code={result.get('code')}, message={result.get('message')}")
                return {}
        except requests.RequestException as e:
            logger.error(f"B站 API 视频信息请求失败: {e}")
            return {}

    def _fetch_play_info(self):
        """
        调用 /x/player/playurl 接口获取 DASH 流地址。
        需要 bvid 和 cid 两个参数，cid 从 video_info 中获取。
        fnval=16 表示请求 DASH 格式，qn=80 表示 1080P 画质。
        """
        cid = self._get_cid()
        if not self.bvid or not cid:
            return {}
        try:
            resp = self.session.get(
                self.API_PLAYURL,
                params={
                    'bvid': self.bvid,
                    'cid': cid,
                    'qn': 80,
                    'fnval': 16  # DASH 格式
                },
                headers=self.headers,
                timeout=10
            )
            resp.raise_for_status()
            result = resp.json()
            if result.get('code') == 0:
                logger.debug(f"B站 API DASH 流地址获取成功: {self.bvid}")
                return result.get('data', {})
            else:
                logger.error(f"B站 API playurl 返回错误: code={result.get('code')}, message={result.get('message')}")
                return {}
        except requests.RequestException as e:
            logger.error(f"B站 API playurl 请求失败: {e}")
            return {}

    def _get_cid(self):
        """从 video_info 中提取第一个分P的 cid"""
        pages = self.video_info.get('pages', [])
        if pages:
            return pages[0].get('cid')
        return None

    def get_video_m4s_url(self):
        try:
            videos = self.play_info.get('dash', {}).get('video', [])
            if videos:
                return videos[0].get('baseUrl')
            return None
        except (KeyError, TypeError) as e:
            logger.warning(f"Failed to parse Bilibili video URL: {e}")
            return None

    def get_audio_m4s_url(self):
        try:
            audios = self.play_info.get('dash', {}).get('audio', [])
            if audios:
                return audios[0].get('baseUrl')
            return None
        except (KeyError, TypeError) as e:
            logger.warning(f"Failed to parse Bilibili audio URL: {e}")
            return None

    def get_title_content(self):
        return self.video_info.get('title', '')

    def get_cover_photo_url(self):
        return self.video_info.get('pic', '')

    def get_author_info(self):
        owner = self.video_info.get('owner', {})
        author_info = {
            'nickname': owner.get('name', ''),
            'author_id': str(owner.get('mid', '')),
            'avatar': owner.get('face', '')
        }
        # B站的头像 URL 经常以 // 开头，缺少协议头，做个兼容处理
        if author_info['avatar'] and author_info['avatar'].startswith('//'):
            author_info['avatar'] = 'https:' + author_info['avatar']
        return author_info

    def get_real_video_url(self):
        """
        durl 单文件方案（480P）：获取包含视频+音频的单个 mp4 文件链接，
        下载到服务器后返回自有域名的可播放链接。
        B站 CDN 有 Referer 防盗链和链接时效限制，无法直接返回 CDN 原始链接。
        """
        cid = self._get_cid()
        if not self.bvid or not cid:
            logger.error("无法获取 BV 号或 cid，跳过 durl 获取")
            return None
        try:
            resp = self.session.get(
                self.API_PLAYURL,
                params={
                    'bvid': self.bvid,
                    'cid': cid,
                    'qn': 64,
                    'fnval': 0  # fnval=0 返回 durl 格式（单文件）
                },
                headers=self.headers,
                timeout=10
            )
            resp.raise_for_status()
            result = resp.json()
            if result.get('code') == 0:
                durls = result.get('data', {}).get('durl', [])
                if durls:
                    cdn_url = durls[0].get('url')
                    logger.debug(f"B站 durl 单文件链接获取成功: {self.bvid}")
                    # 下载到服务器，返回自有域名链接
                    saved_path = self.download_and_save(SAVE_VIDEO_PATH, cdn_url, "mp4")
                    if saved_path:
                        filename = os.path.basename(saved_path)
                        return f"{DOMAIN}/static/videos/{filename}"
                    return None
            logger.error(f"B站 durl 获取失败: {result.get('message')}")
            return None
        except requests.RequestException as e:
            logger.error(f"B站 durl 请求失败: {e}")
            return None

    def get_real_video_url_hd(self):
        """
        DASH 高清方案（1080P）：下载视频的 m4s 和音频的 m4s 文件，
        使用 FFmpeg 合并为 mp4，保存到 static/videos 中，并返回服务器可访问的视频链接。
        """
        video_url = self.get_video_m4s_url()
        audio_url = self.get_audio_m4s_url()

        if not video_url or not audio_url:
            logger.error("无法获取 B 站视频或音频链接 m4s 地址")
            return None

        # 并发下载 m4s 发挥最大网络带宽
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            future_video = executor.submit(self.download_and_save, SAVE_VIDEO_PATH, video_url, "m4s")
            future_audio = executor.submit(self.download_and_save, SAVE_VIDEO_PATH, audio_url, "m4s")

            video_m4s_path = future_video.result()
            audio_m4s_path = future_audio.result()

        if not video_m4s_path or not audio_m4s_path:
            logger.error("下载 B 站视频或音频 m4s 文件失败")
            return None

        # 随机生成最终的 mp4 文件名
        output_filename = f"{uuid.uuid4()}.mp4"
        output_path = os.path.join(SAVE_VIDEO_PATH, output_filename)

        # 使用 ffmpeg 拼接
        command = [
            "ffmpeg",
            "-y",  # overwrite output file if it exists
            "-i", video_m4s_path,
            "-i", audio_m4s_path,
            "-c:v", "copy",
            "-c:a", "copy",
            output_path
        ]

        try:
            logger.debug(f"正在使用 FFmpeg 合并视频和音频: {' '.join(command)}")
            subprocess.run(command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            # 拼接服务器地址
            server_video_url = f"{DOMAIN}/static/videos/{output_filename}"
            return server_video_url
        except subprocess.CalledProcessError as e:
            error_message = e.stderr.decode("utf-8") if e.stderr else str(e)
            logger.error(f"FFmpeg 合并失败: {error_message}")
            return None
        finally:
            # 无论成功或失败，都清理临时 m4s 文件
            if os.path.exists(video_m4s_path):
                os.remove(video_m4s_path)
            if os.path.exists(audio_m4s_path):
                os.remove(audio_m4s_path)



if __name__ == '__main__':
    real_url = 'https://www.bilibili.com/video/BV1df421v7xm/?share_source=copy_web&vd_source=5ac2e55972f5e2fd96b63d01ee42ff01'

    dl = BilibiliDownloader(real_url)

    print("-" * 30)
    print(f"作者信息：{dl.get_author_info()}")
    print(f"标题内容：{dl.get_title_content()[:30]}...")
    print(f"封面图片：{dl.get_cover_photo_url()}")
    print(f"\n【durl 单文件方案 - 480P】")
    print(f"视频链接：{dl.get_real_video_url()}")
    print(f"\n【DASH 高清方案 - 1080P（需要 FFmpeg 合并）】")
    print(f"视频链接：{dl.get_real_video_url_hd()}")
    print("-" * 30)

