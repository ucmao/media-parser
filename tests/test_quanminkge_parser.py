import unittest
from unittest.mock import Mock, patch

from src.parsers.quanminkge_parser import QuanminkgeParser


class QuanminkgeParserTest(unittest.TestCase):
    @patch("src.parsers.quanminkge_parser.random.choice", return_value="test-agent")
    def test_extracts_page_data_without_space_before_script_tag(self, _user_agent):
        response = Mock()
        response.text = '''<script>window.__DATA__ = {"detail": {
            "playurl_video": "https://media.example.com/video.mp4",
            "cover": "https://media.example.com/cover.jpg",
            "content": "测试作品"
        }}; </script>'''
        response.raise_for_status.return_value = None

        with patch("requests.Session.get", return_value=response) as get:
            parser = QuanminkgeParser("https://kg.qq.com/node/play?s=share-id")

        get.assert_called_once_with(
            "https://kg.qq.com/node/play?s=share-id", headers=parser.headers, timeout=10
        )
        self.assertEqual(parser.get_real_video_url(), "https://media.example.com/video.mp4")
        self.assertEqual(parser.get_cover_photo_url(), "https://media.example.com/cover.jpg")
        self.assertEqual(parser.get_title_content(), "测试作品")

    def test_skips_request_for_url_without_share_id(self):
        with patch("requests.Session.get") as get:
            parser = QuanminkgeParser("https://kg.qq.com/node/play")

        get.assert_not_called()
        self.assertEqual(parser.data, {})


if __name__ == "__main__":
    unittest.main()
