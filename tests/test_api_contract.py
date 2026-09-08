import unittest
from unittest.mock import Mock, patch

from app import app
from src.api.parse import _fetch_with_retry, safe_execute


class ApiContractTest(unittest.TestCase):
    def setUp(self):
        app.testing = True
        self.client = app.test_client()

    def test_health_check(self):
        response = self.client.get("/api/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), {"status": "ok"})

    def test_index_page(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("Media Parser", response.get_data(as_text=True))
        self.assertIn("多平台媒体解析", response.get_data(as_text=True))
        self.assertIn("githubStars", response.get_data(as_text=True))
        self.assertIn("api.github.com/repos/ucmao/media-parser", response.get_data(as_text=True))
        self.assertIn("开源自部署", response.get_data(as_text=True))
        self.assertNotIn("套餐资费", response.get_data(as_text=True))
        self.assertNotIn("SLA 99.9%", response.get_data(as_text=True))
        self.assertNotIn("绝对保证", response.get_data(as_text=True))
        self.assertNotIn("小程序", response.get_data(as_text=True))
        self.assertNotIn("qr_code", response.get_data(as_text=True))
        self.assertIn('id="subtitleContainer"', response.get_data(as_text=True))
        self.assertIn('id="resultAuthorAvatar"', response.get_data(as_text=True))
        self.assertNotIn('>正文</span><span id="resultDescText"', response.get_data(as_text=True))
        self.assertIn("normalizeSubtitles", response.get_data(as_text=True))
        self.assertIn("copyFormattedResult", response.get_data(as_text=True))
        self.assertIn("格式化复制", response.get_data(as_text=True))
        self.assertIn("视频列表：", response.get_data(as_text=True))
        self.assertIn("图集：", response.get_data(as_text=True))
        self.assertIn("字幕/歌词：", response.get_data(as_text=True))
        self.assertIn("【使用声明】上述内容及素材版权均归原平台及创作者所有。", response.get_data(as_text=True))

    @staticmethod
    def parser(**overrides):
        values = {
            "title": "测试作品",
            "desc": None,
            "video_url": "https://example.com/video.mp4",
            "video_list": [],
            "cover_url": "https://example.com/cover.jpg",
            "author": None,
            "image_list": [],
            "audio_url": None,
            "subtitles": None,
        }
        values.update(overrides)
        parser = Mock()
        parser.get_title_content.return_value = values["title"]
        parser.get_description.return_value = values["desc"]
        parser.get_real_video_url.return_value = values["video_url"]
        parser.get_video_list.return_value = values["video_list"]
        parser.get_cover_photo_url.return_value = values["cover_url"]
        parser.get_author_info.return_value = values["author"]
        parser.get_image_list.return_value = values["image_list"]
        parser.get_audio_url.return_value = values["audio_url"]
        parser.get_subtitles.return_value = values["subtitles"]
        return parser

    def post_with_parser(self, parser, redirect_url="https://www.douyin.com/video/123"):
        with patch("src.api.parse.WebFetcher.fetch_redirect_url", return_value=redirect_url):
            with patch("src.api.parse.ParserFactory.create_parser", return_value=parser):
                return self.client.post("/api/parse", json={"text": "https://example.com/share"})

    def assert_bad_request(self, response, message, error_code):
        self.assertEqual(response.status_code, 400)
        payload = response.get_json()
        self.assertFalse(payload["succ"])
        self.assertEqual(payload["retcode"], 400)
        self.assertEqual(payload["retdesc"], message)
        self.assertEqual(payload["error_code"], error_code)

    def test_rejects_non_json_body(self):
        response = self.client.post("/api/parse", data="text")
        self.assert_bad_request(response, "请求体必须是 JSON 对象", "INVALID_REQUEST")

    def test_rejects_missing_or_blank_text(self):
        for body in ({}, {"text": "  "}, {"text": 123}):
            with self.subTest(body=body):
                response = self.client.post("/api/parse", json=body)
                self.assert_bad_request(response, "请提供包含分享链接的文本", "INVALID_TEXT")

    def test_rejects_overlong_text(self):
        response = self.client.post("/api/parse", json={"text": "a" * 2001})
        self.assert_bad_request(response, "分享文本不能超过 2000 个字符", "TEXT_TOO_LONG")

    def test_rejects_text_without_url(self):
        response = self.client.post("/api/parse", json={"text": "没有链接"})
        self.assert_bad_request(response, "未找到有效的分享链接", "URL_NOT_FOUND")

    def test_rejects_unresolvable_redirect(self):
        with patch("src.api.parse.WebFetcher.fetch_redirect_url", return_value=None):
            response = self.client.post("/api/parse", json={"text": "https://example.com"})
        self.assert_bad_request(response, "无法访问或识别该分享链接", "REDIRECT_FAILED")

    def test_rejects_unsupported_domain(self):
        response = self.post_with_parser(self.parser(), "https://unsupported.example/video/1")
        self.assert_bad_request(response, "该链接尚未支持提取", "PLATFORM_NOT_SUPPORTED")

    def test_rejects_empty_media_with_platform_specific_message(self):
        empty_parser = self.parser(video_url=None, video_list=[], image_list=[])
        cases = [
            ("https://www.douyin.com/video/1", "提取媒体内容失败，请检查链接或稍后重试", "MEDIA_NOT_FOUND"),
            (
                "https://www.xiaohongshu.com/explore/1",
                "解析失败：该链接需要小红书登录 Cookie 校验，请在配置中提供有效 Cookie 后重试",
                "XIAOHONGSHU_COOKIE_REQUIRED",
            ),
            (
                "https://mobile.yangkeduo.com/fyxmkief.html?feed_id=1",
                "解析失败：该链接需要拼多多登录 Cookie 校验，请在配置中提供有效 Cookie 后重试",
                "PINDUODUO_COOKIE_REQUIRED",
            ),
        ]
        for url, message, error_code in cases:
            with self.subTest(url=url):
                self.assert_bad_request(self.post_with_parser(empty_parser, url), message, error_code)

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

    def test_response_exposes_optional_description(self):
        response = self.post_with_parser(self.parser(desc="这是作品正文"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["data"]["desc"], "这是作品正文")

    def test_response_keeps_null_description_when_unsupported(self):
        response = self.post_with_parser(self.parser())

        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.get_json()["data"]["desc"])

    def test_response_exposes_subtitles(self):
        subtitles = [
            {"start": 1.25, "end": 3.5, "text": "第一句字幕"},
            {"start": 4, "text": "第二句歌词"},
            {"text": "未带时间的歌词"},
        ]
        response = self.post_with_parser(self.parser(subtitles=subtitles))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["data"]["subtitles"], subtitles)

    def test_response_uses_description_as_legacy_title_fallback(self):
        response = self.post_with_parser(self.parser(title="同一段文案", desc="同一段文案"))

        self.assertEqual(response.status_code, 200)
        data = response.get_json()["data"]
        self.assertEqual(data["title"], "同一段文案")
        self.assertEqual(data["desc"], "同一段文案")

        response = self.post_with_parser(self.parser(title=None, desc="只有正文"))
        data = response.get_json()["data"]
        self.assertEqual(data["title"], "只有正文")
        self.assertEqual(data["desc"], "只有正文")

    def test_image_only_result_is_successful(self):
        response = self.post_with_parser(
            self.parser(
                video_url=None,
                video_list=[],
                cover_url=None,
                image_list=["https://example.com/1.jpg"],
            )
        )
        self.assertEqual(response.status_code, 200)
        data = response.get_json()["data"]
        self.assertIsNone(data["video_url"])
        self.assertEqual(data["cover_url"], "https://example.com/1.jpg")

    def test_unexpected_parser_error_uses_stable_500_contract(self):
        with patch("src.api.parse.WebFetcher.fetch_redirect_url", side_effect=RuntimeError("boom")):
            response = self.client.post("/api/parse", json={"text": "https://example.com"})
        self.assertEqual(response.status_code, 500)
        payload = response.get_json()
        self.assertEqual(payload["retdesc"], "功能太火爆啦，请稍后再试")
        self.assertEqual(payload["error_code"], "INTERNAL_ERROR")

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

    def test_api_response_includes_tip_payload(self):
        response = self.client.get("/api/health")
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["status"], "ok")

        # Test make_response contract
        from src.api.response import make_response
        with app.test_request_context():
            res = make_response(200, "ok", {"foo": "bar"}, True)
            data = res.get_json()
            self.assertIn("_tip", data)
            self.assertEqual(data["_tip"]["author"], "ucmao")
            self.assertEqual(data["_tip"]["website"], "https://github.com/ucmao/media-parser")
            self.assertEqual(data["_tip"]["notice"], "本接口由开源项目 media-parser 提供服务")


if __name__ == "__main__":
    unittest.main()
