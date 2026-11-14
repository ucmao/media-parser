"""巨量代理库存与平台窗口；通过 SQLite 短事务协调同容器内的工作进程。"""

import ipaddress
import os
import re
import sqlite3
import threading
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime

import requests
from urllib3.util import Timeout

from configs.logging_config import get_logger

logger = get_logger(__name__)
PROXY_MODES = ("auto", "always")
DEFAULT_POOL_SIZE = 2
MAX_POOL_SIZE = 100
DEFAULT_FETCH_PER_SECOND = 1
MAX_FETCH_PER_SECOND = 20


def _bounded_int(value, default, minimum, maximum):
    try:
        return max(minimum, min(int(str(value).strip()), maximum))
    except (TypeError, ValueError):
        return default


SCHEMA = """
CREATE TABLE IF NOT EXISTS proxy_platform_windows (
    platform TEXT PRIMARY KEY, until_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS proxy_addresses (
    address TEXT PRIMARY KEY, expires_at REAL NOT NULL,
    created_at REAL NOT NULL, invalid INTEGER NOT NULL DEFAULT 0,
    retired INTEGER NOT NULL DEFAULT 0, last_used REAL NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS proxy_coordination (
    id INTEGER PRIMARY KEY CHECK(id=1), owner TEXT,
    lease_until REAL NOT NULL DEFAULT 0, next_fetch REAL NOT NULL DEFAULT 0,
    failures INTEGER NOT NULL DEFAULT 0
);
INSERT OR IGNORE INTO proxy_coordination(id) VALUES(1);
CREATE TABLE IF NOT EXISTS proxy_active_uses (
    token TEXT PRIMARY KEY, until_at REAL NOT NULL
);
"""


@dataclass(frozen=True)
class ProxyAddress:
    address: str
    expires_at: float

    @property
    def url(self):
        return f"http://{self.address}"


