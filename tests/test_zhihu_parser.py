import unittest
from unittest.mock import Mock, patch

from src.parsers.zhihu_parser import ZhihuParser


class ZhihuParserTest(unittest.TestCase):
    def test_maps_video_pin_playlist(self):
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {
            "excerpt_title": "测试知乎视频",
            "content_html": "<p>视频正文</p>",
            "author": {"name": "测试作者", "id": "author-id", "avatar_url": "https://image.example.com/avatar.jpg"},
            "content": [{
                "type": "video",
                "thumbnail": "https://image.example.com/cover.jpg",
                "playlist": [
                    {"quality": "sd", "bitrate": 100, "url": "https://video.example.com/sd.mp4"},
                    {"quality": "hd", "bitrate": 200, "url": "https://video.example.com/hd.mp4"},
                ],
            }],
        }
        with patch("requests.Session.get", return_value=response) as get:
            parser = ZhihuParser("https://www.zhihu.com/pin/2066168388699807826")

        self.assertEqual(parser.get_real_video_url(), "https://video.example.com/hd.mp4")
        self.assertEqual(parser.get_cover_photo_url(), "https://image.example.com/cover.jpg")
        self.assertEqual(parser.get_title_content(), "测试知乎视频")
        self.assertEqual(parser.get_author_info()["nickname"], "测试作者")
        self.assertEqual(get.call_args.args[0], "https://api.zhihu.com/pins/2066168388699807826")
