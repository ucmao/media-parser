import os
import sqlite3
import tempfile
import unittest

from app import create_app
from src.db import get_db, set_setting, utcnow
from src.ip_rules import ip_matches, parse_ip_rules


class IpRulesTest(unittest.TestCase):
    def test_parse_supports_ip_cidr_ipv6_and_comments(self):
        networks, normalized, invalid = parse_ip_rules(
            "1.2.3.4  # 批量注册\n\n5.6.7.0/24\n2001:db8::/32\nnot-an-ip\n"
        )
        self.assertEqual(normalized, ["1.2.3.4", "5.6.7.0/24", "2001:db8::/32"])
        self.assertEqual(invalid, ["not-an-ip"])
        self.assertTrue(ip_matches("5.6.7.200", networks))
        self.assertTrue(ip_matches("2001:db8::1", networks))
        self.assertFalse(ip_matches("5.6.8.1", networks))
        self.assertFalse(ip_matches("garbage", networks))


class IpSecurityTest(unittest.TestCase):
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

    def csrf(self, client=None):
        with (client or self.client).session_transaction() as session:
            session["csrf_token"] = "test-csrf"
        return "test-csrf"

    def set_blacklist(self, text):
        with self.app.app_context():
            set_setting("ip_blacklist", text)
            get_db().commit()

    def register(self, username, ip, client=None):
        client = client or self.client
        return client.post(
            "/auth/register",
            environ_base={"REMOTE_ADDR": ip},
            data={"csrf_token": self.csrf(client), "username": username, "password": "password123", "confirm_password": "password123"},
        )

    def login_admin(self, ip="192.0.2.99"):
        self.client.post(
            "/auth/setup",
            environ_base={"REMOTE_ADDR": ip},
            data={"csrf_token": self.csrf(), "username": "admin", "password": "password123", "confirm_password": "password123"},
        )
        self.client.post(
            "/auth/login",
            environ_base={"REMOTE_ADDR": ip},
            data={"csrf_token": self.csrf(), "username": "admin", "password": "password123"},
        )

    def test_old_database_gets_new_ip_columns(self):
        path = os.path.join(self.temp_dir.name, "legacy.db")
        conn = sqlite3.connect(path)
        conn.executescript(
            "CREATE TABLE users (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT NOT NULL UNIQUE COLLATE NOCASE,"
            " password_hash TEXT NOT NULL, role TEXT NOT NULL DEFAULT 'user', active INTEGER NOT NULL DEFAULT 1,"
            " expires_at TEXT, qps_limit INTEGER NOT NULL DEFAULT 2, credits INTEGER NOT NULL DEFAULT 100, created_at TEXT NOT NULL);"
            "CREATE TABLE request_logs (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, api_key_id INTEGER, platform TEXT,"
            " path TEXT NOT NULL, status_code INTEGER NOT NULL, error_code TEXT, duration_ms INTEGER NOT NULL, input_url TEXT, created_at TEXT NOT NULL);"
            "INSERT INTO users(username,password_hash,created_at) VALUES('old_user','x','2026-01-01T00:00:00+00:00');"
        )
        conn.commit()
        conn.close()
        create_app({"TESTING": True, "SECRET_KEY": "s", "DATABASE": path})
        conn = sqlite3.connect(path)
        user_cols = {row[1] for row in conn.execute("PRAGMA table_info(users)")}
        log_cols = {row[1] for row in conn.execute("PRAGMA table_info(request_logs)")}
        self.assertTrue({"register_ip", "last_login_ip", "last_login_at"} <= user_cols)
        self.assertIn("client_ip", log_cols)
        self.assertEqual(conn.execute("SELECT username FROM users").fetchone()[0], "old_user")
        conn.close()

    def test_register_and_login_record_ip(self):
        self.assertEqual(self.register("ip_user", "198.51.100.1").status_code, 302)
        with self.client.session_transaction() as sess:
            sess.clear()
        self.client.post(
            "/auth/login",
            environ_base={"REMOTE_ADDR": "198.51.100.2"},
            data={"csrf_token": self.csrf(), "username": "ip_user", "password": "password123"},
        )
        with self.app.app_context():
            user = get_db().execute("SELECT * FROM users WHERE username='ip_user'").fetchone()
        self.assertEqual(user["register_ip"], "198.51.100.1")
        self.assertEqual(user["last_login_ip"], "198.51.100.2")
        self.assertIsNotNone(user["last_login_at"])

    def test_blacklisted_ip_cannot_register_login_or_call_api(self):
        self.set_blacklist("203.0.113.0/24")
        response = self.register("bad_user", "203.0.113.5")
        self.assertEqual(response.status_code, 403)
        login = self.client.get("/auth/login", environ_base={"REMOTE_ADDR": "203.0.113.5"})
        self.assertEqual(login.status_code, 403)
        api = self.client.get("/api/v1/parse", query_string={"key": "x", "url": "https://example.com"},
                              environ_base={"REMOTE_ADDR": "203.0.113.5"})
        self.assertEqual(api.status_code, 403)
        self.assertEqual(api.get_json()["error_code"], "IP_BLOCKED")
        # 网段外的 IP 不受影响
        self.assertEqual(self.register("good_user", "203.0.114.5").status_code, 302)

    def test_logged_in_admin_is_not_blocked(self):
        self.login_admin(ip="192.0.2.99")
        self.set_blacklist("192.0.2.99")
        response = self.client.get("/admin/settings", environ_base={"REMOTE_ADDR": "192.0.2.99"})
        self.assertEqual(response.status_code, 200)

    def test_settings_rejects_invalid_rules_and_own_ip(self):
        self.login_admin(ip="192.0.2.99")
        headers = {"X-Requested-With": "XMLHttpRequest"}
        bad = self.client.post("/admin/settings", headers=headers, environ_base={"REMOTE_ADDR": "192.0.2.99"},
                               data={"csrf_token": self.csrf(), "ip_blacklist": "1.2.3.4\nhello"})
        self.assertEqual(bad.status_code, 400)
        self.assertIn("hello", bad.get_json()["message"])
        own = self.client.post("/admin/settings", headers=headers, environ_base={"REMOTE_ADDR": "192.0.2.99"},
                               data={"csrf_token": self.csrf(), "ip_blacklist": "192.0.2.0/24"})
        self.assertEqual(own.status_code, 400)
        self.assertIn("192.0.2.99", own.get_json()["message"])
        ok = self.client.post("/admin/settings", headers=headers, environ_base={"REMOTE_ADDR": "192.0.2.99"},
                              data={"csrf_token": self.csrf(), "ip_blacklist": "1.2.3.4 # spam\n1.2.3.4\n5.6.7.8/24"})
        self.assertEqual(ok.status_code, 200)
        with self.app.app_context():
            self.assertEqual(get_db().execute("SELECT value FROM system_settings WHERE key='ip_blacklist'").fetchone()[0],
                             "1.2.3.4\n5.6.7.0/24")

    def test_admin_can_search_users_and_logs_by_ip(self):
        self.register("from_a", "198.51.100.10")
        self.register("from_b", "198.51.100.20")
        with self.app.app_context():
            db = get_db()
            db.execute(
                "INSERT INTO request_logs(path,status_code,duration_ms,created_at,client_ip) VALUES(?,?,?,?,?)",
                ("/api/v1/parse", 200, 10, utcnow(), "198.51.100.77"),
            )
            db.commit()
        with self.client.session_transaction() as sess:
            sess.clear()
        self.login_admin()
        users = self.client.get("/admin/users", query_string={"users_q": "198.51.100.10"}).get_data(as_text=True)
        self.assertIn("from_a", users)
        self.assertNotIn("from_b", users)
        logs = self.client.get("/admin/logs", query_string={"logs_q": "198.51.100.77"}).get_data(as_text=True)
        self.assertIn("198.51.100.77", logs)
        csv_body = self.client.get("/admin/logs/export.csv").get_data(as_text=True)
        self.assertIn("198.51.100.77", csv_body)

    def test_malicious_username_and_key_name_cannot_break_out_of_onclick(self):
        import html
        import re
        payload = "x');alert(1);//"
        self.register(payload, "198.51.100.30")
        self.client.post("/console/keys", data={"csrf_token": self.csrf(), "name": "k');alert(2);//"})
        with self.client.session_transaction() as sess:
            sess.clear()
        self.login_admin()
        for path, fn in (("/admin/users", "openAdminEditUserModal"), ("/admin/keys", "openAdminEditKeyModal")):
            page = self.client.get(path).get_data(as_text=True)
            for attr in re.findall(r'onclick="([^"]*%s\([^"]*)"' % fn, page):
                js = html.unescape(attr)
                self.assertNotIn("');alert(", js, f"{path} 中的 onclick 可被注入：{js}")


if __name__ == "__main__":
    unittest.main()
