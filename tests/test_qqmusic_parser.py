import json
import unittest
from unittest.mock import Mock, patch

from src.parsers.qqmusic_parser import QQMusicParser


class QQMusicParserTest(unittest.TestCase):
    URL = "https://i2.y.qq.com/n3/other/pages/details/mv.html?vid=012XViNT0znYUR"

    @staticmethod
    def response(*, text="", payload=None, url=URL):
        response = Mock()
        response.text = text
        response.url = url
        response.json.return_value = payload or {}
        response.raise_for_status.return_value = None
        return response

    @staticmethod
    def ssr_html():
        payload = {
            "data": {
                "video": {
                    "name": "《Speed of Summer》WINTER Teaser",
                    "cover_pic": "http://img.tencentmusic.com/cover.jpg",
                    "uploader_nick": "普通搞笑人类",
                },
                "creator": [
                    {
                        "nick": "普通搞笑人类",
                        "mid": "creator-id",
                        "avatar": "https://y.qq.com/avatar.png",
                    }
                ],
            }
        }
        encoded = json.dumps(json.dumps(payload, ensure_ascii=False))
        return f"<script>window.__ssrFirstPageData__={encoded}</script>"

    @staticmethod
    def api_payload():
        return {
            "mvInfo": {
                "data": {
                    "012XViNT0znYUR": {
                        "name": "API title",
                        "cover_pic": "http://img.tencentmusic.com/api-cover.jpg",
                    }
                }
            },
            "mvUrl": {
                "data": {
                    "012XViNT0znYUR": {
                        "mp4": [
                            {"code": 0, "filetype": 20, "freeflow_url": ["http://v0.stream.tencentmusic.com/720.mp4"]},
                            {"code": 0, "filetype": 40, "freeflow_url": ["http://v0.stream.tencentmusic.com/1080.mp4"]},
                            {"code": 2000, "filetype": 60, "freeflow_url": []},
                        ]
                    }
                }
            },
        }

    @patch("src.parsers.base_parser.requests.Session.post")
    @patch("src.parsers.base_parser.requests.Session.get")
    def test_parses_ssr_metadata_and_highest_quality_video(self, get, post):
        get.return_value = self.response(text=self.ssr_html())
        post.return_value = self.response(payload=self.api_payload())

        parser = QQMusicParser(self.URL)

        self.assertEqual(parser.get_title_content(), "《Speed of Summer》WINTER Teaser")
        self.assertEqual(parser.get_cover_photo_url(), "http://img.tencentmusic.com/cover.jpg")
        self.assertEqual(parser.get_author_info()["nickname"], "普通搞笑人类")
        self.assertEqual(parser.get_real_video_url(), "http://v0.stream.tencentmusic.com/1080.mp4")
        self.assertEqual(
            parser.get_video_list(),
            [
                "http://v0.stream.tencentmusic.com/1080.mp4",
                "http://v0.stream.tencentmusic.com/720.mp4",
            ],
        )

    @patch("src.parsers.base_parser.requests.Session.post")
    @patch("src.parsers.base_parser.requests.Session.get")
    def test_supports_desktop_mv_path(self, get, post):
        get.return_value = self.response(text="", url="https://y.qq.com/n/ryqq/mv/0140GhZ72SKjiQ")
        post.return_value = self.response(payload={})
        parser = QQMusicParser("https://y.qq.com/n/ryqq/mv/0140GhZ72SKjiQ")
        self.assertEqual(parser.vid, "0140GhZ72SKjiQ")

    @patch("src.parsers.base_parser.requests.Session.post")
    @patch("src.parsers.base_parser.requests.Session.get")
    def test_handles_unavailable_streams(self, get, post):
        get.return_value = self.response(text=self.ssr_html())
        post.return_value = self.response(payload={})
        parser = QQMusicParser(self.URL)
        self.assertIsNone(parser.get_real_video_url())
        self.assertEqual(parser.get_video_list(), [])


if __name__ == "__main__":
    unittest.main()