class ProxyManager:
    def __init__(self, database, api_url, mode=None, pool_size=None, fetch_per_second=None):
        self.database = database
        self.api_url = api_url
        # 环境变量层默认值；后台 system_settings 中的同名配置优先。
        self.default_mode = mode
        self.default_pool_size = pool_size
        self.default_fetch_per_second = fetch_per_second
        self._thread = None
        self._pid = None
        self._start_lock = threading.Lock()
        self._stop = threading.Event()
        self._wake = threading.Event()
        with self.connection() as db:
            db.executescript(SCHEMA)
            columns = {row["name"] for row in db.execute("PRAGMA table_info(proxy_addresses)")}
            if "last_used" not in columns:
                # 旧库升级：轮换分配依赖最近分配时间。
                db.execute("ALTER TABLE proxy_addresses ADD COLUMN last_used REAL NOT NULL DEFAULT 0")

    def get_active_api_url(self):
        """三级优先级：后台在线配置 (system_settings) > .env 环境变量 > 留空"""
        try:
            with self.connection() as db:
                row = db.execute(
                    "SELECT value FROM system_settings WHERE key IN ('dynamic_proxy_api_url', 'cookie_dynamic_proxy_api_url') AND value != '' LIMIT 1"
                ).fetchone()
                if row and row["value"].strip():
                    return row["value"].strip()
        except Exception:
            pass
        return (self.api_url or "").strip()

    @property
    def switch_on(self):
        """后台代理总开关；从未保存过时沿用旧行为：填了提取 URL 即视为开启。"""
        value = self._setting("proxy_enabled", None)
        if value is None:
            return bool(self.get_active_api_url())
        return value == "1"

    @property
    def enabled(self):
        return self.switch_on and bool(self.get_active_api_url())

    def _setting(self, key, default):
        """后台在线配置 (system_settings) > 构造参数（来自 .env）> 内置默认。"""
        try:
            with self.connection() as db:
                row = db.execute("SELECT value FROM system_settings WHERE key=?", (key,)).fetchone()
                if row and str(row["value"]).strip():
                    return str(row["value"]).strip()
        except Exception:
            pass
        return default

    @property
    def mode(self):
        value = str(self._setting("proxy_mode", self.default_mode) or "").strip().lower()
        return value if value in PROXY_MODES else "auto"

    @property
    def always(self):
        return self.mode == "always" and self.enabled

    @property
    def pool_size(self):
        return _bounded_int(
            self._setting("proxy_pool_size", self.default_pool_size), DEFAULT_POOL_SIZE, 1, MAX_POOL_SIZE
        )

    @property
    def fetch_interval(self):
        rate = _bounded_int(
            self._setting("proxy_fetch_per_second", self.default_fetch_per_second),
            DEFAULT_FETCH_PER_SECOND, 1, MAX_FETCH_PER_SECOND,
        )
        return 1.0 / rate

    @contextmanager
    def connection(self, write=False):
        # 独立连接，避免与请求积分事务或 Flask 的线程局部连接互相干扰。
        db = sqlite3.connect(self.database, timeout=1, isolation_level=None)
        db.row_factory = sqlite3.Row
        try:
            if write:
                db.execute("BEGIN IMMEDIATE")
            yield db
            if write:
                db.commit()
        except Exception:
            if write:
                db.rollback()
            raise
        finally:
            db.close()

    def active(self, platform):
        if self.always:
            # 始终走代理：从短链展开起即使用代理，未知平台同样适用。
            return True
        if not self.enabled or not platform:
            return False
        with self.connection() as db:
            row = db.execute(
                "SELECT until_at FROM proxy_platform_windows WHERE platform=?", (platform,)
            ).fetchone()
        return bool(row and row["until_at"] > time.time())

    def activate(self, platform):
        if self.always:
            return
        now = time.time()
        with self.connection(write=True) as db:
            changed = db.execute(
                "INSERT INTO proxy_platform_windows(platform, until_at) VALUES(?, ?) "
                "ON CONFLICT(platform) DO UPDATE SET until_at=excluded.until_at "
                "WHERE proxy_platform_windows.until_at<=?",
                (platform, now + 900, now),
            ).rowcount
        if changed:
            logger.info("平台切换代理访问：%s，持续 900 秒", platform)
        self._wake.set()

    def begin_use(self, remaining):
        token = uuid.uuid4().hex
        with self.connection(write=True) as db:
            db.execute("INSERT INTO proxy_active_uses VALUES(?, ?)", (token, time.time() + remaining))
        return token

    def end_use(self, token):
        with self.connection(write=True) as db:
            db.execute("DELETE FROM proxy_active_uses WHERE token=?", (token,))

    def available(self, excluded=()):
        """按最近分配时间轮换：每次解析领取最久未分配的地址，跨进程分散到整个池。"""
        now = time.time()
        with self.connection(write=True) as db:
            rows = db.execute(
                "SELECT address, expires_at FROM proxy_addresses "
                "WHERE invalid=0 AND retired=0 AND expires_at>? ORDER BY last_used, created_at, address",
                (now + 10,),
            ).fetchall()
            for row in rows:
                if row["address"] not in excluded:
                    db.execute("UPDATE proxy_addresses SET last_used=? WHERE address=?", (now, row["address"]))
                    return ProxyAddress(row["address"], row["expires_at"])
        return None

    def valid(self, proxy):
        with self.connection() as db:
            row = db.execute(
                "SELECT invalid, expires_at FROM proxy_addresses WHERE address=?", (proxy.address,)
            ).fetchone()
        # 退休仅停止分配，进行中的尝试仍可使用到有效期结束。
        return bool(row and not row["invalid"] and row["expires_at"] > time.time())

    def invalidate(self, proxy, reason):
        with self.connection(write=True) as db:
            changed = db.execute(
                "UPDATE proxy_addresses SET invalid=1 WHERE address=? AND invalid=0", (proxy.address,)
            ).rowcount
        if changed:
            logger.info("剔除代理 %s：%s", proxy.address, reason)
        self._wake.set()

    @staticmethod
    def decode(payload, started):
        """通用代理解码器：支持 巨量、芝麻、青果、Data5U、多米 等各种 JSON 结构以及 TXT 文本。"""
        ip = None
        port = None
        remain = None

        # 1. 如果输入为纯文本 TXT（或字符串格式）
        if isinstance(payload, str):
            match = re.search(r"(\d{1,3}(?:\.\d{1,3}){3}):(\d{1,5})", payload)
            if match:
                ip = match.group(1)
                port = int(match.group(2))
                remain = 300.0

        # 2. 如果输入为 JSON (dict)
        elif isinstance(payload, dict):
            # 校验响应 Code / Status
            code = payload.get("code")
            success = payload.get("success")
            valid_code = code in (200, 0, "200", "0", "SUCCESS") or success is True
            if not valid_code and code is not None:
                raise ValueError(f"代理供应商返回失败: code={code}, msg={payload.get('msg') or payload.get('message')}")

            # 寻找代理列表项 (兼容不同数据节点的层级)
            rows = None
            data_field = payload.get("data")
            if isinstance(data_field, dict):
                rows = data_field.get("proxy_list") or data_field.get("list") or data_field.get("proxies") or [data_field]
            elif isinstance(data_field, list):
                rows = data_field
            elif isinstance(payload.get("proxy_list"), list):
                rows = payload.get("proxy_list")

            if isinstance(rows, list) and len(rows) > 0 and isinstance(rows[0], dict):
                row = rows[0]
                ip = str(row.get("ip") or row.get("outip") or row.get("server") or row.get("host") or "")
                port = int(row.get("port") or row.get("server_port") or 0)

                # 解析有效期 (ip_remain / ttl / expire_seconds / expire_time / deadline)
                has_explicit_remain = "ip_remain" in row or "ttl" in row or "expire_seconds" in row
                raw_remain = row.get("ip_remain") if "ip_remain" in row else (row.get("ttl") if "ttl" in row else row.get("expire_seconds"))

                if has_explicit_remain:
                    try:
                        remain = float(raw_remain)
                    except (ValueError, TypeError):
                        raise ValueError("代理端口或有效期无效")
                else:
                    exp_val = row.get("expire_time") or row.get("deadline")
                    if isinstance(exp_val, (int, float)) and exp_val > 1000000000:
                        remain = float(exp_val) - started
                    elif isinstance(exp_val, str):
                        try:
                            dt = datetime.strptime(exp_val.strip(), "%Y-%m-%d %H:%M:%S")
                            remain = dt.timestamp() - started
                        except ValueError:
                            pass

                if remain is None:
                    remain = 300.0  # 其它未明示有效期的结构给保底默认 5 分钟

        if not ip or not port:
            raise ValueError("未能提取到有效的代理 IP/端口")

        ip = str(ipaddress.IPv4Address(ip))
        if not 1 <= port <= 65535 or not 10 < remain < float("inf"):
            raise ValueError("代理端口或有效期无效")

        expires = started + remain
        if expires <= time.time() + 10:
            raise ValueError("代理剩余有效期不足")
        return ProxyAddress(f"{ip}:{port}", expires)

    def replenish(self, deadline):
        """领取一次提取租约；返回是否实际调用供应商，便于请求计数。"""
        if not self.enabled or deadline - time.monotonic() <= 0:
            return False
        now = time.time()
        owner = uuid.uuid4().hex
        pool_size = self.pool_size
        interval = self.fetch_interval
        with self.connection(write=True) as db:
            db.execute("DELETE FROM proxy_addresses WHERE expires_at<=?", (now,))
            db.execute("UPDATE proxy_addresses SET retired=1 WHERE expires_at<=?", (now + 20,))
            count = db.execute(
                "SELECT count(*) FROM proxy_addresses WHERE invalid=0 AND retired=0"
            ).fetchone()[0]
            row = db.execute("SELECT * FROM proxy_coordination WHERE id=1").fetchone()
            if count >= pool_size or row["lease_until"] > now or row["next_fetch"] > now:
                return False
            db.execute(
                "UPDATE proxy_coordination SET owner=?, lease_until=?, next_fetch=? WHERE id=1",
                (owner, now + 8, now + interval),
            )
        proxy = None
        try:
            # 不继承服务环境中的 HTTP_PROXY，供应商请求必须直连。
            with requests.Session() as session:
                session.trust_env = False
                budget = min(5, deadline - time.monotonic())
                if budget <= 0:
                    raise ValueError("解析预算已耗尽")
                active_url = self.get_active_api_url()
                if not active_url:
                    raise ValueError("代理提取 API URL 未配置")
                response = session.get(
                    active_url, timeout=Timeout(total=budget, connect=min(2, budget), read=budget),
                )
                response.raise_for_status()
                try:
                    payload = response.json()
                except ValueError:
                    payload = response.text
                proxy = self.decode(payload, now)
        except (requests.RequestException, ValueError, TypeError, KeyError, AttributeError):
            # 不记录完整异常，避免将含签名的提取 URL 写入日志。
            logger.warning("代理提取失败：网络、供应商状态或响应字段异常")
        with self.connection(write=True) as db:
            row = db.execute("SELECT * FROM proxy_coordination WHERE id=1").fetchone()
            if row["owner"] != owner:
                return True
            accepted = False
            if proxy and proxy.expires_at > time.time() + 10:
                existing = db.execute(
                    "SELECT * FROM proxy_addresses WHERE address=?", (proxy.address,)
                ).fetchone()
                if not existing:
                    db.execute("INSERT INTO proxy_addresses(address, expires_at, created_at) VALUES(?, ?, ?)",
                               (proxy.address, proxy.expires_at, now))
                    accepted = True
                # 重复地址不延长旧 IP 的寿命，也不复活已剔除的地址。
            failures = 0 if accepted else row["failures"] + 1
            delay = interval if accepted else (1, 2, 4, 8, 15)[min(failures - 1, 4)]
            db.execute(
                "UPDATE proxy_coordination SET owner=NULL, lease_until=0, next_fetch=?, failures=? WHERE id=1",
                (max(now + interval, time.time() + (0 if accepted else delay)), failures),
            )
        if accepted:
            logger.info("已补充代理 %s，剩余有效期 %.0f 秒", proxy.address, proxy.expires_at - time.time())
        return True

    def maintain_once(self):
        now = time.time()
        with self.connection(write=True) as db:
            expired = db.execute("SELECT platform FROM proxy_platform_windows WHERE until_at<=?", (now,)).fetchall()
            db.execute("DELETE FROM proxy_platform_windows WHERE until_at<=?", (now,))
            db.execute("DELETE FROM proxy_active_uses WHERE until_at<=?", (now,))
            needed = db.execute("SELECT 1 FROM proxy_platform_windows LIMIT 1").fetchone() or db.execute(
                "SELECT 1 FROM proxy_active_uses LIMIT 1"
            ).fetchone()
        # 始终走代理时持续维持库存，避免高峰请求同步等待提取。
        needed = needed or self.always
        for row in expired:
            logger.info("平台恢复直接访问：%s", row["platform"])
        if needed:
            self.replenish(time.monotonic() + 5)

    def start(self):
        if not self.enabled:
            return
        with self._start_lock:
            if self._pid == os.getpid() and self._thread and self._thread.is_alive():
                return
            self._pid = os.getpid()
            self._stop = threading.Event()
            self._thread = threading.Thread(target=self._maintain, daemon=True, name="proxy-maintenance")
            self._thread.start()

    def _maintain(self):
        while not self._stop.is_set():
            try:
                self.maintain_once()
            except Exception:
                logger.exception("代理库存维护异常")
            self._wake.wait(min(1.0, self.fetch_interval))
            self._wake.clear()

    def stop(self):
        self._stop.set()
        self._wake.set()
        if self._thread:
            self._thread.join(timeout=6)
