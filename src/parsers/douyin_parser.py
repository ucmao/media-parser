import copy
import hashlib
import json
import os
import random
import re
import threading
import time
import urllib.parse
import urllib3
import warnings

from bs4 import BeautifulSoup

from configs.logging_config import get_logger
from src.parser_factory import register_parser
from src.parsers.base_parser import BaseParser
from src.utils.cookie_manager import get_platform_cookie, cookies_suppressed
from utils.signer.bytedance.bogus_signer import BogusSigner
from utils.web_fetcher import UrlParser

logger = get_logger(__name__)

warnings.filterwarnings("ignore", category=urllib3.exceptions.InsecureRequestWarning)

# 兜底 ttwid：动态申请失败时使用
FALLBACK_TTWID = ('1%7CvDWCB8tYdKPbdOlqwNTkDPhizBaV9i91KjYLKJbqurg%7C1723536402'
                  '%7C314e63000decb79f46b8ff255560b29f4d8c57352dad465b41977db4830b4c7e')

# 抖音 /aweme/v1/web/ 系列接口位于 Argus 风控网关之后，会概率性返回
# 403 "Blocked by ArgusSecurityPlugin Uifid Not Found"。实测同一个字节完全一致的请求
# （相同 ttwid / msToken / a_bogus / Cookie / Session）也会在 200 与 403 之间随机跳变，
# 历史样本中的单次通过率随时段波动；重试改善最终成功率，但不能证明已修复风控原因。
# 这些观测也不能排除正确的服务端身份材料与签名的作用。
def _get_env_int(key, default):
    val = os.getenv(key, "").strip()
    return int(val) if val.isdigit() else default


def _get_env_float(key, default):
    val = os.getenv(key, "").strip()
    try:
        return float(val) if val else default
    except ValueError:
        return default


API_MAX_ATTEMPTS = max(1, _get_env_int("DOUYIN_API_MAX_ATTEMPTS", 2))
# 请求过密会额外触发速率型拦截，重试之间使用紧凑的指数退避 + 随机抖动（单次上限 0.8s，避免图文重试总耗时过长）。
RETRY_BASE_DELAY = _get_env_float("DOUYIN_RETRY_BASE_DELAY", 0.2)
RETRY_MAX_DELAY = _get_env_float("DOUYIN_RETRY_MAX_DELAY", 0.8)

# 刚发布的作品在审核通过前，接口会返回 status_self_see（仅自己可见），几分钟后即可正常解析。
# 作品发布不超过该时长（秒）且命中 status_self_see 时，按"审核中"返回可重试的错误码，而不是"已删除/私密"。
UNDER_REVIEW_MAX_AGE = _get_env_int("DOUYIN_UNDER_REVIEW_MAX_AGE", 7200)
UNDER_REVIEW_MESSAGE = "该作品刚发布，正在抖音审核中，暂时无法查看，请几分钟后重试"

