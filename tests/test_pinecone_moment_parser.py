import unittest
from unittest.mock import Mock, patch

from src.parsers.pinecone_moment_parser import PineconeMomentParser


class PineconeMomentParserTest(unittest.TestCase):
    URL = (
        "https://m.pineconemoment.com/h5/share/story/3473384016073334784?"
        "sharer_id=3458889976808366080&author_id=3458889976808366080&"
        "channel=7&version=1.19.0.47&share_id=3474647521796464640&story_type=1"
    )

    @patch("src.parsers.base_parser.requests.Session.get")
    def test_parses_story_videos_images_and_dubbing_audio(self, get):
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {
            "code": 0,
            "data": {
                "story": {
                    "title": "有一種信念叫越野跑",
                    "creator": {"user_id": "3458889976808366080", "nickname": "MissK", "avatar": "https://oss.example.com/avatar.png"},
                    "images": [
                        {"url": "https://oss.example.com/page1.webp", "video_url": "https://oss.example.com/page1.mp4", "video_cover_url": "https://oss.example.com/cover.jpg"},
                        {"url": "https://oss.example.com/page2.webp", "video_url": "https://oss.example.com/page2.mp4"},
                    ],
                    "dubbing": {"h5_audio": {"audio_url": "https://oss.example.com/dubbing.m4a"}},
                }
            },
        }
        get.return_value = response
        parser = PineconeMomentParser(self.URL)
        self.assertEqual(parser.get_title_content(), "有一種信念叫越野跑")
        self.assertEqual(parser.get_author_info()["nickname"], "MissK")
        self.assertEqual(parser.get_real_video_url(), "https://oss.example.com/page1.mp4")
        self.assertEqual(len(parser.get_image_list()), 2)
        self.assertEqual(parser.get_audio_url(), "https://oss.example.com/dubbing.m4a")
        self.assertEqual(parser.get_cover_photo_url(), "https://oss.example.com/cover.jpg")
        self.assertEqual(get.call_args.kwargs["params"]["item_id"], "3473384016073334784")

    def test_rejects_link_without_story_id(self):
        parser = PineconeMomentParser("https://m.pineconemoment.com/o/4buqAENzZFE")
        self.assertIsNone(parser.get_real_video_url())


if __name__ == "__main__":
    unittest.main()
