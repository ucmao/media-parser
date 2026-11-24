import json
import time
import os
import unittest
import urllib.parse
from unittest.mock import Mock, patch
from src.parsers import douyin_parser as douyin_module
from src.parsers.douyin_parser import DouyinParser


class DouyinParserTest(unittest.TestCase):
    def setUp(self):
        # 生产代码在 403 重试之间会退避 sleep；单测里去掉退避以免整个用例集变慢
        no_backoff = patch.multiple(douyin_module, RETRY_BASE_DELAY=0, RETRY_MAX_DELAY=0)
        no_backoff.start()
        self.addCleanup(no_backoff.stop)
        no_network = patch.object(DouyinParser, '_get_ttwid', return_value='test-ttwid')
        no_network.start()
        self.addCleanup(no_network.stop)

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

    def test_image_note_returns_none_video_url(self):
        data = {
            "aweme_detail": {
                "desc": "图文作品测试",
                "media_type": 2,
                "images": [
                    {
                        "url_list": [
                            "https://p3-pc-sign.douyinpic.com/img1.webp",
                            "https://p3-pc-sign.douyinpic.com/img1.jpeg"
                        ]
                    }
                ],
                "video": {
                    "bit_rate": None,
                    "play_addr": {
                        "url_list": [
                            "https://lf26-music-east.douyinstatic.com/obj/ies-music-hj/bgm.mp3"
                        ]
                    }
                }
            }
        }
        parser = self.make_parser(data)
        self.assertIsNone(parser.get_real_video_url())
        self.assertEqual(parser.get_video_list(), [])
        self.assertEqual(len(parser.get_image_list()), 1)

    def test_audio_fallback_filtered_out(self):
        data = {
            "aweme_detail": {
                "desc": "异常作品，无bit_rate且play_addr为音频",
                "video": {
                    "bit_rate": [],
                    "play_addr": {
                        "url_list": [
                            "https://sf6-cdn-tos.douyinstatic.com/obj/ies-music/audio.mp3"
                        ]
                    }
                }
            }
        }
        parser = self.make_parser(data)
        self.assertIsNone(parser.get_real_video_url())
        self.assertEqual(parser.get_video_list(), [])


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
        mock_vtt = (
            "WEBVTT\n\n"
            "1\n"
            "00:00:01.000 --> 00:00:03.500\n"
            "大家好我是小李\n\n"
            "2\n"
            "00:00:03.800 --> 00:00:06.200\n"
            "今天给大家分享一个好消息\n"
        )
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = mock_vtt

        parser = self.make_parser(data)
        with patch.object(parser.session, "get", return_value=mock_response) as mock_get:
            subtitles = parser.get_subtitles()
            mock_get.assert_called_once_with(
                "https://p3-sign.douyinpic.com/tos-cn-p-0015/zh.vtt",
                headers=parser.headers,
                timeout=5
            )

        self.assertIsNotNone(subtitles)
        self.assertEqual(len(subtitles), 2)
        self.assertEqual(subtitles[0], {"start": 1.0, "end": 3.5, "text": "大家好我是小李"})
        self.assertEqual(subtitles[1], {"start": 3.8, "end": 6.2, "text": "今天给大家分享一个好消息"})

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
        mock_vtt = "WEBVTT\n\n00:00.500 --> 00:02.300\n单一字幕行\n"
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = mock_vtt

        parser = self.make_parser(data)
        with patch.object(parser.session, "get", return_value=mock_response):
            subtitles = parser.get_subtitles()

        self.assertEqual(subtitles, [{"start": 0.5, "end": 2.3, "text": "单一字幕行"}])

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

    def test_parse_webvtt_with_cue_tags_and_multi_line(self):
        vtt_content = (
            "WEBVTT\n\n"
            "00:01:05.120 --> 00:01:08.500 line:0% position:50%\n"
            "<c.yellow>欢迎收看</c><b>今日头条</b>\n"
            "精彩内容不容错过\n\n"
            "00:01:09.000 --> 00:01:12.000\n"
            "感谢大家支持\n"
        )
        segments = DouyinParser._parse_webvtt_to_segments(vtt_content)
        self.assertEqual(len(segments), 2)
        self.assertEqual(segments[0], {
            "start": 65.12,
            "end": 68.5,
            "text": "欢迎收看今日头条 精彩内容不容错过"
        })
        self.assertEqual(segments[1], {
            "start": 69.0,
            "end": 72.0,
            "text": "感谢大家支持"
        })

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

        self.assertIsNone(parser.get_title_content())
        self.assertEqual(parser.get_description(), "SSR Universal 降级视频")
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

        self.assertIsNone(parser.get_title_content())
        self.assertEqual(parser.get_description(), "SSR RENDER_DATA 降级视频")
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

        self.assertIsNone(parser.get_title_content())
        self.assertEqual(parser.get_description(), "SSR Router Data 正则降级视频")
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

    def test_music_standalone_link_parsing(self):
        music_data = {
            "music_info": {
                "title": "流行背景音乐",
                "author": "抖音音乐人",
                "owner_id": "999888777",
                "play_url": {"url_list": ["http://origin.douyin.com/music.mp3"]},
                "cover_large": {"url_list": ["http://origin.douyin.com/music_cover.jpg"]},
                "user_count": 52000,
                "duration": 45
            }
        }
        with patch.object(DouyinParser, "fetch_html_content", return_value="<html></html>"):
            with patch.object(DouyinParser, "fetch_html_data", return_value=music_data):
                with patch("utils.signer.bytedance.bogus_signer.BogusSigner.get_ms_token", return_value="mock_token"):
                    parser = DouyinParser("https://www.douyin.com/music/7123456789012345678")
                    parser.data = music_data

        self.assertTrue(parser.is_music)
        self.assertEqual(parser.get_title_content(), "流行背景音乐")
        self.assertEqual(parser.get_audio_url(), "http://origin.douyin.com/music.mp3")
        self.assertEqual(parser.get_cover_photo_url(), "http://origin.douyin.com/music_cover.jpg")
        self.assertIsNone(parser.get_real_video_url())
        self.assertEqual(parser.get_video_list(), [])
        self.assertEqual(parser.get_image_list(), [])
        self.assertIsNone(parser.get_subtitles())
        author = parser.get_author_info()
        self.assertEqual(author["nickname"], "抖音音乐人")
        self.assertEqual(author["author_id"], "999888777")

    def test_audio_url_fallback_to_original_song_url(self):
        data = {
            "aweme_detail": {
                "desc": "原声被标记不可用的作品",
                "music": {
                    "offline_desc": "该声音不可用",
                    "play_url": {"url_list": None},
                    "extra": json.dumps({
                        "filter_reason": "gov_takedown",
                        "original_song_url": "https://sf26-sign.douyinstatic.com/ies-music/test_orig.mp3?x-expires=123"
                    })
                }
            }
        }
        parser = self.make_parser(data)
        self.assertEqual(
            parser.get_audio_url(),
            "https://sf26-sign.douyinstatic.com/ies-music/test_orig.mp3?x-expires=123"
        )

    def test_audio_url_fallback_with_dict_extra_and_music_page(self):
        music_data = {
            "music_info": {
                "title": "已下架原声",
                "offline_desc": "该声音不可用",
                "play_url": {"url_list": []},
                "extra": {
                    "original_sound_url": "https://sf26-sign.douyinstatic.com/ies-music/test_sound.mp3"
                }
            }
        }
        with patch.object(DouyinParser, "fetch_html_content", return_value="<html></html>"):
            with patch.object(DouyinParser, "fetch_html_data", return_value=music_data):
                with patch("utils.signer.bytedance.bogus_signer.BogusSigner.get_ms_token", return_value="mock_token"):
                    parser = DouyinParser("https://www.douyin.com/music/7123456789012345678")
                    parser.data = music_data

        self.assertEqual(
            parser.get_audio_url(),
            "https://sf26-sign.douyinstatic.com/ies-music/test_sound.mp3"
        )

    def test_collection_standalone_link_parsing(self):
        collection_data = {
            "mix_info": {
                "mix_id": "7123456789012345678",
                "mix_name": "年度爆笑连续剧",
                "total_episodes": 12,
                "cover_url": {"url_list": ["http://origin.douyin.com/mix_cover.jpg"]},
                "author": {
                    "nickname": "短剧创作者",
                    "unique_id": "creator_007",
                    "avatar_thumb": {"url_list": ["http://origin.douyin.com/avatar.jpg"]}
                }
            },
            "aweme_list": [
                {
                    "desc": "第1集",
                    "video": {
                        "bit_rate": [
                            {"bit_rate": 1500000, "is_h265": 0, "play_addr": {"url_list": ["http://origin.douyin.com/ep1.mp4"]}}
                        ]
                    }
                },
                {
                    "desc": "第2集",
                    "video": {
                        "bit_rate": [
                            {"bit_rate": 1500000, "is_h265": 0, "play_addr": {"url_list": ["http://origin.douyin.com/ep2.mp4"]}}
                        ]
                    }
                }
            ]
        }
        with patch.object(DouyinParser, "fetch_html_content", return_value="<html></html>"):
            with patch.object(DouyinParser, "fetch_html_data", return_value=collection_data):
                with patch("utils.signer.bytedance.bogus_signer.BogusSigner.get_ms_token", return_value="mock_token"):
                    parser = DouyinParser("https://www.douyin.com/collection/7123456789012345678")
                    parser.data = collection_data

        self.assertTrue(parser.is_collection)
        self.assertEqual(parser.get_title_content(), "【合集】年度爆笑连续剧")
        self.assertEqual(parser.get_real_video_url(), "http://origin.douyin.com/ep1.mp4")
        self.assertEqual(parser.get_video_list(), ["http://origin.douyin.com/ep1.mp4", "http://origin.douyin.com/ep2.mp4"])
        self.assertEqual(parser.get_cover_photo_url(), "http://origin.douyin.com/mix_cover.jpg")
        self.assertEqual(parser.get_author_info()["nickname"], "短剧创作者")

    def test_lvdetail_single_episode_extraction(self):
        lv_data = {
            "album_info": {
                "album_id": "7677129845654061500",
                "album_name": "放映厅热播剧",
                "cover_url": {"url_list": ["http://origin.douyin.com/album_cover.jpg"]},
                "author": {
                    "nickname": "影视出品方",
                    "unique_id": "film_studio",
                    "avatar_thumb": {"url_list": ["http://origin.douyin.com/studio_avatar.jpg"]}
                }
            },
            "episode_info": {
                "episode_id": "7677129845654061595",
                "episode_name": "第01集 精彩开播",
                "video": {
                    "bit_rate": [
                        {"bit_rate": 2500000, "is_h265": 0, "play_addr": {"url_list": ["http://origin.douyin.com/lv_ep1_1080.mp4"]}},
                        {"bit_rate": 1200000, "is_h265": 0, "play_addr": {"url_list": ["http://origin.douyin.com/lv_ep1_720.mp4"]}}
                    ],
                    "cla_info": {
                        "caption_infos": [
                            {
                                "language_code": "zh-Hans",
                                "url": "https://p3-sign.douyinpic.com/tos-cn-p-0015/zh.vtt",
                                "format": "webvtt"
                            }
                        ]
                    }
                }
            }
        }
        with patch.object(DouyinParser, "fetch_html_content", return_value="<html></html>"):
            with patch.object(DouyinParser, "fetch_html_data", return_value=lv_data):
                with patch("utils.signer.bytedance.bogus_signer.BogusSigner.get_ms_token", return_value="mock_token"):
                    parser = DouyinParser("https://www.douyin.com/lvdetail/7677129845654061595")
                    parser.data = lv_data

        self.assertTrue(parser.is_lvdetail)
        self.assertEqual(parser.get_title_content(), "【放映厅】放映厅热播剧 - 第01集 精彩开播")
        self.assertEqual(parser.get_real_video_url(), "http://origin.douyin.com/lv_ep1_1080.mp4")
        self.assertEqual(parser.get_video_list(), ["http://origin.douyin.com/lv_ep1_1080.mp4"])
        self.assertEqual(parser.get_cover_photo_url(), "http://origin.douyin.com/album_cover.jpg")
        self.assertEqual(parser.get_author_info()["nickname"], "影视出品方")
        self.assertEqual(parser.get_author_info()["author_id"], "film_studio")
        self.assertEqual(parser.get_author_info()["avatar"], "http://origin.douyin.com/studio_avatar.jpg")
        self.assertEqual(parser.get_image_list(), [])

    def test_lvdetail_multi_episode_video_list(self):
        lv_multi_data = {
            "album_info": {
                "album_name": "经典连载剧集",
                "horizontal_cover": "http://origin.douyin.com/album_h_cover.jpg"
            },
            "episode_list": [
                {
                    "episode_name": "第1集",
                    "video": {
                        "bit_rate": [
                            {"bit_rate": 2000000, "is_h265": 0, "play_addr": {"url_list": ["http://origin.douyin.com/ep1.mp4"]}}
                        ]
                    }
                },
                {
                    "episode_name": "第2集",
                    "video": {
                        "bit_rate": [
                            {"bit_rate": 2000000, "is_h265": 0, "play_addr": {"url_list": ["http://origin.douyin.com/ep2.mp4"]}}
                        ]
                    }
                },
                {
                    "episode_name": "第3集",
                    "video": {
                        "bit_rate": [
                            {"bit_rate": 2000000, "is_h265": 0, "play_addr": {"url_list": ["http://origin.douyin.com/ep3.mp4"]}}
                        ]
                    }
                }
            ]
        }
        with patch.object(DouyinParser, "fetch_html_content", return_value="<html></html>"):
            with patch.object(DouyinParser, "fetch_html_data", return_value=lv_multi_data):
                with patch("utils.signer.bytedance.bogus_signer.BogusSigner.get_ms_token", return_value="mock_token"):
                    parser = DouyinParser("https://www.iesdouyin.com/share/video/123/?ep_id=7677129845654061595")
                    parser.data = lv_multi_data

        self.assertTrue(parser.is_lvdetail)
        self.assertEqual(parser.get_title_content(), "【放映厅】经典连载剧集 - 第1集")
        self.assertEqual(parser.get_real_video_url(), "http://origin.douyin.com/ep1.mp4")
        self.assertEqual(parser.get_video_list(), [
            "http://origin.douyin.com/ep1.mp4",
            "http://origin.douyin.com/ep2.mp4",
            "http://origin.douyin.com/ep3.mp4"
        ])
        self.assertEqual(parser.get_cover_photo_url(), "http://origin.douyin.com/album_h_cover.jpg")

    def test_lvdetail_ssr_universal_data_fallback(self):
        ssr_payload = {
            "__DEFAULT_SCOPE__": {
                "webapp.lvideo-detail": {
                    "lvideo_detail": {
                        "album_info": {
                            "album_name": "SSR放映厅电影",
                            "poster_url": "http://origin.douyin.com/ssr_poster.jpg"
                        },
                        "episode_info": {
                            "episode_name": "正片",
                            "video": {
                                "play_addr": {
                                    "url_list": ["http://origin.douyin.com/ssr_movie.mp4"]
                                }
                            }
                        }
                    }
                }
            }
        }
        html = f'<html><body><script id="__UNIVERSAL_DATA_FOR_REHYDRATION__" type="application/json">{json.dumps(ssr_payload)}</script></body></html>'

        api_response = Mock(status_code=404, text="Not Found")
        with patch("requests.Session.get", return_value=api_response):
            with patch.object(DouyinParser, "fetch_html_content", return_value=html):
                with patch("utils.signer.bytedance.bogus_signer.BogusSigner.get_ms_token", return_value="mock_token"):
                    parser = DouyinParser("https://www.douyin.com/lvdetail/7677129845654061595")
                    parser.html_content = html
                    parser.data = parser.fetch_html_data()

        self.assertTrue(parser.is_lvdetail)
        self.assertEqual(parser.get_title_content(), "【放映厅】SSR放映厅电影 - 正片")
        self.assertEqual(parser.get_real_video_url(), "http://origin.douyin.com/ssr_movie.mp4")
        self.assertEqual(parser.get_cover_photo_url(), "http://origin.douyin.com/ssr_poster.jpg")

    def test_mobile_feed_direct_success(self):
        aweme_id = "7677522557314197114"
        feed_payload = {
            "status_code": 0,
            "aweme_list": [
                {
                    "aweme_id": aweme_id,
                    "desc": "移动端Feed测试视频",
                    "video": {
                        "bit_rate": [
                            {"bit_rate": 2000000, "is_h265": 0, "play_addr": {"url_list": ["http://cdn.douyin.com/feed_v1.mp4"]}}
                        ]
                    }
                }
            ]
        }
        mock_resp = Mock(status_code=200, text=json.dumps(feed_payload))
        mock_resp.json.return_value = feed_payload

        with patch("requests.Session.get", return_value=mock_resp) as mock_get:
            with patch.object(DouyinParser, "_request_api_with_retry") as mock_web_api:
                parser = DouyinParser(f"https://www.douyin.com/video/{aweme_id}")
                self.assertIsNotNone(parser.data)
                self.assertIn("aweme_detail", parser.data)
                self.assertEqual(parser.data["aweme_detail"]["desc"], "移动端Feed测试视频")
                self.assertEqual(parser.get_real_video_url(), "http://cdn.douyin.com/feed_v1.mp4")
                # 命中移动端 Feed 后，不应再调用 Web API
                mock_web_api.assert_not_called()

    def test_mobile_feed_failover_to_secondary(self):
        aweme_id = "7677522557314197114"
        feed_payload = {
            "status_code": 0,
            "aweme_list": [{"aweme_id": aweme_id, "desc": "备用节点视频"}]
        }
        fail_resp = Mock(status_code=502, text="Bad Gateway")
        succ_resp = Mock(status_code=200, text=json.dumps(feed_payload))
        succ_resp.json.return_value = feed_payload

        with patch("requests.Session.get", side_effect=[fail_resp, succ_resp]) as mock_get:
            parser = DouyinParser(f"https://www.douyin.com/video/{aweme_id}")
            self.assertIsNotNone(parser.data)
            self.assertEqual(parser.data["aweme_detail"]["desc"], "备用节点视频")
            self.assertEqual(mock_get.call_count, 2)

    def test_mobile_feed_fallback_to_web_api(self):
        aweme_id = "7681860997179940209"
        # 移动端 Feed 未包含目标 ID（如 Note 图文）
        feed_payload = {"status_code": 0, "aweme_list": [{"aweme_id": "other_id"}]}
        mock_feed_resp = Mock(status_code=200, text=json.dumps(feed_payload))
        mock_feed_resp.json.return_value = feed_payload

        web_detail_payload = {
            "status_code": 0,
            "aweme_detail": {"aweme_id": aweme_id, "desc": "Web API 兜底图文"}
        }

        with patch.object(DouyinParser, "_request_mobile_feed", return_value=None):
            with patch.object(DouyinParser, "_request_api_with_retry", return_value=web_detail_payload) as mock_web_api:
                parser = DouyinParser(f"https://www.douyin.com/note/{aweme_id}")
                self.assertIsNotNone(parser.data)
                self.assertEqual(parser.data["aweme_detail"]["desc"], "Web API 兜底图文")
                mock_web_api.assert_called_once()

    def test_terminal_failure_stops_retry_immediately(self):
        aweme_id = "7683421854267204985"
        terminal_payload = {
            "status_code": 0,
            "aweme_detail": None,
            "filter_detail": {
                "aweme_id": aweme_id,
                "detail_msg": "因作品权限或已被删除，无法观看，去看看其他作品吧",
                "filter_reason": "status_self_see",
                "notice": "抱歉，作品不见了"
            }
        }
        mock_resp = Mock(status_code=200, text=json.dumps(terminal_payload))
        mock_resp.json.return_value = terminal_payload

        with patch.object(DouyinParser, "_request_mobile_feed", return_value=None):
            with patch.object(DouyinParser, "_try_share_ssr_detail", return_value=None):
                with patch.object(DouyinParser, "fetch_html_content") as mock_ssr:
                    with patch("requests.Session.get", return_value=mock_resp) as mock_get:
                        parser = DouyinParser(f"https://www.douyin.com/video/{aweme_id}")
                        # 应该在第 1 次拿到 terminal 响应后立即退出，不能重试 8 次
                        self.assertEqual(mock_get.call_count, 1)
                        # 应该跳过末级 SSR 兜底
                        mock_ssr.assert_not_called()
                        self.assertIsNone(parser.data)

    def _terminal_parser(self, aweme_id, filter_reason):
        payload = {
            "status_code": 0,
            "aweme_detail": None,
            "filter_detail": {
                "aweme_id": aweme_id,
                "detail_msg": "因作品权限或已被删除，无法观看，去看看其他作品吧",
                "filter_reason": filter_reason,
                "notice": "抱歉，作品不见了",
            },
        }
        mock_resp = Mock(status_code=200, text=json.dumps(payload))
        mock_resp.json.return_value = payload
        with patch.object(DouyinParser, "_request_mobile_feed", return_value=None):
            with patch.object(DouyinParser, "_try_share_ssr_detail", return_value=None):
                with patch.object(DouyinParser, "fetch_html_content"):
                    with patch("requests.Session.get", return_value=mock_resp):
                        return DouyinParser(f"https://www.douyin.com/video/{aweme_id}")

    @staticmethod
    def _aweme_id_published_at(ts):
        return str((int(ts) << 32) | 123456)

    def test_fresh_self_see_is_reported_as_under_review(self):
        aweme_id = self._aweme_id_published_at(time.time() - 120)
        parser = self._terminal_parser(aweme_id, "status_self_see")
        self.assertEqual(parser.terminal_error["error_code"], "MEDIA_UNDER_REVIEW")
        self.assertIn("审核", parser.terminal_error["detail_msg"])

    def test_old_self_see_stays_private(self):
        aweme_id = self._aweme_id_published_at(time.time() - 3 * 86400)
        parser = self._terminal_parser(aweme_id, "status_self_see")
        self.assertNotIn("error_code", parser.terminal_error)

    def test_fresh_deleted_stays_deleted(self):
        aweme_id = self._aweme_id_published_at(time.time() - 60)
        parser = self._terminal_parser(aweme_id, "status_deleted")
        self.assertNotIn("error_code", parser.terminal_error)

    def test_share_ssr_precedence_over_web_api(self):
        aweme_id = "7675236180098600202"
        ssr_payload = {
            "aweme_detail": {
                "aweme_id": aweme_id,
                "desc": "分享页 SSR 优先解析图文",
                "images": [{"url_list": ["https://p3.douyinpic.com/img1.jpg"]}]
            }
        }
        with patch.object(DouyinParser, "_request_mobile_feed", return_value=None):
            with patch.object(DouyinParser, "_try_share_ssr_detail", return_value=ssr_payload) as mock_share_ssr:
                with patch.object(DouyinParser, "_request_api_with_retry") as mock_web_api:
                    parser = DouyinParser(f"https://www.iesdouyin.com/share/video/{aweme_id}")
                    self.assertIsNotNone(parser.data)
                    self.assertEqual(parser.data["aweme_detail"]["desc"], "分享页 SSR 优先解析图文")
                    mock_share_ssr.assert_called_once()
                    # 分享页 SSR 成功时无需再调用 Web a_bogus API，避开 403
                    mock_web_api.assert_not_called()

    def test_parses_playlet_detail_series(self):
        playlet_payload = {
            "status_code": 0,
            "series_info": {
                "series_id": "7401234567890",
                "series_name": "热血神医",
                "cover_url": "https://p3.douyinpic.com/cover.jpg",
            },
            "aweme_list": [
                {
                    "itemTitle": "第1集",
                    "video": {
                        "bit_rate": [
                            {
                                "bit_rate": 1500000,
                                "is_h265": 0,
                                "play_addr": {
                                    "url_list": ["https://cdn.douyin.com/ep1.mp4"]
                                }
                            }
                        ]
                    }
                }
            ]
        }
        mock_resp = Mock(status_code=200, text=json.dumps(playlet_payload))
        mock_resp.json.return_value = playlet_payload

        with patch("requests.Session.get", return_value=mock_resp):
            parser = DouyinParser("https://www.douyin.com/share/playlet/detail/7401234567890")

        self.assertTrue(parser.is_lvdetail)
        self.assertEqual(parser.album_id, "7401234567890")
        self.assertEqual(parser.get_title_content(), "【短剧】热血神医 - 第1集")
        self.assertEqual(parser.get_cover_photo_url(), "https://p3.douyinpic.com/cover.jpg")
        self.assertEqual(parser.get_real_video_url(), "https://cdn.douyin.com/ep1.mp4")

    def test_note_routes_to_web_api_first_for_live_photo(self):
        aweme_id = "7337547837338668300"
        web_payload = {
            "status_code": 0,
            "aweme_detail": {
                "aweme_id": aweme_id,
                "desc": "实况作品测试",
                "images": [
                    {
                        "url_list": ["https://p3.douyinpic.com/img1.jpg"],
                        "video": {
                            "play_addr": {
                                "url_list": ["https://v1.douyinvod.com/live1.mp4"]
                            }
                        }
                    }
                ]
            }
        }
        with patch.object(DouyinParser, "_request_api_with_retry", return_value=web_payload) as mock_web_api:
            with patch.object(DouyinParser, "_try_share_ssr_detail") as mock_share_ssr:
                parser = DouyinParser(f"https://www.iesdouyin.com/share/slides/{aweme_id}")
                self.assertTrue(parser.is_note)
                self.assertIsNotNone(parser.data)
                mock_web_api.assert_called_once()
                mock_share_ssr.assert_not_called()
                images = parser.get_image_list()
                self.assertEqual(len(images), 1)
                self.assertEqual(images[0]["live_photo_url"], "https://v1.douyinvod.com/live1.mp4")

    def test_note_falls_back_to_share_ssr_when_web_api_fails(self):
        aweme_id = "7337547837338668300"
        ssr_payload = {
            "aweme_detail": {
                "aweme_id": aweme_id,
                "desc": "实况作品降级到SSR纯图片",
                "images": [
                    {
                        "url_list": ["https://p3.douyinpic.com/img1.jpg"]
                    }
                ]
            }
        }
        with patch.object(DouyinParser, "_request_api_with_retry", return_value=None) as mock_web_api:
            with patch.object(DouyinParser, "_try_share_ssr_detail", return_value=ssr_payload) as mock_share_ssr:
                parser = DouyinParser(f"https://www.douyin.com/note/{aweme_id}")
                self.assertTrue(parser.is_note)
                self.assertIsNotNone(parser.data)
                mock_web_api.assert_called_once()
                mock_share_ssr.assert_called_once()
                images = parser.get_image_list()
                self.assertEqual(len(images), 1)
                self.assertEqual(images[0], "https://p3.douyinpic.com/img1.jpg")

    def test_cover_photo_priority_origin_over_cover_and_dynamic(self):
        data = {
            "aweme_detail": {
                "desc": "封面优先级测试",
                "video": {
                    "origin_cover": {"url_list": ["https://p3.douyinpic.com/origin_cover.jpg"]},
                    "cover": {"url_list": ["https://p3.douyinpic.com/normal_cover.jpg"]},
                    "dynamic_cover": {"url_list": ["https://p3.douyinpic.com/dynamic_cover.webp"]},
                }
            }
        }
        parser = self.make_parser(data)
        self.assertEqual(parser.get_cover_photo_url(), "https://p3.douyinpic.com/origin_cover.jpg")

    def test_cover_photo_fallback_to_cover_when_no_origin(self):
        data = {
            "aweme_detail": {
                "desc": "无origin_cover时降级cover",
                "video": {
                    "cover": {"url_list": ["https://p3.douyinpic.com/normal_cover.jpg"]},
                    "dynamic_cover": {"url_list": ["https://p3.douyinpic.com/dynamic_cover.webp"]},
                }
            }
        }
        parser = self.make_parser(data)
        self.assertEqual(parser.get_cover_photo_url(), "https://p3.douyinpic.com/normal_cover.jpg")

    def test_cover_photo_fallback_to_dynamic_when_no_static(self):
        data = {
            "aweme_detail": {
                "desc": "无静态封面时降级动图",
                "video": {
                    "dynamic_cover": {"url_list": ["https://p3.douyinpic.com/dynamic_cover.webp"]},
                }
            }
        }
        parser = self.make_parser(data)
        self.assertEqual(parser.get_cover_photo_url(), "https://p3.douyinpic.com/dynamic_cover.webp")

    def test_image_post_info_and_live_photo_uri_extraction(self):
        """测试现代 image_post_info 结构与 Live Photo 从 video.play_addr.uri 自动构造播放端点"""
        data = {
            "aweme_detail": {
                "desc": "新版实况图集测试",
                "image_post_info": {
                    "images": [
                        {
                            "url_list": [
                                "https://p1.douyinpic.com/thumb.jpg",
                                "https://p3.douyinpic.com/origin.jpg"
                            ],
                            "video": {
                                "play_addr": {
                                    "uri": "v0200fg10000abc12345"
                                }
                            }
                        },
                        {
                            "display_image": {
                                "url_list": ["https://p3.douyinpic.com/static.jpg"]
                            }
                        }
                    ]
                }
            }
        }
        parser = self.make_parser(data)
        images = parser.get_image_list()
        self.assertEqual(len(images), 2)
        # 第一张为实况图，包含 url 和 live_photo_url
        self.assertIsInstance(images[0], dict)
        self.assertEqual(images[0]['url'], "https://p3.douyinpic.com/origin.jpg")
        self.assertIn("v0200fg10000abc12345", images[0]['live_photo_url'])
        self.assertIn("ratio=1080p", images[0]['live_photo_url'])
        # 第二张为普通图片
        self.assertEqual(images[1], "https://p3.douyinpic.com/static.jpg")

    def test_video_download_addr_original_endpoint_and_multi_metric_selection(self):
        """测试无 bit_rate 时从 download_addr 提取原画端点，以及多分辨率综合仲裁"""
        data_orig = {
            "aweme_detail": {
                "desc": "原画端点测试",
                "video": {
                    "download_addr": {
                        "uri": "v0300fg10000xyz7890"
                    }
                }
            }
        }
        parser_orig = self.make_parser(data_orig)
        url = parser_orig.get_real_video_url()
        self.assertIsNotNone(url)
        self.assertIn("v0300fg10000xyz7890", url)
        self.assertIn("ratio=default", url)

        # 测试在 bit_rate 中按 分辨率(宽*高) 与码率 综合仲裁
        data_streams = {
            "aweme_detail": {
                "desc": "画质多维度仲裁",
                "video": {
                    "bit_rate": [
                        {
                            "bit_rate": 1500000,
                            "is_h265": 0,
                            "width": 1280,
                            "height": 720,
                            "play_addr": {"url_list": ["http://cdn.douyin.com/720p.mp4"]}
                        },
                        {
                            "bit_rate": 1200000,
                            "is_h265": 0,
                            "width": 1920,
                            "height": 1080,  # 分辨率更高
                            "play_addr": {"url_list": ["http://cdn.douyin.com/1080p.mp4"]}
                        }
                    ]
                }
            }
        }
        parser_stream = self.make_parser(data_streams)
        # 应当优选 1080p 分辨率流（像素数 1920*1080 > 1280*720）
        self.assertEqual(parser_stream.get_real_video_url(), "http://cdn.douyin.com/1080p.mp4")

    def test_uifid_extracted_and_header_injected(self):
        """测试从 Cookie、纯 hash 或独立环境变量中自动提取 UIFID 并注入到 uifid 请求头"""
        parser = self.make_parser({})
        parser.cookie = "odin_tt=123; UIFID=deadbeef123456; ttwid=abc"
        self.assertEqual(parser._get_uifid(), "deadbeef123456")

        # 验证直接传入纯 hex 字符串作为 cookie 也能被识别为 uifid
        parser.cookie = "ccaf4ddfc567c2ea7983832ca74975440c9b4528762c7e101401412a981d7e99"
        self.assertEqual(parser._get_uifid(), "ccaf4ddfc567c2ea7983832ca74975440c9b4528762c7e101401412a981d7e99")

        # 验证独立环境变量 DOUYIN_UIFID
        with patch.dict(os.environ, {"DOUYIN_UIFID": "env_uifid_value_123456"}):
            self.assertEqual(parser._get_uifid(), "env_uifid_value_123456")

        # 验证 _request_api_with_retry 发送时携带了 uifid header
        parser.cookie = "UIFID=deadbeef123456"
        with patch.object(parser.session, "get") as mock_get:
            mock_resp = Mock()
            mock_resp.status_code = 200
            mock_resp.text = json.dumps({"aweme_detail": {"desc": "test"}})
            mock_resp.json.return_value = {"aweme_detail": {"desc": "test"}}
            mock_get.return_value = mock_resp

            parser._request_api_with_retry("https://www.douyin.com/aweme/v1/web/aweme/detail/?aweme_id=123",
                                           referer="https://www.douyin.com/note/123",
                                           validate=lambda d: bool(d.get("aweme_detail")))
            self.assertTrue(mock_get.called)
            call_headers = mock_get.call_args[1]["headers"]
            self.assertEqual(call_headers.get("uifid"), "deadbeef123456")

    def test_default_api_max_attempts_is_two(self):
        """测试 Web 接口重试次数默认降为 2 次，避免长时间阻塞"""
        self.assertEqual(douyin_module.API_MAX_ATTEMPTS, 2)

    def test_secsdk_cookies_sanitized_in_cookie_header(self):
        """测试自动过滤导致 Argus 报 Signature Not Found 403 的 SecSDK 指纹和票据 Cookie"""
        parser = self.make_parser({})
        parser.cookie = (
            "sessionid=my_sess; sessionid_ss=my_sess; UIFID=my_uifid; "
            "bd_ticket_guard_client_data=toxic; _bd_ticket_crypt_cookie=toxic; "
            "__security_mc_1_s_sdk_cert_key=toxic; fpk1=toxic; fpk2=toxic; "
            "x_tt_token=toxic; sdk_source_info=toxic; odin_tt=safe_odin"
        )
        cookie_header = parser._get_cookie_header(ttwid="test_ttwid")
        self.assertIn("sessionid=my_sess", cookie_header)
        self.assertIn("UIFID=my_uifid", cookie_header)
        self.assertIn("odin_tt=safe_odin", cookie_header)
        self.assertIn("ttwid=test_ttwid", cookie_header)
        # 验证危险 SecSDK 字段均被彻底过滤
        self.assertNotIn("bd_ticket_guard", cookie_header)
        self.assertNotIn("_bd_ticket_crypt_cookie", cookie_header)
        self.assertNotIn("__security", cookie_header)
        self.assertNotIn("fpk", cookie_header)
        self.assertNotIn("x_tt_token", cookie_header)
        self.assertNotIn("sdk_source_info", cookie_header)

    def test_sign_secsdk_calculation(self):
        """测试 x-secsdk-web-signature 签名纯算与参数规范化"""
        uifid = "deadbeef123456"
        ts = 1789880000
        url = "https://www.douyin.com/aweme/v1/web/aweme/detail/?aweme_id=123"
        signed_url = DouyinParser._sign_secsdk(url, uifid, ts=ts)
        self.assertIn("uifid=deadbeef123456", signed_url)
        self.assertIn(f"timestamp={ts}", signed_url)
        self.assertIn("x-secsdk-web-signature=", signed_url)
        # 验证空 uifid 时原样返回
        self.assertEqual(DouyinParser._sign_secsdk(url, ""), url)

    def test_extract_best_url_sanitizes_playwm_to_play(self):
        """测试将 playwm 水印播放地址自动转换为无水印 play 播放地址并升级 ratio 为 1080p"""
        play_addr = {
            "uri": "v0d00fg10000dao171fog65tkue6mba0",
            "url_list": [
                "https://aweme.snssdk.com/aweme/v1/playwm/?line=0&logo_name=aweme_diversion_search&ratio=720p&video_id=v0d00fg10000dao171fog65tkue6mba0"
            ]
        }
        url = DouyinParser._extract_best_url_from_play_addr(play_addr)
        self.assertNotIn("/playwm/", url)
        self.assertIn("/play/", url)
        self.assertIn("ratio=1080p", url)
        self.assertNotIn("ratio=720p", url)


if __name__ == "__main__":
    unittest.main()


