import base64
import html
import json
import unittest
from unittest.mock import Mock, patch

from src.parsers.doubao_parser import DoubaoParser
from utils.web_fetcher import UrlParser


class DoubaoParserTest(unittest.TestCase):
    def test_thread_parses_images_and_videos_from_nested_json(self):
        video_url = "https://video.example.com/source.mp4?token=abc"
        video_model = json.dumps({
            "video_list": [{
                "main_url": base64.b64encode(video_url.encode()).decode(),
            }]
        })
        message_content = json.dumps([{
            "title": "测试豆包作品",
            "creation_block": {
                "creations": [
                    {"image": {"image_ori_raw": {"url": "https://image.example.com/original.png"}}},
                    {"video": {"video_model": video_model}},
                ]
            },
        }], ensure_ascii=False)
        router_payload = {
            "data": {
                "message_snapshot": {
                    "message_list": [{"content": message_content}]
                }
            }
        }
        script_payload = [
            "thread_(token)/page",
            [{"key": "shareInfo", "routerDataFnArgs": [json.dumps(router_payload, ensure_ascii=False)]}],
        ]
        page = (
            '<script data-fn-name="mergeLoaderData" data-script-src="modern-run-window-fn" '
            f'data-fn-args="{html.escape(json.dumps(script_payload, ensure_ascii=False), quote=True)}"></script>'
        )
        response = Mock(text=page)
        response.raise_for_status.return_value = None

        with patch("requests.Session.get", return_value=response):
            parser = DoubaoParser("https://www.doubao.com/thread/example")

        self.assertEqual(parser.get_title_content(), "测试豆包作品")
        self.assertEqual(parser.get_image_list(), ["https://image.example.com/original.png"])
        self.assertEqual(parser.get_video_list(), [video_url])
        self.assertEqual(parser.get_real_video_url(), video_url)

    def test_video_sharing_uses_official_api_response(self):
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {
            "code": 0,
            "data": {
                "prompt": "测试独立视频",
                "play_info": {
                    "main": "https://video.example.com/main.mp4?lr=video_gen_watermark_dyn&download=true&token=abc",
                    "backup": "https://video.example.com/backup.mp4",
                    "poster_url": "https://image.example.com/poster.jpg",
                },
                "user_info": {
                    "nickname": "测试作者",
                    "user_id": 123,
                },
            },
        }
        url = (
            "https://www.doubao.com/video-sharing?share_id=456"
            "&source_type=mobile&video_id=video123&share_scene=video_viewer"
        )

        with patch("requests.Session.post", return_value=response) as post:
            parser = DoubaoParser(url)

        self.assertEqual(parser.get_real_video_url(), "https://video.example.com/main.mp4?token=abc")
        self.assertEqual(parser.get_video_list(), ["https://video.example.com/main.mp4?token=abc"])
        self.assertEqual(parser.get_cover_photo_url(), "https://image.example.com/poster.jpg")
        self.assertEqual(parser.get_author_info()["author_id"], "123")
        self.assertEqual(post.call_args.kwargs["json"]["vid"], "video123")

    def test_url_parser_preserves_video_sharing_parameters(self):
        url = (
            "https://www.doubao.com/video-sharing?share_id=456"
            "&source_type=mobile&video_id=video123&share_scene=video_viewer&ignored=value"
        )

        normalized = UrlParser.extract_video_address(url)

        self.assertIn("share_id=456", normalized)
        self.assertIn("video_id=video123", normalized)
        self.assertNotIn("ignored=value", normalized)
        self.assertEqual(UrlParser.get_video_id(normalized), "video123")

    def test_video_sharing_without_required_ids_does_not_call_api(self):
        with patch("requests.Session.post") as post:
            parser = DoubaoParser("https://www.doubao.com/video-sharing?share_id=456")

        post.assert_not_called()
        self.assertIsNone(parser.get_real_video_url())
        self.assertEqual(parser.get_video_list(), [])

    def test_thread_video_urls_drop_watermarks_and_keep_signed_parameters(self):
        clean_url = "https://video.example.com/source.mp4?token=abc&lr=1"
        watermarked_url = "https://video.example.com/video_gen_watermark.mp4"
        video = {
            "download_url": watermarked_url,
            "video_model": json.dumps({
                "video_list": [{
                    "main_url": base64.b64encode(clean_url.encode()).decode(),
                }]
            }),
        }

        self.assertEqual(
            DoubaoParser._extract_thread_video_urls(video),
            ["https://video.example.com/source.mp4?token=abc"],
        )


if __name__ == "__main__":
    unittest.main()
