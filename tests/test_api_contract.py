import unittest
from unittest.mock import Mock, patch

import py_mini_racer


if not hasattr(py_mini_racer, "MiniRacer"):
    py_mini_racer.MiniRacer = object

from app import app
from src.api.parse import _fetch_with_retry, safe_execute


class ApiContractTest(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    @staticmethod
    def parser(**overrides):
        values = {
            "title": "测试作品",
            "video_url": "https://example.com/video.mp4",
            "video_list": [],
            "cover_url": "https://example.com/cover.jpg",
            "author": None,
            "image_list": [],
            "audio_url": None,
        }
        values.update(overrides)
        parser = Mock()
        parser.get_title_content.return_value = values["title"]
        parser.get_real_video_url.return_value = values["video_url"]
        parser.get_video_list.return_value = values["video_list"]
        parser.get_cover_photo_url.return_value = values["cover_url"]
        parser.get_author_info.return_value = values["author"]
        parser.get_image_list.return_value = values["image_list"]
        parser.get_audio_url.return_value = values["audio_url"]
        return parser

    def post_with_parser(self, parser, redirect_url="https://www.douyin.com/video/123"):
        with patch("src.api.parse.WebFetcher.fetch_redirect_url", return_value=redirect_url):
            with patch("src.api.parse.ParserFactory.create_parser", return_value=parser):
                return self.client.post("/api/parse", json={"text": "https://example.com/share"})

    def assert_bad_request(self, response, message):
        self.assertEqual(response.status_code, 400)
        payload = response.get_json()
        self.assertFalse(payload["succ"])
        self.assertEqual(payload["retcode"], 400)
        self.assertEqual(payload["retdesc"], message)

    def test_rejects_non_json_body(self):
        response = self.client.post("/api/parse", data="text")
        self.assert_bad_request(response, "请求体必须是 JSON 对象")

    def test_rejects_missing_or_blank_text(self):
        for body in ({}, {"text": "  "}, {"text": 123}):
            with self.subTest(body=body):
                response = self.client.post("/api/parse", json=body)
                self.assert_bad_request(response, "请提供包含分享链接的文本")

    def test_rejects_text_without_url(self):
        response = self.client.post("/api/parse", json={"text": "没有链接"})
        self.assert_bad_request(response, "未找到有效的分享链接")

    def test_rejects_unresolvable_redirect(self):
        with patch("src.api.parse.WebFetcher.fetch_redirect_url", return_value=None):
            response = self.client.post("/api/parse", json={"text": "https://example.com"})
        self.assert_bad_request(response, "无法访问或识别该分享链接")

    def test_rejects_unsupported_domain(self):
        response = self.post_with_parser(self.parser(), "https://unsupported.example/video/1")
        self.assert_bad_request(response, "该链接尚未支持提取")

    def test_rejects_empty_media_with_platform_specific_message(self):
        empty_parser = self.parser(video_url=None, video_list=[], image_list=[])
        cases = [
            ("https://www.douyin.com/video/1", "提取媒体内容失败，请检查链接或稍后重试"),
            (
                "https://www.xiaohongshu.com/explore/1",
                "解析失败：该链接需要小红书登录 Cookie 校验，请在配置中提供有效 Cookie 后重试",
            ),
        ]
        for url, message in cases:
            with self.subTest(url=url):
                self.assert_bad_request(self.post_with_parser(empty_parser, url), message)

    def test_normalizes_and_deduplicates_media_urls(self):
        parser = self.parser(
            video_url="http://cdn.example/main.mp4",
            video_list=[
                "http://cdn.example/other.mp4",
                "http://cdn.example/main.mp4",
                "http://cdn.example/other.mp4",
                None,
            ],
            audio_url="http://cdn.example/audio.mp3",
            cover_url="http://cdn.example/cover.jpg",
            image_list=[
                "http://cdn.example/image.jpg",
                {
                    "url": "http://cdn.example/live.jpg",
                    "live_photo_url": "http://cdn.example/live.mp4",
                },
            ],
        )

        response = self.post_with_parser(parser)

        self.assertEqual(response.status_code, 200)
        data = response.get_json()["data"]
        self.assertEqual(data["video_url"], "https://cdn.example/main.mp4")
        self.assertEqual(
            data["video_list"],
            ["https://cdn.example/main.mp4", "https://cdn.example/other.mp4"],
        )
        self.assertEqual(data["audio_url"], "https://cdn.example/audio.mp3")
        self.assertEqual(data["cover_url"], "https://cdn.example/cover.jpg")
        self.assertEqual(data["image_list"][0], "https://cdn.example/image.jpg")
        self.assertEqual(data["image_list"][1]["live_photo_url"], "https://cdn.example/live.mp4")

    def test_image_only_result_is_successful(self):
        response = self.post_with_parser(
            self.parser(video_url=None, video_list=[], image_list=["https://example.com/1.jpg"])
        )
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.get_json()["data"]["video_url"])

    def test_unexpected_parser_error_uses_stable_500_contract(self):
        with patch("src.api.parse.WebFetcher.fetch_redirect_url", side_effect=RuntimeError("boom")):
            response = self.client.post("/api/parse", json={"text": "https://example.com"})
        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.get_json()["retdesc"], "功能太火爆啦，请稍后再试")

    def test_xiaohongshu_retries_three_times(self):
        parser = self.parser(video_url=None, video_list=[], image_list=[])
        _fetch_with_retry(parser, "小红书")
        self.assertEqual(parser.get_real_video_url.call_count, 3)

    def test_other_platform_does_not_retry(self):
        parser = self.parser(video_url=None, video_list=[], image_list=[])
        _fetch_with_retry(parser, "抖音")
        self.assertEqual(parser.get_real_video_url.call_count, 1)

    def test_safe_execute_returns_default_on_error(self):
        self.assertEqual(
            safe_execute(Mock(side_effect=RuntimeError("boom")), default=[]),
            [],
        )


if __name__ == "__main__":
    unittest.main()
