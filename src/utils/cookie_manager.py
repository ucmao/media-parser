import os
from contextlib import contextmanager
from contextvars import ContextVar


_cookie_suppressed = ContextVar("cookie_suppressed", default=False)


def cookies_suppressed():
    return _cookie_suppressed.get()


@contextmanager
def without_platform_cookies():
    """仅在当前解析上下文禁用凭据，不影响并发请求及已导入的函数引用。"""
    token = _cookie_suppressed.set(True)
    try:
        yield
    finally:
        _cookie_suppressed.reset(token)

# 平台 Cookie 环境变量及别名映射表
PLATFORM_COOKIE_ALIASES = {
    "xhs": ["XIAOHONGSHU_COOKIE", "XHS_COOKIE"],
    "xiaohongshu": ["XIAOHONGSHU_COOKIE", "XHS_COOKIE"],
    "pinduoduo": ["PINDUODUO_COOKIE", "PDD_COOKIE"],
    "douyin": ["DOUYIN_COOKIE", "DY_COOKIE"],
    "yuanbao": ["YUANBAO_COOKIE", "WECHAT_CHANNELS_COOKIE"],
    "wechat_channels": ["YUANBAO_COOKIE", "WECHAT_CHANNELS_COOKIE"],
    "doubao": ["DOUBAO_COOKIE"],
    "jimeng": ["JIMENG_COOKIE"],
    "weibo": ["WEIBO_COOKIE"],
    "kuaishou": ["KUAISHOU_COOKIE", "KS_COOKIE"],
    "zhihu": ["ZHIHU_COOKIE"],
}


def clean_cookie_quotes(val: str) -> str:
    val = val.strip()
    if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
        val = val[1:-1].strip()
    return val


def get_platform_cookie(platform_key: str, env_var: str | None = None) -> str:
    """获取指定平台的 Cookie 凭据。

    按优先级依次检查：
    1. 后台数据库系统配置 (system_settings 表中的 cookie_{platform})；
    2. 指定的环境变量 (如 env_var="XIAOHONGSHU_COOKIE")；
    3. 标准环境变量 ({PLATFORM}_COOKIE)；
    4. 别名列表 (如 XHS_COOKIE)。
    """
    if cookies_suppressed():
        return ""
    key_normalized = platform_key.lower().replace("-", "_")

    # 1. 优先读取后台系统设置 (数据库)
    db_keys = [f"cookie_{key_normalized}"]
    for alias in PLATFORM_COOKIE_ALIASES.get(key_normalized, []):
        alias_name = alias.lower().replace("_cookie", "").replace("cookie_", "")
        if alias_name and f"cookie_{alias_name}" not in db_keys:
            db_keys.append(f"cookie_{alias_name}")

    try:
        from src.db import setting
        for db_key in db_keys:
            val = setting(db_key)
            if val is not None and str(val).strip():
                return clean_cookie_quotes(str(val))
    except Exception:
        pass

    # 2. 检查指定环境变量
    if env_var is None:
        env_var = f"{key_normalized.upper()}_COOKIE"

    val = os.getenv(env_var, "").strip()
    if val:
        return clean_cookie_quotes(val)

    # 3. 检查别名列表
    for alias in PLATFORM_COOKIE_ALIASES.get(key_normalized, []):
        val = os.getenv(alias, "").strip()
        if val:
            return clean_cookie_quotes(val)

    return ""
