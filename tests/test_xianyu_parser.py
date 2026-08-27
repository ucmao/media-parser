import unittest
from unittest.mock import Mock, patch

from src.parsers.xianyu_parser import XianyuParser


class XianyuParserTest(unittest.TestCase):
    def test_parses_xianyu_short_link(self):
        page_html = """
        <!DOCTYPE html>
        <html>
        <head><title>闲鱼分享</title></head>
        <body>
        <script>
        var shortName = "h.87fj9SNrqHW8kfC";
        var url = 'https://item.taobao.com/item.htm?id=967494320598&price=12.2&short_name=h.87fj9SNrqHW8kfC';
        </script>
        </body>
        </html>
        """

        page_resp = Mock()
        page_resp.raise_for_status.return_value = None
        page_resp.text = page_html

        url = "https://e.tb.cn/h.87fj9SNrqHW8kfC?tk=y1E5Tb4wkGd"
        with patch("requests.Session.get", return_value=page_resp):
            parser = XianyuParser(url)

        self.assertEqual(parser.get_title_content(), "闲鱼商品 (商品ID: 967494320598, 标价: ¥12.2)")

    def test_invalid_url_handles_gracefully(self):
        parser = XianyuParser("https://e.tb.cn/invalid")
        self.assertEqual(parser.get_title_content(), "")
        self.assertIsNone(parser.get_real_video_url())
        self.assertEqual(parser.get_image_list(), [])
        self.assertIsNone(parser.get_cover_photo_url())


if __name__ == "__main__":
    unittest.main()
