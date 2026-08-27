import unittest
from unittest.mock import Mock, patch

from src.parsers.jianying_parser import JianyingParser


class JianyingParserTest(unittest.TestCase):
    URL = "https://lv.ulikecam.com/activity/lv/sharevideo?template_id=123456&item_type=0"

    def test_maps_template_response(self):
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {"data": {"templates": [{
            "title": "测试剪映模板",
            "video_url": "https://video.example.com/template.mp4",
            "cover_url": "https://image.example.com/cover.jpg",
            "author": {"name": "测试作者", "uid": 42, "avatar": "https://image.example.com/avatar.jpg"},
            "music_info": {"play_url": "https://audio.example.com/music.mp3"},
            "images": ["https://image.example.com/one.jpg"],
        }]}}
        with patch("requests.Session.post", return_value=response) as post:
            parser = JianyingParser(self.URL)

        self.assertEqual(parser.get_real_video_url(), "https://video.example.com/template.mp4")
        self.assertEqual(parser.get_cover_photo_url(), "https://image.example.com/cover.jpg")
        self.assertEqual(parser.get_title_content(), "测试剪映模板")
        self.assertEqual(parser.get_author_info()["author_id"], "42")
        self.assertEqual(parser.get_audio_url(), "https://audio.example.com/music.mp3")
        self.assertEqual(parser.get_video_list(), ["https://video.example.com/template.mp4"])
        self.assertEqual(post.call_args.kwargs["json"]["id"], ["123456"])

    def test_invalid_link_does_not_call_api(self):
        with patch("requests.Session.post") as post:
            parser = JianyingParser("https://lv.ulikecam.com/activity/lv/sharevideo")

        post.assert_not_called()
        self.assertIsNone(parser.get_real_video_url())

    def test_uses_nested_aweme_author_fields_as_fallback(self):
        parser = JianyingParser.__new__(JianyingParser)
        parser.template = {"author": {"aweme_info": {
            "name": "嵌套作者", "uid": "nested-id", "avatar_url": "https://image.example.com/nested.jpg",
        }}}

        self.assertEqual(parser.get_author_info()["nickname"], "嵌套作者")
        self.assertEqual(parser.get_author_info()["author_id"], "nested-id")
