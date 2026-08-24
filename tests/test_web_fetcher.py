import unittest
from unittest.mock import Mock, patch

import requests

from utils.web_fetcher import UrlParser, WebFetcher


class UrlParserTest(unittest.TestCase):
    def test_extracts_url_from_share_text(self):
        text = "复制打开应用 https://v.douyin.com/abc123/ 查看作品"
        self.assertEqual(UrlParser.get_url(text), "https://v.douyin.com/abc123/")

    def test_get_url_handles_non_string_values(self):
        for value in (None, 1, {}, []):
            with self.subTest(value=value):
                self.assertIsNone(UrlParser.get_url(value))

    def test_preserves_only_platform_specific_query_parameters(self):
        cases = [
            ("https://haokan.baidu.com/v?vid=11&noise=x", "https://haokan.baidu.com/v?vid=11"),
            ("https://isee.weishi.qq.com/ws/app-pages/share/index.html?id=22&noise=x", "https://isee.weishi.qq.com/ws/app-pages/share/index.html?id=22"),
            ("https://www.xiaohongshu.com/explore/33?xsec_token=token&noise=x", "https://www.xiaohongshu.com/explore/33?xsec_token=token"),
            ("https://www.douyin.com/?modal_id=44&noise=x", "https://www.douyin.com?modal_id=44"),
            ("https://www.youtube.com/watch?v=55&feature=share", "https://www.youtube.com/watch?v=55"),
            ("https://kg.qq.com/node/play?s=66&noise=x", "https://kg.qq.com/node/play?s=66"),
            ("https://izuiyou.com/post/detail?pid=77&noise=x", "https://izuiyou.com/post/detail?pid=77"),
        ]
        for original, expected in cases:
            with self.subTest(original=original):
                self.assertEqual(UrlParser.extract_video_address(original), expected)

    def test_get_video_id_supports_query_path_and_html_suffix(self):
        cases = [
            ("https://www.youtube.com/watch?v=query-id", "query-id"),
            ("https://www.doubao.com/video-sharing?video_id=video-id", "video-id"),
            ("https://www.bilibili.com/video/BV123", "BV123"),
            ("https://www.pearvideo.com/video_123.html", "video_123"),
        ]
        for url, expected in cases:
            with self.subTest(url=url):
                self.assertEqual(UrlParser.get_video_id(url), expected)

    def test_converts_only_http_urls(self):
        self.assertEqual(UrlParser.convert_to_https("http://example.com/a"), "https://example.com/a")
        self.assertEqual(UrlParser.convert_to_https("https://example.com/a"), "https://example.com/a")
        self.assertIsNone(UrlParser.convert_to_https(None))


class WebFetcherTest(unittest.TestCase):
    @staticmethod
    def response(location=None, status_code=200):
        response = Mock(status_code=status_code)
        response.headers = {"location": location} if location else {}
        response.raise_for_status.return_value = None
        return response

    def test_returns_supported_url_without_redirect(self):
        with patch("utils.web_fetcher.requests.get", return_value=self.response()):
            result = WebFetcher.fetch_redirect_url("https://www.douyin.com/video/123?noise=x")
        self.assertEqual(result, "https://www.douyin.com/video/123")

    def test_follows_relative_redirect(self):
        responses = [
            self.response("https://www.douyin.com/share/123"),
        ]
        with patch("utils.web_fetcher.requests.get", side_effect=responses):
            result = WebFetcher.fetch_redirect_url("https://short.example/a")
        self.assertEqual(result, "https://www.douyin.com/share/123")

    def test_stops_before_login_or_verification_page(self):
        for blocked_path in ("/login", "/404", "/captcha", "/verify", "/error"):
            with self.subTest(blocked_path=blocked_path):
                with patch(
                    "utils.web_fetcher.requests.get",
                    return_value=self.response(f"https://www.douyin.com{blocked_path}"),
                ):
                    result = WebFetcher.fetch_redirect_url("https://www.douyin.com/video/123")
                self.assertEqual(result, "https://www.douyin.com/video/123")

    def test_returns_none_for_unsupported_final_domain(self):
        with patch("utils.web_fetcher.requests.get", return_value=self.response()):
            self.assertIsNone(WebFetcher.fetch_redirect_url("https://unsupported.example/a"))

    def test_returns_none_after_redirect_limit(self):
        with patch(
            "utils.web_fetcher.requests.get",
            return_value=self.response("https://unsupported.example/next"),
        ):
            self.assertIsNone(WebFetcher.fetch_redirect_url("https://unsupported.example/start", max_redirects=2))

    def test_returns_none_on_request_error_or_invalid_input(self):
        with patch(
            "utils.web_fetcher.requests.get",
            side_effect=requests.RequestException("network error"),
        ):
            self.assertIsNone(WebFetcher.fetch_redirect_url("https://www.douyin.com/video/1"))
        self.assertIsNone(WebFetcher.fetch_redirect_url(None))
        self.assertIsNone(WebFetcher.fetch_redirect_url("", max_redirects=0))


if __name__ == "__main__":
    unittest.main()
