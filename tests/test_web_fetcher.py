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
            ("https://kg.qq.com/node/play?s=66&noise=x", "https://kg.qq.com/node/play?s=66"),
            ("https://izuiyou.com/post/detail?pid=77&noise=x", "https://izuiyou.com/post/detail?pid=77"),
            ("https://weixin.qq.com/sph/AzGrUgqzFv?noise=x", "https://weixin.qq.com/sph/AzGrUgqzFv"),
            (
                "https://klingai-share.kuaishou.com/h5-app/share?creative_id=123&work_id=123&creative_type=WORK&noise=x",
                "https://klingai-share.kuaishou.com/h5-app/share?creative_id=123&work_id=123&creative_type=WORK",
            ),
            (
                "https://w13.soulsmile.cn/activity/#/web/topic/detail?postIdEcpt=post&sign=signature&signVersion=0.0.1&noise=x",
                "https://w13.soulsmile.cn/activity#/web/topic/detail?postIdEcpt=post&sign=signature&signVersion=0.0.1",
            ),
            (
                "https://music.douyin.com/qishui/share/ugc_video?ugc_video_id=123&noise=x",
                "https://music.douyin.com/qishui/share/ugc_video?ugc_video_id=123",
            ),
            (
                "https://channels.weixin.qq.com/finder-preview/pages/sph?id=AzGrUgqzFv&noise=x",
                "https://channels.weixin.qq.com/finder-preview/pages/sph?id=AzGrUgqzFv",
            ),
        ]
        for original, expected in cases:
            with self.subTest(original=original):
                self.assertEqual(UrlParser.extract_video_address(original), expected)

    def test_get_video_id_supports_query_path_and_html_suffix(self):
        cases = [
            ("https://www.doubao.com/video-sharing?video_id=video-id", "video-id"),
            ("https://klingai-share.kuaishou.com/h5-app/share?creative_id=123", "123"),
            ("https://w13.soulsmile.cn/activity#/web/topic/detail?postIdEcpt=post", "post"),
            ("https://music.douyin.com/qishui/share/ugc_video?ugc_video_id=123", "123"),
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

    def test_recognizes_kuaishou_random_mobile_subdomains(self):
        self.assertEqual(
            UrlParser.get_platform("https://random-value.m.chenzhongtech.com/fw/photo/123"),
            "快手",
        )

    def test_rejects_domains_that_only_resemble_kuaishou_mobile_subdomains(self):
        unsupported_urls = [
            "https://random-value.m.chenzhongtech.com.evil.example/fw/photo/123",
            "https://random-valuem.chenzhongtech.com/fw/photo/123",
            "https://fakechenzhongtech.com/fw/photo/123",
        ]
        for url in unsupported_urls:
            with self.subTest(url=url):
                self.assertIsNone(UrlParser.get_platform(url))

    def test_recognizes_wechat_channels_domains(self):
        self.assertEqual(UrlParser.get_platform("https://weixin.qq.com/sph/AzGrUgqzFv"), "微信视频号")
        self.assertEqual(
            UrlParser.get_platform("https://channels.weixin.qq.com/finder-preview/pages/sph?id=abc"),
            "微信视频号",
        )

    def test_recognizes_kling_share_domain(self):
        self.assertEqual(
            UrlParser.get_platform("https://klingai-share.kuaishou.com/h5-app/share?creative_id=123"),
            "可灵 AI",
        )

    def test_recognizes_soul_share_domain(self):
        self.assertEqual(UrlParser.get_platform("https://w13.soulsmile.cn/activity/"), "Soul")

    def test_recognizes_qishui_music_domains(self):
        self.assertEqual(UrlParser.get_platform("https://qishui.douyin.com/s/code/"), "汽水音乐")
        self.assertEqual(UrlParser.get_platform("https://music.douyin.com/track/123"), "汽水音乐")

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

    def test_accepts_kuaishou_random_mobile_subdomain_redirect(self):
        redirect_url = "https://random-value.m.chenzhongtech.com/fw/photo/123?noise=x"
        with patch(
            "utils.web_fetcher.requests.get",
            return_value=self.response(redirect_url),
        ):
            result = WebFetcher.fetch_redirect_url("https://v.kuaishou.com/short-code")
        self.assertEqual(result, "https://random-value.m.chenzhongtech.com/fw/photo/123")

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
