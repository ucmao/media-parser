import unittest
from unittest.mock import Mock, patch

from src.parsers.pinduoduo_parser import PinduoduoParser


class PinduoduoParserTest(unittest.TestCase):
    def test_parses_oak_share_material_url(self):
        url = (
            "https://mobile.yangkeduo.com/mall_quality_assurance.html?"
            "_t_timestamp=comm_share_landing&goods_id=768457919955&_oak_share_type=2&"
            "_oak_share_url=https%3A%2F%2Fimg.pddpic.com%2Fmms-material-img%2F2025-05-30%2Ffb07fde6.jpeg"
        )
        parser = PinduoduoParser(url)
        self.assertEqual(parser.get_title_content(), "拼多多商品 (商品ID: 768457919955)")
        self.assertEqual(
            parser.get_cover_photo_url(),
            "https://img.pddpic.com/mms-material-img/2025-05-30/fb07fde6.jpeg",
        )
        self.assertEqual(
            parser.get_image_list(),
            ["https://img.pddpic.com/mms-material-img/2025-05-30/fb07fde6.jpeg"],
        )
        self.assertIsNone(parser.get_real_video_url())

    def test_parses_review_share_with_oak_url(self):
        url = (
            "https://mobile.yangkeduo.com/mall_quality_assurance.html?"
            "_t_timestamp=review_detail&goods_id=947457222887&review_id=754367546181347559&"
            "_oak_share_url=https%3A%2F%2Fimg.pddpic.com%2Freview-img%2F1.jpeg"
        )
        parser = PinduoduoParser(url)
        self.assertEqual(
            parser.get_title_content(),
            "拼多多评价分享 (商品ID: 947457222887, 评价ID: 754367546181347559)",
        )
        self.assertEqual(parser.get_cover_photo_url(), "https://img.pddpic.com/review-img/1.jpeg")

    def test_parses_duoduo_video_via_api(self):
        mock_api_resp = Mock()
        mock_api_resp.status_code = 200
        mock_api_resp.text = '{"dummy": 1}'
        mock_api_resp.json.return_value = {
            "result": {
                "feeds": [
                    {
                        "data": {
                            "feedId": "6960355310530660128",
                            "feedTitle": "超好用厨房清洁神器，实测效果惊艳！",
                            "feedMedia": [
                                {
                                    "mediaType": 1,
                                    "url": "https://video.pddpic.com/live/clean_kitchen.mp4",
                                },
                                {
                                    "mediaType": 2,
                                    "url": "https://img.pddpic.com/feed/cover.jpg",
                                },
                            ],
                            "authorInfo": {
                                "authorName": "居家好物推荐官",
                                "avatar": "https://avatar.pddpic.com/u1.jpg",
                                "authorId": "10086",
                            },
                        }
                    }
                ]
            }
        }

        url = "https://mobile.yangkeduo.com/fyxmkief.html?feed_id=6960355310530660128&goods_id=978211601383"
        with patch("requests.Session.post", return_value=mock_api_resp):
            parser = PinduoduoParser(url)

        self.assertEqual(parser.get_title_content(), "超好用厨房清洁神器，实测效果惊艳！")
        self.assertEqual(parser.get_real_video_url(), "https://video.pddpic.com/live/clean_kitchen.mp4")
        self.assertEqual(parser.get_cover_photo_url(), "https://img.pddpic.com/feed/cover.jpg")
        self.assertEqual(
            parser.get_author_info(),
            {
                "nickname": "居家好物推荐官",
                "avatar": "https://avatar.pddpic.com/u1.jpg",
                "author_id": "10086",
            },
        )
        self.assertEqual(
            parser.get_video_list(),
            ["https://video.pddpic.com/live/clean_kitchen.mp4"],
        )

    def test_parses_goods_ssr_raw_data(self):
        page_html = """
        <!DOCTYPE html>
        <html>
        <head><title>商品详情</title></head>
        <body>
        <script>
        window.rawData = {
            "store": {
                "initDataObj": {
                    "goods": {
                        "goods_name": "加厚纯棉大浴巾吸水速干",
                        "banner": [
                            "https://img.pddpic.com/mms/banner1.jpg",
                            "https://img.pddpic.com/mms/banner2.jpg"
                        ],
                        "hd_thumb_url": "https://img.pddpic.com/mms/banner1.jpg",
                        "video": {
                            "url": "https://video.pddpic.com/goods/bath_towel.mp4"
                        }
                    }
                }
            }
        };
        </script>
        </body>
        </html>
        """
        page_resp = Mock()
        page_resp.raise_for_status.return_value = None
        page_resp.text = page_html

        url = "https://mobile.yangkeduo.com/goods.html?goods_id=935025706654"
        with patch("requests.Session.get", return_value=page_resp):
            parser = PinduoduoParser(url)

        self.assertEqual(parser.get_title_content(), "加厚纯棉大浴巾吸水速干")
        self.assertEqual(
            parser.get_real_video_url(), "https://video.pddpic.com/goods/bath_towel.mp4"
        )
        self.assertEqual(
            parser.get_cover_photo_url(), "https://img.pddpic.com/mms/banner1.jpg"
        )
        self.assertEqual(
            parser.get_image_list(),
            [
                "https://img.pddpic.com/mms/banner1.jpg",
                "https://img.pddpic.com/mms/banner2.jpg",
            ],
        )

    def test_handles_unauthenticated_duoduo_video_gracefully(self):
        mock_api_resp = Mock()
        mock_api_resp.status_code = 403
        mock_api_resp.text = '{"success":false,"http_code":403,"error_code":40001}'

        url = "https://mobile.yangkeduo.com/fyxmkief.html?feed_id=6960355310530660128"
        with patch("requests.Session.post", return_value=mock_api_resp):
            with patch("requests.Session.get", return_value=Mock(text="")):
                parser = PinduoduoParser(url)

        self.assertIsNone(parser.get_real_video_url())
        self.assertEqual(parser.get_image_list(), [])
        self.assertIsNone(parser.get_cover_photo_url())
        self.assertEqual(parser.get_title_content(), "多多视频 (FeedID: 6960355310530660128)")


if __name__ == "__main__":
    unittest.main()
