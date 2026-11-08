"""平台 Cookie 凭据注册表与巡检辅助。

本模块是巡检页的单一事实源：各平台 Cookie 的能力门控、必需字段、
金丝雀配置与状态记录都从这里读写。能力门控信息整理自 docs/parsers/
各平台逆向文档，新增平台时只需在此追加一条注册项。

字段校验为纯本地解析（零网络），保存 Cookie 时即时反馈；真实探针
见 src/utils/cookie_prober.py（阶段三实现）。
"""

import json
import threading
import time
from http.cookies import SimpleCookie

from configs.logging_config import get_logger
from src.db import get_db, setting, utcnow
from src.utils.cookie_samples import default_probe_sample

logger = get_logger(__name__)

# 自动巡检间隔（秒）：仅跑零网络的字段校验与被动信号，真实探针由管理员手动触发。
AUTO_CHECK_INTERVAL_SECONDS = 6 * 3600

# 平台 Cookie 凭据注册表。
# severity: critical(缺失=能力整体消失或核心能力降级) / enhanced(降质) / fallback(风控兜底)
# db_keys:  按优先级排列的后台配置键（首键为设置页写入键）
# env_keys: 环境变量及别名（与 cookie_manager.PLATFORM_COOKIE_ALIASES 对齐）
COOKIE_REGISTRY = {
    "douyin": {
        "platform_name": "抖音",
        "db_keys": ["cookie_douyin"],
        "env_keys": ["DOUYIN_COOKIE", "DY_COOKIE"],
        "required_fields": ["sessionid", "sessionid_ss", "passport_csrf_token", "odin_tt"],
        "optional_fields": ["UIFID"],
        "uifid_env": ["DOUYIN_UIFID", "DY_UIFID"],
        "severity": "enhanced",
        "capabilities": [
            {"name": "视频", "needs_cookie": False},
            {"name": "图文图集", "needs_cookie": False},
            {"name": "实况动轨", "needs_cookie": True},
            {"name": "放映厅/短剧", "needs_cookie": True},
        ],
        "canary_setting": "canary_douyin",
        "passive_error_codes": ["COOKIE_REQUIRED"],
        "log_names": ["抖音"],
        "config_hint": "完整登录 Cookie，须含 sessionid、sessionid_ss、passport_csrf_token、odin_tt；实况动轨另需 UIFID（可配 DOUYIN_UIFID）。",
    },
    "yuanbao": {
        "platform_name": "腾讯元宝 / 视频号",
        "db_keys": ["cookie_yuanbao", "cookie_wechat_channels"],
        "env_keys": ["YUANBAO_COOKIE", "WECHAT_CHANNELS_COOKIE"],
        "required_fields": ["hy_user", "hy_token"],
        "optional_fields": [],
        "severity": "critical",
        "capabilities": [
            {"name": "元宝分享", "needs_cookie": False},
            {"name": "视频号无水印视频", "needs_cookie": True},
            {"name": "视频号图集", "needs_cookie": True},
        ],
        "canary_setting": "canary_yuanbao",
        "passive_error_codes": ["WECHAT_CHANNELS_COOKIE_REQUIRED"],
        "log_names": ["腾讯元宝", "视频号", "微信视频号"],
        "config_hint": "元宝会话凭据 hy_user 与 hy_token；视频号全平台能力依赖此项，强烈建议使用闲置小号。",
    },
    "pinduoduo": {
        "platform_name": "拼多多",
        "db_keys": ["cookie_pinduoduo"],
        "env_keys": ["PINDUODUO_COOKIE", "PDD_COOKIE"],
        "required_fields": ["PDDAccessToken"],
        "optional_fields": [],
        "severity": "enhanced",
        "capabilities": [
            {"name": "实物/评价秀", "needs_cookie": False},
            {"name": "多多视频", "needs_cookie": True},
        ],
        "canary_setting": "canary_pinduoduo",
        "log_names": ["拼多多"],
        "passive_error_codes": ["PINDUODUO_COOKIE_REQUIRED"],
        "config_hint": "已登录账号 Cookie（PDDAccessToken=xxx;），仅多多视频需要；实物/评价秀分享免配。",
    },
    "doubao": {
        "platform_name": "豆包",
        "db_keys": ["cookie_doubao"],
        "env_keys": ["DOUBAO_COOKIE"],
        "required_fields": ["sessionid_ss"],
        "optional_fields": ["passport_csrf_token"],
        "severity": "critical",
        "capabilities": [
            {"name": "图片/音乐/对话", "needs_cookie": False},
            {"name": "视频无水印原画", "needs_cookie": True},
        ],
        "canary_setting": "canary_doubao",
        "log_names": ["豆包"],
        "passive_error_codes": [],
        "config_hint": "sessionid_ss 即可；未配置时视频降级为带水印预览切片。",
    },
    "xiaohongshu": {
        "platform_name": "小红书",
        "db_keys": ["cookie_xiaohongshu"],
        "env_keys": ["XHS_COOKIE", "XIAOHONGSHU_COOKIE"],
        "required_fields": [],
        "optional_fields": ["a1", "webId", "web_session"],
        "severity": "fallback",
        "capabilities": [
            {"name": "视频/图文/实况", "needs_cookie": False},
            {"name": "风控兜底", "needs_cookie": True},
        ],
        "canary_setting": "canary_xiaohongshu",
        "log_names": ["小红书"],
        "passive_error_codes": ["XIAOHONGSHU_COOKIE_REQUIRED"],
        "config_hint": "仅需设备凭据 a1 与访客 webId 或登录 web_session；机房 IP/高频场景配置后成功率 99%+。",
    },
    "kuaishou": {
        "platform_name": "快手",
        "db_keys": ["cookie_kuaishou"],
        "env_keys": ["KUAISHOU_COOKIE", "KS_COOKIE"],
        "required_fields": [],
        "optional_fields": ["did", "kpf", "kpn"],
        "severity": "fallback",
        "capabilities": [
            {"name": "视频/图集", "needs_cookie": False},
            {"name": "风控兜底", "needs_cookie": True},
        ],
        "canary_setting": "canary_kuaishou",
        "log_names": ["快手"],
        "passive_error_codes": ["KUAISHOU_COOKIE_REQUIRED"],
        "config_hint": "兜底凭据：仅当常规路由触发反爬校验时启用，平时无需配置。",
    },
    "weibo": {
        "platform_name": "微博",
        "db_keys": ["cookie_weibo"],
        "env_keys": ["WEIBO_COOKIE"],
        "required_fields": ["SUB"],
        "optional_fields": ["SUBP"],
        "severity": "enhanced",
        "capabilities": [
            {"name": "常规图文/视频", "needs_cookie": False},
            {"name": "高规格视频", "needs_cookie": True},
        ],
        "canary_setting": "canary_weibo",
        "log_names": ["微博"],
        "passive_error_codes": [],
        "config_hint": "推荐精简字段 SUB=xxx; 常规图文/视频内置访客会话免配；机房 IP 或高规格视频建议配置。",
    },
    "jimeng": {
        "platform_name": "即梦AI",
        "db_keys": ["cookie_jimeng"],
        "env_keys": ["JIMENG_COOKIE"],
        "required_fields": [],
        "optional_fields": ["sessionid"],
        "severity": "enhanced",
        "capabilities": [
            {"name": "AI视频/生图", "needs_cookie": False},
            {"name": "接口增强", "needs_cookie": True},
        ],
        "canary_setting": "canary_jimeng",
        "log_names": ["即梦AI"],
        "passive_error_codes": [],
        "config_hint": "可选增强凭据；配置后附带 appid 与 device-platform 请求头，提升接口成功率。",
    },
    "zhihu": {
        "platform_name": "知乎",
        "db_keys": ["cookie_zhihu"],
        "env_keys": ["ZHIHU_COOKIE"],
        "required_fields": [],
        "optional_fields": ["d_c0", "z_c0"],
        "severity": "fallback",
        "capabilities": [
            {"name": "视频/回答/专栏", "needs_cookie": False},
            {"name": "风控兜底", "needs_cookie": True},
        ],
        "canary_setting": "canary_zhihu",
        "log_names": ["知乎"],
        "passive_error_codes": [],
        "config_hint": "推荐精简字段 d_c0=xxx; z_c0=xxx; 常规解析免配，用于绕过反爬风控或提取登录可见内容。",
    },
}

