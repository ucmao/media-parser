import re
import requests
import random
from urllib.parse import urljoin, urlparse, parse_qs, urlencode
from configs.logging_config import get_logger
from configs.general_constants import USER_AGENT_PC, DOMAIN_TO_NAME

logger = get_logger(__name__)


class WebFetcher:
    headers = {
        "content-type": "application/json; charset=UTF-8",
        "User-Agent": random.choice(USER_AGENT_PC)
    }

    @staticmethod
    def fetch_redirect_url(url, max_redirects=5):
        if not isinstance(url, str) or not url.strip() or max_redirects < 1:
            return None
        # 知乎公开 API 可直接通过内容 ID 解析，访问网页常触发 403 风控。
        # 绿洲分享页会对通用桌面请求头返回 500，由解析器使用移动端请求头抓取。
        # 微博博文可通过 API 直接根据 ID 解析，直接访问网页端常触发访客系统重定向。
        domain = UrlParser.get_domain(url)
        if domain not in {"t.cn", "b23.tv", "xhslink.cn", "xhslink.com", "hy.fan"}:
            if UrlParser.get_platform(url) in {"知乎", "绿洲", "新片场", "夸克AI", "通义千问", "微博", "小云雀AI", "哔哩哔哩"}:
                return UrlParser.extract_video_address(url)
        try:
            current_url = url
            for _ in range(max_redirects):
                # 发送请求，禁止重定向
                resp = requests.get(current_url, headers=WebFetcher.headers, allow_redirects=False, timeout=5)
                resp.raise_for_status()
                redirect_url = resp.headers.get("location")
                if redirect_url:
                    redirect_url = urljoin(current_url, redirect_url)
                    # 如果重定向到了登录页、404拦截页、验证码校验页或错误页，不要更新 url，直接中断以保留原始有效 URL
                    if any(path in redirect_url for path in ["/login", "/404", "/captcha", "/verify", "/error", "/visitor"]):
                        break
                    current_url = redirect_url
                    if UrlParser.get_platform(current_url):
                        break
                else:
                    break

            else:
                return None

            if not UrlParser.get_platform(current_url):
                return None

            return UrlParser.extract_video_address(current_url)
        except requests.RequestException as e:
            logger.error(f"Failed to get the page: {e}")
            return None
        except Exception as e:
            logger.error(f"An error occurred: {e}")
            return None


