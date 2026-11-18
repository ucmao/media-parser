import json
import unittest
from unittest.mock import Mock, patch

from src.parsers.xinpianchang_parser import XinpianchangParser


class XinpianchangParserTest(unittest.TestCase):
    def test_parses_xinpianchang_article_and_media(self):
        article_response = Mock(status_code=200)
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
        self.assertIsNone(parser.get_real_video_url())
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

    def test_falls_back_to_web_page_when_app_api_fails(self):
        next_data = {
            "props": {"pageProps": {"detail": {
                "title": "这就是深圳",
                "cover": "https://oss-xpc0.xpccdn.com/cover.jpg",
                "vid": "P2MmN45WBmE7X0zL",
                "video": {"appKey": "61a2f329348b3bf77", "vid": "P2MmN45WBmE7X0zL"},
                "author": {"userinfo": {"id": 10767403, "username": "heart的旅行日记", "avatar": ""}},
            }}}
        }
        page_response = Mock(status_code=200)
        page_response.text = (
            '<html><script id="__NEXT_DATA__" type="application/json">'
            + json.dumps(next_data, ensure_ascii=False)
            + "</script></html>"
        )
        media_response = Mock(status_code=200)
        media_response.json.return_value = {
            "status": 0,
            "data": {"resource": {"progressive": [{"url": "https://us-xpc5.xpccdn.com/720p.mp4"}]}},
        }
        requested = []

        def mock_get(url, **kwargs):
            requested.append(url)
            if "app.xinpianchang.com" in url:
                return Mock(status_code=403)
            if "www.xinpianchang.com/a11812492" in url:
                return page_response
            if "mod-api.xinpianchang.com/mod/api/v2/media/P2MmN45WBmE7X0zL" in url:
                return media_response
            return Mock(status_code=404)

        with patch("requests.Session.get", side_effect=mock_get):
            parser = XinpianchangParser("https://www.xinpianchang.com/a11812492?from=webShare&channel=copyLink")

        self.assertEqual(parser.get_title_content(), "这就是深圳")
        self.assertEqual(parser.get_video_list(), ["https://us-xpc5.xpccdn.com/720p.mp4"])
        self.assertEqual(parser.get_author_info()["nickname"], "heart的旅行日记")
        self.assertTrue(any("www.xinpianchang.com" in u for u in requested))

    def test_invalid_url_handles_gracefully(self):
        parser = XinpianchangParser("https://www.xinpianchang.com/invalid")
        self.assertEqual(parser.get_title_content(), "")
        self.assertIsNone(parser.get_real_video_url())
        self.assertEqual(parser.get_video_list(), [])
        self.assertIsNone(parser.get_cover_photo_url())
        self.assertIsNone(parser.get_author_info())


if __name__ == "__main__":
    unittest.main()
