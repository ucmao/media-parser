import unittest
from unittest.mock import Mock, patch

from src.parsers.qianwen_parser import QianwenParser


class QianwenParserTest(unittest.TestCase):
    def test_parses_qianwen_share_props(self):
        page_html = """
        <!DOCTYPE html>
        <html>
        <head><title>千问</title></head>
        <body>
        <script>
        window.__INITIAL_PROPS__ = {
            "initialData": {
                "data": {
                    "shareId": "ZeeOedXncnGlElkluRMA",
                    "title": "给右边男生的黑色卫衣换成灰色",
                    "creator": {
                        "nick": "Qwen5361",
                        "authorId": "OjTAcGHgZgyeCwY4jeMDuH9Je4J92YdmlmTiIxK0cRWKzw==",
                        "avatar": "https://gw.alicdn.com/avatar.png"
                    },
                    "images": [
                        {
                            "downloadUrl": "https://quark-aistudio-cdn.quark.cn/test1.png",
                            "url": "https://quark-aistudio-cdn.quark.cn/test1_preview.png"
                        }
                    ]
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

        url = "https://activity.qianwen.com/r/ai-studio-mobile/qwen-external-share?shareId=ZeeOedXncnGlElkluRMA"
        with patch("requests.Session.get", return_value=page_resp):
            parser = QianwenParser(url)

        self.assertEqual(parser.get_title_content(), "给右边男生的黑色卫衣换成灰色")
        self.assertEqual(parser.get_cover_photo_url(), "https://quark-aistudio-cdn.quark.cn/test1.png")
        self.assertEqual(parser.get_image_list(), ["https://quark-aistudio-cdn.quark.cn/test1.png"])
        self.assertEqual(
            parser.get_author_info(),
            {
                "nickname": "Qwen5361",
                "author_id": "OjTAcGHgZgyeCwY4jeMDuH9Je4J92YdmlmTiIxK0cRWKzw==",
                "avatar": "https://gw.alicdn.com/avatar.png",
            },
        )

    def test_invalid_url_handles_gracefully(self):
        parser = QianwenParser("https://activity.qianwen.com/invalid")
        self.assertEqual(parser.get_title_content(), "")
        self.assertIsNone(parser.get_real_video_url())
        self.assertEqual(parser.get_image_list(), [])
        self.assertIsNone(parser.get_cover_photo_url())
        self.assertIsNone(parser.get_author_info())


if __name__ == "__main__":
    unittest.main()
