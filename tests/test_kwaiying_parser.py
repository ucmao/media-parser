import unittest
from unittest.mock import Mock, patch

from src.parsers.kwaiying_parser import KwaiyingParser


class KwaiyingParserTest(unittest.TestCase):
    URL = "https://share.kwaiying.com/share/template/index.html?id=8467216&userId=702561542395651960"

    def test_maps_template_response(self):
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {
            "result": 1,
            "resource": {
                "id": "8467216",
                "name": "测试快影模板",
                "videoUrl": "https://video.example.com/kwaiying_video.mp4",
                "templateBean": {
                    "coverUrl": "https://image.example.com/kwaiying_cover.jpg",
                    "description": "快影描述文案",
                    "videoDuration": 25000,
                },
                "user": {
                    "nickName": "快影测试作者",
                    "userId": "12345678",
                    "iconUrlList": ["https://image.example.com/kwaiying_avatar.jpg"],
                },
                "music": {
                    "url": "https://audio.example.com/kwaiying_music.mp3"
                }
            }
        }

        with patch("requests.Session.get", return_value=response):
            parser = KwaiyingParser(self.URL)

        self.assertEqual(parser.get_real_video_url(), "https://video.example.com/kwaiying_video.mp4")
        self.assertEqual(parser.get_title_content(), "测试快影模板")
        self.assertEqual(parser.get_cover_photo_url(), "https://image.example.com/kwaiying_cover.jpg")
        self.assertEqual(parser.get_author_info()["nickname"], "快影测试作者")
        self.assertEqual(parser.get_author_info()["author_id"], "12345678")
        self.assertEqual(parser.get_author_info()["avatar"], "https://image.example.com/kwaiying_avatar.jpg")
        self.assertEqual(parser.get_audio_url(), "https://audio.example.com/kwaiying_music.mp3")
        self.assertEqual(parser.get_video_list(), ["https://video.example.com/kwaiying_video.mp4"])

    def test_missing_template_id_does_not_call_api(self):
        with patch("requests.Session.get") as get_mock:
            parser = KwaiyingParser("https://share.kwaiying.com/share/template/index.html")

        get_mock.assert_not_called()
        self.assertIsNone(parser.get_real_video_url())

    def test_extracts_id_from_templateId_param(self):
        url = "https://share.kwaiying.com/share/template/index.html?templateId=999888"
        self.assertEqual(KwaiyingParser._extract_template_id(url), "999888")


if __name__ == "__main__":
    unittest.main()
