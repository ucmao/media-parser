import os
import sqlite3
import tempfile
import unittest

from app import create_app
from src.auth import generate_api_key
from src.db import init_db


class TestPlaintextKeyRefactor(unittest.TestCase):
    def setUp(self):
        self.db_fd, self.db_path = tempfile.mkstemp()
        self.app = create_app({"TESTING": True, "DATABASE": self.db_path, "SECRET_KEY": "test_secret"})
        self.client = self.app.test_client()

    def tearDown(self):
        os.close(self.db_fd)
        try:
            os.unlink(self.db_path)
        except OSError:
            pass

    def test_db_migration_rekeys_legacy_database(self):
        """测试已有的旧版本数据库，在 init_db 升级后会自动赋予 mp- 开头的新明文 Key。"""
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE COLLATE NOCASE,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'user',
                active INTEGER NOT NULL DEFAULT 1,
                qps_limit INTEGER NOT NULL DEFAULT 2,
                credits INTEGER NOT NULL DEFAULT 100,
                created_at TEXT NOT NULL
            );
        """)
        conn.execute("DROP TABLE IF EXISTS api_keys;")
        conn.execute("""
            CREATE TABLE api_keys (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                name TEXT NOT NULL,
                key_hash TEXT NOT NULL UNIQUE,
                key_prefix TEXT NOT NULL,
                active INTEGER NOT NULL DEFAULT 1,
                qps_limit INTEGER,
                created_at TEXT NOT NULL,
                last_used_at TEXT
            );
        """)
        conn.execute(
            "INSERT INTO api_keys(user_id, name, key_hash, key_prefix, created_at) VALUES (?, ?, ?, ?, ?)",
            (1, "旧哈希密钥", "some_old_hash_value", "mp_old123", "2026-01-01T00:00:00"),
        )
        conn.commit()
        conn.close()

        # 执行数据库初始化升级
        with self.app.app_context():
            init_db()

            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cols = [r[1] for r in conn.execute("PRAGMA table_info(api_keys)").fetchall()]
            self.assertIn("key", cols)

            row = conn.execute("SELECT * FROM api_keys WHERE name='旧哈希密钥'").fetchone()
            self.assertIsNotNone(row)
            self.assertIsNotNone(row["key"])
            self.assertTrue(row["key"].startswith("mp-"))
            self.assertEqual(len(row["key"]), 27)  # mp- (3) + 24 rand chars = 27

            # 验证向升级后的数据库插入新 Key 不会再因 key_hash / key_prefix NOT NULL 导致报错
            conn.execute(
                "INSERT INTO api_keys(user_id, name, key, created_at) VALUES(?, ?, ?, ?)",
                (1, "新创建密钥", generate_api_key(), "2026-01-01T00:00:00"),
            )
            conn.commit()
            new_row = conn.execute("SELECT * FROM api_keys WHERE name='新创建密钥'").fetchone()
            self.assertIsNotNone(new_row)
            conn.close()

    def test_new_key_format(self):
        """测试生成的全新 API Key 格式为 mp- + 24 位字符。"""
        key = generate_api_key()
        self.assertTrue(key.startswith("mp-"))
        self.assertEqual(len(key), 27)


if __name__ == "__main__":
    unittest.main()
