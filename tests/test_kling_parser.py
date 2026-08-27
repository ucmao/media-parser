import unittest
from unittest.mock import Mock, patch

from src.parsers.kling_parser import KlingParser


class KlingParserTest(unittest.TestCase):
    def test_maps_public_api_response(self):
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {
            "status": 200,
            "result": 1,
            "data": {
                "introduction": "测试可灵作品",
                "resource": {"resource": "https:\\/\\/video.example.com\\/work.mp4"},
                "cover": {"resource": "https://image.example.com/cover.jpg"},
                "userProfile": {
                    "userName": "测试作者",
                    "userId": 42,
                    "avatar": {"resource": "https://image.example.com/avatar.jpg"},
                },
            },
        }
        url = (
            "https://klingai-share.kuaishou.com/h5-app/share?"
            "creative_id=123456&creative_type=WORK"
        )

        with patch("requests.Session.get", return_value=response) as get:
            parser = KlingParser(url)

        self.assertEqual(parser.get_title_content(), "测试可灵作品")
        self.assertEqual(parser.get_real_video_url(), "https://video.example.com/work.mp4")
        self.assertEqual(parser.get_cover_photo_url(), "https://image.example.com/cover.jpg")
        self.assertEqual(parser.get_author_info()["nickname"], "测试作者")
        self.assertEqual(parser.get_author_info()["author_id"], "42")
        self.assertEqual(get.call_args.kwargs["params"], {"creativeId": "123456", "creativeType": "WORK"})

    def test_supports_work_id_and_falls_back_to_first_frame(self):
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {
            "status": 200,
            "result": 1,
            "data": {"firstFrame": {"resource": "https://image.example.com/first.jpg"}},
        }
        with patch("requests.Session.get", return_value=response) as get:
            parser = KlingParser(
                "https://klingai-share.kuaishou.com/h5-app/share?work_id=654321"
            )

        self.assertEqual(parser.get_cover_photo_url(), "https://image.example.com/first.jpg")
        self.assertEqual(get.call_args.kwargs["params"]["creativeId"], "654321")

    def test_invalid_url_does_not_call_api(self):
        with patch("requests.Session.get") as get:
            parser = KlingParser("https://klingai-share.kuaishou.com/h5-app/share")

        get.assert_not_called()
        self.assertIsNone(parser.get_real_video_url())


if __name__ == "__main__":
    unittest.main()
