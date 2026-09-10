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

    def test_db_init_schema(self):
        """测试 init_db 初始化的数据库包含包含 key 和 credits 字段的最新 Schema。"""
        with self.app.app_context():
            init_db()

            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            user_cols = [r[1] for r in conn.execute("PRAGMA table_info(users)").fetchall()]
            key_cols = [r[1] for r in conn.execute("PRAGMA table_info(api_keys)").fetchall()]
            self.assertIn("credits", user_cols)
            self.assertIn("key", key_cols)
            conn.close()

    def test_new_key_format(self):
        """测试生成的全新 API Key 格式为 mp- + 24 位字符。"""
        key = generate_api_key()
        self.assertTrue(key.startswith("mp-"))
        self.assertEqual(len(key), 27)


if __name__ == "__main__":
    unittest.main()
