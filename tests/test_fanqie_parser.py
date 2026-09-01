import unittest
from unittest.mock import patch
from utils.web_fetcher import UrlParser
from src.parser_factory import ParserFactory
from src.parsers.fanqie_parser import FanqieParser
from utils.html_video_extractor import HtmlVideoExtractor


MOCK_NOVEL_HTML = """
<!doctype html>
<html>
<head>
    <meta data-react-helmet="true" name="og:description" content="测试短剧描述标题"/>
    <meta data-react-helmet="true" name="og:image" content="https://p3-novel.byteimg.com/cover.image"/>
    <meta data-react-helmet="true" name="og:url" content="https://v3-share.qznovel.com/video.mp4?mime_type=video_mp4"/>
</head>
<body>
    <script>
        window._ROUTER_DATA = {
            "loaderData": {
                "video-animation-share_page": {
                    "pageData": {
                        "series_data": {
                            "title": "护镖人之无敌镖人！",
                            "play_url": "https:\\u002F\\u002Fv3-share.qznovel.com\\u002Freal_play.mp4"
                        }
                    }
                }
            }
        };
    </script>
</body>
</html>
"""


class FanqieParserTest(unittest.TestCase):

    def test_platform_recognition(self):
        self.assertEqual(UrlParser.get_platform("https://novelquickapp.com/s/xCkhRnNOiTc/"), "红果短剧")
        self.assertEqual(UrlParser.get_platform("https://changdunovel.com/t/byybBzZfKbg/"), "畅读短剧")
        self.assertEqual(UrlParser.get_platform("https://kylin.hainanyuyue.com/s/bR1qzzEd1A0/"), "鱼跃短剧")

    def test_parser_factory_registration(self):
        cls_hongguo = ParserFactory.get_parser_class("红果短剧")
        cls_fanqie = ParserFactory.get_parser_class("番茄短剧")
        cls_changdu = ParserFactory.get_parser_class("畅读短剧")
        cls_yuyue = ParserFactory.get_parser_class("鱼跃短剧")
        self.assertEqual(cls_hongguo, FanqieParser)
        self.assertEqual(cls_fanqie, FanqieParser)
        self.assertEqual(cls_changdu, FanqieParser)
        self.assertEqual(cls_yuyue, FanqieParser)

    def test_html_video_extractor(self):
        res = HtmlVideoExtractor.parse_page(MOCK_NOVEL_HTML)
        self.assertEqual(res['title'], "护镖人之无敌镖人！")
        self.assertEqual(res['video_url'], "https://v3-share.qznovel.com/real_play.mp4")
        self.assertEqual(res['cover_url'], "https://p3-novel.byteimg.com/cover.image")

    @patch.object(FanqieParser, 'fetch_html_content', return_value=MOCK_NOVEL_HTML)
    def test_fanqie_parser_execution(self, mock_fetch):
        parser = FanqieParser("https://novelquickapp.com/s/xCkhRnNOiTc/")
        self.assertEqual(parser.get_title_content(), "护镖人之无敌镖人！")
        self.assertEqual(parser.get_real_video_url(), "https://v3-share.qznovel.com/real_play.mp4")
        self.assertEqual(parser.get_cover_photo_url(), "https://p3-novel.byteimg.com/cover.image")


if __name__ == '__main__':
    unittest.main()
