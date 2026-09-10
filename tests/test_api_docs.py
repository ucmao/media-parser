import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone

from app import create_app
from src.auth import hash_api_key
from src.db import get_db, utcnow


class ApiDocsRenderTest(unittest.TestCase):
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

    def setup_admin(self):
        self.client.post(
            "/auth/setup",
            data={
                "csrf_token": self.csrf(),
                "username": "admin",
                "password": "password123",
                "confirm_password": "password123"
            },
        )
        self.client.post(
            "/auth/login",
            data={
                "csrf_token": self.csrf(),
                "username": "admin",
                "password": "password123"
            },
        )

    def setup_customer(self):
        raw_key = "mp_testkey_1234567890"
        with self.app.app_context():
            db = get_db()
            expires_at = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat(timespec="seconds")
            from werkzeug.security import generate_password_hash
            cursor = db.execute(
                "INSERT INTO users(username,password_hash,role,expires_at,qps_limit,created_at) VALUES(?,?,?,?,?,?)",
                ("testuser", generate_password_hash("password123"), "user", expires_at, 5, utcnow()),
            )
            user_id = cursor.lastrowid
            db.execute(
                "INSERT INTO api_keys(user_id,name,key,created_at) VALUES(?,?,?,?)",
                (user_id, "我的测试密钥", raw_key, utcnow()),
            )
            db.commit()

        self.client.post(
            "/auth/login",
            data={
                "csrf_token": self.csrf(),
                "username": "testuser",
                "password": "password123"
            },
        )

    def test_admin_dashboard_renders_api_docs_tab(self):
        self.setup_admin()
        resp = self.client.get("/admin/docs")
        self.assertEqual(resp.status_code, 200)
        html = resp.get_data(as_text=True)
        self.assertIn("开发者文档", html)
        self.assertIn("api-playground-form", html)
        self.assertIn("在线接口调试", html)
        self.assertIn("多语言对接代码示例", html)
        self.assertIn("返回 JSON 数据字典", html)
        self.assertIn("标准错误码与排错指南", html)
        self.assertIn("/api/v1/parse", html)
        self.assertIn('href="/admin/keys"', html)

    def test_customer_portal_renders_api_docs_tab(self):
        self.setup_customer()
        resp = self.client.get("/console/docs")
        self.assertEqual(resp.status_code, 200)
        html = resp.get_data(as_text=True)
        self.assertIn("开发者文档", html)
        self.assertIn("api-playground-form", html)
        self.assertIn("在线接口调试", html)
        self.assertIn("我的测试密钥", html)
        self.assertIn("多语言对接代码示例", html)
        self.assertIn("返回 JSON 数据字典", html)
        self.assertIn("标准错误码与排错指南", html)
        self.assertIn('href="/console/keys"', html)

    def test_session_authenticated_playground_supports_key_prefix(self):
        self.setup_customer()
        # In a logged in session, using the selected key prefix from dropdown works
        resp = self.client.get(
            "/api/v1/parse?url=https://v.douyin.com/test12345/&key=mp_testkey_...",
        )
        # Should authenticate and proceed to execute parse (not blocked by 401 INVALID_API_KEY)
        self.assertNotEqual(resp.status_code, 401)

    def test_unauthenticated_request_rejects_key_prefix(self):
        # Without a logged-in session, using prefix is rejected for security
        resp = self.client.get(
            "/api/v1/parse?url=https://v.douyin.com/test12345/&key=mp_testkey_...",
        )
        self.assertEqual(resp.status_code, 401)
        data = resp.get_json()
        self.assertEqual(data.get("error_code"), "INVALID_API_KEY")

    def test_admin_cannot_use_customer_key_prefix(self):
        # Create a customer with a key
        self.setup_customer()
        # Log out customer and log in as admin
        self.client.get("/auth/logout")
        self.setup_admin()
        
        # Admin trying to use customer's prefix must be rejected
        resp = self.client.get(
            "/api/v1/parse?url=https://v.douyin.com/test12345/&key=mp_testkey_...",
        )
        self.assertEqual(resp.status_code, 401)
        data = resp.get_json()
        self.assertEqual(data.get("error_code"), "INVALID_API_KEY")

    def test_playground_deducts_customer_credits_on_success(self):
        from unittest.mock import patch
        self.setup_customer()

        with self.app.app_context():
            db = get_db()
            db.execute("UPDATE users SET credits=10 WHERE username='testuser'")
            db.commit()

        mock_parser = unittest.mock.MagicMock()
        mock_parser.get_title_content.return_value = "测试视频标题"
        mock_parser.get_description.return_value = "描述"
        mock_parser.get_real_video_url.return_value = "https://example.com/video.mp4"
        mock_parser.get_cover_photo_url.return_value = "https://example.com/cover.jpg"
        mock_parser.get_video_list.return_value = []
        mock_parser.get_author_info.return_value = "测试作者"
        mock_parser.get_image_list.return_value = []
        mock_parser.get_audio_url.return_value = None
        mock_parser.get_subtitles.return_value = None

        with patch("src.api.parse.WebFetcher.fetch_redirect_url", return_value="https://www.douyin.com/video/123456"), \
             patch("src.api.parse.UrlParser.get_platform", return_value="抖音"), \
             patch("src.api.parse.UrlParser.extract_video_address", return_value="https://www.douyin.com/video/123456"), \
             patch("src.api.parse.ParserFactory.create_parser", return_value=mock_parser):
            resp = self.client.get("/api/v1/parse?url=https://v.douyin.com/test12345/&key=mp_testkey_...")
            self.assertEqual(resp.status_code, 200)
            data = resp.get_json()
            self.assertTrue(data.get("succ"))

        with self.app.app_context():
            user = get_db().execute("SELECT credits FROM users WHERE username='testuser'").fetchone()
            self.assertEqual(user["credits"], 9)

    def test_playground_blocks_when_customer_credits_zero(self):
        self.setup_customer()

        with self.app.app_context():
            db = get_db()
            db.execute("UPDATE users SET credits=0 WHERE username='testuser'")
            db.commit()

        resp = self.client.get("/api/v1/parse?url=https://v.douyin.com/test12345/&key=mp_testkey_...")
        self.assertEqual(resp.status_code, 402)
        data = resp.get_json()
        self.assertEqual(data.get("error_code"), "INSUFFICIENT_CREDITS")