SEVERITY_ORDER = {"critical": 0, "enhanced": 1, "fallback": 2}
STATUS_ORDER = {"stale": 0, "not_configured": 1, "incomplete": 2, "probe_failed": 3, "unverified": 4, "healthy": 5}

STATUS_LABELS = {
    "healthy": "有效",
    "unverified": "待验证",
    "stale": "疑似失效",
    "incomplete": "字段缺失",
    "not_configured": "未配置",
    "probe_failed": "探针失败",
}

SEVERITY_LABELS = {
    "critical": "必需",
    "enhanced": "增强",
    "fallback": "兜底",
}


def get_entry(platform_key):
    return COOKIE_REGISTRY.get(platform_key)


def _parse_cookie_pairs(cookie_str):
    """容错解析 Cookie 字符串为 {name: value}，解析失败的片段跳过。"""
    pairs = {}
    if not cookie_str:
        return pairs
    try:
        jar = SimpleCookie()
        jar.load(cookie_str)
        for name, morsel in jar.items():
            if morsel.value:
                pairs[name.strip()] = morsel.value
    except Exception:
        pass
    # SimpleCookie 会拒绝含非法字符的分段；对被丢弃的字段做兜底切分。
    if len(pairs) < cookie_str.count("="):
        for chunk in cookie_str.split(";"):
            if "=" not in chunk:
                continue
            name, _, value = chunk.partition("=")
            name = name.strip().strip("'\"")
            if name and name not in pairs:
                pairs[name] = value.strip().strip("'\"")
    return pairs


