import unittest
from unittest.mock import Mock, patch

from src.parsers.huya_parser import HuyaParser


class HuyaParserTest(unittest.TestCase):
    @patch("src.parsers.huya_parser.random.choice", return_value="test-agent")
    def test_extracts_video_cover_and_title(self, _user_agent):
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {
            "data": {
                "moment": {
                    "videoInfo": {
                        "videoTitle": "测试虎牙作品",
                        "videoCover": "https://image.example.com/cover.jpg",
                        "definitions": [{"url": "https://video.example.com/video.mp4"}],
                    }
                }
            }
        }
        with patch("requests.Session.get", return_value=response) as get:
            parser = HuyaParser("https://www.huya.com/video/play/123.html")

        get.assert_called_once_with(
            "https://liveapi.huya.com/moment/getMomentContent?videoId=123",
            headers=parser.headers,
            timeout=10,
        )
        self.assertEqual(parser.get_real_video_url(), "https://video.example.com/video.mp4")
        self.assertEqual(parser.get_cover_photo_url(), "https://image.example.com/cover.jpg")
        self.assertEqual(parser.get_title_content(), "测试虎牙作品")

    def test_skips_request_for_invalid_video_id(self):
        with patch("requests.Session.get") as get:
            parser = HuyaParser("https://www.huya.com/video/play/not-a-video")

        get.assert_not_called()
        self.assertEqual(parser.data, {})


if __name__ == "__main__":
    unittest.main()
