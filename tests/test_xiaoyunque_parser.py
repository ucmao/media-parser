import unittest
from unittest.mock import Mock, patch

from src.parsers.xiaoyunque_parser import XiaoyunqueParser
from utils.web_fetcher import UrlParser


class XiaoyunqueParserTest(unittest.TestCase):
    def test_maps_official_api_response(self):
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {
            "err_no": 0,
            "err_tips": "success",
            "data": {
                "page_info": {
                    "generate_page": {
                        "user_info": {
                            "nick_name": "测试作者",
                            "avatar_url": "https://image.example.com/avatar.jpg",
                        },
                        "item_info": {
                            "desc": "测试小云雀作品描述",
                            "image_info": [
                                {"image_url": "https://image.example.com/item1.png", "width": 1000, "height": 1000}
                            ],
                        },
                    }
                }
            },
        }
        url = "https://xiaoyunque.jianying.com/activities/pippit_share?artifact_id=12345&generate_id=abcde"

        with patch("requests.Session.post", return_value=response) as post:
            parser = XiaoyunqueParser(url)

        self.assertEqual(parser.get_title_content(), "测试小云雀作品描述")
        self.assertEqual(parser.get_image_list(), ["https://image.example.com/item1.png"])
        self.assertEqual(parser.get_cover_photo_url(), "https://image.example.com/item1.png")
        self.assertEqual(parser.get_author_info()["nickname"], "测试作者")
        self.assertEqual(
            post.call_args.kwargs["json"]["query_params"]["artifact_id"],
            "12345",
        )

    def test_url_parser_recognizes_xiaoyunque(self):
        url = "https://xiaoyunque.jianying.com/s/z_7nWGLGruM/"
        self.assertEqual(UrlParser.get_platform(url), "小云雀 AI")


if __name__ == "__main__":
    unittest.main()