def get_cookie_value(platform_key):
    """按 注册表 DB 键 → 指定环境变量 → 别名 的顺序取当前生效凭据。"""
    entry = get_entry(platform_key)
    if not entry:
        return ""
    for db_key in entry["db_keys"]:
        val = setting(db_key)
        if val is not None and str(val).strip():
            return str(val).strip()
    import os

    for env_key in entry["env_keys"]:
        val = os.getenv(env_key, "").strip()
        if val:
            return val
    return ""


def get_cookie_source(platform_key):
    """凭据来源：database / env / none。"""
    entry = get_entry(platform_key)
    if not entry:
        return "none"
    for db_key in entry["db_keys"]:
        val = setting(db_key)
        if val is not None and str(val).strip():
            return "database"
    import os

    for env_key in entry["env_keys"]:
        if os.getenv(env_key, "").strip():
            return "env"
    return "none"


def _extract_uifid(cookie_str):
    """抖音 UIFID 三来源：独立环境变量 / Cookie 字段 / 256 位裸串。"""
    import os

    for env_key in ("DOUYIN_UIFID", "DY_UIFID"):
        val = os.getenv(env_key, "").strip()
        if val:
            return val
    pairs = _parse_cookie_pairs(cookie_str)
    val = pairs.get("UIFID", "").strip()
    if val:
        return val
    for token in (cookie_str or "").replace(";", " ").split():
        token = token.strip().strip("'\"")
        if len(token) >= 32 and "=" not in token:
            return token
    return ""


def check_cookie_fields(platform_key, cookie=None):
    """字段完整度校验（纯本地，零网络）。

    返回 {"status": "ok"|"incomplete"|"empty", "missing": [...], "detail": str}
    """
    entry = get_entry(platform_key)
    if not entry:
        return {"status": "empty", "missing": [], "detail": "未注册的平台"}
    if cookie is None:
        cookie = get_cookie_value(platform_key)
    if not cookie:
        return {"status": "empty", "missing": list(entry["required_fields"]), "detail": "未配置凭据"}

    pairs = _parse_cookie_pairs(cookie)
    missing = [name for name in entry["required_fields"] if not pairs.get(name)]
    if platform_key == "douyin":
        # UIFID 可能来自独立环境变量或裸串，单独判定。
        if not _extract_uifid(cookie):
            missing.append("UIFID")

    if missing:
        return {
            "status": "incomplete",
            "missing": missing,
            "detail": f"缺少必需字段: {', '.join(missing)}",
        }
    return {"status": "ok", "missing": [], "detail": "必需字段齐备"}


