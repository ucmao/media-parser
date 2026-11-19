import os
import re
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from app import create_app
from src.db import get_db, set_setting, utcnow

SMTP_CONFIG = {"SMTP_HOST": "smtp.example.test", "SMTP_PORT": 465, "SMTP_SECURITY": "ssl",
               "SMTP_USER": "bot@example.test", "SMTP_PASSWORD": "x", "SMTP_FROM": "bot@example.test"}


class EmailRegistrationTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "test.db")

    def tearDown(self):
        self.temp_dir.cleanup()

    def make_app(self, smtp=False, path=None):
        config = {"TESTING": True, "SECRET_KEY": "test-secret", "DATABASE": path or self.db_path,
                  "SMTP_HOST": "", "SMTP_FROM": ""}
        if smtp:
            config.update(SMTP_CONFIG)
        self.app = create_app(config)
        self.client = self.app.test_client()
        return self.app

    def csrf(self):
        with self.client.session_transaction() as session:
            session["csrf_token"] = "test-csrf"
        return "test-csrf"

    def register(self, username, email=None, code=None, ip="198.51.100.1"):
        data = {"csrf_token": self.csrf(), "username": username,
                "password": "password123", "confirm_password": "password123"}
        if email is not None:
            data["email"] = email
        if code is not None:
            data["email_code"] = code
        return self.client.post("/auth/register", data=data, environ_base={"REMOTE_ADDR": ip})

    def send_code(self, email, ip="198.51.100.1"):
        sent = {}

        def fake_send(to, subject, body):
            sent["to"] = to
            sent["code"] = re.search(r"\d{6}", body).group(0)

        with patch("src.mailer.send_mail", side_effect=fake_send):
            resp = self.client.post("/auth/register/send-code", environ_base={"REMOTE_ADDR": ip},
                                    data={"csrf_token": self.csrf(), "email": email})
        return resp, sent.get("code")

    def user(self, username):
        with self.app.app_context():
            return get_db().execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()

    def test_without_smtp_registration_is_unchanged(self):
        self.make_app(smtp=False)
        page = self.client.get("/auth/register").get_data(as_text=True)
        self.assertNotIn('name="email"', page)
        self.assertEqual(self.register("plain_user").status_code, 302)
        self.assertIsNone(self.user("plain_user")["email"])
        resp = self.client.post("/auth/register/send-code", data={"csrf_token": self.csrf(), "email": "a@b.cn"})
        self.assertEqual(resp.status_code, 404)

    def test_with_smtp_requires_valid_code(self):
        self.make_app(smtp=True)
        self.assertIn('name="email_code"', self.client.get("/auth/register").get_data(as_text=True))

        resp = self.register("no_code", email="no_code@example.com", code="")
        self.assertEqual(resp.status_code, 200)
        self.assertIsNone(self.user("no_code"))

        resp, code = self.send_code("Mail_User@Example.com")
        self.assertEqual(resp.status_code, 200, resp.get_json())
        wrong = "000000" if code != "000000" else "111111"
        self.assertEqual(self.register("mail_user", email="mail_user@example.com", code=wrong).status_code, 200)
        self.assertIsNone(self.user("mail_user"))

        self.assertEqual(self.register("mail_user", email="mail_user@example.com", code=code).status_code, 302)
        self.assertEqual(self.user("mail_user")["email"], "mail_user@example.com")
        with self.app.app_context():
            self.assertIsNone(get_db().execute("SELECT 1 FROM email_verification_codes").fetchone())

        # 同一邮箱不能再次获取验证码或注册
        resp, _ = self.send_code("mail_user@example.com", ip="198.51.100.2")
        self.assertEqual(resp.status_code, 400)

    def test_code_locks_after_max_attempts(self):
        self.make_app(smtp=True)
        _, code = self.send_code("lock@example.com")
        wrong = "000000" if code != "000000" else "111111"
        for i in range(5):
            self.register(f"lock_{i}", email="lock@example.com", code=wrong, ip=f"198.51.100.{10 + i}")
        self.assertEqual(self.register("lock_ok", email="lock@example.com", code=code, ip="198.51.100.30").status_code, 200)
        self.assertIsNone(self.user("lock_ok"))

    def test_send_failure_reports_error_and_discards_code(self):
        self.make_app(smtp=True)
        with patch("src.mailer.send_mail", side_effect=OSError("boom")):
            resp = self.client.post("/auth/register/send-code", data={"csrf_token": self.csrf(), "email": "f@example.com"})
        self.assertEqual(resp.status_code, 502)
        with self.app.app_context():
            self.assertIsNone(get_db().execute("SELECT 1 FROM email_verification_codes").fetchone())

    def test_send_code_respects_daily_quota(self):
        self.make_app(smtp=True)
        with self.app.app_context():
            set_setting("registration_daily_limit", "1")
            get_db().execute("INSERT INTO users(username,password_hash,created_at) VALUES('q','x',?)",
                             (utcnow(),))
            get_db().commit()
        resp, code = self.send_code("quota@example.com")
        self.assertEqual(resp.status_code, 429)
        self.assertIsNone(code)

    def test_admin_can_disable_email_verification(self):
        self.make_app(smtp=True)
        with self.app.app_context():
            set_setting("email_verification_enabled", "0")
            get_db().commit()
        self.assertEqual(self.register("toggle_off").status_code, 302)

    def test_admin_user_list_searches_and_shows_email(self):
        self.make_app(smtp=False)
        self.client.post("/auth/setup", data={"csrf_token": self.csrf(), "username": "admin",
                                              "password": "password123", "confirm_password": "password123"})
        self.client.post("/auth/login", data={"csrf_token": self.csrf(), "username": "admin", "password": "password123"})
        with self.app.app_context():
            db = get_db()
            db.execute("INSERT INTO users(username,password_hash,created_at,email) VALUES('has_mail','x','2026-01-01','found@example.com')")
            db.execute("INSERT INTO users(username,password_hash,created_at) VALUES('no_mail','x','2026-01-01')")
            db.commit()
        page = self.client.get("/admin/users?users_q=found@").get_data(as_text=True)
        self.assertIn("has_mail", page)
        self.assertNotIn("no_mail", page)
        self.assertIn("found@example.com", page)
        self.assertIn('id="admin-edit-user-email"', page)

    def test_legacy_database_gets_nullable_unique_email(self):
        path = os.path.join(self.temp_dir.name, "legacy.db")
        conn = sqlite3.connect(path)
        conn.executescript(
            "CREATE TABLE users (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT NOT NULL UNIQUE COLLATE NOCASE,"
            " password_hash TEXT NOT NULL, role TEXT NOT NULL DEFAULT 'user', active INTEGER NOT NULL DEFAULT 1,"
            " expires_at TEXT, qps_limit INTEGER NOT NULL DEFAULT 2, credits INTEGER NOT NULL DEFAULT 100, created_at TEXT NOT NULL);"
            "INSERT INTO users(username,password_hash,created_at) VALUES('old_a','x','2026-01-01T00:00:00+00:00');"
            "INSERT INTO users(username,password_hash,created_at) VALUES('old_b','x','2026-01-01T00:00:00+00:00');"
        )
        conn.commit()
        conn.close()
        self.make_app(smtp=False, path=path)
        self.make_app(smtp=False, path=path)  # 二次启动迁移需幂等
        conn = sqlite3.connect(path)
        self.assertIn("email", {row[1] for row in conn.execute("PRAGMA table_info(users)")})
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM users WHERE email IS NULL").fetchone()[0], 2)
        conn.execute("UPDATE users SET email='dup@example.com' WHERE username='old_a'")
        with self.assertRaises(sqlite3.IntegrityError):
            conn.execute("UPDATE users SET email='DUP@example.com' WHERE username='old_b'")
        conn.close()


if __name__ == "__main__":
    unittest.main()
