import json
import unittest
from unittest.mock import Mock, patch

from src.parsers.tencent_channel_parser import TencentChannelParser


class TencentChannelParserTest(unittest.TestCase):
    def test_maps_json_ld_media_data(self):
        data = {
            "headline": "测试视频｜测试频道｜腾讯频道",
            "author": {"name": "测试作者", "url": "https://image.example.com/avatar.jpg"},
            "video": {
                "contentUrl": "https://qchannelvideo.photo.qq.com/video.mp4",
                "thumbnailUrl": "https://image.example.com/cover.jpg",
            },
        }
        response = Mock()
        response.text = f'<script type="application/ld+json">{json.dumps(data)}</script>'
        with patch("requests.Session.get", return_value=response):
            parser = TencentChannelParser("https://pd.qq.com/s/code?b=2")

        self.assertEqual(parser.get_real_video_url(), "https://qchannelvideo.photo.qq.com/video.mp4")
        self.assertEqual(parser.get_cover_photo_url(), "https://image.example.com/cover.jpg")
        self.assertEqual(parser.get_author_info()["nickname"], "测试作者")
        self.assertEqual(parser.get_author_info()["guild_name"], "测试频道")

    def test_maps_fallback_media_data(self):
        response = Mock()
        response.text = ('<meta property="og:title" content="测试标题">'
                         '<meta property="og:image" content="https://image.example.com/cover.jpg">'
                         '<video src="https://qchannelvideo.photo.qq.com/video.mp4"></video>')
        with patch("requests.Session.get", return_value=response):
            parser = TencentChannelParser("https://pd.qq.com/s/code?b=2")

        self.assertEqual(parser.get_title_content(), "测试标题")
        self.assertEqual(parser.get_real_video_url(), "https://qchannelvideo.photo.qq.com/video.mp4")


if __name__ == "__main__":
    unittest.main()
