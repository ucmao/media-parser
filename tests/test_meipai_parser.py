import unittest
from unittest.mock import Mock, patch

from src.parsers.meipai_parser import MeipaiParser


class MeipaiParserTest(unittest.TestCase):
    def test_parses_meipai_page_and_decodes_video(self):
        page_html = """
        <!DOCTYPE html>
        <html>
        <head><title>Test</title></head>
        <body>
        <script>
        window.PHPDATA = {
            "mediaInfo": {
                "id": "6777602107506448933",
                "caption_origin": "无绳跳绳到底是不是智商税#美图创作者计划#",
                "cover_pic": "//mvimg10.meitudata.com/6050c5d992a842467.jpg!thumb480",
                "video": "1911Ly9tBl1QdnZpZGVvMTAubWVpdHVkYXRhLmNvbS82MDUwYzU4NWIzZTRjNjQybTg2YTduODIzN19IMjY0XzFfNjg4NjY0YjllN2YBt1J9lz3ZTkubXA0",
                "user": {
                    "id": 1508802142,
                    "screen_name": "曾志明z",
                    "avatar": "//maavatar1.meitudata.com/5d4fb5e4616276250.jpg"
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

        cdn_resp = Mock()
        cdn_resp.status_code = 200
        cdn_resp.url = (
            "https://mvvideoshare1.meitudata.com/6050c585b3e4c642m86a7n8237_H264_1_688664b9e7f7e9.mp4"
            "?k=test&t=test"
        )

        def mock_get(url, **kwargs):
            if "cracl.meitubase.com" in url:
                return cdn_resp
            return page_resp

        url = "http://www.meipai.com/video/533/6777602107506448933"
        with patch("requests.Session.get", side_effect=mock_get):
            parser = MeipaiParser(url)

        self.assertEqual(parser.get_title_content(), "无绳跳绳到底是不是智商税#美图创作者计划#")
        self.assertEqual(parser.get_cover_photo_url(), "https://mvimg10.meitudata.com/6050c5d992a842467.jpg")
        self.assertEqual(
            parser.get_real_video_url(),
            "https://mvvideoshare1.meitudata.com/6050c585b3e4c642m86a7n8237_H264_1_688664b9e7f7e9.mp4?k=test&t=test",
        )
        self.assertEqual(
            parser.get_author_info(),
            {
                "nickname": "曾志明z",
                "author_id": "1508802142",
                "avatar": "https://maavatar1.meitudata.com/5d4fb5e4616276250.jpg",
            },
        )

    def test_invalid_url_handles_gracefully(self):
        parser = MeipaiParser("http://www.meipai.com/invalid")
        self.assertEqual(parser.get_title_content(), "")
        self.assertIsNone(parser.get_real_video_url())
        self.assertIsNone(parser.get_cover_photo_url())
        self.assertIsNone(parser.get_author_info())


if __name__ == "__main__":
    unittest.main()
