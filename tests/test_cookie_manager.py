import os
import unittest
from unittest.mock import patch

from src.utils.cookie_manager import get_platform_cookie, PLATFORM_COOKIE_ALIASES


class CookieManagerTest(unittest.TestCase):
    def test_reads_direct_env_var(self):
        with patch.dict(os.environ, {"XHS_COOKIE": "a1=from_env_123;"}):
            cookie = get_platform_cookie("xhs")
            self.assertEqual(cookie, "a1=from_env_123;")

    def test_reads_custom_env_var(self):
        with patch.dict(os.environ, {"MY_CUSTOM_COOKIE": "token=custom_456;"}):
            cookie = get_platform_cookie("douyin", env_var="MY_CUSTOM_COOKIE")
            self.assertEqual(cookie, "token=custom_456;")

    def test_falls_back_to_alias_env(self):
        with patch.dict(os.environ, {"XHS_COOKIE": "a1=from_alias_789;", "XIAOHONGSHU_COOKIE": ""}):
            cookie = get_platform_cookie("xiaohongshu")
            self.assertEqual(cookie, "a1=from_alias_789;")

    def test_xiaohongshu_official_name_wins_over_alias(self):
        with patch.dict(os.environ, {"XIAOHONGSHU_COOKIE": "a1=official;", "XHS_COOKIE": "a1=alias;"}):
            self.assertEqual(get_platform_cookie("xiaohongshu"), "a1=official;")

    def test_returns_empty_string_when_not_configured(self):
        with patch.dict(os.environ, {}, clear=True):
            cookie = get_platform_cookie("nonexistent_platform")
            self.assertEqual(cookie, "")

    def test_db_setting_overrides_env_var(self):
        with patch("src.db.setting", side_effect=lambda k: "hybrid_sess=from_db;" if k == "cookie_wechat_channels" else None):
            with patch.dict(os.environ, {"YUANBAO_COOKIE": "pass_ticket=from_env;"}):
                cookie = get_platform_cookie("wechat_channels")
                self.assertEqual(cookie, "hybrid_sess=from_db;")

    def test_db_setting_empty_falls_back_to_env_var(self):
        with patch("src.db.setting", return_value=""):
            with patch.dict(os.environ, {"YUANBAO_COOKIE": "pass_ticket=from_env;"}):
                cookie = get_platform_cookie("wechat_channels")
                self.assertEqual(cookie, "pass_ticket=from_env;")

    def test_db_setting_yuanbao_reads_wechat_channels_cookie(self):
        with patch("src.db.setting", side_effect=lambda k: "hybrid_sess=from_db;" if k == "cookie_wechat_channels" else None):
            with patch.dict(os.environ, {}, clear=True):
                cookie = get_platform_cookie("yuanbao")
                self.assertEqual(cookie, "hybrid_sess=from_db;")

    def test_supported_platform_aliases(self):
        self.assertIn("xhs", PLATFORM_COOKIE_ALIASES)
        self.assertIn("douyin", PLATFORM_COOKIE_ALIASES)
        self.assertIn("doubao", PLATFORM_COOKIE_ALIASES)
        self.assertIn("yuanbao", PLATFORM_COOKIE_ALIASES)
        self.assertIn("pinduoduo", PLATFORM_COOKIE_ALIASES)


if __name__ == "__main__":
    unittest.main()
