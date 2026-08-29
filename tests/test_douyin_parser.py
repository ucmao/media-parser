import json
import unittest
import urllib.parse
from unittest.mock import Mock, patch
from src.parsers.douyin_parser import DouyinParser


class DouyinParserTest(unittest.TestCase):
    def make_parser(self, data=None):
        with patch.object(DouyinParser, "fetch_html_content", return_value="<html></html>"):
            with patch.object(DouyinParser, "fetch_html_data", return_value=data or {}):
                with patch("utils.signer.bytedance.bogus_signer.BogusSigner.get_ms_token", return_value="mock_ms_token"):
                    parser = DouyinParser("https://www.douyin.com/video/7341234567890123456")
                    parser.data = data or {}
                    return parser

    def test_highest_bitrate_h264_selected(self):
        data = {
            "aweme_detail": {
                "desc": "测试视频",
                "video": {
                    "bit_rate": [
                        {
                            "bit_rate": 800000,
                            "is_h265": 0,
                            "play_addr": {
                                "url_list": [
                                    "http://cdn1.douyin.com/720p_1.mp4",
                                    "http://cdn2.douyin.com/720p_2.mp4",
                                    "http://origin.douyin.com/720p_origin.mp4"
                                ]
                            }
                        },
                        {
                            "bit_rate": 3000000,
                            "is_h265": 1,  # H.265 超清
                            "play_addr": {
                                "url_list": [
                                    "http://origin.douyin.com/hevc_origin.mp4"
                                ]
                            }
                        },
                        {
                            "bit_rate": 2000000,
                            "is_h265": 0,  # H.264 最高画质
                            "play_addr": {
                                "url_list": [
                                    "http://cdn1.douyin.com/1080p_1.mp4",
                                    "http://cdn2.douyin.com/1080p_2.mp4",
                                    "http://origin.douyin.com/1080p_origin.mp4"
                                ]
                            }
                        }
                    ]
                }
            }
        }
        parser = self.make_parser(data)
        # 应当优先选 H.264 中的最高码率 (2000000)，且优先取 url_list[2] 官方源站 CDN
        self.assertEqual(parser.get_real_video_url(), "http://origin.douyin.com/1080p_origin.mp4")
        self.assertEqual(parser.get_video_list(), ["http://origin.douyin.com/1080p_origin.mp4"])

    def test_h265_fallback_when_no_h264(self):
        data = {
            "aweme_detail": {
                "desc": "纯HEVC视频",
                "video": {
                    "bit_rate": [
                        {
                            "bit_rate": 1000000,
                            "is_h265": 1,
                            "play_addr": {"url_list": ["http://origin.douyin.com/hevc_720.mp4"]}
                        },
                        {
                            "bit_rate": 3500000,
                            "is_h265": 1,
                            "play_addr": {"url_list": ["http://origin.douyin.com/hevc_1080.mp4"]}
                        }
                    ]
                }
            }
        }
        parser = self.make_parser(data)
        self.assertEqual(parser.get_real_video_url(), "http://origin.douyin.com/hevc_1080.mp4")

    def test_play_addr_fallback_when_bit_rate_empty(self):
        data = {
            "aweme_detail": {
                "desc": "老视频无bit_rate",
                "video": {
                    "bit_rate": [],
                    "play_addr": {
                        "url_list": [
                            "http://cdn1.douyin.com/video_1.mp4",
                            "http://cdn2.douyin.com/video_2.mp4",
                            "http://origin.douyin.com/video_origin.mp4"
                        ]
                    }
                }
            }
        }
        parser = self.make_parser(data)
        self.assertEqual(parser.get_real_video_url(), "http://origin.douyin.com/video_origin.mp4")

    def test_extracts_subtitles_from_cla_info(self):
        data = {
            "aweme_detail": {
                "desc": "带字幕视频",
                "video": {
                    "cla_info": {
                        "caption_infos": [
                            {
                                "language_code": "zh-Hans",
                                "language_id": 1,
                                "url": "http://p3-sign.douyinpic.com/tos-cn-p-0015/zh.vtt",
                                "format": "webvtt",
                                "sub_id": 12345678,
                                "is_auto_generated": True
                            },
                            {
                                "language_code": "en",
                                "language_id": 2,
                                "url": "http://p3-sign.douyinpic.com/tos-cn-p-0015/en.vtt",
                                "format": "webvtt",
                                "sub_id": 87654321,
                                "is_auto_generated": False
                            }
                        ]
                    }
                }
            }
        }
        parser = self.make_parser(data)
        subtitles = parser.get_subtitles()
        self.assertIsNotNone(subtitles)
        self.assertEqual(len(subtitles), 2)
        self.assertEqual(subtitles[0], {
            "language_code": "zh-Hans",
            "url": "https://p3-sign.douyinpic.com/tos-cn-p-0015/zh.vtt",
            "format": "webvtt",
            "is_auto_generated": True,
            "sub_id": "12345678"
        })
        self.assertEqual(subtitles[1]["language_code"], "en")
        self.assertEqual(subtitles[1]["url"], "https://p3-sign.douyinpic.com/tos-cn-p-0015/en.vtt")

    def test_extracts_subtitles_from_subtitle_infos_fallback(self):
        data = {
            "aweme_detail": {
                "desc": "subtitle_infos 格式",
                "video": {
                    "subtitle_infos": [
                        {
                            "language_code": "zh-Hans",
                            "url": "https://p3-sign.douyinpic.com/tos-cn-p-0015/zh.vtt",
                            "format": "webvtt",
                            "is_auto_generated": True
                        }
                    ]
                }
            }
        }
        parser = self.make_parser(data)
        subtitles = parser.get_subtitles()
        self.assertEqual(len(subtitles), 1)
        self.assertEqual(subtitles[0]["language_code"], "zh-Hans")
        self.assertEqual(subtitles[0]["format"], "webvtt")

    def test_returns_none_subtitles_when_no_captions(self):
        data = {
            "aweme_detail": {
                "desc": "无字幕视频",
                "video": {
                    "cla_info": {"caption_infos": []}
                }
            }
        }
        parser = self.make_parser(data)
        self.assertIsNone(parser.get_subtitles())

    def test_image_note_and_live_photo_extraction(self):
        data = {
            "aweme_detail": {
                "desc": "图文与实况",
                "images": [
                    {
                        "url_list": [
                            "http://cdn1.douyin.com/img1_thumb.jpg",
                            "http://cdn2.douyin.com/img1_hd.jpg"
                        ]
                    },
                    {
                        "url_list": [
                            "http://cdn1.douyin.com/img2_hd.jpg"
                        ],
                        "video": {
                            "play_addr": {
                                "url_list": [
                                    "http://cdn1.douyin.com/livephoto.mp4"
                                ]
                            }
                        }
                    }
                ]
            }
        }
        parser = self.make_parser(data)
        image_list = parser.get_image_list()
        self.assertEqual(len(image_list), 2)
        # 第一张为纯静态图，取最后一个最高画质 CDN
        self.assertEqual(image_list[0], "http://cdn2.douyin.com/img1_hd.jpg")
        # 第二张为实况 Live Photo
        self.assertEqual(image_list[1], {
            "url": "http://cdn1.douyin.com/img2_hd.jpg",
            "live_photo_url": "http://cdn1.douyin.com/livephoto.mp4"
        })

    def test_safe_empty_data(self):
        parser = self.make_parser({})
        self.assertIsNone(parser.get_real_video_url())
        self.assertEqual(parser.get_video_list(), [])
        self.assertIsNone(parser.get_subtitles())
        self.assertEqual(parser.get_image_list(), [])
        self.assertIsNone(parser.get_cover_photo_url())
        self.assertIsNone(parser.get_title_content())
        self.assertIsNone(parser.get_author_info())


    def test_ssr_fallback_universal_data_when_api_fails(self):
        ssr_payload = {
            "__DEFAULT_SCOPE__": {
                "webapp.video-detail": {
                    "itemInfo": {
                        "itemStruct": {
                            "aweme_id": "7341234567890123456",
                            "desc": "SSR Universal 降级视频",
                            "video": {
                                "play_addr": {
                                    "url_list": ["http://origin.douyin.com/ssr_universal.mp4"]
                                }
                            }
                        }
                    }
                }
            }
        }
        html = f'<html><body><script id="__UNIVERSAL_DATA_FOR_REHYDRATION__" type="application/json">{json.dumps(ssr_payload)}</script></body></html>'

        # 模拟 API 失败 (403)，HTML 页面包含 SSR 数据
        api_response = Mock(status_code=403, text="Forbidden")
        with patch("requests.Session.get", return_value=api_response):
            with patch.object(DouyinParser, "fetch_html_content", return_value=html):
                with patch("utils.signer.bytedance.bogus_signer.BogusSigner.get_ms_token", return_value="mock_token"):
                    parser = DouyinParser("https://www.douyin.com/video/7341234567890123456")
                    parser.html_content = html
                    parser.data = parser.fetch_html_data()

        self.assertEqual(parser.get_title_content(), "SSR Universal 降级视频")
        self.assertEqual(parser.get_real_video_url(), "http://origin.douyin.com/ssr_universal.mp4")

    def test_ssr_fallback_render_data_when_api_fails(self):
        import urllib.parse
        ssr_payload = {
            "app": {
                "videoDetail": {
                    "aweme_id": "7341234567890123456",
                    "desc": "SSR RENDER_DATA 降级视频",
                    "video": {
                        "play_addr": {
                            "url_list": ["http://origin.douyin.com/ssr_render.mp4"]
                        }
                    }
                }
            }
        }
        encoded_json = urllib.parse.quote(json.dumps(ssr_payload))
        html = f'<html><body><script id="RENDER_DATA" type="application/json">{encoded_json}</script></body></html>'

        api_response = Mock(status_code=500, text="Internal Error")
        with patch("requests.Session.get", return_value=api_response):
            with patch.object(DouyinParser, "fetch_html_content", return_value=html):
                with patch("utils.signer.bytedance.bogus_signer.BogusSigner.get_ms_token", return_value="mock_token"):
                    parser = DouyinParser("https://www.douyin.com/video/7341234567890123456")
                    parser.html_content = html
                    parser.data = parser.fetch_html_data()

        self.assertEqual(parser.get_title_content(), "SSR RENDER_DATA 降级视频")
        self.assertEqual(parser.get_real_video_url(), "http://origin.douyin.com/ssr_render.mp4")

    def test_ssr_fallback_router_data_regex_when_api_fails(self):
        ssr_payload = {
            "loaderData": {
                "video": {
                    "aweme_detail": {
                        "aweme_id": "7341234567890123456",
                        "desc": "SSR Router Data 正则降级视频",
                        "video": {
                            "play_addr": {
                                "url_list": ["http://origin.douyin.com/ssr_router.mp4"]
                            }
                        }
                    }
                }
            }
        }
        html = f'<html><body><script>window._ROUTER_DATA = {json.dumps(ssr_payload)};</script></body></html>'

        api_response = Mock(status_code=200, text=json.dumps({"status_code": 0}))  # 无 aweme_detail
        api_response.json = Mock(return_value={"status_code": 0})
        with patch("requests.Session.get", return_value=api_response):
            with patch.object(DouyinParser, "fetch_html_content", return_value=html):
                with patch("utils.signer.bytedance.bogus_signer.BogusSigner.get_ms_token", return_value="mock_token"):
                    parser = DouyinParser("https://www.douyin.com/video/7341234567890123456")
                    parser.html_content = html
                    parser.data = parser.fetch_html_data()

        self.assertEqual(parser.get_title_content(), "SSR Router Data 正则降级视频")
        self.assertEqual(parser.get_real_video_url(), "http://origin.douyin.com/ssr_router.mp4")

    def test_api_success_takes_precedence_over_ssr(self):
        api_payload = {
            "aweme_detail": {
                "aweme_id": "7341234567890123456",
                "desc": "API 优先视频",
                "video": {
                    "play_addr": {"url_list": ["http://origin.douyin.com/api_video.mp4"]}
                }
            }
        }
        ssr_payload = {
            "__DEFAULT_SCOPE__": {
                "webapp.video-detail": {
                    "itemInfo": {
                        "itemStruct": {
                            "aweme_id": "7341234567890123456",
                            "desc": "SSR 视频",
                            "video": {"play_addr": {"url_list": ["http://origin.douyin.com/ssr_video.mp4"]}}
                        }
                    }
                }
            }
        }
        html = f'<html><body><script id="__UNIVERSAL_DATA_FOR_REHYDRATION__">{json.dumps(ssr_payload)}</script></body></html>'

        api_response = Mock(status_code=200, text=json.dumps(api_payload))
        api_response.json = Mock(return_value=api_payload)
        with patch("requests.Session.get", return_value=api_response):
            with patch.object(DouyinParser, "fetch_html_content", return_value=html):
                with patch("utils.signer.bytedance.bogus_signer.BogusSigner.get_ms_token", return_value="mock_token"):
                    parser = DouyinParser("https://www.douyin.com/video/7341234567890123456")
                    parser.html_content = html
                    parser.data = parser.fetch_html_data()

        self.assertEqual(parser.get_title_content(), "API 优先视频")
        self.assertEqual(parser.get_real_video_url(), "http://origin.douyin.com/api_video.mp4")


if __name__ == "__main__":
    unittest.main()