# 移动端 Feed 核心接口配置：免 ArgusSecurityPlugin 门禁的主路径（常规视频测试中 0 次 403）
ENABLE_MOBILE_FEED = (os.getenv("DOUYIN_ENABLE_MOBILE_FEED", "1") or "1").strip().lower() in ("1", "true", "yes", "on")
MOBILE_FEED_ENDPOINTS = [
    "https://api5-normal-c-hl.amemv.com/aweme/v1/feed/",
    "https://aweme.snssdk.com/aweme/v1/feed/",
]
MOBILE_FEED_USER_AGENT = (
    "com.ss.android.ugc.aweme/290101 (Linux; U; Android 10; zh_CN; Pixel 4; "
    "Build/QQ3A.200805.001; Cronet/TTNetVersion:5f9037be 2023-01-13 QuicVersion:4668bb42 2022-11-21)"
)


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
        self.cookie = get_platform_cookie("douyin")
        self.ttwid = FALLBACK_TTWID
        self.webid = '7307457174287205926'
        self.is_music = bool(self.real_url and ('/music/' in self.real_url or '/share/music/' in self.real_url))
        self.is_collection = bool(self.real_url and ('/collection/' in self.real_url or '/mix/' in self.real_url or '/mix/detail/' in self.real_url))
        self.is_lvdetail = bool(self.real_url and ('/lvdetail/' in self.real_url or 'ep_id=' in self.real_url or 'episode_id=' in self.real_url or 'album_id=' in self.real_url or '/playlet/' in self.real_url or 'playlet_id=' in self.real_url or 'series_id=' in self.real_url))
        self.is_note = bool(self.real_url and ('/note/' in self.real_url or '/slides/' in self.real_url or '/share/slides/' in self.real_url or '/share/note/' in self.real_url))
        self.aweme_id = UrlParser.get_video_id(self.real_url)
        parsed = urllib.parse.urlparse(self.real_url) if self.real_url else None
        q = urllib.parse.parse_qs(parsed.query) if parsed else {}
        self.ep_id = q.get('ep_id', [None])[0] or q.get('episode_id', [None])[0]
        self.album_id = q.get('album_id', [None])[0] or q.get('playlet_id', [None])[0] or q.get('series_id', [None])[0]
        if not self.album_id and self.real_url:
            m_playlet = re.search(r'/playlet/detail/(\d+)', self.real_url)
            if m_playlet:
                self.album_id = m_playlet.group(1)
        if self.is_lvdetail and not self.ep_id and self.aweme_id and not self.album_id:
            self.ep_id = self.aweme_id
        # 注意：不在此处预取网页 HTML。抖音 PC 端 /video/{id} 页面现已是纯客户端渲染的空壳
        # （固定 72KB，不含 __UNIVERSAL_DATA_FOR_REHYDRATION__ / aweme_detail / 标题），
        # 预取既拿不到数据，又多消耗一次请求配额并增加整体延迟。改为仅在 API 全部失败时惰性拉取。
        self.data = self.fetch_html_data()

    def fetch_html_content(self):
        """
        拉取可能含 SSR 数据的页面。

        注意：PC 端 /video/{id} 现已是纯 CSR 空壳（无 _ROUTER_DATA / aweme_detail），
        分享页 iesdouyin.com/share/video/{id} 仍嵌入 videoInfoRes，必须优先使用。
        """
        target_url = self.real_url
        use_mobile_ua = False
        if self.is_lvdetail and getattr(self, 'ep_id', None):
            target_url = f"https://www.douyin.com/lvdetail/{self.ep_id}"
        elif self.is_lvdetail and getattr(self, 'album_id', None):
            target_url = f"https://www.douyin.com/share/playlet/detail/{self.album_id}"
        elif self.is_collection and getattr(self, 'aweme_id', None):
            target_url = f"https://www.douyin.com/collection/{self.aweme_id}"
        elif getattr(self, 'aweme_id', None) and not self.is_music:
            # 勿改写为 www.douyin.com/video（空壳）；统一走分享页拿 SSR
            target_url = f"https://www.iesdouyin.com/share/video/{self.aweme_id}"
            use_mobile_ua = True

        headers = copy.deepcopy(self.headers)
        ttwid = self._get_ttwid()
        headers['Cookie'] = self._get_cookie_header(ttwid)
        uifid = self._get_uifid()
        if uifid:
            headers['uifid'] = uifid
        if use_mobile_ua:
            # 与站点旧 VideoService 一致：分享页对移动 UA 更友好
            headers['User-Agent'] = (
                'Mozilla/5.0 (Linux; Android 8.0.0; SM-G955U Build/R16NW) '
                'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Mobile Safari/537.36'
            )
            headers['Referer'] = 'https://www.douyin.com/?is_from_mobile_home=1&recommend=1'
        try:
            resp = self.session.get(target_url, headers=headers, timeout=5, verify=False)
            if resp.status_code == 200:
                self.html_content = resp.text
            else:
                self.html_content = ""
        except Exception as e:
            logger.warning(f"Failed to fetch HTML content for {target_url}: {e}")
            self.html_content = ""

    _TTWID_CACHE = None
    _TTWID_LOCK = threading.Lock()

    def _get_cookie_header(self, ttwid=None):
        """
        生成完整 Cookie 字符串：用户自配 Cookie + ttwid + Session 中已有的抖音 Cookie。

        手工设置 Cookie 头会阻止 requests 自动合并 Session Cookie，因此这里显式把
        Session 里已取得的 __ac_nonce 等补回去，避免丢掉服务端刚下发的会话状态。
        """
        parts = []
        seen = set()
        if self.cookie:
            for item in self.cookie.split(';'):
                if '=' not in item:
                    continue
                k, v = item.split('=', 1)
                k = k.strip().strip("'\"")
                v = v.strip().strip("'\"")
                if k in ('__ac_nonce', '__ac_signature'):
                    continue
                # 过滤触发 SecSDK 强校验的动态票据与防护指纹，防止 Argus 网关因缺少客户端动态签名报 403 Signature Not Found
                if k.startswith(('bd_ticket_guard', '__security', 'fpk')) or k in ('_bd_ticket_crypt_cookie', 'x_tt_token', 'sdk_source_info'):
                    continue
                # verify_ 开头的临时验证码通行证仅在放映厅 lvdetail 中使用，常规作品携带过期验证码会导致 403
                if k == 's_v_web_id' and v.startswith('verify_') and not getattr(self, 'is_lvdetail', False):
                    continue
                if k not in seen:
                    parts.append(f"{k}={v}")
                    seen.add(k)
        if ttwid and 'ttwid' not in seen:
            parts.append(f"ttwid={ttwid}")
            seen.add('ttwid')
        for name in ('__ac_nonce', '__ac_signature', 's_v_web_id', 'msToken', 'UIFID'):
            if name in seen:
                continue
            # 同名 Cookie 可来自不同域，不能直接 .get(name)（可能冲突或串域）。
            value = next((c.value for c in self.session.cookies
                          if c.name == name and not c.is_expired()
                          and c.domain in ('', 'douyin.com', '.douyin.com', 'www.douyin.com')
                          and c.path == '/'), None)
            if value:
                parts.append(f"{name}={value}")
                seen.add(name)
        return '; '.join(parts)

    def _get_uifid(self):
        """
        获取 UIFID 字段，用于计算 x-secsdk-web-signature 及作为独立 HTTP 请求头 (uifid: <value>) 发送给 Argus 网关。
        支持场景：
        1. 独立环境变量 DOUYIN_UIFID / DY_UIFID
        2. 从 Cookie 字符串中解析 UIFID=...
        3. 用户直接将 256 位 uifid 字符串传入 DOUYIN_COOKIE (无 = 号，长度 >= 32)
        4. 从 session.cookies 中提取
        """
        if cookies_suppressed():
            return ""
        # 1. 优先读取独立环境变量
        for env_key in ("DOUYIN_UIFID", "DY_UIFID"):
            env_val = os.getenv(env_key, "").strip().strip("'\"")
            if env_val:
                return env_val

        # 2. 从 self.cookie 中解析
        if self.cookie:
            raw_cookie = self.cookie.strip().strip("'\"")
            # 若用户直接把 uifid 填入 DOUYIN_COOKIE（纯 hash/token 字符串）
            if '=' not in raw_cookie and len(raw_cookie) >= 32:
                return raw_cookie

            for item in self.cookie.split(';'):
                if '=' not in item:
                    continue
                k, v = item.split('=', 1)
                if k.strip().strip("'\"").upper() == 'UIFID' and v.strip().strip("'\""):
                    return v.strip().strip("'\"")

        # 3. 从 session.cookies 提取
        value = next((c.value for c in self.session.cookies
                      if c.name.upper() == 'UIFID' and not c.is_expired()
                      and c.domain in ('', 'douyin.com', '.douyin.com', 'www.douyin.com')), None)
        return value or ""

    @staticmethod
    def _sign_secsdk(url: str, uifid: str, ts: int | None = None) -> str:
        """
        为抖音核心 Web 接口规范化 query 并计算 x-secsdk-web-signature。
        击穿 IDC 机房 IP 下 ArgusSecurityPlugin 报 Signature Not Found (403) 门禁。
        明文结构：{uifid}_{timestamp}_{CONST}_{canonical_query}
        """
        if not uifid:
            return url
        if ts is None:
            ts = int(time.time())

        base, _, query = url.partition('?')
        safe_chars = "!*'()"
        parts = []
        for pair in query.split('&'):
            if not pair:
                continue
            if '=' in pair:
                k, v = pair.split('=', 1)
            else:
                k, v = pair, ''
            k = urllib.parse.unquote_plus(k, encoding='utf-8', errors='replace')
            v = urllib.parse.unquote_plus(v, encoding='utf-8', errors='replace')
            encoded_val = urllib.parse.quote(str(v), safe=safe_chars, encoding='utf-8')
            parts.append(f"{k}={encoded_val}")
        canon = '&'.join(parts)

        names = [p.split('=', 1)[0] for p in canon.split('&') if p]
        if 'uifid' not in names:
            encoded_uifid = urllib.parse.quote(str(uifid), safe=safe_chars, encoding='utf-8')
            canon = f"{canon}&uifid={encoded_uifid}" if canon else f"uifid={encoded_uifid}"

        signed_query = f"{canon}&timestamp={ts}"
        websign_const = "A96D855A08C0A9707F8BEF0D9A527E4E"
        plain = f"{uifid}_{ts}_{websign_const}_{signed_query}"
        signature = hashlib.md5(plain.encode('utf-8')).hexdigest()
        return f"{base}?{signed_query}&x-secsdk-web-signature={signature}"

    def _get_ttwid(self):
        """
        动态获取 ttwid，使用带锁的类级缓存以减少重复请求。

        注意：不要在接口返回 403 时清空该缓存。实测更换 ttwid（乃至整个 Session）
        对 Argus 概率性拦截没有可测量的影响，churn 只会额外浪费一次请求配额。
        """
        if DouyinParser._TTWID_CACHE:
            return DouyinParser._TTWID_CACHE

        with DouyinParser._TTWID_LOCK:
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

    def _is_under_review(self, filter_reason):
        """作品 ID 高 32 位是发布时间戳；刚发布就返回 status_self_see 的作品大概率仍在审核。"""
        if filter_reason != 'status_self_see':
            return False
        try:
            published = int(self.aweme_id) >> 32
        except (TypeError, ValueError):
            return False
        age = time.time() - published
        return -300 <= age <= UNDER_REVIEW_MAX_AGE

    def _is_terminal_failure(self, data):
        """
        判断接口响应是否为明确的不可重试终端状态（如作品已被删除、仅自己可见、朋友日常权限限制等）。
        当命中终态时，无需经历 8 次指数退避重试，可直接短路退出以节省系统资源与等待耗时。
        """
        if not isinstance(data, dict):
            return False

        # 1. 含有明确的 filter_detail 过滤原因（如 status_self_see, status_deleted, status_part_see 等）
        filter_detail = data.get('filter_detail')
        if isinstance(filter_detail, dict):
            if filter_detail.get('filter_reason') or filter_detail.get('detail_msg') or filter_detail.get('notice'):
                return True

        # 2. status_code 为 0 且明确带有 filter_detail
        if data.get('status_code') == 0 and 'filter_detail' in data and data.get('filter_detail') is not None:
            return True

        # 3. status_msg 或 filter_msg 含有明确的不可恢复业务语义
        status_msg = str(data.get('status_msg') or '')
        terminal_keywords = ('已删除', '不存在', '私密', '权限', '无法查看', '不见了')
        if any(kw in status_msg for kw in terminal_keywords):
            return True

        filter_msg = str((data.get('filter_detail') or {}).get('detail_msg') or '')
        if any(kw in filter_msg for kw in terminal_keywords):
            return True

        return False

    def _request_api_with_retry(self, base_api, referer, validate, max_attempts=None):
        """
        带指数退避 + 抖动的抖音 Web 接口请求，用于抵御 Argus 网关的概率性 403。

        base_api: 不含 msToken 与 a_bogus 的完整接口地址（已含 `?` 及其余查询参数）。
        validate: 接收解析后的 JSON，返回 True 表示数据可用。
        每次重试都会重新生成 msToken 与 a_bogus 签名。

        注意不要往 base_api 里补"浏览器指纹"查询参数：实测整套指纹参数对通过率没有可测量
        提升（n=32 时 59% vs 基线 66%），而其中的 webid 会让接口 100% 失败（0/16）。
        """
        attempts = API_MAX_ATTEMPTS if max_attempts is None else max_attempts
        last_status = None
        for attempt in range(attempts):
            ttwid = self._get_ttwid() or FALLBACK_TTWID
            headers = copy.deepcopy(self.headers)
            headers['Referer'] = referer
            headers['Cookie'] = self._get_cookie_header(ttwid)
            uifid = self._get_uifid()
            if uifid:
                headers['uifid'] = uifid

            api_url = f"{base_api}&msToken={self.signer.get_ms_token()}"
            try:
                api_url = f"{api_url}&a_bogus={self.signer.get_abogus(api_url, self.signer.user_agent)}"
            except Exception as e:
                logger.warning(f"生成 a_bogus 签名异常: {e}")
                return None

            if uifid:
                api_url = self._sign_secsdk(api_url, uifid)

            try:
                response = self.session.get(api_url, headers=headers, verify=False, timeout=8)
                last_status = response.status_code
                if last_status == 200 and response.text:
                    data = response.json()
                    if validate(data):
                        return data
                    if self._is_terminal_failure(data):
                        filter_msg = ((data.get('filter_detail') or {}).get('detail_msg')
                                      or (data.get('filter_detail') or {}).get('notice')
                                      or data.get('status_msg')
                                      or "作品权限受限或已被删除")
                        filter_reason = (data.get('filter_detail') or {}).get('filter_reason') or "terminal_status"
                        logger.info(f"抖音接口返回明确的不可重试终端状态 ({filter_reason}: {filter_msg})，立即终止重试: {base_api.split('?')[0]}")
                        detail = dict(data.get('filter_detail') or {"filter_reason": filter_reason, "detail_msg": filter_msg})
                        if self._is_under_review(filter_reason):
                            detail.update(error_code='MEDIA_UNDER_REVIEW', detail_msg=UNDER_REVIEW_MESSAGE)
                        self._terminal_filter_detail = detail
                        self.terminal_error = self._terminal_filter_detail
                        return None
                elif last_status != 200:
                    abort_data = response.headers.get("X-Whale-Throughput-Abort-Data")
                    abort_info = f", abort={abort_data}" if abort_data else ""
                    logger.warning(
                        f"抖音 Web 接口响应异常 (attempt {attempt + 1}/{attempts}, status={last_status}{abort_info}): "
                        f"{response.text[:200]}"
                    )
            except Exception as e:
                logger.debug(f"请求抖音接口异常 (第 {attempt + 1}/{attempts} 次): {e}")

            if attempt < attempts - 1:
                # 指数退避 + 抖动（抖动按退避时长等比缩放，便于测试中整体关闭）
                delay = min(RETRY_BASE_DELAY * (2 ** attempt), RETRY_MAX_DELAY)
                if delay > 0:
                    time.sleep(delay * random.uniform(1.0, 1.5))

        logger.warning(f"抖音接口重试 {attempts} 次仍未取得有效数据 "
                       f"(last status={last_status}): {base_api.split('?')[0]}")
        # 全部重试耗尽后才让下一次解析换一个 ttwid，避免正常路径上的无谓 churn
        DouyinParser._TTWID_CACHE = None
        return None

    def _request_mobile_feed(self, aweme_id):
        """
        通过抖音移动端 Feed 核心接口获取作品详情。

        该接口不经过 PC Web 端的 ArgusSecurityPlugin 门禁，无需 uifid、
        a_bogus 签名与 Cookie，响应极快且对常规视频保持高可用（测试中 0 次 403）。
        如果主节点异常、超时或未命中目标作品，自动尝试备用 snssdk 节点。
        """
        if not aweme_id or not ENABLE_MOBILE_FEED:
            return None

        headers = {
            'User-Agent': MOBILE_FEED_USER_AGENT,
            'Accept': 'application/json, text/plain, */*',
        }
        params = {
            'aweme_id': str(aweme_id),
            'aid': '1128',
        }

        for endpoint in MOBILE_FEED_ENDPOINTS:
            try:
                resp = self.session.get(endpoint, params=params, headers=headers, timeout=4, verify=False)
                if resp.status_code == 200 and resp.text:
                    data = resp.json()
                    aweme_list = data.get('aweme_list') or []
                    matched = next(
                        (item for item in aweme_list
                         if str(item.get('aweme_id') or item.get('id') or '') == str(aweme_id)),
                        None,
                    )
                    if matched:
                        logger.info(f"Successfully fetched Douyin video detail via mobile feed API: {aweme_id}")
                        return {"aweme_detail": matched}
                    # 未命中则继续试备用节点（不同节点对同一 aweme_id 的收录不一致）
            except Exception as e:
                logger.debug(f"Mobile feed API failed on {endpoint}: {e}")
                continue

        return None

    def _try_share_ssr_detail(self):
        """
        从 iesdouyin 分享页提取 aweme_detail（免 a_bogus，避开 Argus 403）。
        在 Web detail API 重试之前调用，避免白白耗尽 8 次退避。
        """
        if not self.aweme_id or self.is_music or self.is_collection or self.is_lvdetail:
            return None
        if not self.html_content:
            self.fetch_html_content()
        if not self.html_content:
            return None
        ssr_data = self._parse_ssr_data(self.html_content)
        if ssr_data and ssr_data.get('aweme_detail'):
            logger.info(f"Successfully extracted Douyin detail via share-page SSR: {self.aweme_id}")
            return ssr_data
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
    def _find_lvideo_detail(data, target_id=None):
        """
        递归查找嵌套字典或列表中的放映厅 / 长视频 (lvideo / episode / album) 节点。
        """
        if not data:
            return None

        if isinstance(data, dict):
            # 1. 含有明确的 lvideo_detail 节点
            if "lvideo_detail" in data and isinstance(data["lvideo_detail"], dict):
                return data["lvideo_detail"]

            # 2. 含有 episode_info 或 album_info 或 episode_list
            if ("episode_info" in data and isinstance(data["episode_info"], dict)) or \
               ("album_info" in data and isinstance(data["album_info"], dict)) or \
               ("episode_list" in data and isinstance(data["episode_list"], list)):
                return data

            # 3. 自身即为一个 episode / album 对象
            if ("video" in data or "play_addr" in data) and ("episode_id" in data or "episode_name" in data or "album_id" in data):
                return {"episode_info": data}

            for _, v in data.items():
                if isinstance(v, (dict, list)):
                    found = DouyinParser._find_lvideo_detail(v, target_id)
                    if found:
                        return found

        elif isinstance(data, list):
            for item in data:
                if isinstance(item, (dict, list)):
                    found = DouyinParser._find_lvideo_detail(item, target_id)
                    if found:
                        return found

        return None

    @staticmethod
    def _extract_json_object_after(marker, text):
        """
        从 marker 后截取完整 JSON 对象（按花括号配对），避免非贪婪正则在嵌套 JSON 上提前截断。
        用于 window._ROUTER_DATA = {...} 等分享页内嵌数据。
        """
        if not text or not marker:
            return None
        idx = text.find(marker)
        if idx < 0:
            return None
        start = text.find('{', idx + len(marker))
        if start < 0:
            return None
        depth = 0
        in_str = False
        escape = False
        for i in range(start, len(text)):
            ch = text[i]
            if in_str:
                if escape:
                    escape = False
                elif ch == '\\':
                    escape = True
                elif ch == '"':
                    in_str = False
                continue
            if ch == '"':
                in_str = True
            elif ch == '{':
                depth += 1
            elif ch == '}':
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(text[start:i + 1])
                    except json.JSONDecodeError:
                        return None
        return None

    @staticmethod
    def _find_aweme_detail(data, target_id=None):
        """
        递归查找嵌套字典或列表中的 aweme_detail / itemStruct / videoInfoRes.item_list 节点。
        """
        if not data:
            return None

        if isinstance(data, dict):
            # 0. 分享页经典结构：videoInfoRes.item_list[0]
            video_info_res = data.get('videoInfoRes')
            if isinstance(video_info_res, dict):
                item_list = video_info_res.get('item_list') or video_info_res.get('itemList') or []
                if isinstance(item_list, list):
                    for item in item_list:
                        if not isinstance(item, dict):
                            continue
                        if target_id is None or str(item.get('aweme_id') or item.get('id') or '') == str(target_id):
                            return item
                    if item_list and isinstance(item_list[0], dict) and target_id is None:
                        return item_list[0]

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
                if self.is_lvdetail:
                    lvideo_info = self._find_lvideo_detail(raw_json, self.aweme_id)
                    if lvideo_info:
                        logger.info("Successfully extracted Douyin lvideo detail from __UNIVERSAL_DATA_FOR_REHYDRATION__")
                        return lvideo_info
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
                if self.is_lvdetail:
                    lvideo_info = self._find_lvideo_detail(raw_json, self.aweme_id)
                    if lvideo_info:
                        logger.info("Successfully extracted Douyin lvideo detail from RENDER_DATA")
                        return lvideo_info
                detail = self._find_aweme_detail(raw_json, self.aweme_id)
                if detail:
                    logger.info("Successfully extracted Douyin detail from RENDER_DATA")
                    return {"aweme_detail": detail}
            except Exception as e:
                logger.debug(f"Failed to parse RENDER_DATA: {e}")

        # 策略 3: 正则 / 花括号配对提取 _ROUTER_DATA / _SSR_DATA / __INIT_PROPS__
        # 分享页 _ROUTER_DATA 为深层嵌套 JSON，非贪婪 \{.*?\} 会在首个 } 处截断，必须配对提取
        for marker in ('_ROUTER_DATA', '_SSR_DATA', '__INIT_PROPS__'):
            raw_json = self._extract_json_object_after(marker, html_content)
            if not raw_json:
                continue
            try:
                if self.is_music:
                    music_info = self._find_music_info(raw_json, self.aweme_id)
                    if music_info:
                        logger.info(f"Successfully extracted Douyin music detail from {marker}")
                        return {"music_info": music_info}
                if self.is_lvdetail:
                    lvideo_info = self._find_lvideo_detail(raw_json, self.aweme_id)
                    if lvideo_info:
                        logger.info(f"Successfully extracted Douyin lvideo detail from {marker}")
                        return lvideo_info
                detail = self._find_aweme_detail(raw_json, self.aweme_id)
                if detail:
                    logger.info(f"Successfully extracted Douyin detail from {marker}")
                    return {"aweme_detail": detail}
            except Exception as e:
                logger.debug(f"Failed to parse {marker}: {e}")

        # 策略 4: self.__pace_f.push (React Server Components / Next.js 流式 SSR 数据)
        pace_matches = re.findall(r'self\.__pace_f\.push\(\[1,\s*\"(.*?)\"\]\)', html_content)
        for m in pace_matches:
            try:
                raw_decoded = json.loads('\"' + m + '\"')
                if 'defaultAwemeInfo' in raw_decoded or 'lvideoBrief' in raw_decoded:
                    colon_idx = raw_decoded.find(':')
                    if colon_idx != -1:
                        json_part = raw_decoded[colon_idx + 1:]
                        json_part = re.sub(r':\s*\"\$undefined\"', ': null', json_part)
                        json_part = re.sub(r':\s*\"\$L[0-9a-zA-Z_]+\"', ': null', json_part)
                        parsed_arr = json.loads(json_part)
                        if isinstance(parsed_arr, list) and len(parsed_arr) >= 4 and isinstance(parsed_arr[3], dict):
                            dict_obj = parsed_arr[3]
                            aweme_info = dict_obj.get('defaultAwemeInfo')
                            if aweme_info:
                                logger.info("Successfully extracted Douyin defaultAwemeInfo from streaming SSR (pace_f)")
                                album_info = (aweme_info.get('lvideoBrief') or {}).get('albumInfo') or (aweme_info.get('lvideo_brief') or {}).get('album_info')
                                ep_info = (aweme_info.get('lvideoBrief') or {}).get('episodeInfo') or (aweme_info.get('lvideo_brief') or {}).get('episode_info') or aweme_info
                                return {
                                    "aweme_detail": aweme_info,
                                    "album_info": album_info,
                                    "episode_info": ep_info
                                }
            except Exception as e:
                logger.debug(f"Failed to parse pace_f chunk: {e}")

        return None

    def fetch_html_data(self):
        """
        获取抖音作品元数据（支持单视频、图文、音乐原声、合集、放映厅长视频与 SSR HTML 免签名多级容灾兜底）。
        """
        # 0. 针对音乐 / 原声独立链接 (/music/)
        if self.is_music:
            music_api = (f"https://www.douyin.com/aweme/v1/web/music/detail/?music_id={self.aweme_id}"
                         "&device_platform=webapp&aid=6383&channel=channel_pc_web")
            data = self._request_api_with_retry(
                music_api,
                referer=f"https://www.douyin.com/music/{self.aweme_id}",
                validate=lambda d: bool(d.get('music_info')),
            )
            if data:
                return data

            if not self.html_content:
                self.fetch_html_content()
            if self.html_content:
                ssr_data = self._parse_ssr_data(self.html_content)
                if ssr_data and ssr_data.get('music_info'):
                    return ssr_data
            return None

        # 0. 针对合集链接 (/collection/ 或 /mix/)
        if self.is_collection:
            mix_api = (f"https://www.douyin.com/aweme/v1/web/mix/aweme/?mix_id={self.aweme_id}"
                       "&cursor=0&count=20&device_platform=webapp&aid=6383&channel=channel_pc_web")
            data = self._request_api_with_retry(
                mix_api,
                referer=f"https://www.douyin.com/collection/{self.aweme_id}",
                validate=lambda d: bool(d.get('aweme_list') or d.get('mix_info')),
            )
            if data:
                aweme_list = data.get('aweme_list') or []
                if 'aweme_detail' not in data and aweme_list:
                    data['aweme_detail'] = aweme_list[0]
                return data

            if not self.html_content:
                self.fetch_html_content()
            if self.html_content:
                ssr_data = self._parse_ssr_data(self.html_content)
                if ssr_data and (ssr_data.get('aweme_detail') or ssr_data.get('mix_info')):
                    return ssr_data
            return None

        # 0. 针对放映厅 / 影视长片 / 剧集 / 短剧链接 (/lvdetail/ 或 /playlet/ 或 ep_id / album_id)
        if self.is_lvdetail:
            ep_id = self.ep_id or self.aweme_id
            album_id = self.album_id or self.aweme_id
            referer = f"https://www.douyin.com/share/playlet/detail/{album_id}" if ('/playlet/' in (self.real_url or '') or 'playlet' in (self.real_url or '')) else f"https://www.douyin.com/lvdetail/{ep_id}"

            def _lv_valid(d):
                return d.get('status_code') == 0 and bool(
                    d.get('lvideo_detail') or d.get('episode_info') or d.get('album_info')
                    or d.get('series_info') or d.get('playlet_info')
                    or d.get('aweme_list') or d.get('episode_list'))

            candidate_apis = []
            if album_id:
                candidate_apis.append(
                    f"https://www.douyin.com/aweme/v1/web/series/aweme/?series_id={album_id}"
                    "&cursor=0&count=20&device_platform=webapp&aid=6383&channel=channel_pc_web"
                )
            if ep_id and ep_id != album_id:
                candidate_apis.append(
                    f"https://www.douyin.com/aweme/v1/web/lvideo/aweme/?episode_id={ep_id}"
                    "&device_platform=webapp&aid=6383&channel=channel_pc_web"
                )
            for api_url in candidate_apis:
                # 多候选接口逐个尝试，单个接口分摊一半重试预算，避免最坏情况累积过长
                data = self._request_api_with_retry(
                    api_url, referer=referer, validate=_lv_valid,
                    max_attempts=max(2, API_MAX_ATTEMPTS // 2))
                if data:
                    return data

            if not self.html_content:
                self.fetch_html_content()
            if self.html_content:
                ssr_data = self._parse_ssr_data(self.html_content)
                if ssr_data and (ssr_data.get('lvideo_detail') or ssr_data.get('episode_info') or ssr_data.get('album_info') or ssr_data.get('series_info') or ssr_data.get('aweme_detail') or ssr_data.get('aweme_list')):
                    return ssr_data
            return None

        # 1. 针对明确的图文/幻灯片作品 (/note/ 或 /slides/)：
        # 优先请求 PC Web Detail API 以获取包含 LivePhoto 实况视频流的完整元数据；
        # 若 Web API 遭遇风控或失败，再自动降级至分享页 SSR（至少保障静态原图可用）。
        if getattr(self, 'is_note', False):
            detail_api = ("https://www.douyin.com/aweme/v1/web/aweme/detail/?device_platform=webapp"
                          f"&aid=6383&channel=channel_pc_web&pc_client_type=1&version_code=190500&version_name=19.5.0&aweme_id={self.aweme_id}")
            data = self._request_api_with_retry(
                detail_api,
                referer=f"https://www.douyin.com/note/{self.aweme_id}?previous_page=web_code_link",
                validate=lambda d: bool(d.get('aweme_detail')),
            )
            if data:
                return data
            if getattr(self, '_terminal_filter_detail', None):
                logger.info(f"作品确认处于明确的不可用终端状态，跳过 SSR HTML 兜底解析: {self.real_url}")
                return None
            share_ssr = self._try_share_ssr_detail()
            if share_ssr:
                return share_ssr
            return None

        # 2. 针对常规视频：优先尝试移动端 Feed 核心接口（主路径：免 Argus 门禁、零 403、响应毫秒级）
        mobile_data = self._request_mobile_feed(self.aweme_id)
        if mobile_data:
            return mobile_data

        # 3. 分享页 SSR（免 a_bogus）：常规视频 mobile miss 时先走这里，避免先烧 8 次 Argus 403
        share_ssr = self._try_share_ssr_detail()
        if share_ssr:
            return share_ssr

        # 4. 兜底路径：当分享页未收录时，回退到 Web API 并进行退避重试
        page_type = "note" if getattr(self, 'is_note', False) else "video"
        detail_api = ("https://www.douyin.com/aweme/v1/web/aweme/detail/?device_platform=webapp"
                      f"&aid=6383&channel=channel_pc_web&pc_client_type=1&version_code=190500&version_name=19.5.0&aweme_id={self.aweme_id}")
        data = self._request_api_with_retry(
            detail_api,
            referer=f"https://www.douyin.com/{page_type}/{self.aweme_id}?previous_page=web_code_link",
            validate=lambda d: bool(d.get('aweme_detail')),
        )
        if data:
            return data

        # 如果 Web API 已明确返回终端过滤状态（如私密/已删除/日常不可见），无需再进行耗时的 SSR HTML 抓取
        if getattr(self, '_terminal_filter_detail', None):
            logger.info(f"作品确认处于明确的不可用终端状态，跳过 SSR HTML 兜底解析: {self.real_url}")
            return None

        # 5. 末级容灾：Web API 失败后若此前 SSR 未命中，再试一次（html 可能已缓存）
        logger.info(f"抖音 a_bogus API 未返回有效详情，再次尝试 SSR HTML 兜底解析: {self.real_url}")
        if not self.html_content:
            self.fetch_html_content()

        if self.html_content:
            ssr_data = self._parse_ssr_data(self.html_content)
            if ssr_data and ssr_data.get('aweme_detail'):
                return ssr_data

        return None

    @staticmethod
    def _build_play_endpoint_url(video_id: str, ratio: str = "1080p") -> str:
        """从 video_id 或 uri 构造 iesdouyin 播放/下载端点（无水印、指定清晰度）"""
        if not video_id:
            return ""
        vid_str = str(video_id).strip()
        if not vid_str or vid_str.lower().startswith("http") or "mp3" in vid_str.lower():
            return vid_str
        encoded_vid = urllib.parse.quote(vid_str)
        encoded_ratio = urllib.parse.quote(str(ratio).strip() if ratio else "default")
        return (
            f"https://www.iesdouyin.com/aweme/v1/play/"
            f"?video_id={encoded_vid}&ratio={encoded_ratio}&line=0"
            f"&is_play_url=1&watermark=0&source=PackSourceEnum_PUBLISH"
        )

    @staticmethod
    def _extract_best_url_from_play_addr(play_addr_dict):
        """
        从 play_addr 字典中提取最佳播放链接。
        play_addr_list 结构通常为：[主CDN节点, 备用CDN节点, 抖音官方源站URL]
        优先取源站 URL（如列表中有 3 个或更多元素，取 index 2），否则取第 1 个。
        若 url_list 缺失但存在 uri，则自动格式化为 iesdouyin 播放端点。
        """
        if not play_addr_dict or not isinstance(play_addr_dict, dict):
            return None
        target_url = None
        url_list = play_addr_dict.get('url_list') or play_addr_dict.get('download_url_list') or []
        if isinstance(url_list, list) and url_list:
            valid_urls = [u for u in url_list if isinstance(u, str) and u.strip()]
            if len(valid_urls) >= 3 and valid_urls[2]:
                target_url = valid_urls[2]
            elif valid_urls:
                target_url = valid_urls[0]
        if target_url:
            if '/playwm/' in target_url:
                target_url = target_url.replace('/playwm/', '/play/')
            if 'ratio=720p' in target_url:
                target_url = target_url.replace('ratio=720p', 'ratio=1080p')
            return target_url

        uri = play_addr_dict.get('uri')
        if uri and isinstance(uri, str):
            clean_uri = uri.strip()
            if clean_uri.startswith('http'):
                if '/playwm/' in clean_uri:
                    clean_uri = clean_uri.replace('/playwm/', '/play/')
                return clean_uri
            if 'mp3' not in clean_uri.lower():
                return DouyinParser._build_play_endpoint_url(clean_uri, ratio="1080p")
        return None

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

            if not detail and self.is_lvdetail:
                detail = data_dict.get('episode_info') or (data_dict.get('lvideo_detail') or {}).get('episode_info') or data_dict.get('lvideo_detail') or {}
                if not detail and data_dict.get('episode_list'):
                    detail = data_dict['episode_list'][0]
                elif not detail and data_dict.get('aweme_list'):
                    detail = data_dict['aweme_list'][0]

            video = detail.get('video', {}) or (detail if 'play_addr' in detail or 'bit_rate' in detail else {})
            bit_rate_list = video.get('bit_rate', []) or []
            images = detail.get('images') or detail.get('image_list') or []
            media_type = detail.get('media_type')

            # 1. 图文作品识别：如果存在 images 列表或 media_type=2，且没有视频码率流，则为纯图文作品，不返回视频地址
            if (images or media_type == 2) and not bit_rate_list:
                return None

            # 2. 尝试从 bit_rate 列表中选择最佳流（优先 H.264，按 分辨率 > 码率 > 大小 > 质量类型 综合仲裁）
            valid_streams = []
            for item in bit_rate_list:
                if not isinstance(item, dict):
                    continue
                play_addr = item.get('play_addr')
                url = self._extract_best_url_from_play_addr(play_addr)
                if url:
                    rate = item.get('bit_rate') or 0
                    is_h265 = item.get('is_h265', 0)
                    p_addr = play_addr if isinstance(play_addr, dict) else {}
                    width = int(p_addr.get('width') or item.get('width') or 0)
                    height = int(p_addr.get('height') or item.get('height') or 0)
                    data_size = int(p_addr.get('data_size') or item.get('data_size') or 0)
                    quality_type = int(item.get('quality_type') or p_addr.get('quality_type') or 0)
                    valid_streams.append({
                        'bit_rate': rate,
                        'is_h265': is_h265,
                        'width': width,
                        'height': height,
                        'pixels': width * height,
                        'data_size': data_size,
                        'quality_type': quality_type,
                        'is_direct': 0 if '/aweme/v1/play/' in url else 1,
                        'url': url
                    })

            if valid_streams:
                # 优先筛选 H.264 流 (兼容性最好)
                h264_streams = [s for s in valid_streams if not s.get('is_h265')]
                target_pool = h264_streams if h264_streams else valid_streams
                # 多维度仲裁排序：像素数 -> 码率 -> 文件大小 -> 质量类型 -> 直链优先级
                target_pool.sort(
                    key=lambda s: (s['pixels'], s['bit_rate'], s['data_size'], s['quality_type'], s['is_direct']),
                    reverse=True
                )
                return target_pool[0]['url']

            # 2.5 检查 videoModel.dynamicVideo / playApi (长视频 / 放映厅流)
            dynamic_video = (video.get('videoModel') or {}).get('dynamicVideo') or (video.get('video_model') or {}).get('dynamic_video') or {}
            if isinstance(dynamic_video, dict):
                dyn_list = dynamic_video.get('dynamic_video_list') or dynamic_video.get('dynamicVideoList') or []
                if dyn_list:
                    # 优先筛选 H.264
                    h264_dyn = [v for v in dyn_list if (v.get('video_meta') or {}).get('codec_type') == 'h264']
                    if h264_dyn:
                        # 按码率降序
                        h264_dyn.sort(key=lambda s: (s.get('video_meta') or {}).get('bitrate', 0), reverse=True)
                        return h264_dyn[0].get('main_url') or h264_dyn[0].get('backup_url')
                    # 否则取最高码率
                    dyn_list.sort(key=lambda s: (s.get('video_meta') or {}).get('bitrate', 0), reverse=True)
                    return dyn_list[0].get('main_url') or dyn_list[0].get('backup_url')

            # 2.8 尝试从 download_addr 提取无水印原画质端点 (ratio=default)
            download_addr = video.get('download_addr')
            if isinstance(download_addr, dict):
                dl_uri = download_addr.get('uri')
                if dl_uri and isinstance(dl_uri, str) and not dl_uri.startswith('http') and 'mp3' not in dl_uri.lower():
                    original_url = self._build_play_endpoint_url(dl_uri, ratio='default')
                    if original_url:
                        return original_url
                dl_urls = download_addr.get('url_list') or []
                if isinstance(dl_urls, list) and dl_urls:
                    for d_u in dl_urls:
                        if isinstance(d_u, str) and d_u.strip():
                            return d_u.strip()

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
        """获取视频列表（单视频作品返回包含主视频的列表；合集或放映厅返回所有分集视频列表）"""
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

        if self.is_lvdetail and self.data:
            ep_list = self.data.get('episode_list') or self.data.get('aweme_list') or (self.data.get('album_info') or {}).get('episode_list') or []
            if ep_list:
                video_urls = []
                for item in ep_list:
                    video_item = item.get('video') or (item if 'play_addr' in item or 'bit_rate' in item else {})
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
                        dynamic_video = (video_item.get('videoModel') or {}).get('dynamicVideo') or (video_item.get('video_model') or {}).get('dynamic_video') or {}
                        if isinstance(dynamic_video, dict):
                            dyn_list = dynamic_video.get('dynamic_video_list') or dynamic_video.get('dynamicVideoList') or []
                            if dyn_list:
                                url = dyn_list[0].get('main_url') or dyn_list[0].get('backup_url')
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
            if not data_dict:
                return None

            detail = data_dict.get('aweme_detail', {}) or {}
            if not detail and self.is_lvdetail:
                detail = data_dict.get('episode_info') or (data_dict.get('lvideo_detail') or {}).get('episode_info') or {}
                if not detail and data_dict.get('episode_list'):
                    detail = data_dict['episode_list'][0]

            video = detail.get('video', {}) or (detail if 'cla_info' in detail or 'subtitle_infos' in detail or 'claInfo' in detail else {})

            # 1. 优先从 video.cla_info 中提取
            cla_info = video.get('cla_info') or video.get('claInfo') or detail.get('claInfo') or {}
            caption_infos = cla_info.get('caption_infos') or cla_info.get('captionInfos') or cla_info.get('captions') or []

            # 2. 兜底从 video.subtitle_infos 提取
            if not caption_infos:
                caption_infos = video.get('subtitle_infos') or video.get('subtitleInfos') or []

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
                    if isinstance(cap, dict) and (cap.get('url') or cap.get('url_list') or cap.get('urlList')):
                        target_cap = cap
                        break

            if not target_cap:
                return None

            url = target_cap.get('url')
            if not url:
                url_list = target_cap.get('url_list') or target_cap.get('urlList') or []
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

            if self.is_lvdetail:
                series_info = data_dict.get('series_info') or (data_dict.get('lvideo_detail') or {}).get('series_info') or data_dict.get('playlet_info') or {}
                series_title = series_info.get('series_name') or series_info.get('title') or series_info.get('name') or ''

                album_info = data_dict.get('album_info') or (data_dict.get('lvideo_detail') or {}).get('album_info') or {}
                album_title = album_info.get('album_name') or album_info.get('title') or album_info.get('name') or ''

                ep_info = data_dict.get('episode_info') or (data_dict.get('lvideo_detail') or {}).get('episode_info') or {}
                if not ep_info and data_dict.get('episode_list'):
                    ep_info = data_dict['episode_list'][0]
                elif not ep_info and data_dict.get('aweme_list'):
                    aw0 = data_dict['aweme_list'][0]
                    ep_info = aw0.get('episode_info') or aw0

                ep_title = ep_info.get('episode_name') or ep_info.get('title') or ep_info.get('itemTitle') or ''

                prefix = "【短剧】" if ('/playlet/' in (self.real_url or '') or 'playlet' in (self.real_url or '') or series_title) else "【放映厅】"
                main_title = series_title or album_title
                if main_title and ep_title and main_title != ep_title:
                    return f"{prefix}{main_title} - {ep_title}"
                if main_title:
                    return f"{prefix}{main_title}"
                if ep_title:
                    return f"{prefix}{ep_title}"

            if not data_dict.get('aweme_detail'):
                if data_dict.get('aweme_list'):
                    aw0 = data_dict['aweme_list'][0]
                    t = aw0.get('itemTitle') or aw0.get('desc')
                    if t:
                        return t
                return None
            aweme = data_dict['aweme_detail']
            title = aweme.get('itemTitle') or None
            desc = aweme.get('desc') or None
            # itemTitle 与 desc 相同通常只是接口冗余字段，不将文案伪装成标题。
            if title and desc and title.strip() == desc.strip():
                return None
            return title
        except (KeyError, json.JSONDecodeError, TypeError) as e:
            logger.warning(f"Failed to parse title content: {e}")
            return None

    def get_description(self):
        """返回抖音原始作品文案，不用标题字段回填。"""
        try:
            data_dict = self.data
            if not data_dict:
                return None
            return (data_dict.get('aweme_detail') or {}).get('desc') or None
        except (AttributeError, TypeError) as e:
            logger.warning(f"Failed to parse Douyin description: {e}")
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

            if self.is_lvdetail:
                series_info = data_dict.get('series_info') or (data_dict.get('lvideo_detail') or {}).get('series_info') or data_dict.get('playlet_info') or {}
                for k in ('cover_url', 'poster_url', 'horizontal_cover', 'vertical_cover', 'verticalCover', 'cover'):
                    val = series_info.get(k)
                    if isinstance(val, dict):
                        url_list = val.get('url_list') or val.get('urlList') or []
                        if url_list:
                            return url_list[0]
                    elif isinstance(val, str) and val:
                        return val

                album_info = data_dict.get('album_info') or (data_dict.get('lvideo_detail') or {}).get('album_info') or {}
                for k in ('cover_url', 'poster_url', 'horizontal_cover', 'vertical_cover', 'verticalCover', 'cover'):
                    val = album_info.get(k)
                    if isinstance(val, dict):
                        url_list = val.get('url_list') or val.get('urlList') or []
                        if url_list:
                            return url_list[0]
                    elif isinstance(val, str) and val:
                        return val

                ep_info = data_dict.get('episode_info') or (data_dict.get('lvideo_detail') or {}).get('episode_info') or {}
                if not ep_info and data_dict.get('episode_list'):
                    ep_info = data_dict['episode_list'][0]
                elif not ep_info and data_dict.get('aweme_list'):
                    ep_info = data_dict['aweme_list'][0]
                for k in ('cover_url', 'poster_url', 'origin_cover', 'cover', 'dynamic_cover'):
                    val = ep_info.get(k)
                    if isinstance(val, dict):
                        url_list = val.get('url_list') or val.get('urlList') or []
                        if url_list:
                            return url_list[0]
                    elif isinstance(val, str) and val:
                        return val

                aweme_detail = data_dict.get('aweme_detail') or {}
                video = aweme_detail.get('video') or {}
                cover = video.get('cover')
                if isinstance(cover, str) and cover:
                    return cover

            detail = data_dict.get('aweme_detail') or {}

            # 1. 优先获取视频静态封面（origin_cover -> cover -> dynamic_cover 兜底）
            video_cover = None
            video_data = detail.get('video') or {}
            for cover_key in ('origin_cover', 'cover', 'dynamic_cover'):
                cover_obj = video_data.get(cover_key)
                if isinstance(cover_obj, dict):
                    url_list = cover_obj.get('url_list') or cover_obj.get('urlList') or []
                    if url_list:
                        video_cover = url_list[0]
                        break
                elif isinstance(cover_obj, str) and cover_obj:
                    video_cover = cover_obj
                    break

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

    @staticmethod
    def _extract_audio_from_music(music):
        """
        从音乐对象 (music / music_info) 中提取可用音频播放直链。
        优先读取 play_url.url_list；若原声被平台下架或标记不可用（play_url 为空），
        则自动从 extra.original_song_url 中提取底层有效的签名直链。
        """
        if not isinstance(music, dict):
            return None

        # 1. 常规 play_url 结构
        play_url = music.get('play_url') or music.get('playUrl') or {}
        if isinstance(play_url, dict):
            url_list = play_url.get('url_list') or play_url.get('urlList') or []
            for u in url_list:
                if u and isinstance(u, str) and u.startswith('http'):
                    return u
            uri = play_url.get('uri') or ''
            if isinstance(uri, str) and uri.startswith('http'):
                return uri
        elif isinstance(play_url, str) and play_url.startswith('http'):
            return play_url

        # 2. 从 extra 中提取 original_song_url（原声被下架或标记不可用时，底层仍保留的有效签名直链）
        extra = music.get('extra')
        if extra:
            if isinstance(extra, str):
                try:
                    extra = json.loads(extra)
                except Exception:
                    extra = None
            if isinstance(extra, dict):
                for k in ('original_song_url', 'original_sound_url'):
                    orig = extra.get(k)
                    if orig and isinstance(orig, str) and orig.startswith('http'):
                        return orig

        for k in ('original_song_url', 'original_sound_url'):
            orig = music.get(k)
            if orig and isinstance(orig, str) and orig.startswith('http'):
                return orig

        return None

    def get_audio_url(self):
        try:
            data_dict = self.data
            if not data_dict:
                return None

            if self.is_music:
                music_info = data_dict.get('music_info') or {}
                return self._extract_audio_from_music(music_info)

            if self.is_lvdetail:
                ep_info = data_dict.get('episode_info') or (data_dict.get('lvideo_detail') or {}).get('episode_info') or {}
                aweme_detail = data_dict.get('aweme_detail') or {}
                music = ep_info.get('music') or aweme_detail.get('music') or {}
                audio_url = self._extract_audio_from_music(music)
                if audio_url:
                    return audio_url

                video = aweme_detail.get('video') or ep_info.get('video') or {}
                dynamic_video = (video.get('videoModel') or {}).get('dynamicVideo') or (video.get('video_model') or {}).get('dynamic_video') or {}
                if isinstance(dynamic_video, dict):
                    dyn_audio = dynamic_video.get('dynamic_audio_list') or dynamic_video.get('dynamicAudioList') or []
                    for a in dyn_audio:
                        u = a.get('main_url') or a.get('backup_url')
                        if u:
                            return u
                return None

            detail = data_dict.get('aweme_detail') or {}
            if not detail and self.is_collection and data_dict.get('aweme_list'):
                detail = data_dict['aweme_list'][0]

            if detail:
                music = detail.get('music') or {}
                audio_url = self._extract_audio_from_music(music)
                if audio_url:
                    return audio_url

                # 兜底检查视频的分离音轨（如 dynamic_video / bit_rate_audio）
                video = detail.get('video') or {}
                dynamic_video = (video.get('videoModel') or {}).get('dynamicVideo') or (video.get('video_model') or {}).get('dynamic_video') or {}
                if isinstance(dynamic_video, dict):
                    dyn_audio = dynamic_video.get('dynamic_audio_list') or dynamic_video.get('dynamicAudioList') or []
                    for a in dyn_audio:
                        u = a.get('main_url') or a.get('backup_url')
                        if u:
                            return u

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

            if self.is_lvdetail:
                album_info = data_dict.get('album_info') or (data_dict.get('lvideo_detail') or {}).get('album_info') or {}
                ep_info = data_dict.get('episode_info') or (data_dict.get('lvideo_detail') or {}).get('episode_info') or {}
                aweme_detail = data_dict.get('aweme_detail') or {}
                author = album_info.get('author') or album_info.get('owner') or ep_info.get('author') or aweme_detail.get('authorInfo') or aweme_detail.get('author') or {}
                if author:
                    avatar_thumb = author.get('avatar_thumb') or author.get('avatarThumb') or author.get('avatar') or author.get('avatarUri') or {}
                    if isinstance(avatar_thumb, dict):
                        avatar_url_list = avatar_thumb.get('url_list') or avatar_thumb.get('urlList') or [None]
                        avatar_url = avatar_url_list[0]
                    else:
                        avatar_url = avatar_thumb if isinstance(avatar_thumb, str) else None
                    return {
                        "nickname": author.get('nickname') or author.get('name', ''),
                        "author_id": str(author.get('unique_id') or author.get('short_id') or author.get('uid') or author.get('id', '')),
                        "avatar": avatar_url
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
        针对图文笔记 / 幻灯片 / 实况图集（Live Photo），提取所有高清图片与实况动轨。
        兼容以下多源结构：
        - aweme_detail.image_post_info.images (现代 Web 端新版结构)
        - aweme_detail.image_post_info.image_list
        - aweme_detail.images
        - aweme_detail.image_list
        - aweme_detail.image_infos
        - aweme_detail.original_images
        实况图（Live Photo）支持递归提取 video、video_play_addr、video_download_addr 及 uri 端点。
        """
        if self.is_music or self.is_lvdetail:
            return []

        try:
            data_dict = self.data
            if not data_dict:
                return []

            detail = data_dict.get('aweme_detail') or {}
            if not detail and self.is_collection and data_dict.get('aweme_list'):
                detail = data_dict['aweme_list'][0]
            if not detail:
                detail = data_dict

            # 1. 扫描所有可能的图集字段结构
            image_post_info = detail.get('image_post_info') if isinstance(detail.get('image_post_info'), dict) else {}
            candidates = [
                image_post_info.get('images'),
                image_post_info.get('image_list'),
                detail.get('images'),
                detail.get('image_list'),
                detail.get('image_infos'),
                detail.get('original_images')
            ]

            images = []
            for candidate in candidates:
                if candidate and isinstance(candidate, list) and len(candidate) > 0:
                    images = candidate
                    break

            if not images:
                return []

            image_results = []
            for img in images:
                if not img or not isinstance(img, dict):
                    continue

                # 2. 提取静态图片 URL（优先 url_list 无水印原图，其次 display_image/image_url/download_url）
                img_url = None
                raw_urls = img.get('url_list') or []
                if isinstance(raw_urls, list) and raw_urls:
                    valid_urls = [u for u in raw_urls if isinstance(u, str) and u.strip()]
                    if valid_urls:
                        # 优先取最后一个 URL（通常是最高质量的源站 CDN）
                        img_url = valid_urls[-1]

                if not img_url:
                    for fallback_key in ('display_image', 'image_url', 'image', 'origin_cover', 'cover', 'download_url_list', 'download_url'):
                        val = img.get(fallback_key)
                        if isinstance(val, dict):
                            val_urls = val.get('url_list') or []
                            if val_urls and isinstance(val_urls, list) and val_urls:
                                img_url = val_urls[0]
                                break
                        elif isinstance(val, list) and val:
                            img_url = val[0]
                            break
                        elif isinstance(val, str) and val.strip():
                            img_url = val.strip()
                            break

                # 3. 提取实况照片（Live Photo）动轨视频 URL
                live_photo_url = None
                live_video = img.get('video') if isinstance(img.get('video'), dict) else None
                if not live_video:
                    for v_key in ('video_play_addr', 'video_download_addr'):
                        if isinstance(img.get(v_key), dict):
                            live_video = {'play_addr': img.get(v_key)}
                            break

                if live_video:
                    # 3.1 优先检查 play_addr.uri / vid / download_addr.uri
                    vid = (
                        (live_video.get('play_addr') or {}).get('uri')
                        or (live_video.get('download_addr') or {}).get('uri')
                        or live_video.get('vid')
                    )
                    if vid and isinstance(vid, str):
                        clean_vid = vid.strip()
                        if clean_vid.startswith('http'):
                            live_photo_url = clean_vid
                        elif 'mp3' not in clean_vid.lower():
                            live_photo_url = self._build_play_endpoint_url(clean_vid, ratio='1080p')

                    # 3.2 检查多格式 play_addr 列表
                    if not live_photo_url:
                        for lk in ('play_addr', 'play_addr_h264', 'play_addr_lowbr', 'download_addr'):
                            addr_obj = live_video.get(lk)
                            if isinstance(addr_obj, dict):
                                l_urls = addr_obj.get('url_list') or addr_obj.get('download_url_list') or []
                                if isinstance(l_urls, list) and l_urls:
                                    valid_l_urls = [u for u in l_urls if isinstance(u, str) and u.strip()]
                                    if valid_l_urls:
                                        live_photo_url = valid_l_urls[0]
                                        break
                                l_uri = addr_obj.get('uri')
                                if l_uri and isinstance(l_uri, str) and not l_uri.startswith('http') and 'mp3' not in l_uri.lower():
                                    live_photo_url = self._build_play_endpoint_url(l_uri, ratio='1080p')
                                    break

                # 4. 组装结果
                if img_url or live_photo_url:
                    if live_photo_url:
                        image_results.append({
                            'url': img_url or '',
                            'live_photo_url': live_photo_url
                        })
                    else:
                        image_results.append(img_url)

            return image_results

        except Exception as e:
            logger.warning(f"Failed to parse image list: {e}")
            return []
