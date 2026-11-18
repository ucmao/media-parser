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

    def test_maps_video_response(self):
        html_content = """
        <!DOCTYPE html>
        <html>
        <body>
            <script>
                window.cgiData = {
                    title: '测试视频标题',
                    user_name: 'gh_video123',
                    nick_name: '视频号博主',
                    round_head_img: 'https://mmbiz.qpic.cn/avatar.png',
                    cdn_url: 'https://mmbiz.qpic.cn/cover.jpg',
                };
                video_page_info = {
                    mp_video_trans_info: [
                        {
                            format_id: 10004,
                            width: 480,
                            height: 854,
                            filesize: 1000,
                            video_quality_level: 1,
                            url: 'http://mpvideo.qpic.cn/video_low.mp4?k=1'
                        },
                        {
                            format_id: 10002,
                            width: 1080,
                            height: 1920,
                            filesize: 5000,
                            video_quality_level: 3,
                            url: 'http://mpvideo.qpic.cn/video_hd.mp4?k=2&amp;p=1'
                        }
                    ]
                };
            </script>
        </body>
        </html>
        """
        response = Mock()
        response.status_code = 200
        response.raise_for_status.return_value = None
        response.text = html_content

        with patch("requests.Session.get", return_value=response):
            parser = WechatMpParser(self.URL)

        self.assertEqual(parser.get_title_content(), "测试视频标题")
        self.assertEqual(parser.get_author_info()["nickname"], "视频号博主")
        self.assertEqual(parser.get_author_info()["author_id"], "gh_video123")
        self.assertEqual(parser.get_author_info()["avatar"], "https://mmbiz.qpic.cn/avatar.png")
        self.assertEqual(parser.get_real_video_url(), "http://mpvideo.qpic.cn/video_hd.mp4?k=2&p=1")
        self.assertEqual(parser.get_video_list(), ["http://mpvideo.qpic.cn/video_hd.mp4?k=2&p=1"])

    def test_maps_multiple_videos_response(self):
        html_content = """
        <!DOCTYPE html>
        <html>
        <head>
            <meta property="og:title" content="多视频文章测试" />
        </head>
        <body>
            <script>
                var videoPageInfos = [
                    {
                        video_id: 'wxv_video_1',
                        mp_video_trans_info: [
                            {
                                format_id: 10004,
                                width: 480,
                                height: 854,
                                filesize: 1000,
                                video_quality_level: 1,
                                url: 'http://mpvideo.qpic.cn/0bc3vid1aaaa.f10004.mp4?k=1'
                            },
                            {
                                format_id: 10002,
                                width: 1080,
                                height: 1920,
                                filesize: 5000,
                                video_quality_level: 3,
                                url: 'http://mpvideo.qpic.cn/0bc3vid1aaaa.f10002.mp4?k=2'
                            }
                        ]
                    },
                    {
                        video_id: 'wxv_video_2',
                        mp_video_trans_info: [
                            {
                                format_id: 10004,
                                width: 640,
                                height: 360,
                                filesize: 2000,
                                video_quality_level: 1,
                                url: 'http://mpvideo.qpic.cn/0bc3vid2bbbb.f10004.mp4?k=3'
                            },
                            {
                                format_id: 10002,
                                width: 1280,
                                height: 720,
                                filesize: 6000,
                                video_quality_level: 3,
                                url: 'http://mpvideo.qpic.cn/0bc3vid2bbbb.f10002.mp4?k=4'
                            }
                        ]
                    }
                ];
            </script>
        </body>
        </html>
        """
        response = Mock()
        response.status_code = 200
        response.raise_for_status.return_value = None
        response.text = html_content

        with patch("requests.Session.get", return_value=response):
            parser = WechatMpParser(self.URL)

        self.assertEqual(parser.get_title_content(), "多视频文章测试")
        self.assertEqual(parser.get_real_video_url(), "http://mpvideo.qpic.cn/0bc3vid1aaaa.f10002.mp4?k=2")
        self.assertEqual(
            parser.get_video_list(),
            [
                "http://mpvideo.qpic.cn/0bc3vid1aaaa.f10002.mp4?k=2",
                "http://mpvideo.qpic.cn/0bc3vid2bbbb.f10002.mp4?k=4",
            ],
        )

    def test_handles_request_failure_gracefully(self):
        response = Mock()
        response.raise_for_status.side_effect = Exception("HTTP 404")

        with patch("requests.Session.get", return_value=response):
            parser = WechatMpParser(self.URL)

        self.assertEqual(parser.get_title_content(), "微信公众号文章")
        self.assertEqual(parser.get_image_list(), [])
        self.assertIsNone(parser.get_real_video_url())
        self.assertEqual(parser.get_video_list(), [])

    def test_detects_environment_verify_page(self):
        response = Mock()
        response.raise_for_status.return_value = None
        response.text = '<html><head><link rel="stylesheet" href="//res.wx.qq.com/secitptpage/verify.css"></head><body><h2 class="weui-msg__title">环境异常</h2><p>当前环境异常，完成验证后即可继续访问。</p></body></html>'

        with patch("requests.Session.get", return_value=response):
            parser = WechatMpParser(self.URL)

        self.assertIsNotNone(parser.terminal_error)
        self.assertEqual(parser.terminal_error["error_code"], "WECHAT_MP_VERIFY_REQUIRED")

    def test_detects_deleted_article(self):
        response = Mock()
        response.raise_for_status.return_value = None
        response.text = '<html><body><h3>该内容已被发布者删除</h3></body></html>'

        with patch("requests.Session.get", return_value=response):
            parser = WechatMpParser(self.URL)

        self.assertIsNotNone(parser.terminal_error)
        self.assertEqual(parser.terminal_error["error_code"], "MEDIA_DELETED_OR_PRIVATE")


if __name__ == "__main__":
    unittest.main()


