import json
import random
from utils.web_fetcher import UrlParser
from src.parsers.base_parser import BaseParser
from configs.general_constants import USER_AGENT_PC
from configs.logging_config import get_logger

logger = get_logger(__name__)


class KuaishouParser(BaseParser):
    def __init__(self, real_url):
        super().__init__(real_url)

        self.headers = {
            "content-type": "application/json; charset=UTF-8",
            'User-Agent': random.choice(USER_AGENT_PC),
            'referer': 'https://www.kuaishou.com/',
            # 快手加入无登录的cookie，解析成功率高
            'cookie': f'kpf=PC_WEB; clientid=3; did=web_bfbcdb2f5b3dc663a745deabafcf61e6; kwpsecproductname=kuaishou-vision; didv=1773330035000; kwpsecproductname=kuaishou-vision; userId=446442483; kuaishou.server.webday7_st=ChprdWFpc2hvdS5zZXJ2ZXIud2ViZGF5Ny5zdBKwAeuBbGjVcz39sj4G7d7P54r9C1etC_QftYb2I1XMg01WSbw9NefL7E6EmwkYxHf70B9BM3Oyk20kFv1Y0xnRcfHtGNHYUHkmKguP6cvFeACofr2zPAZYRchRkndIBk5qExOlkr4FSoGpY-WqXeibapHNEbfZTLZl_QkQA4aGWotSZpBMv6wR3RxZWiMv60xc-CIndGICJbbRAaRGZNxz7QBj2Mr-SeU2o0bVi7esnD1AGhKquV16S9dezebl5ZuYo_R_JKgiIAidQF8n526Yos_GTgm3KrGknnEbkK-NMiNvTw3YBehZKAUwAQ; kuaishou.server.webday7_ph=f3720606882f1d7a76ab1ab52a489c4d44a1; bUserId=1000583835422; ktrace-context=1|MS44Nzg0NzI0NTc4Nzk2ODY5Ljg3MTE4OTQ4LjE3NzM1NzExNTEyMjQuNDQ0OTc1MTI=|MS44Nzg0NzI0NTc4Nzk2ODY5LjUxNTU3MjM4LjE3NzM1NzExNTEyMjQuNDQ0OTc1MTM=|0|webservice-user-growth-node|webservice|true|src-Js; kwssectoken=BIjmefxxiTpXOdz9/RQ6Gl7cR5/0J7xaPzJ18udJgBSLTrJy4O7LhrYtbeeHGW+AOJrI6P8LQnioDWSuuQxV8Q==; kwscode=75d440673de879734b8700f363119968b4fabb4eb0369b1607e206d8e8c1ac9d; kpn=KUAISHOU_VISION; kwfv1=PnGU+9+Y8008S+nH0U+0mjPf8fP08f+98f+nLlwnrIP9P9G98YPf8jPBQSweS0+nr9G0mD8B+fP/L98/qlPe4f8eDI8f8jwBGh8BPAPfLEGALhGf+f+AYj+e4jPfLl+AY0G/cI+/Q0G0DEPfc98/mjw/pSPBbjGArh8erl+ezfG/HlP0zf+0b0+n+DGnpj+0HI+9Qj+0p0PeDF+ADIPeL7+W==; kwssectoken=IMLS/eg005i6IUbIoIB/7WByh8ciKMPUXULQ3a5/m3dK5D9ez8He/oMP2QLhil52v7Bk3O0CO2g6t5R/5XjSCw==; kwscode=75d440673de879734b8700f363119968b4fabb4eb0369b1607e206d8e8c1ac9d'
        }
        self.video_id = UrlParser.get_video_id(self.real_url)
        # 第一次请求获取基础数据
        self.html_content = self.fetch_html_content()

        # 识别页面类型并解析数据
        self.page_type, self.structured_data = self._identify_and_parse_data()

        # 提取核心数据客户端对象
        self.client = self.structured_data.get('defaultClient',
                                               {}) if self.page_type == "VIDEO" else self.structured_data

    def _extract_json_object(self, text, start_index):
        """稳健提取 JSON 对象：通过括号匹配解决额外数据报错"""
        if start_index == -1: return None
        bracket_count = 0
        found_start = False
        for i in range(start_index, len(text)):
            if text[i] == '{':
                bracket_count += 1
                found_start = True
            elif text[i] == '}':
                bracket_count -= 1
                if found_start and bracket_count == 0:
                    return text[start_index:i + 1]
        return None

    def _identify_and_parse_data(self):
        """识别快手不同的数据载体（Apollo 或 InitState）"""
        # 1. 视频详情页 (Apollo)
        if "window.__APOLLO_STATE__" in self.html_content:
            marker = "window.__APOLLO_STATE__"
            start_pos = self.html_content.find(marker) + len(marker)
            start_pos = self.html_content.find("{", start_pos)
            json_str = self._extract_json_object(self.html_content, start_pos)
            if json_str:
                try:
                    return "VIDEO", json.loads(json_str)
                except:
                    pass

        # 2. 某些图文或移动端适配页 (INIT_STATE)
        if "window.INIT_STATE" in self.html_content:
            marker = "window.INIT_STATE"
            start_pos = self.html_content.find(marker) + len(marker)
            start_pos = self.html_content.find("{", start_pos)
            json_str = self._extract_json_object(self.html_content, start_pos)
            if json_str:
                try:
                    return "ATLAS", json.loads(json_str, strict=False)
                except:
                    pass

        return "UNKNOWN", {}

    def get_real_video_url(self):
        if self.page_type != "VIDEO": return None
        try:
            # 优先从标准表示层获取
            video_url = self.client.get('VisionVideoSetRepresentation:1', {}).get('url')
            # 兜底：直接从 Photo 对象获取
            if not video_url:
                photo_key = f"VisionVideoDetailPhoto:{self.video_id}"
                video_url = self.client.get(photo_key, {}).get('photoUrl')

            return video_url.replace("\u002F", "/") if video_url else None
        except Exception as e:
            logger.warning(f"Failed to parse video URL: {e}")
            return None

    def get_title_content(self):
        try:
            photo_key = f"VisionVideoDetailPhoto:{self.video_id}"
            if self.page_type == "VIDEO":
                return self.client.get(photo_key, {}).get('caption', '')
            # 图文页兜底逻辑...
        except:
            pass
        return ""

    def get_cover_photo_url(self):
        try:
            photo_key = f"VisionVideoDetailPhoto:{self.video_id}"
            return self.client.get(photo_key, {}).get('coverUrl', '')
        except:
            pass
        return ""

    def get_author_info(self):
        """
        核心修正：通过引用 ID 在扁平化的状态机中进行二次索引
        """
        try:
            if self.page_type == "VIDEO":
                # 1. 定位视频对象中的作者引用
                photo_key = f"VisionVideoDetailPhoto:{self.video_id}"
                author_ref = self.client.get(photo_key, {}).get('author')

                # 2. 模糊匹配兜底（防止 Key 中带有复杂参数）
                if not author_ref:
                    for k in self.client.keys():
                        if f'photoId":"{self.video_id}"' in k:
                            author_ref = self.client[k].get('author')
                            break

                # 3. 提取详情
                if author_ref and author_ref.get('id') in self.client:
                    author_detail = self.client[author_ref['id']]
                    return {
                        "nickname": author_detail.get('name'),
                        "unique_id": author_detail.get('id'),
                        "avatar": author_detail.get('headerUrl')
                    }
            elif self.page_type == "ATLAS":
                # 图文页通常直接在某个 Profile 节点下
                for val in self.structured_data.values():
                    if isinstance(val, dict) and "userProfile" in val:
                        p = val['userProfile']['profile']
                        return {
                            "nickname": p.get('user_name'),
                            "unique_id": p.get('user_id'),
                            "avatar": p.get('headurl')
                        }
        except Exception as e:
            logger.error(f"Author parse error: {e}")
        return None

    def get_audio_url(self):
        """
        获取独立的音频链接。
        快手网页端大部分不直接暴露独立的音频源 URL，因此采用通用提取方案：
        获取无水印视频 URL -> 解析此视频 -> 使用 FFmpeg 分离提取纯音频（不重编码） -> 存放在服务器 -> 返回本地链接
        """
        video_url = self.get_real_video_url()
        if not video_url:
             return None
             
        import os, uuid, subprocess
        from configs.general_constants import SAVE_VIDEO_PATH, DOMAIN
        
        video_path = self.download_and_save(SAVE_VIDEO_PATH, video_url, "mp4")
        if not video_path:
             logger.error("快手获取视频文件失败，无法提取音频")
             return None
             
        output_filename = f"{uuid.uuid4()}_audio.m4a"
        output_path = os.path.join(SAVE_VIDEO_PATH, output_filename)
        
        command = [
             "ffmpeg",
             "-y",
             "-i", video_path,
             "-vn",           # 去掉视频流
             "-c:a", "copy",  # 直接提取底层原始音频流，无需重复编码，极速秒级完成
             output_path
        ]
        
        try:
             logger.debug(f"正在使用 FFmpeg 提取快手音频: {' '.join(command)}")
             subprocess.run(command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
             return f"{DOMAIN}/static/videos/{output_filename}"
        except subprocess.CalledProcessError as e:
             error_message = e.stderr.decode("utf-8") if e.stderr else str(e)
             logger.error(f"FFmpeg 提取音频失败: {error_message}")
             return None
        finally:
             if os.path.exists(video_path):
                 os.remove(video_path)


if __name__ == '__main__':
    real_url = 'https://www.kuaishou.com/short-video/3xwyjn4ipdhss5c?authorId=3xasa85baf6ipp4&streamSource=find&area=homexxbrilliant'

    dl = KuaishouParser(real_url)

    print("-" * 30)
    print(f"作者信息：{dl.get_author_info()}")
    print(f"标题内容：{dl.get_title_content()[:30]}...")  # 仅打印前30字
    print(f"封面图片：{dl.get_cover_photo_url()}")
    print(f"视频链接：{dl.get_real_video_url()}")
    print(f"音频链接：{dl.get_audio_url()}")
    print("-" * 30)