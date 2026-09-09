import random
import re
import sys
import time

from flask import current_app, has_app_context, request, session

from src.auth import hash_api_key, legacy_hash_api_key, user_is_expired
from src.db import get_db, setting, transaction, utcnow


class SQLiteRateLimiter:
    """使用 SQLite 原子事务在所有 Gunicorn worker 之间共享限流状态。"""

    def consume_many(self, limits):
        normalized = []
        for subject, limit, window_seconds in limits:
            try:
                parsed_limit = int(limit)
                parsed_window = max(1, int(window_seconds))
            except (TypeError, ValueError):
                continue
            if parsed_limit > 0:
                normalized.append((str(subject), parsed_limit, parsed_window))
        if not normalized:
            return None

        now_time = int(time.time())
        exceeded = None
        with transaction(immediate=True) as db:
            for subject, limit, window_seconds in normalized:
                bucket_start = (now_time // window_seconds) * window_seconds
                bucket_subject = f"{subject}:{window_seconds}"
                db.execute(
                    "INSERT INTO rate_limit_buckets(subject,bucket_second,count) VALUES(?,?,1) "
                    "ON CONFLICT(subject,bucket_second) DO UPDATE SET count=count+1",
                    (bucket_subject, bucket_start),
                )
                count = db.execute(
                    "SELECT count FROM rate_limit_buckets WHERE subject=? AND bucket_second=?",
                    (bucket_subject, bucket_start),
                ).fetchone()["count"]
                if exceeded is None and count > limit:
                    exceeded = (subject, limit)

            if random.randint(1, 100) == 1:
                db.execute(
                    "DELETE FROM rate_limit_buckets WHERE bucket_second < ?",
                    (now_time - 86400,),
                )
        return exceeded

    def consume(self, subject, limit, window_seconds=1):
        return self.consume_many([(subject, limit, window_seconds)]) is None

    def reset(self):
        if has_app_context():
            db = get_db()
            db.execute("DELETE FROM rate_limit_buckets")
            db.commit()


rate_limiter = SQLiteRateLimiter()


_URL_PATTERN = re.compile(r"https?://[^\s<>\"']+", re.IGNORECASE)


def sanitize_log_url(value):
    """提取用户提交的原始链接，供运行日志持久化。"""
    if not isinstance(value, str):
        return None
    match = _URL_PATTERN.search(value.strip())
    if not match:
        return None
    return match.group(0).rstrip(".,;:!?)]}，。；：！？）】》")[:4096]


def _request_log_url():
    value = request.args.get("url") or request.args.get("text")
    if value is None and request.form:
        value = request.form.get("url") or request.form.get("text")
    if value is None and request.is_json:
        payload = request.get_json(silent=True) or {}
        if isinstance(payload, dict):
            value = payload.get("url") or payload.get("text")
    return sanitize_log_url(value)


def consume_rate_limit(subject, limit, window_seconds=1):
    return rate_limiter.consume(subject, limit, window_seconds)


def consume_rate_limits(limits):
    return rate_limiter.consume_many(limits)


def get_client_ip():
    if current_app.config.get("TRUST_PROXY_HEADERS"):
        forwarded = request.headers.get("X-Forwarded-For", "")
        if forwarded:
            return forwarded.split(",")[0].strip()
    return request.remote_addr or "127.0.0.1"


def authenticate_api_key():
    authorization = request.headers.get("Authorization", "")
    raw_key = authorization[7:].strip() if authorization.lower().startswith("bearer ") else request.args.get("key", "").strip()
    if not raw_key:
        return None, (401, "请提供 API Key", "API_KEY_REQUIRED")
    db = get_db()
    row = db.execute(
        "SELECT k.*, u.username, u.role, u.active user_active, u.expires_at, u.qps_limit user_qps, u.credits user_credits "
        "FROM api_keys k JOIN users u ON u.id=k.user_id WHERE k.key_hash=?",
        (hash_api_key(raw_key),),
    ).fetchone()
    if row is None:
        legacy_hash = legacy_hash_api_key(raw_key)
        if legacy_hash:
            row = db.execute(
                "SELECT k.*, u.username, u.role, u.active user_active, u.expires_at, u.qps_limit user_qps, u.credits user_credits "
                "FROM api_keys k JOIN users u ON u.id=k.user_id WHERE k.key_hash=?",
                (legacy_hash,),
            ).fetchone()
    if row is None:
        user_id = session.get("user_id")
        if user_id:
            clean_prefix = raw_key.rstrip(".").rstrip("•").strip()
            if clean_prefix:
                # 仅允许使用当前登录账号自己创建的 Key 进行在线调试（即使是管理员也不允许越权使用客户 Key）
                row = db.execute(
                    "SELECT k.*, u.username, u.role, u.active user_active, u.expires_at, u.qps_limit user_qps, u.credits user_credits "
                    "FROM api_keys k JOIN users u ON u.id=k.user_id WHERE k.key_prefix=? AND k.user_id=?",
                    (clean_prefix, user_id),
                ).fetchone()
    if row is None:
        return None, (401, "API Key 无效", "INVALID_API_KEY")
    if not row["active"] or not row["user_active"]:
        return None, (403, "API Key 或账号已停用", "API_KEY_DISABLED")
    if user_is_expired(row):
        return None, (403, "账号尚未开通或已到期", "ACCOUNT_EXPIRED")
    if row["role"] != "admin" and row["user_credits"] is not None and row["user_credits"] != -1 and row["user_credits"] <= 0:
        return None, (402, "账号解析积分已耗尽，请联系管理员充值", "INSUFFICIENT_CREDITS")
    limits = [(f"user:{row['user_id']}", row["user_qps"], 1)]
    if row["qps_limit"]:
        limits.append((f"key:{row['id']}", row["qps_limit"], 1))
    exceeded = consume_rate_limits(limits)
    if exceeded:
        subject, limit = exceeded
        level = "账号" if subject.startswith("user:") else "API Key"
        return None, (429, f"请求过于频繁，当前{level}限制为 {limit} QPS", "RATE_LIMITED")
    db.execute("UPDATE api_keys SET last_used_at=? WHERE id=?", (utcnow(), row["id"]))
    db.commit()
    return row, None


def platform_access(platform):
    row = get_db().execute(
        "SELECT enabled,qps_limit FROM platform_settings WHERE platform=?", (platform,)
    ).fetchone()
    if row is not None and not row["enabled"]:
        return 503, f"{platform} 接口维护中", "PLATFORM_DISABLED"
    if row is not None and row["qps_limit"]:
        if not consume_rate_limit(f"platform:{platform}", row["qps_limit"]):
            return 429, f"{platform} 接口请求过于频繁", "PLATFORM_RATE_LIMITED"
    return None


def global_api_enabled():
    return setting("global_api_enabled", "1") == "1"


def demo_enabled():
    return setting("demo_enabled", "1") == "1"


def record_request(access, platform, path, status_code, error_code, duration_ms):
    if (current_app and (current_app.testing or current_app.config.get("TESTING"))) or "unittest" in sys.modules or "pytest" in sys.modules:
        return
    db = get_db()
    db.execute(
        "INSERT INTO request_logs(user_id,api_key_id,platform,path,status_code,error_code,duration_ms,input_url,created_at) "
        "VALUES(?,?,?,?,?,?,?,?,?)",
        (
            access["user_id"] if access else None,
            access["id"] if access else None,
            platform,
            path,
            status_code,
            error_code,
            duration_ms,
            _request_log_url(),
            utcnow(),
        ),
    )
    db.commit()
