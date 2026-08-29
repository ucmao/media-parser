import unittest
from unittest.mock import Mock, patch

from src.parsers.wechat_mp_parser import WechatMpParser


class WechatMpParserTest(unittest.TestCase):
    URL = "https://mp.weixin.qq.com/s/test_article_123"

    def test_maps_article_response(self):
        html_content = """
        <!DOCTYPE html>
        <html>
        <head>
            <meta property="og:title" content="测试公众号标题" />
            <meta property="og:article:author" content="测试公众号" />
            <meta property="og:image" content="https://mmbiz.qpic.cn/cover.jpg" />
        </head>
        <body>
            <script>
                var msg_title = '测试公众号标题';
                var nickname = '测试公众号';
                var user_name = 'gh_123456789abc';
                var msg_cdn_url = 'https://mmbiz.qpic.cn/cover.jpg';
            </script>
            <h1 id="activity-name">测试公众号标题</h1>
            <a id="js_name">测试公众号</a>
            <div id="js_content">
                <p>正文内容</p>
                <img data-src="https://mmbiz.qpic.cn/mmbiz_png/test/640?wx_fmt=png" />
                <img data-src="https://mmbiz.qpic.cn/mmbiz_jpg/test2/300?wx_fmt=jpeg" />
                <mpvoice voice_encode_fileid="voice_file_999" name="语音"></mpvoice>
            </div>
        </body>
        </html>
        """
        response = Mock()
        response.status_code = 200
        response.raise_for_status.return_value = None
        response.text = html_content

        with patch("requests.Session.get", return_value=response):
            parser = WechatMpParser(self.URL)

        self.assertEqual(parser.get_title_content(), "测试公众号标题")
        self.assertEqual(parser.get_author_info()["nickname"], "测试公众号")
        self.assertEqual(parser.get_author_info()["author_id"], "gh_123456789abc")
        self.assertEqual(parser.get_cover_photo_url(), "https://mmbiz.qpic.cn/cover.jpg")
        self.assertEqual(len(parser.get_image_list()), 2)
        self.assertEqual(parser.get_image_list()[0], "https://mmbiz.qpic.cn/mmbiz_png/test/0?wx_fmt=png")
        self.assertEqual(parser.get_audio_url(), "https://res.wx.qq.com/voice/getvoice?mediaid=voice_file_999")

    def test_handles_request_failure_gracefully(self):
        response = Mock()
        response.raise_for_status.side_effect = Exception("HTTP 404")

        with patch("requests.Session.get", return_value=response):
            parser = WechatMpParser(self.URL)

        self.assertEqual(parser.get_title_content(), "微信公众号文章")
        self.assertEqual(parser.get_image_list(), [])
        self.assertIsNone(parser.get_real_video_url())


if __name__ == "__main__":
    unittest.main()