class UrlParser:
    @staticmethod
    def convert_to_https(url):
        if not url:
            return None
        if url.startswith('http://'):
            return 'https://' + url[7:]
        return url

    @staticmethod
    def get_url(text):
        if not isinstance(text, str):
            return None
        url_pattern = re.compile(r'\bhttps?:\/\/(?:www\.|[-a-zA-Z0-9.@:%_+~#=]{1,256}\.[a-zA-Z0-9()]{1,6})\b(?:[-a-zA-Z0-9()@:%_+.~#?&//=]*)?')
        match = url_pattern.search(text)
        if match:
            return match.group()
        else:
            return None

    @staticmethod
    def get_domain(url):
        if not isinstance(url, str):
            return ''
        parsed_url = urlparse(url)
        return (parsed_url.hostname or '').lower().rstrip('.')

    @staticmethod
    def get_platform(url):
        """识别链接所属平台，并兼容快手生成的随机移动端子域名。"""
        domain = UrlParser.get_domain(url)
        path = urlparse(url).path
        if domain in {"www.iesdouyin.com", "iesdouyin.com"} and path.startswith("/xg/"):
            return "西瓜视频"
        platform = DOMAIN_TO_NAME.get(domain)
        if platform:
            return platform

        if domain.endswith('.m.chenzhongtech.com'):
            return '快手'

        return None

    @staticmethod
    def extract_video_address(url):
        if not isinstance(url, str) or not url:
            return None
        parsed_url = urlparse(url)
        domain = UrlParser.get_domain(url)
        platform = UrlParser.get_platform(url)
        address = f"{parsed_url.scheme}://{domain}{parsed_url.path}"
        if address.endswith('/'):
            address = address[:-1]
        if platform == '好看视频':
            query_params = parse_qs(parsed_url.query)
            vid = query_params.get('vid', [None])[0]  # 使用 get 方法避免 KeyError
            if vid:
                address = f"{address}?vid={vid}"
        elif platform == "微视":
            query_params = parse_qs(parsed_url.query)
            vid = query_params.get('id', [None])[0]  # 使用 get 方法避免 KeyError
            if vid:
                address = f"{address}?id={vid}"
        elif platform == "小红书":
            query_params = parse_qs(parsed_url.query)
            xsec_token = query_params.get('xsec_token', [None])[0]  # 使用 get 方法避免 KeyError
            if xsec_token:
                address = f"{address}?xsec_token={xsec_token}"
        elif platform == "快手":
            address = address.replace('http://', 'https://')
        elif platform == "抖音":
            query_params = parse_qs(parsed_url.query)
            modal_id = query_params.get('modal_id', [None])[0]
            if modal_id:
                address = f"{address}?modal_id={modal_id}"
        elif platform == "全民K歌":
            query_params = parse_qs(parsed_url.query)
            s = query_params.get('s', [None])[0]
            if s:
                address = f"{address}?s={s}"
        elif platform == "最右":
            query_params = parse_qs(parsed_url.query)
            pid = query_params.get('pid', [None])[0]
            if pid:
                address = f"{address}?pid={pid}"
        elif platform == "豆包":
            query_params = parse_qs(parsed_url.query)
            preserved_params = []
            for key in ('share_id', 'source_type', 'video_id', 'share_scene'):
                value = query_params.get(key, [None])[0]
                if value is not None:
                    preserved_params.append((key, value))
            if preserved_params:
                address = f"{address}?{urlencode(preserved_params)}"
        elif platform == "即梦AI":
            query_params = parse_qs(parsed_url.query)
            preserved_params = []
            for key in ('item_id', 'id'):
                value = query_params.get(key, [None])[0]
                if value is not None:
                    preserved_params.append((key, value))
            if preserved_params:
                address = f"{address}?{urlencode(preserved_params)}"
        elif platform == "夸克AI":
            query_params = parse_qs(parsed_url.query)
            preserved_params = []
            for key in ("shareId", "share_id", "authorId", "author_id", "channel_from", "biz_id", "qwcontainer", "url", "env"):
                value = query_params.get(key, [None])[0]
                if value is not None:
                    preserved_params.append((key, value))
            if preserved_params:
                address = f"{address}?{urlencode(preserved_params)}"
        elif platform == "可灵AI":
            query_params = parse_qs(parsed_url.query)
            preserved_params = []
            for key in ("creative_id", "work_id", "creative_type"):
                value = query_params.get(key, [None])[0]
                if value is not None:
                    preserved_params.append((key, value))
            if preserved_params:
                address = f"{address}?{urlencode(preserved_params)}"
        elif platform == "微博":
            query_params = parse_qs(parsed_url.query)
            if value := query_params.get("fid", [None])[0]:
                address = f"{address}?{urlencode({'fid': value})}"
        elif platform == "Soul":
            fragment = parsed_url.fragment
            if "?" in fragment:
                fragment_path, fragment_query = fragment.split("?", 1)
                query_params = parse_qs(fragment_query)
                preserved_params = []
                for key in ("postIdEcpt", "sign", "signVersion"):
                    value = query_params.get(key, [None])[0]
                    if value is not None:
                        preserved_params.append((key, value))
                if preserved_params:
                    address = f"{address}#{fragment_path}?{urlencode(preserved_params)}"
        elif platform == "汽水音乐":
            query_params = parse_qs(parsed_url.query)
            preserved_params = []
            for key in ("track_id", "ugc_video_id"):
                value = query_params.get(key, [None])[0]
                if value is not None:
                    preserved_params.append((key, value))
            if preserved_params:
                address = f"{address}?{urlencode(preserved_params)}"
        elif platform == "腾讯频道":
            query_params = parse_qs(parsed_url.query)
            if value := query_params.get("b", [None])[0]:
                address = f"{address}?{urlencode({'b': value})}"
        elif platform == "剪映":
            query_params = parse_qs(parsed_url.query)
            preserved_params = []
            for key in ("template_id", "item_type"):
                value = query_params.get(key, [None])[0]
                if value is not None:
                    preserved_params.append((key, value))
            if preserved_params:
                address = f"{address}?{urlencode(preserved_params)}"
        elif platform == "视频号":
            query_params = parse_qs(parsed_url.query)
            short_uri = query_params.get('id', [None])[0]
            if short_uri:
                address = f"{address}?{urlencode({'id': short_uri})}"
        elif platform == "绿洲":
            query_params = parse_qs(parsed_url.query)
            if value := query_params.get("sid", [None])[0]:
                address = f"{address}?{urlencode({'sid': value})}"
        elif platform == "通义千问":
            query_params = parse_qs(parsed_url.query)
            preserved_params = []
            for key in ("shareId", "authorId", "enter_from", "fp_from", "channel_from", "image_index"):
                value = query_params.get(key, [None])[0]
                if value is not None:
                    preserved_params.append((key, value))
            if preserved_params:
                address = f"{address}?{urlencode(preserved_params)}"
        elif platform == "闲鱼":
            query_params = parse_qs(parsed_url.query)
            preserved_params = []
            for key in ("tk", "id", "price", "shareurl", "short_name", "sp_tk"):
                value = query_params.get(key, [None])[0]
                if value is not None:
                    preserved_params.append((key, value))
            if preserved_params:
                address = f"{address}?{urlencode(preserved_params)}"
        elif platform == "小云雀AI":
            if parsed_url.query:
                address = f"{address}?{parsed_url.query}"
        return address

    @staticmethod
    def get_video_id(url):
        try:
            parsed_url = urlparse(url)
            query_params = parse_qs(parsed_url.query)
            # 尝试从查询参数中获取视频ID
            params_share_id = query_params.get('shareId', [None])[0]
            if params_share_id:
                return params_share_id
            params_vid = query_params.get('vid', [None])[0]
            if params_vid:
                return params_vid
            params_id = query_params.get('id', [None])[0]
            if params_id:
                return params_id
            params_modal_id = query_params.get('modal_id', [None])[0]
            if params_modal_id:
                return params_modal_id
            params_v = query_params.get('v', [None])[0]
            if params_v:
                return params_v
            params_s = query_params.get('s', [None])[0]
            if params_s:
                return params_s
            params_pid = query_params.get('pid', [None])[0]
            if params_pid:
                return params_pid
            params_video_id = query_params.get('video_id', [None])[0]
            if params_video_id:
                return params_video_id
            params_creative_id = query_params.get('creative_id', [None])[0]
            if params_creative_id:
                return params_creative_id
            params_work_id = query_params.get('work_id', [None])[0]
            if params_work_id:
                return params_work_id
            fragment_query = parse_qs(parsed_url.fragment.split('?', 1)[1]) if '?' in parsed_url.fragment else {}
            params_post_id = fragment_query.get('postIdEcpt', [None])[0]
            if params_post_id:
                return params_post_id
            params_track_id = query_params.get('track_id', [None])[0]
            if params_track_id:
                return params_track_id
            params_ugc_video_id = query_params.get('ugc_video_id', [None])[0]
            if params_ugc_video_id:
                return params_ugc_video_id
            params_template_id = query_params.get('template_id', [None])[0]
            if params_template_id:
                return params_template_id
            # 尝试从URL路径中获取视频ID
            path_segments = parsed_url.path.strip('/').split('/')
            if path_segments:
                video_id = path_segments[-1]
                if video_id.endswith('.html'):
                    video_id = video_id[:-5]
                return video_id
            logger.warning(f'Unable to retrieve video ID from URL: {url}')
            return None
        except Exception as e:
            logger.error(f"An error occurred while extracting video ID: {e}")
            return None

