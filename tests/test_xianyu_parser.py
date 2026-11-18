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

    def test_parses_goofish_item_id_url(self):
        page_resp = Mock()
        page_resp.raise_for_status.return_value = None
        page_resp.text = "<html><body>闲鱼商品页</body></html>"

        mtop_init_resp = Mock()
        mtop_init_resp.raise_for_status.return_value = None

        mtop_info_resp = Mock()
        mtop_info_resp.raise_for_status.return_value = None
        mtop_info_resp.json.return_value = {
            "ret": ["SUCCESS::接口调用成功"],
            "data": {
                "title": "测试闲鱼商品标题",
                "description": "商品详细描述",
                "reservePrice": "99.0",
                "imageInfos": [
                    {"url": "http://img.alicdn.com/bao/uploaded/i1/test1.png"},
                    {"url": "http://img.alicdn.com/bao/uploaded/i2/test2.png"}
                ],
            },
        }

        mtop_awesome_resp = Mock()
        mtop_awesome_resp.raise_for_status.return_value = None
        mtop_awesome_resp.json.return_value = {
            "ret": ["SUCCESS::接口调用成功"],
            "data": {
                "sellerDO": {
                    "nick": "卖家小明",
                },
            },
        }

        def side_effect(url, *args, **kwargs):
            if "mtop" in url:
                params = kwargs.get("params", {})
                if params.get("sign") == "dummy":
                    return mtop_init_resp
                if "item.info" in url:
                    return mtop_info_resp
                if "awesome.detail" in url:
                    return mtop_awesome_resp
            return page_resp

        url = "https://www.goofish.com/item?itemId=834469366646"
        with patch("requests.Session.get", side_effect=side_effect):
            parser = XianyuParser(url)

        self.assertEqual(parser.get_title_content(), "测试闲鱼商品标题")
        self.assertEqual(parser.get_description(), "商品详细描述")
        self.assertEqual(parser.get_author_info(), "卖家小明")
        self.assertEqual(parser.get_cover_photo_url(), "https://img.alicdn.com/bao/uploaded/i1/test1.png")
        self.assertEqual(
            parser.get_image_list(),
            [
                "https://img.alicdn.com/bao/uploaded/i1/test1.png",
                "https://img.alicdn.com/bao/uploaded/i2/test2.png",
            ],
        )

    def test_deleted_item_handles_terminal_detail(self):
        page_resp = Mock()
        page_resp.raise_for_status.return_value = None
        page_resp.text = "<html><body>闲鱼商品页</body></html>"

        mtop_init_resp = Mock()
        mtop_init_resp.raise_for_status.return_value = None

        mtop_data_resp = Mock()
        mtop_data_resp.raise_for_status.return_value = None
        mtop_data_resp.json.return_value = {
            "ret": ["FAIL_BIZ_ITEM_QUERY_FAILED::查询商品信息失败"],
            "data": {},
        }

        def side_effect(url, *args, **kwargs):
            if "mtop" in url:
                params = kwargs.get("params", {})
                if params.get("sign") == "dummy":
                    return mtop_init_resp
                return mtop_data_resp
            return page_resp

        url = "https://www.goofish.com/item?itemId=999999999999"
        with patch("requests.Session.get", side_effect=side_effect):
            parser = XianyuParser(url)

        self.assertEqual(parser.get_image_list(), [])
        self.assertIsNotNone(parser.get_terminal_detail())
        self.assertIsNotNone(parser.terminal_error)
        self.assertEqual(parser.get_terminal_detail().get("error_code"), "ITEM_NOT_FOUND")
        self.assertEqual(parser.terminal_error.get("error_code"), "ITEM_NOT_FOUND")

    def test_invalid_url_handles_gracefully(self):
        parser = XianyuParser("https://e.tb.cn/invalid")
        self.assertEqual(parser.get_title_content(), "")
        self.assertIsNone(parser.get_real_video_url())
        self.assertEqual(parser.get_image_list(), [])
        self.assertIsNone(parser.get_cover_photo_url())


if __name__ == "__main__":
    unittest.main()
