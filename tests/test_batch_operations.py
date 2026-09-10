import sqlite3
import unittest
from datetime import datetime, timezone
from src.auth import generate_api_key, hash_api_key
from werkzeug.security import generate_password_hash


class TestBatchOperationsDB(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(":memory:")
        self.db.row_factory = sqlite3.Row

        # Setup schema
        self.db.execute("""
            CREATE TABLE users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'user',
                active INTEGER NOT NULL DEFAULT 1,
                qps_limit INTEGER NOT NULL DEFAULT 2,
                credits INTEGER DEFAULT 100,
                expires_at TEXT,
                created_at TEXT NOT NULL
            )
        """)
        self.db.execute("""
            CREATE TABLE api_keys (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                key TEXT UNIQUE NOT NULL,
                active INTEGER NOT NULL DEFAULT 1,
                qps_limit INTEGER,
                last_used_at TEXT,
                created_at TEXT NOT NULL
            )
        """)
        self.db.execute("""
            CREATE TABLE platform_settings (
                platform TEXT PRIMARY KEY,
                enabled INTEGER NOT NULL DEFAULT 1,
                qps_limit INTEGER,
                updated_at TEXT
            )
        """)
        self.db.execute("""
            CREATE TABLE request_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                api_key_id INTEGER,
                platform TEXT,
                input_url TEXT,
                status_code INTEGER,
                duration_ms INTEGER,
                created_at TEXT
            )
        """)

        # Insert test users
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        self.db.execute("INSERT INTO users (username, password_hash, role, active, created_at) VALUES ('admin', 'hash', 'admin', 1, ?)", (now,))
        for i in range(1, 6):
            self.db.execute(
                "INSERT INTO users (username, password_hash, role, active, qps_limit, credits, created_at) VALUES (?, 'hash', 'user', 1, 2, 100, ?)",
                (f"user{i}", now),
            )

        # Insert test keys
        for i in range(1, 6):
            self.db.execute(
                "INSERT INTO api_keys (user_id, name, key, active, qps_limit, created_at) VALUES (?, ?, ?, 1, 5, ?)",
                (i + 1, f"key{i}", f"mp-key-{i}-12345678901234567890", now),
            )

        # Insert test logs
        for i in range(1, 10):
            self.db.execute(
                "INSERT INTO request_logs (user_id, platform, status_code, duration_ms, created_at) VALUES (?, 'douyin', 200, 150, ?)",
                (2, now),
            )

        self.db.commit()

    def tearDown(self):
        self.db.close()

    def test_batch_users_update_active(self):
        user_ids = [2, 3, 4]
        placeholders = ",".join(["?"] * len(user_ids))
        self.db.execute(f"UPDATE users SET active=0 WHERE id IN ({placeholders}) AND role!='admin'", user_ids)
        self.db.commit()

        disabled_count = self.db.execute("SELECT COUNT(*) FROM users WHERE active=0").fetchone()[0]
        self.assertEqual(disabled_count, 3)

    def test_batch_users_adjust_credits(self):
        user_ids = [2, 3]
        placeholders = ",".join(["?"] * len(user_ids))
        self.db.execute(f"UPDATE users SET credits=credits+50 WHERE id IN ({placeholders}) AND role!='admin'", user_ids)
        self.db.commit()

        res = self.db.execute("SELECT credits FROM users WHERE id IN (2, 3)").fetchall()
        for r in res:
            self.assertEqual(r["credits"], 150)

    def test_batch_users_protection_on_admin(self):
        # Trying to delete user IDs 1 (admin) and 2 (user)
        user_ids = [1, 2]
        placeholders = ",".join(["?"] * len(user_ids))
        self.db.execute(f"DELETE FROM users WHERE id IN ({placeholders}) AND role!='admin'", user_ids)
        self.db.commit()

        admin_exists = self.db.execute("SELECT COUNT(*) FROM users WHERE role='admin'").fetchone()[0]
        self.assertEqual(admin_exists, 1)  # Admin should NOT be deleted!

    def test_batch_keys_disable_and_qps(self):
        key_ids = [1, 2]
        placeholders = ",".join(["?"] * len(key_ids))
        self.db.execute(f"UPDATE api_keys SET active=0, qps_limit=20 WHERE id IN ({placeholders})", key_ids)
        self.db.commit()

        k1 = self.db.execute("SELECT * FROM api_keys WHERE id=1").fetchone()
        self.assertEqual(k1["active"], 0)
        self.assertEqual(k1["qps_limit"], 20)

    def test_batch_logs_delete(self):
        log_ids = [1, 2, 3]
        placeholders = ",".join(["?"] * len(log_ids))
        self.db.execute(f"DELETE FROM request_logs WHERE id IN ({placeholders})", log_ids)
        self.db.commit()

        remaining_logs = self.db.execute("SELECT COUNT(*) FROM request_logs").fetchone()[0]
        self.assertEqual(remaining_logs, 6)


if __name__ == "__main__":
    unittest.main()
