import json
import unittest
from unittest.mock import Mock, patch

from src.parsers.hailuo_parser import HailuoParser
from utils.web_fetcher import UrlParser


class HailuoParserTest(unittest.TestCase):
    def test_parses_nextjs_flight_ssr_payload(self):
        video_asset = {
            "id": "546156739889123328",
            "desc": "第一秒的时候轻微点头，第二秒连续摇头",
            "coverURL": "https://cdn.hailuoai.com/cover.jpg",
            "videoURL": "https://cdn.hailuoai.com/preview.mp4",
            "downloadURL": "https://cdn.hailuoai.com/download.mp4",
            "userIDStr": "546139659380772869",
            "originFiles": [
                {
                    "id": "1",
                    "url": "https://cdn.hailuoai.com/ref1.jpg",
                    "coverUrl": "https://cdn.hailuoai.com/ref1_thumb.jpg",
                },
                {
                    "id": "2",
                    "url": "https://cdn.hailuoai.com/ref2.jpg",
                },
            ],
            "videoURLs": {
                "downloadURLWithAIWatermark": "https://cdn.hailuoai.com/clean_ai.mp4",
                "downloadURLWithHailuoWatermark": "https://cdn.hailuoai.com/brand_hailuo.mp4",
            },
        }

        # 构建类似于 Next.js Flight SSR 的 push 片段
        flight_tree = ["$", "div", None, {"video": {"videoAsset": video_asset}}]
        flight_chunk = "25:" + json.dumps(flight_tree, ensure_ascii=False)
        escaped_chunk = json.dumps(flight_chunk)[1:-1]  # 去掉前后引号，作为 js 字符串

        html_text = (
            '<!DOCTYPE html><html><head></head><body>'
            f'<script>self.__next_f.push([1,"{escaped_chunk}"])</script>'
            '</body></html>'
        )

        response = Mock(text=html_text)
        response.raise_for_status.return_value = None

        with patch("requests.Session.get", return_value=response) as get:
            parser = HailuoParser("https://hailuoai.com/share/ai-video/enbrdg0JlAen?source-scene=shared")

        self.assertEqual(parser.get_title_content(), "第一秒的时候轻微点头，第二秒连续摇头")
        # 优先选用去品牌水印的 downloadURLWithAIWatermark
        self.assertEqual(parser.get_real_video_url(), "https://cdn.hailuoai.com/clean_ai.mp4")
        self.assertEqual(parser.get_cover_photo_url(), "https://cdn.hailuoai.com/cover.jpg")
        self.assertEqual(parser.get_author_info()["author_id"], "546139659380772869")
        self.assertEqual(
            parser.get_image_list(),
            ["https://cdn.hailuoai.com/ref1.jpg", "https://cdn.hailuoai.com/ref2.jpg"],
        )

    def test_parses_json_ld_fallback(self):
        ld_json = {
            "@context": "https://schema.org",
            "@graph": [
                {
                    "@type": "VideoObject",
                    "name": "海螺视频测试标题",
                    "description": "这是详细描述",
                    "contentUrl": "https://cdn.hailuoai.com/ld_video.mp4",
                    "thumbnailUrl": "https://cdn.hailuoai.com/ld_thumb.jpg",
                    "author": {"@type": "Person", "name": "创作者小明"},
                }
            ],
        }

        html_text = (
            '<!DOCTYPE html><html><head>'
            f'<script type="application/ld+json">{json.dumps(ld_json)}</script>'
            '</head><body></body></html>'
        )

        response = Mock(text=html_text)
        response.raise_for_status.return_value = None

        with patch("requests.Session.get", return_value=response):
            parser = HailuoParser("https://hailuoai.com/share/ai-video/test123")

        self.assertEqual(parser.get_title_content(), "这是详细描述")
        self.assertEqual(parser.get_real_video_url(), "https://cdn.hailuoai.com/ld_video.mp4")
        self.assertEqual(parser.get_cover_photo_url(), "https://cdn.hailuoai.com/ld_thumb.jpg")
        self.assertEqual(parser.get_author_info()["nickname"], "创作者小明")

    def test_handles_empty_or_failed_response(self):
        response = Mock(text="")
        response.raise_for_status.return_value = None

        with patch("requests.Session.get", return_value=response):
            parser = HailuoParser("https://hailuoai.com/share/ai-video/invalid")

        self.assertIsNone(parser.get_real_video_url())
        self.assertEqual(parser.get_title_content(), "海螺AI 作品")
        self.assertIsNone(parser.get_cover_photo_url())
        self.assertIsNone(parser.get_author_info())
        self.assertEqual(parser.get_image_list(), [])


class HailuoUrlParserTest(unittest.TestCase):
    def test_detects_hailuo_domains(self):
        cases = [
            ("https://hailuoai.com/share/ai-video/enbrdg0JlAen?source-scene=shared", "海螺AI"),
            ("https://www.hailuoai.com/share/ai-video/enbrdg0JlAen", "海螺AI"),
            ("https://hailuoai.video/share/ai-video/RkDkwWYZQRby", "海螺AI"),
            ("https://www.hailuoai.video/share/ai-video/RkDkwWYZQRby", "海螺AI"),
        ]
        for url, expected_platform in cases:
            with self.subTest(url=url):
                self.assertEqual(UrlParser.get_platform(url), expected_platform)

    def test_extracts_clean_address(self):
        url = "https://hailuoai.com/share/ai-video/enbrdg0JlAen?source-scene=shared&source-media=shared_wechat"
        clean = UrlParser.extract_video_address(url)
        self.assertEqual(clean, "https://hailuoai.com/share/ai-video/enbrdg0JlAen")

    def test_extracts_video_id(self):
        url = "https://hailuoai.com/share/ai-video/enbrdg0JlAen?source-scene=shared"
        video_id = UrlParser.get_video_id(url)
        self.assertEqual(video_id, "enbrdg0JlAen")
