import unittest
from unittest.mock import Mock, patch

from src.parsers.jimeng_parser import JimengParser
from utils.web_fetcher import UrlParser


class JimengParserTest(unittest.TestCase):
    def test_maps_official_api_response(self):
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {
            "ret": "0",
            "data": {
                "common_attr": {
                    "description": "测试即梦作品",
                    "published_item_id": "1234567890123456",
                    "cover_url_map": {
                        "1080": "https://image.example.com/1080.jpg",
                        "4096": "https://image.example.com/4096.jpg",
                    },
                },
                "author": {
                    "name": "测试作者",
                    "uid": "author123",
                    "avatar_url": "https://image.example.com/avatar.jpg",
                },
                "video": {
                    "origin_video": {
                        "video_url": "https://video.example.com/origin.mp4",
                    },
                    "transcoded_video": {
                        "720p": {
                            "video_url": "https://video.example.com/720.mp4",
                            "width": 1280,
                            "height": 720,
                        },
                    },
                },
            },
        }
        url = "https://jimeng.jianying.com/activities/reflux/mproject?id=1234567890123456"

        with patch("requests.Session.post", return_value=response) as post:
            parser = JimengParser(url)

        self.assertEqual(parser.get_title_content(), "测试即梦作品")
        self.assertEqual(parser.get_real_video_url(), "https://video.example.com/origin.mp4")
        self.assertEqual(parser.get_video_list(), ["https://video.example.com/origin.mp4"])
        self.assertEqual(parser.get_cover_photo_url(), "https://image.example.com/4096.jpg")
        self.assertEqual(parser.get_author_info()["nickname"], "测试作者")
        self.assertEqual(
            post.call_args.kwargs["json"]["published_item_id"],
            "1234567890123456",
        )

    def test_url_parser_preserves_item_id(self):
        url = (
            "https://jimeng.jianying.com/activities/reflux/mproject"
            "?id=1234567890123456&share_token=ignored"
        )

        normalized = UrlParser.extract_video_address(url)

        self.assertEqual(
            normalized,
            "https://jimeng.jianying.com/activities/reflux/mproject?id=1234567890123456",
        )
        self.assertEqual(UrlParser.get_video_id(normalized), "1234567890123456")

    def test_short_link_can_resolve_inside_parser(self):
        redirect_response = Mock(
            url="https://jimeng.jianying.com/activities/reflux/mproject?id=1234567890123456"
        )
        redirect_response.raise_for_status.return_value = None
        api_response = Mock()
        api_response.raise_for_status.return_value = None
        api_response.json.return_value = {
            "ret": "0",
            "data": {
                "common_attr": {},
                "author": {},
                "video": {},
            },
        }

        with patch("requests.Session.get", return_value=redirect_response) as get:
            with patch("requests.Session.post", return_value=api_response) as post:
                JimengParser("https://jimeng.jianying.com/s/example/")

        get.assert_called_once()
        self.assertEqual(
            post.call_args.kwargs["json"]["published_item_id"],
            "1234567890123456",
        )


if __name__ == "__main__":
    unittest.main()
