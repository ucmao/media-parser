import os
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch

from app import create_app
from src.auth import hash_api_key
from src.api.access import SQLiteRateLimiter, get_client_ip, sanitize_log_url
from src.db import get_db, reserve_user_credit, utcnow


class ManagementTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.app = create_app({
            "TESTING": True,
            "SECRET_KEY": "test-secret",
            "DATABASE": os.path.join(self.temp_dir.name, "test.db"),
        })
        self.client = self.app.test_client()

    def tearDown(self):
        self.temp_dir.cleanup()

    def csrf(self):
        with self.client.session_transaction() as session:
            session["csrf_token"] = "test-csrf"
        return "test-csrf"

    def create_customer_and_key(self, qps=2, expires=True):
        raw_key = "mp_test_key_123456789"
        with self.app.app_context():
            db = get_db()
            expires_at = (
                (datetime.now(timezone.utc) + timedelta(days=1)).isoformat(timespec="seconds")
                if expires else None
            )
            cursor = db.execute(
                "INSERT INTO users(username,password_hash,expires_at,qps_limit,created_at) VALUES(?,?,?,?,?)",
                ("customer", "unused", expires_at, qps, utcnow()),
            )
            user_id = cursor.lastrowid
            cursor = db.execute(
                "INSERT INTO api_keys(user_id,name,key_hash,key_prefix,created_at) VALUES(?,?,?,?,?)",
                (user_id, "test", hash_api_key(raw_key), raw_key[:11], utcnow()),
            )
            key_id = cursor.lastrowid
            db.commit()
        return raw_key, user_id, key_id

    @staticmethod
    def parser():
        parser = Mock()
        parser.get_title_content.return_value = "测试"
        parser.get_real_video_url.return_value = "https://example.com/a.mp4"
        parser.get_video_list.return_value = []
        parser.get_cover_photo_url.return_value = None
        parser.get_author_info.return_value = None
        parser.get_image_list.return_value = []
        parser.get_audio_url.return_value = None
        parser.get_subtitles.return_value = None
        return parser

    def test_first_admin_setup_and_login(self):
        response = self.client.post(
            "/auth/setup",
            data={"csrf_token": self.csrf(), "username": "admin", "password": "password123", "confirm_password": "password123"},
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("管理员创建成功", response.get_data(as_text=True))
        response = self.client.post(
            "/auth/login",
            data={"csrf_token": self.csrf(), "username": "admin", "password": "password123"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.location.endswith("/admin"))

    def test_login_remember_me_controls_session_permanence(self):
        self.client.post(
            "/auth/setup",
            data={"csrf_token": self.csrf(), "username": "admin", "password": "password123", "confirm_password": "password123"},
        )
        # Without remember_me
        with self.client:
            self.client.post(
                "/auth/login",
                data={"csrf_token": self.csrf(), "username": "admin", "password": "password123"},
            )
            from flask import session
            self.assertFalse(session.permanent)

        # With remember_me
        with self.client:
            self.client.post(
                "/auth/login",
                data={"csrf_token": self.csrf(), "username": "admin", "password": "password123", "remember_me": "1"},
            )
            from flask import session
            self.assertTrue(session.permanent)

    def test_setup_rejects_missing_csrf_token(self):
        response = self.client.post(
            "/auth/setup",
            data={"username": "attacker", "password": "password123", "confirm_password": "password123"},
        )
        self.assertEqual(response.status_code, 200)
        with self.app.app_context():
            admin = get_db().execute("SELECT 1 FROM users WHERE role='admin'").fetchone()
        self.assertIsNone(admin)

    def test_authenticated_management_rejects_missing_csrf_token(self):
        self.client.post(
            "/auth/setup",
            data={"csrf_token": self.csrf(), "username": "admin", "password": "password123", "confirm_password": "password123"},
        )
        self.client.post(
            "/auth/login",
            data={"csrf_token": self.csrf(), "username": "admin", "password": "password123"},
        )
        response = self.client.post("/admin/settings", data={"global_api_enabled": "0"})
        self.assertEqual(response.status_code, 302)
        with self.app.app_context():
            from src.db import setting
            self.assertEqual(setting("global_api_enabled"), "1")

    def test_secret_key_is_generated_and_reused(self):
        database = os.path.join(self.temp_dir.name, "auto-secret.db")
        first = create_app({"TESTING": True, "DATABASE": database, "SECRET_KEY": None})
        second = create_app({"TESTING": True, "DATABASE": database, "SECRET_KEY": None})
        self.assertTrue(first.config["SECRET_KEY"])
        self.assertEqual(first.config["SECRET_KEY"], second.config["SECRET_KEY"])

    def test_api_key_is_required(self):
        response = self.client.get("/api/v1/parse?url=https://example.com")
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.get_json()["error_code"], "API_KEY_REQUIRED")

    def test_unconfigured_expiry_rejects_key(self):
        raw_key, _, _ = self.create_customer_and_key(expires=False)
        response = self.client.get("/api/v1/parse", query_string={"key": raw_key, "url": "https://example.com"})
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.get_json()["error_code"], "ACCOUNT_EXPIRED")

    def test_valid_key_can_call_get_api(self):
        raw_key, _, _ = self.create_customer_and_key()
        with patch("src.api.parse.WebFetcher.fetch_redirect_url", return_value="https://www.douyin.com/video/1"), patch(
            "src.api.parse.ParserFactory.create_parser", return_value=self.parser()
        ):
            response = self.client.get("/api/v1/parse", query_string={"key": raw_key, "url": "https://example.com"})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_json()["succ"])

    def test_key_qps_limit_is_enforced(self):
        raw_key, _, key_id = self.create_customer_and_key(qps=10)
        with self.app.app_context():
            db = get_db()
            db.execute("UPDATE api_keys SET qps_limit=1 WHERE id=?", (key_id,))
            db.commit()
        with patch("src.api.access.time.time", return_value=123456), patch(
            "src.api.parse.WebFetcher.fetch_redirect_url", return_value="https://www.douyin.com/video/1"
        ), patch("src.api.parse.ParserFactory.create_parser", return_value=self.parser()):
            first = self.client.get("/api/v1/parse", query_string={"key": raw_key, "url": "https://example.com"})
            second = self.client.get("/api/v1/parse", query_string={"key": raw_key, "url": "https://example.com"})
        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 429)
        self.assertEqual(second.get_json()["error_code"], "RATE_LIMITED")

    def test_user_qps_is_shared_by_all_of_the_users_keys(self):
        raw_key, user_id, _ = self.create_customer_and_key(qps=1)
        second_key = "mp_second_key_123456789"
        with self.app.app_context():
            db = get_db()
            db.execute(
                "INSERT INTO api_keys(user_id,name,key_hash,key_prefix,created_at) VALUES(?,?,?,?,?)",
                (user_id, "second", hash_api_key(second_key), second_key[:11], utcnow()),
            )
            db.commit()
        with patch("src.api.access.time.time", return_value=123456), patch(
            "src.api.parse.WebFetcher.fetch_redirect_url", return_value="https://www.douyin.com/video/1"
        ), patch("src.api.parse.ParserFactory.create_parser", return_value=self.parser()):
            first = self.client.get("/api/v1/parse", query_string={"key": raw_key, "url": "https://example.com"})
            second = self.client.get("/api/v1/parse", query_string={"key": second_key, "url": "https://example.com"})
        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 429)
        self.assertIn("账号限制", second.get_json()["retdesc"])

    def test_platform_qps_is_shared_by_different_users(self):
        first_key, _, _ = self.create_customer_and_key(qps=10)
        second_key = "mp_other_user_key_123456"
        with self.app.app_context():
            db = get_db()
            expires_at = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat(timespec="seconds")
            cursor = db.execute(
                "INSERT INTO users(username,password_hash,expires_at,qps_limit,created_at) VALUES(?,?,?,?,?)",
                ("other_customer", "unused", expires_at, 10, utcnow()),
            )
            db.execute(
                "INSERT INTO api_keys(user_id,name,key_hash,key_prefix,created_at) VALUES(?,?,?,?,?)",
                (cursor.lastrowid, "other", hash_api_key(second_key), second_key[:11], utcnow()),
            )
            db.execute("INSERT INTO platform_settings(platform,enabled,qps_limit) VALUES('抖音',1,1)")
            db.commit()
        with patch("src.api.access.time.time", return_value=123456), patch(
            "src.api.parse.WebFetcher.fetch_redirect_url", return_value="https://www.douyin.com/video/1"
        ), patch("src.api.parse.ParserFactory.create_parser", return_value=self.parser()):
            first = self.client.get("/api/v1/parse", query_string={"key": first_key, "url": "https://example.com"})
            second = self.client.get("/api/v1/parse", query_string={"key": second_key, "url": "https://example.com"})
        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 429)
        self.assertEqual(second.get_json()["error_code"], "PLATFORM_RATE_LIMITED")

    def test_rate_limit_state_is_shared_between_app_instances(self):
        limiter = SQLiteRateLimiter()
        with patch("src.api.access.time.time", return_value=123456):
            with self.app.app_context():
                self.assertTrue(limiter.consume("shared:test", 1))
            second_app = create_app({
                "TESTING": True,
                "SECRET_KEY": "test-secret",
                "DATABASE": self.app.config["DATABASE"],
            })
            with second_app.app_context():
                self.assertFalse(SQLiteRateLimiter().consume("shared:test", 1))

    def test_forwarded_ip_is_only_used_for_trusted_proxies(self):
        headers = {"X-Forwarded-For": "203.0.113.10, 10.0.0.1"}
        with self.app.test_request_context("/", headers=headers, environ_base={"REMOTE_ADDR": "192.0.2.10"}):
            self.app.config["TRUST_PROXY_HEADERS"] = False
            self.assertEqual(get_client_ip(), "192.0.2.10")
            self.app.config["TRUST_PROXY_HEADERS"] = True
            self.assertEqual(get_client_ip(), "203.0.113.10")

    def test_login_attempts_are_rate_limited_by_username(self):
        self.client.post(
            "/auth/setup",
            data={"csrf_token": self.csrf(), "username": "admin", "password": "password123", "confirm_password": "password123"},
        )
        with patch("src.api.access.time.time", return_value=123456):
            for _ in range(10):
                response = self.client.post(
                    "/auth/login",
                    data={"csrf_token": self.csrf(), "username": "admin", "password": "wrong-password"},
                )
                self.assertEqual(response.status_code, 200)
            limited = self.client.post(
                "/auth/login",
                data={"csrf_token": self.csrf(), "username": "admin", "password": "wrong-password"},
            )
        self.assertEqual(limited.status_code, 429)
        self.assertIn("登录尝试过于频繁", limited.get_data(as_text=True))

    def test_registration_attempts_are_rate_limited_by_ip(self):
        with patch("src.api.access.time.time", return_value=123456):
            for _ in range(5):
                response = self.client.post(
                    "/auth/register",
                    data={"csrf_token": self.csrf(), "username": "candidate", "password": "password123", "confirm_password": "different"},
                )
                self.assertEqual(response.status_code, 200)
            limited = self.client.post(
                "/auth/register",
                data={"csrf_token": self.csrf(), "username": "candidate", "password": "password123", "confirm_password": "different"},
            )
        self.assertEqual(limited.status_code, 429)
        self.assertIn("注册尝试过于频繁", limited.get_data(as_text=True))

    def test_disabled_platform_is_rejected(self):
        raw_key, _, _ = self.create_customer_and_key()
        with self.app.app_context():
            db = get_db()
            db.execute("INSERT INTO platform_settings(platform,enabled) VALUES('抖音',0)")
            db.commit()
        with patch("src.api.parse.WebFetcher.fetch_redirect_url", return_value="https://www.douyin.com/video/1"):
            response = self.client.get("/api/v1/parse", query_string={"key": raw_key, "url": "https://example.com"})
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.get_json()["error_code"], "PLATFORM_DISABLED")


    def test_registration_assigns_default_trial_days(self):
        # Mismatched password failure test
        mismatch = self.client.post(
            "/auth/register",
            data={"csrf_token": self.csrf(), "username": "mismatch_user", "password": "password123", "confirm_password": "differentpassword"},
            follow_redirects=True,
        )
        self.assertIn("两次输入的密码不一致", mismatch.get_data(as_text=True))

        response = self.client.post(
            "/auth/register",
            data={"csrf_token": self.csrf(), "username": "new_trial_user", "password": "password123", "confirm_password": "password123"},
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("7 天免费试用", response.get_data(as_text=True))
        with self.app.app_context():
            user = get_db().execute("SELECT * FROM users WHERE username='new_trial_user'").fetchone()
            self.assertIsNotNone(user["expires_at"])

    def test_legacy_key_hash_compatibility(self):
        import hashlib, hmac
        raw_key = "mp_legacy_key_99999"
        legacy_hash = hmac.new(b"test-secret", raw_key.encode(), hashlib.sha256).hexdigest()
        with self.app.app_context():
            db = get_db()
            expires_at = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat(timespec="seconds")
            cursor = db.execute(
                "INSERT INTO users(username,password_hash,expires_at,qps_limit,created_at) VALUES(?,?,?,?,?)",
                ("legacy_user", "unused", expires_at, 10, utcnow()),
            )
            user_id = cursor.lastrowid
            db.execute(
                "INSERT INTO api_keys(user_id,name,key_hash,key_prefix,created_at) VALUES(?,?,?,?,?)",
                (user_id, "legacy", legacy_hash, raw_key[:11], utcnow()),
            )
            db.commit()

        with patch("src.api.parse.WebFetcher.fetch_redirect_url", return_value="https://www.douyin.com/video/1"), patch(
            "src.api.parse.ParserFactory.create_parser", return_value=self.parser()
        ):
            response = self.client.get("/api/v1/parse", query_string={"key": raw_key, "url": "https://example.com"})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_json()["succ"])

    def test_get_daily_trend(self):
        from src.db import get_daily_trend
        with self.app.app_context():
            db = get_db()
            now_iso = utcnow()
            db.execute(
                "INSERT INTO request_logs(user_id,api_key_id,platform,path,status_code,error_code,duration_ms,created_at) "
                "VALUES(1, 1, 'douyin', '/api/v1/parse', 200, NULL, 50, ?)", (now_iso,)
            )
            db.execute(
                "INSERT INTO request_logs(user_id,api_key_id,platform,path,status_code,error_code,duration_ms,created_at) "
                "VALUES(1, 1, 'douyin', '/api/v1/parse', 500, 'ERR', 100, ?)", (now_iso,)
            )
            db.commit()

            trend_all = get_daily_trend(user_id=None, days=7)
            self.assertEqual(len(trend_all["trend"]), 7)
            self.assertGreaterEqual(trend_all["max_val"], 2)

            trend_user = get_daily_trend(user_id=1, days=7)
            self.assertEqual(len(trend_user["trend"]), 7)
            self.assertGreaterEqual(trend_user["max_val"], 2)

    def test_log_url_is_sanitized(self):
        value = sanitize_log_url(
            "复制链接 https://example.com/video/1?share_id=42&token=secret&sign=abc#private"
        )
        self.assertEqual(
            value,
            "https://example.com/video/1?share_id=42&token=secret&sign=abc#private",
        )
        self.assertEqual(
            sanitize_log_url("https://user:password@example.com/private"),
            "https://user:password@example.com/private",
        )

    def test_admin_can_export_logs_as_csv(self):
        self.client.post("/auth/setup", data={"csrf_token": self.csrf(), "username": "admin", "password": "password123", "confirm_password": "password123"})
        self.client.post("/auth/login", data={"csrf_token": self.csrf(), "username": "admin", "password": "password123"})
        with self.app.app_context():
            db = get_db()
            db.execute(
                "INSERT INTO request_logs(platform,path,status_code,error_code,duration_ms,input_url,created_at) "
                "VALUES(?,?,?,?,?,?,?)",
                ("抖音", "/api/v1/parse", 400, "MEDIA_NOT_FOUND", 123, "https://example.com/video/1", utcnow()),
            )
            db.commit()

        response = self.client.get("/admin/logs/export.csv")
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/csv", response.content_type)
        body = response.get_data(as_text=True)
        self.assertIn("请求 URL", body)
        self.assertIn("https://example.com/video/1", body)
        self.assertIn("MEDIA_NOT_FOUND", body)

    def test_user_can_export_only_own_logs_as_csv(self):
        self.client.post(
            "/auth/register",
            data={"csrf_token": self.csrf(), "username": "log_user", "password": "password123", "confirm_password": "password123"},
        )
        self.client.post(
            "/auth/login",
            data={"csrf_token": self.csrf(), "username": "log_user", "password": "password123"},
        )
        with self.app.app_context():
            db = get_db()
            user = db.execute("SELECT id FROM users WHERE username='log_user'").fetchone()
            db.execute(
                "INSERT INTO request_logs(user_id,platform,path,status_code,duration_ms,input_url,created_at) VALUES(?,?,?,?,?,?,?)",
                (user["id"], "抖音", "/api/v1/parse", 200, 88, "https://example.com/mine", utcnow()),
            )
            db.execute(
                "INSERT INTO request_logs(platform,path,status_code,duration_ms,input_url,created_at) VALUES(?,?,?,?,?,?)",
                ("快手", "/api/v1/parse", 200, 99, "https://example.com/other", utcnow()),
            )
            db.commit()

        response = self.client.get("/console/logs/export.csv")
        body = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn("https://example.com/mine", body)
        self.assertNotIn("https://example.com/other", body)

    def test_admin_can_purge_only_selected_old_logs(self):
        self.client.post("/auth/setup", data={"csrf_token": self.csrf(), "username": "admin", "password": "password123", "confirm_password": "password123"})
        self.client.post("/auth/login", data={"csrf_token": self.csrf(), "username": "admin", "password": "password123"})
        with self.app.app_context():
            db = get_db()
            old_time = (datetime.now(timezone.utc) - timedelta(days=31)).isoformat(timespec="seconds")
            db.execute(
                "INSERT INTO request_logs(path,status_code,duration_ms,created_at) VALUES(?,?,?,?)",
                ("/api/v1/parse", 200, 1, old_time),
            )
            db.execute(
                "INSERT INTO request_logs(path,status_code,duration_ms,created_at) VALUES(?,?,?,?)",
                ("/api/v1/parse", 200, 1, utcnow()),
            )
            db.commit()

        response = self.client.post(
            "/admin/logs/purge",
            data={"csrf_token": self.csrf(), "scope": "30", "confirmation": "清理日志"},
            follow_redirects=False,
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.location.endswith("/admin/logs"))

        # Follow redirect and verify flash message
        response = self.client.get(response.location, follow_redirects=True)
        self.assertIn("共 1 条", response.get_data(as_text=True))
        with self.app.app_context():
            self.assertEqual(get_db().execute("SELECT COUNT(*) count FROM request_logs").fetchone()["count"], 1)

    def test_update_api_tip_settings(self):
        # Create admin and login
        self.client.post("/auth/setup", data={"csrf_token": self.csrf(), "username": "admin", "password": "password123", "confirm_password": "password123"})
        self.client.post("/auth/login", data={"csrf_token": self.csrf(), "username": "admin", "password": "password123"})

        # Update settings via admin
        res = self.client.post(
            "/admin/settings",
            data={
                "csrf_token": self.csrf(),
                "global_api_enabled": "1",
                "demo_enabled": "1",
                "registration_enabled": "1",
                "default_user_qps": "5",
                "default_trial_days": "14",
                "api_tip_enabled": "1",
                "api_tip_author": "custom_author",
                "api_tip_website": "https://example.com/api",
                "api_tip_notice": "自定义接口服务文案",
            },
            follow_redirects=True,
        )
        self.assertEqual(res.status_code, 200)

        with self.app.app_context():
            from src.db import setting
            self.assertEqual(setting("api_tip_author"), "custom_author")
            self.assertEqual(setting("api_tip_website"), "https://example.com/api")
            self.assertEqual(setting("api_tip_notice"), "自定义接口服务文案")

    def test_user_change_password(self):
        # Register customer
        self.client.post(
            "/auth/register",
            data={"csrf_token": self.csrf(), "username": "user1", "password": "oldpassword123", "confirm_password": "oldpassword123"},
        )
        # Login
        self.client.post(
            "/auth/login",
            data={"csrf_token": self.csrf(), "username": "user1", "password": "oldpassword123"},
        )

        # Fail change with wrong old password
        res = self.client.post(
            "/auth/change-password",
            data={
                "csrf_token": self.csrf(),
                "old_password": "wrongoldpassword",
                "new_password": "newpassword123",
                "confirm_password": "newpassword123",
            },
            follow_redirects=True,
        )
        self.assertIn("原密码错误", res.get_data(as_text=True))

        # Fail change with password too short
        res = self.client.post(
            "/auth/change-password",
            data={
                "csrf_token": self.csrf(),
                "old_password": "oldpassword123",
                "new_password": "short",
                "confirm_password": "short",
            },
            follow_redirects=True,
        )
        self.assertIn("新密码至少需要 8 位", res.get_data(as_text=True))

        # Fail change with mismatched confirmation
        res = self.client.post(
            "/auth/change-password",
            data={
                "csrf_token": self.csrf(),
                "old_password": "oldpassword123",
                "new_password": "newpassword123",
                "confirm_password": "different123",
            },
            follow_redirects=True,
        )
        self.assertIn("两次输入的新密码不一致", res.get_data(as_text=True))

        # Successful password change
        res = self.client.post(
            "/auth/change-password",
            data={
                "csrf_token": self.csrf(),
                "old_password": "oldpassword123",
                "new_password": "newpassword123",
                "confirm_password": "newpassword123",
            },
            follow_redirects=True,
        )
        self.assertIn("密码修改成功", res.get_data(as_text=True))

        # Verify old password no longer works, new password works
        self.client.post("/auth/logout", data={"csrf_token": self.csrf()})
        fail_login = self.client.post(
            "/auth/login",
            data={"csrf_token": self.csrf(), "username": "user1", "password": "oldpassword123"},
            follow_redirects=True,
        )
        self.assertIn("用户名或密码错误", fail_login.get_data(as_text=True))

        succ_login = self.client.post(
            "/auth/login",
            data={"csrf_token": self.csrf(), "username": "user1", "password": "newpassword123"},
        )
        self.assertEqual(succ_login.status_code, 302)

    def test_admin_reset_customer_password(self):
        # Create admin
        self.client.post(
            "/auth/setup",
            data={"csrf_token": self.csrf(), "username": "admin", "password": "adminpassword123", "confirm_password": "adminpassword123"},
        )
        # Register customer
        self.client.post(
            "/auth/register",
            data={"csrf_token": self.csrf(), "username": "customer1", "password": "userpassword123", "confirm_password": "userpassword123"},
        )

        with self.app.app_context():
            customer = get_db().execute("SELECT * FROM users WHERE username='customer1'").fetchone()
            customer_id = customer["id"]

        # Admin login
        self.client.post(
            "/auth/login",
            data={"csrf_token": self.csrf(), "username": "admin", "password": "adminpassword123"},
        )

        # Admin resets customer password with short password
        res = self.client.post(
            f"/admin/users/{customer_id}/reset-password",
            data={"csrf_token": self.csrf(), "new_password": "short"},
            follow_redirects=True,
        )
        self.assertIn("重置密码至少需要 8 位", res.get_data(as_text=True))

        # Admin resets customer password successfully
        res = self.client.post(
            f"/admin/users/{customer_id}/reset-password",
            data={"csrf_token": self.csrf(), "new_password": "resetpassword888"},
            follow_redirects=True,
        )
        self.assertIn("已成功重置客户「customer1」的密码", res.get_data(as_text=True))

        # Verify customer can login with reset password
        self.client.post("/auth/logout", data={"csrf_token": self.csrf()})
        succ_login = self.client.post(
            "/auth/login",
            data={"csrf_token": self.csrf(), "username": "customer1", "password": "resetpassword888"},
        )
        self.assertEqual(succ_login.status_code, 302)

    def test_initial_credits_and_deduction(self):
        # Register user
        res = self.client.post(
            "/auth/register",
            data={"csrf_token": self.csrf(), "username": "credit_user", "password": "password123", "confirm_password": "password123"},
            follow_redirects=True,
        )
        self.assertIn("100 积分", res.get_data(as_text=True))

        with self.app.app_context():
            db = get_db()
            user = db.execute("SELECT * FROM users WHERE username='credit_user'").fetchone()
            self.assertEqual(user["credits"], 100)
            user_id = user["id"]
            # Create key for user
            raw_key = "mp_credit_test_key_123"
            db.execute(
                "INSERT INTO api_keys(user_id,name,key_hash,key_prefix,created_at) VALUES(?,?,?,?,?)",
                (user_id, "test", hash_api_key(raw_key), raw_key[:11], utcnow()),
            )
            # Set credits to 1 for quick deduction test
            db.execute("UPDATE users SET credits=1 WHERE id=?", (user_id,))
            db.commit()

        # Call API successfully -> should deduct 1 credit (credits becomes 0)
        with patch("src.api.parse.WebFetcher.fetch_redirect_url", return_value="https://www.douyin.com/video/1"), patch(
            "src.api.parse.ParserFactory.create_parser", return_value=self.parser()
        ):
            succ_res = self.client.get("/api/v1/parse", query_string={"key": raw_key, "url": "https://example.com"})
        self.assertEqual(succ_res.status_code, 200)

        with self.app.app_context():
            user = get_db().execute("SELECT * FROM users WHERE username='credit_user'").fetchone()
            self.assertEqual(user["credits"], 0)

        # Call API again -> should return 402 INSUFFICIENT_CREDITS
        fail_res = self.client.get("/api/v1/parse", query_string={"key": raw_key, "url": "https://example.com"})
        self.assertEqual(fail_res.status_code, 402)
        self.assertEqual(fail_res.get_json()["error_code"], "INSUFFICIENT_CREDITS")

    def test_concurrent_credit_reservations_cannot_exceed_balance(self):
        _, user_id, _ = self.create_customer_and_key(qps=10)
        with self.app.app_context():
            db = get_db()
            db.execute("UPDATE users SET credits=1 WHERE id=?", (user_id,))
            db.commit()

        barrier = Barrier(2)

        def reserve_once():
            with self.app.app_context():
                barrier.wait()
                return reserve_user_credit(user_id)

        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(lambda _: reserve_once(), range(2)))

        self.assertEqual(sorted(results, key=lambda value: value is not True), [True, None])
        with self.app.app_context():
            credits = get_db().execute(
                "SELECT credits FROM users WHERE id=?", (user_id,)
            ).fetchone()["credits"]
        self.assertEqual(credits, 0)

    def test_failed_parse_refunds_reserved_credit(self):
        raw_key, user_id, _ = self.create_customer_and_key(qps=10)
        with self.app.app_context():
            db = get_db()
            db.execute("UPDATE users SET credits=1 WHERE id=?", (user_id,))
            db.commit()

        empty_parser = self.parser()
        empty_parser.get_real_video_url.return_value = None
        with patch("src.api.parse.WebFetcher.fetch_redirect_url", return_value="https://www.douyin.com/video/1"), patch(
            "src.api.parse.ParserFactory.create_parser", return_value=empty_parser
        ):
            response = self.client.get(
                "/api/v1/parse", query_string={"key": raw_key, "url": "https://example.com"}
            )
        self.assertEqual(response.status_code, 400)
        with self.app.app_context():
            credits = get_db().execute(
                "SELECT credits FROM users WHERE id=?", (user_id,)
            ).fetchone()["credits"]
        self.assertEqual(credits, 1)

    def test_admin_manage_user_credits(self):
        self.client.post("/auth/setup", data={"csrf_token": self.csrf(), "username": "admin", "password": "password123", "confirm_password": "password123"})
        self.client.post("/auth/login", data={"csrf_token": self.csrf(), "username": "admin", "password": "password123"})
        self.client.post("/auth/register", data={"csrf_token": self.csrf(), "username": "user_cred_test", "password": "password123", "confirm_password": "password123"})

        with self.app.app_context():
            user = get_db().execute("SELECT * FROM users WHERE username='user_cred_test'").fetchone()
            user_id = user["id"]

        # Admin updates user credits to 999
        res = self.client.post(
            f"/admin/users/{user_id}",
            data={"csrf_token": self.csrf(), "credits": "999", "active": "1", "qps_limit": "2"},
            follow_redirects=True,
        )
        self.assertEqual(res.status_code, 200)

    def test_portal_platforms_dashboard(self):
        # Setup admin first, then register regular user
        self.client.post("/auth/setup", data={"csrf_token": self.csrf(), "username": "admin", "password": "password123", "confirm_password": "password123"})
        self.client.post("/auth/register", data={"csrf_token": self.csrf(), "username": "portal_viewer", "password": "password123", "confirm_password": "password123"})
        self.client.post("/auth/login", data={"csrf_token": self.csrf(), "username": "portal_viewer", "password": "password123"})

        with self.app.app_context():
            db = get_db()
            user = db.execute("SELECT id FROM users WHERE username='portal_viewer'").fetchone()
            db.execute(
                "INSERT INTO request_logs(user_id,platform,path,status_code,duration_ms,input_url,created_at) VALUES(?,?,?,?,?,?,?)",
                (user["id"], "抖音", "/api/v1/parse", 200, 50, "https://v.douyin.com/abc", utcnow()),
            )
            db.commit()

        # Access /console/platforms
        res = self.client.get("/console/platforms")
        self.assertEqual(res.status_code, 200)
        body = res.get_data(as_text=True)
        self.assertIn("支持平台", body)
        self.assertIn("AcFun", body)
        # Verify read-only nature: no edit forms or submit buttons for platform settings
        self.assertNotIn('action="/admin/platforms', body)

        # Search filter
        res_search = self.client.get("/console/platforms?platforms_q=抖音")
        self.assertEqual(res_search.status_code, 200)
        self.assertIn("抖音", res_search.get_data(as_text=True))

    def test_console_topbar_api_status(self):
        self.client.post("/auth/setup", data={"csrf_token": self.csrf(), "username": "admin", "password": "password123", "confirm_password": "password123"})
        self.client.post("/auth/login", data={"csrf_token": self.csrf(), "username": "admin", "password": "password123"})

        # API is enabled by default
        res = self.client.get("/admin/overview")
        self.assertEqual(res.status_code, 200)
        body = res.get_data(as_text=True)
        self.assertIn("status-pill online", body)
        self.assertIn("API 正常", body)

        # Disable API via settings (omit global_api_enabled to simulate unchecked checkbox)
        self.client.post(
            "/admin/settings",
            data={
                "csrf_token": self.csrf(),
            },
            follow_redirects=True,
        )

        # Verify topbar now reflects maintenance mode
        res_maint = self.client.get("/admin/overview")
        self.assertEqual(res_maint.status_code, 200)
        body_maint = res_maint.get_data(as_text=True)
        self.assertIn("status-pill offline", body_maint)
        self.assertIn("API 维护中", body_maint)

    def test_customer_login_with_admin_next_param(self):
        # Register a customer
        with self.app.app_context():
            db = get_db()
            from werkzeug.security import generate_password_hash
            db.execute(
                "INSERT INTO users(username,password_hash,role,qps_limit,created_at) VALUES(?,?,?,?,?)",
                ("customer_leo", generate_password_hash("password123"), "user", 2, utcnow()),
            )
            db.commit()

        # Login as customer with next pointing to /admin/overview
        response = self.client.post(
            "/auth/login?next=/admin/overview",
            data={"csrf_token": self.csrf(), "username": "customer_leo", "password": "password123"},
            follow_redirects=False,
        )
        self.assertEqual(response.status_code, 302)
        # Should redirect directly to portal dashboard (/console or /console/overview), not admin
        self.assertTrue(response.location.endswith("/console") or response.location.endswith("/console/overview"))
        self.assertNotIn("/admin", response.location)


if __name__ == "__main__":
    unittest.main()