def record_probe(platform_key, status, trigger_type="manual", detail=None, duration_ms=None):
    """写入一条巡检记录。detail 为可 JSON 序列化的结构或字符串。"""
    if platform_key not in COOKIE_REGISTRY:
        return
    if isinstance(detail, (dict, list)):
        detail = json.dumps(detail, ensure_ascii=False)
    get_db().execute(
        "INSERT INTO cookie_probe_records(platform_key, status, trigger_type, detail, duration_ms, probed_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (platform_key, status, trigger_type, detail, duration_ms, utcnow()),
    )
    get_db().commit()


def latest_probe(platform_key, trigger_types=None):
    row = get_db().execute(
        "SELECT * FROM cookie_probe_records WHERE platform_key = ? "
        "ORDER BY probed_at DESC, id DESC LIMIT 1",
        (platform_key,),
    ).fetchone()
    if not row:
        return None
    detail = row["detail"]
    try:
        detail = json.loads(detail) if detail else None
    except (TypeError, ValueError):
        pass
    return {
        "status": row["status"],
        "trigger_type": row["trigger_type"],
        "detail": detail,
        "duration_ms": row["duration_ms"],
        "probed_at": row["probed_at"],
    }


def passive_signal(platform_key, hours=24):
    """被动巡检：近 N 小时调用日志中该平台的 Cookie 类错误统计。"""
    entry = get_entry(platform_key)
    if not entry or not entry["passive_error_codes"]:
        return {"total": 0, "cookie_required": 0}
    like_clauses = " OR ".join(
        f"error_code LIKE '{code}%'" for code in entry["passive_error_codes"]
    )
    placeholders = ", ".join("?" for _ in entry["log_names"])
    row = get_db().execute(
        f"SELECT COUNT(*) AS total, "
        f"SUM(CASE WHEN ({like_clauses}) THEN 1 ELSE 0 END) AS cookie_required "
        f"FROM request_logs WHERE platform IN ({placeholders}) "
        f"AND created_at >= datetime('now', '-{int(hours)} hours')",
        tuple(entry["log_names"]),
    ).fetchone()
    return {
        "total": row["total"] if row and row["total"] else 0,
        "cookie_required": row["cookie_required"] if row else 0,
    }


def _derive_status(platform_key):
    """汇总字段校验、被动信号与最近探针，得出当前展示状态。"""
    entry = get_entry(platform_key)
    source = get_cookie_source(platform_key)
    if source == "none":
        return "not_configured"

    field = check_cookie_fields(platform_key)
    if field["status"] == "incomplete":
        return "incomplete"

    passive = passive_signal(platform_key)
    if (
        passive["total"] >= 3
        and passive["cookie_required"] * 2 > passive["total"]
    ):
        return "stale"

    latest = latest_probe(platform_key)
    if latest and latest["status"] in ("stale", "probe_failed", "healthy", "unverified"):
        # 历史字段校验及 BOTH_OK 曾记作 healthy，不能作为有效凭据的证据。
        if latest["status"] == "healthy":
            detail = latest.get("detail")
            if latest.get("trigger_type") != "probe" or not isinstance(detail, dict) or detail.get("signal") != "COOKIE_GAIN":
                return "unverified"
        return latest["status"]
    return "unverified"


