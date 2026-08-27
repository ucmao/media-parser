import unittest
from unittest.mock import Mock, patch

from src.parsers.soul_parser import SoulParser


class SoulParserTest(unittest.TestCase):
    URL = (
        "https://w13.soulsmile.cn/activity/#/web/topic/detail?"
        "postIdEcpt=post-id&sign=signature&signVersion=0.0.1"
    )

    def test_maps_video_and_author_responses(self):
        post_response = Mock()
        post_response.raise_for_status.return_value = None
        post_response.json.return_value = {
            "success": True,
            "data": {"post": {
                "content": "测试 Soul 帖子",
                "authorIdEcpt": "author-id",
                "attachments": [{
                    "type": "VIDEO",
                    "fileUrl": "https:\\/\\/video.example.com\\/work.mp4",
                    "ext": '{"videoCoverUrl": "https://image.example.com/cover.jpg"}',
                }],
            }},
        }
        user_response = Mock()
        user_response.raise_for_status.return_value = None
        user_response.json.return_value = {"success": True, "data": {
            "nickName": "测试作者",
            "headImgurl": "https://image.example.com/avatar.jpg",
            "signature": "个人签名",
        }}

        with patch("requests.Session.get", side_effect=[post_response, user_response]) as get:
            parser = SoulParser(self.URL)

        self.assertEqual(parser.get_real_video_url(), "https://video.example.com/work.mp4")
        self.assertEqual(parser.get_cover_photo_url(), "https://image.example.com/cover.jpg")
        self.assertEqual(parser.get_title_content(), "测试 Soul 帖子")
        self.assertEqual(parser.get_author_info()["nickname"], "测试作者")
        self.assertEqual(get.call_args_list[0].kwargs["params"], {
            "postIdEcpt": "post-id", "sign": "signature", "signVersion": "0.0.1",
        })
        self.assertEqual(get.call_args_list[1].kwargs["params"], {"userIdEcpt": "author-id"})

    def test_collects_non_video_attachments_as_images(self):
        parser = SoulParser.__new__(SoulParser)
        parser.post = {"attachments": [
            {"type": "IMAGE", "fileUrl": "https://image.example.com/one.jpg"},
            {"type": "VIDEO", "fileUrl": "https://video.example.com/work.mp4"},
        ]}
        self.assertEqual(parser.get_image_list(), ["https://image.example.com/one.jpg"])

    def test_missing_fragment_parameters_are_rejected(self):
        parser = SoulParser.__new__(SoulParser)
        parser.real_url = "https://w13.soulsmile.cn/activity/#/web/topic/detail?postIdEcpt=post"
        with self.assertRaisesRegex(ValueError, "sign"):
            parser._parse_page_params()


if __name__ == "__main__":
    unittest.main()
