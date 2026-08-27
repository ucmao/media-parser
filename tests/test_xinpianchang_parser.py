import unittest
from unittest.mock import Mock, patch

from src.parsers.xinpianchang_parser import XinpianchangParser


class XinpianchangParserTest(unittest.TestCase):
    def test_parses_xinpianchang_article_and_media(self):
        article_response = Mock()
        article_response.raise_for_status.return_value = None
        article_response.json.return_value = {
            "status": 0,
            "data": {
                "title": "治愈系风景 | 阿尔卑斯徒步",
                "cover": "https://oss-xpc0.xpccdn.com/cover.jpg",
                "vid": "O5vZQVJW06AQDEMW",
                "video": {"appKey": "61a2f329348b3bf77"},
                "author": {
                    "userinfo": {
                        "username": "练凌飞",
                        "id": 10019394,
                        "avatar": "https://oss-xpc0.xpccdn.com/avatar.jpg",
                    }
                },
            },
        }

        media_response = Mock()
        media_response.status_code = 200
        media_response.json.return_value = {
            "status": 0,
            "data": {
                "resource": {
                    "progressive": [
                        {"profile": "高清 1080p", "url": ""},
                        {"profile": "标清 720p", "url": "https://us-xpc5.xpccdn.com/720p.mp4"},
                        {"profile": "流畅 360p", "url": "https://us-xpc5.xpccdn.com/360p.mp4"},
                    ]
                }
            },
        }

        def mock_get(url, **kwargs):
            if "app.xinpianchang.com" in url:
                return article_response
            elif "mod-api.xinpianchang.com" in url:
                return media_response
            return Mock(status_code=404)

        url = "https://www.xinpianchang.com/a13792376?from=share&xpcApp=xpc&channel=link&type=URL"
        with patch("requests.Session.get", side_effect=mock_get):
            parser = XinpianchangParser(url)

        self.assertEqual(parser.get_title_content(), "治愈系风景 | 阿尔卑斯徒步")
        self.assertEqual(parser.get_cover_photo_url(), "https://oss-xpc0.xpccdn.com/cover.jpg")
        self.assertEqual(parser.get_real_video_url(), "https://us-xpc5.xpccdn.com/720p.mp4")
        self.assertEqual(
            parser.get_video_list(),
            ["https://us-xpc5.xpccdn.com/720p.mp4", "https://us-xpc5.xpccdn.com/360p.mp4"],
        )
        self.assertEqual(
            parser.get_author_info(),
            {
                "nickname": "练凌飞",
                "author_id": "10019394",
                "avatar": "https://oss-xpc0.xpccdn.com/avatar.jpg",
            },
        )

    def test_invalid_url_handles_gracefully(self):
        parser = XinpianchangParser("https://www.xinpianchang.com/invalid")
        self.assertEqual(parser.get_title_content(), "")
        self.assertIsNone(parser.get_real_video_url())
        self.assertEqual(parser.get_video_list(), [])
        self.assertIsNone(parser.get_cover_photo_url())
        self.assertIsNone(parser.get_author_info())


if __name__ == "__main__":
    unittest.main()