def build_overview():
    """巡检页 overview 数据：状态总览、one finding 与平台明细。"""
    entries = []
    for key, entry in COOKIE_REGISTRY.items():
        source = get_cookie_source(key)
        status = _derive_status(key)
        field = check_cookie_fields(key)
        capabilities = [
            {
                "name": cap["name"],
                "needs_cookie": cap["needs_cookie"],
                "active": (not cap["needs_cookie"]) or status in ("healthy", "unverified"),
            }
            for cap in entry["capabilities"]
        ]
        default_sample = default_probe_sample(key)
        entries.append({
            "platform_key": key,
            "platform_name": entry["platform_name"],
            "severity": entry["severity"],
            "severity_label": SEVERITY_LABELS[entry["severity"]],
            "source": source,
            "status": status,
            "status_label": STATUS_LABELS.get(status, status),
            "capabilities": capabilities,
            "field_check": {"missing": field["missing"], "detail": field["detail"]},
            "cookie_value": get_cookie_value(key),
            "last_probe": latest_probe(key),
            "passive_24h": passive_signal(key),
            "canary_url": setting(entry["canary_setting"]),
            "default_canary_url": default_sample["url"] if default_sample else None,
            "probe_capability": default_sample["cookie_probe"]["capability"] if default_sample else None,
            "config_hint": entry["config_hint"],
            "env_keys": entry["env_keys"],
        })

    entries.sort(key=lambda x: (SEVERITY_ORDER[x["severity"]], STATUS_ORDER[x["status"]]))

    summary = {"healthy": 0, "stale": 0, "not_configured": 0, "incomplete": 0, "probe_failed": 0, "unverified": 0}
    for item in entries:
        summary[item["status"]] = summary.get(item["status"], 0) + 1

    return {"generated_at": utcnow(), "summary": summary, "entries": entries}


def build_finding(overview):
    """one finding：按严重度取第一条异常，供标题副行展示。"""
    for item in overview["entries"]:
        if item["status"] == "not_configured" and item["severity"] == "critical":
            return f"{item['platform_name']}未配置凭据，平台能力整体不可用"
        if item["status"] == "stale":
            return f"{item['platform_name']}凭据疑似失效，相关能力已降级"
        if item["status"] == "incomplete":
            return f"{item['platform_name']}凭据缺少字段：{'、'.join(item['field_check']['missing'])}"
        if item["status"] == "unverified":
            return f"{item['platform_name']}凭据有效性待验证，请使用依赖 Cookie 的样例进行探针验证"
        if item["status"] == "probe_failed":
            return f"{item['platform_name']}探针失败，请检查测试样例链接"
        if item["status"] == "not_configured":
            return f"{item['platform_name']}未配置凭据，{item['severity_label']}型能力未启用"
    return None


def run_auto_check():
    """一轮自动巡检：全平台字段校验 + 被动信号（零网络）。

    仅在发现异常（stale / incomplete）时写入记录，避免巡检记录被
    周期性 healthy 刷屏；结论由下次真实探针或人工更新凭据澄清。
    """
    findings = []
    for key in COOKIE_REGISTRY:
        if get_cookie_source(key) == "none":
            continue
        status = _derive_status(key)
        if status not in ("stale", "incomplete"):
            continue
        entry = get_entry(key)
        if status == "stale":
            detail = f"{entry['platform_name']}凭据疑似失效，相关能力已降级"
        else:
            missing = "、".join(check_cookie_fields(key)["missing"])
            detail = f"{entry['platform_name']}凭据缺少字段：{missing}"
        record_probe(key, status, "auto", detail)
        findings.append(detail)
        logger.warning(f"Cookie 自动巡检发现异常 - {detail}")
    return findings


def _auto_loop(interval):
    while True:
        time.sleep(interval)
        try:
            run_auto_check()
        except Exception:
            logger.exception("Cookie 自动巡检异常")


_auto_started = threading.Lock()
_auto_thread = None


def start_auto_inspector(interval=AUTO_CHECK_INTERVAL_SECONDS):
    """启动自动巡检守护线程（幂等，testing 环境由调用方跳过）。"""
    global _auto_thread
    with _auto_started:
        if _auto_thread and _auto_thread.is_alive():
            return
        _auto_thread = threading.Thread(
            target=_auto_loop, args=(interval,), daemon=True, name="cookie-auto-inspector",
        )
        _auto_thread.start()
