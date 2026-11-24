import json
import unittest
from unittest.mock import patch, MagicMock

from configs.general_constants import USER_AGENT_M
from src.parsers.kuaishou_parser import KuaishouParser


class KuaishouParserHeadersTest(unittest.TestCase):
    def test_builds_headers_with_configured_mobile_user_agent(self):
        parser = KuaishouParser.__new__(KuaishouParser)
        parser.custom_cookie = ""

        with patch("src.parsers.kuaishou_parser.random.choice", return_value="mobile-user-agent") as choice:
            headers = parser._build_mobile_headers()

        choice.assert_called_once_with(USER_AGENT_M)
        self.assertEqual(headers["User-Agent"], "mobile-user-agent")
        self.assertEqual(headers["referer"], "https://v.m.chenzhongtech.com/")

    def test_graphql_video_parsing(self):
        parser = KuaishouParser.__new__(KuaishouParser)
        parser.page_type = "GRAPHQL"
        parser.video_id = "test_video_123"
        parser.structured_data = {
            "status": 1,
            "author": {
                "id": "author_001",
                "name": "创作者小明",
                "headerUrl": "https://tx-avatar.kuaishou.com/avatar.jpg"
            },
            "photo": {
                "id": "test_video_123",
                "caption": "快手精彩无水印视频",
                "coverUrl": "https://tx-cover.kuaishou.com/cover.jpg",
                "photoUrl": "https://tx-video.kuaishou.com/video_clean.mp4",
                "mainMvUrls": [
                    {"url": "https://tx-video.kuaishou.com/video_clean.mp4"}
                ]
            }
        }

        self.assertEqual(parser.get_real_video_url(), "https://tx-video.kuaishou.com/video_clean.mp4")
        self.assertEqual(parser.get_description(), "快手精彩无水印视频")
        self.assertEqual(parser.get_cover_photo_url(), "https://tx-cover.kuaishou.com/cover.jpg")
        self.assertEqual(parser.get_author_info(), {
            "nickname": "创作者小明",
            "unique_id": "author_001",
            "avatar": "https://tx-avatar.kuaishou.com/avatar.jpg"
        })
        self.assertEqual(parser.get_image_list(), [])

    def test_graphql_atlas_parsing(self):
        parser = KuaishouParser.__new__(KuaishouParser)
        parser.page_type = "GRAPHQL"
        parser.video_id = "test_atlas_456"
        parser.structured_data = {
            "status": 1,
            "author": {
                "id": "author_002",
                "name": "摄影师小红",
                "headerUrl": "https://tx-avatar.kuaishou.com/avatar2.jpg"
            },
            "photo": {
                "id": "test_atlas_456",
                "caption": "快手图集分享",
                "coverUrl": "https://tx-cover.kuaishou.com/cover2.jpg",
                "atlas": {
                    "cdn": "https://tx-atlas.kuaishou.com",
                    "list": [
                        "image1.webp",
                        "image2.webp"
                    ]
                }
            }
        }

        self.assertIsNone(parser.get_real_video_url())
        self.assertEqual(parser.get_description(), "快手图集分享")
        self.assertEqual(parser.get_cover_photo_url(), "https://tx-cover.kuaishou.com/cover2.jpg")
        self.assertEqual(parser.get_author_info(), {
            "nickname": "摄影师小红",
            "unique_id": "author_002",
            "avatar": "https://tx-avatar.kuaishou.com/avatar2.jpg"
        })
        self.assertEqual(parser.get_image_list(), [
            "https://tx-atlas.kuaishou.com/image1.webp",
            "https://tx-atlas.kuaishou.com/image2.webp"
        ])

    def test_blocked_payload_detection(self):
        self.assertTrue(KuaishouParser._is_blocked_payload('{"result": 2}'))
        self.assertTrue(KuaishouParser._is_blocked_payload('{"data": {"result": 400002, "bizName": "ANTICRAWL_DEFAULT"}}'))
        self.assertFalse(KuaishouParser._is_blocked_payload('<html><body>Hello</body></html>'))

    @patch("src.parsers.kuaishou_parser.get_platform_cookie", return_value="custom_kuaishou_cookie")
    @patch("requests.Session.get")
    @patch("requests.Session.post")
    def test_anticrawl_triggers_cookie_required(self, mock_post, mock_get, mock_cookie):
        mock_resp_get = MagicMock()
        mock_resp_get.text = json.dumps({"result": 2})
        mock_resp_get.status_code = 200
        mock_get.return_value = mock_resp_get

        mock_resp_post = MagicMock()
        mock_resp_post.text = json.dumps({"data": {"result": 400002, "bizName": "ANTICRAWL_DEFAULT"}})
        mock_resp_post.status_code = 200
        mock_post.return_value = mock_resp_post

        with patch("utils.web_fetcher.UrlParser.get_video_id", return_value="3x123456"):
            parser = KuaishouParser("https://v.kuaishou.com/3x123456")
            self.assertTrue(parser.cookie_required)
            self.assertIsNotNone(parser.terminal_error)
            self.assertEqual(parser.terminal_error["error_code"], "KUAISHOU_COOKIE_REQUIRED")


class KuaishouSessionCompatibilityTest(unittest.TestCase):
    """保留既有路由次序、请求参数以及成功优先于前序拦截的行为。"""

    URL = 'https://www.kuaishou.com/short-video/123'

    @staticmethod
    def html_response(success=False):
        response = MagicMock()
        response.status_code = 200
        response.text = ('window.INIT_STATE=' + json.dumps({
            'photo': {'caption': '测试文案', 'mainMvUrls': [{'url': 'https://cdn.example/video.mp4'}]}
        })) if success else '<html>empty</html>'
        return response

    def test_mobile_desktop_and_alternative_route_order(self):
        for success_index in (0, 1, 2, 3):
            with self.subTest(success_index=success_index):
                responses = [self.html_response() for _ in range(success_index)] + [self.html_response(True)]
                with patch('requests.Session.get', side_effect=responses) as get, \
                        patch('requests.Session.post') as post, \
                        patch('src.parsers.kuaishou_parser.get_platform_cookie', return_value='configured=yes'):
                    parser = KuaishouParser(self.URL)
                self.assertEqual(parser.get_real_video_url(), 'https://cdn.example/video.mp4')
                self.assertEqual(parser.get_description(), '测试文案')
                self.assertIsNone(parser.terminal_error)
                post.assert_not_called()
                expected_urls = [self.URL, self.URL,
                                 'https://v.m.chenzhongtech.com/fw/photo/123',
                                 'https://v.m.chenzhongtech.com/fw/photo/123']
                for index, call in enumerate(get.call_args_list):
                    self.assertEqual(call.args[0], expected_urls[index])
                    self.assertEqual(call.kwargs['timeout'], 5)
                    headers = call.kwargs['headers']
                    self.assertEqual(headers['cookie'], 'configured=yes')
                    if index % 2 == 0:
                        self.assertEqual(headers['referer'], 'https://v.m.chenzhongtech.com/')
                        self.assertIn('accept', headers)
                        self.assertNotIn('content-type', headers)
                    else:
                        self.assertEqual(headers['referer'], 'https://www.kuaishou.com/')
                        self.assertIn('content-type', headers)
                        self.assertNotIn('accept', headers)

    def test_early_block_does_not_override_later_success(self):
        blocked = self.html_response()
        blocked.text = '{"result":2}'
        with patch('requests.Session.get', side_effect=[blocked, self.html_response(True)]):
            parser = KuaishouParser(self.URL)
        self.assertTrue(parser.cookie_required)
        self.assertIsNone(parser.terminal_error)
        self.assertEqual(parser.get_real_video_url(), 'https://cdn.example/video.mp4')

    def test_graphql_fallback_preserves_json_and_headers(self):
        for media in ('video', 'atlas'):
            with self.subTest(media=media):
                photo = {'caption': '文案', 'coverUrl': 'https://cdn.example/cover.jpg'}
                if media == 'video':
                    photo['photoUrl'] = 'https://cdn.example/video.mp4'
                else:
                    photo['atlas'] = {'cdn': 'https://cdn.example', 'list': ['1.jpg']}
                response = self.html_response()
                response.text = '{}'
                response.json.return_value = {'data': {'visionVideoDetail': {'photo': photo, 'author': {'name': '作者'}}}}
                with patch('requests.Session.get', return_value=self.html_response()) as get, \
                        patch('requests.Session.post', return_value=response) as post, \
                        patch('src.parsers.kuaishou_parser.get_platform_cookie', return_value='configured=yes'):
                    parser = KuaishouParser(self.URL)
                self.assertEqual(get.call_count, 4)
                self.assertEqual(parser.page_type, 'GRAPHQL')
                self.assertEqual(parser.get_description(), '文案')
                post.assert_called_once()
                args = post.call_args.kwargs
                self.assertEqual(args['timeout'], 5)
                self.assertEqual(args['headers']['Cookie'] if 'Cookie' in args['headers'] else args['headers']['cookie'], 'configured=yes')
                self.assertEqual(args['headers']['Referer'], self.URL)
                self.assertEqual(args['json']['operationName'], 'visionVideoDetail')
                self.assertEqual(args['json']['variables'], {'photoId': '123', 'page': 'detail'})
                self.assertIn('atlas', args['json']['query'])
                if media == 'video':
                    self.assertEqual(parser.get_real_video_url(), 'https://cdn.example/video.mp4')
                else:
                    self.assertEqual(parser.get_image_list(), ['https://cdn.example/1.jpg'])

    def test_direct_network_error_keeps_original_fallback(self):
        import requests
        with patch('requests.Session.get', side_effect=[requests.Timeout(), self.html_response(True)]) as get:
            parser = KuaishouParser(self.URL)
        self.assertEqual(get.call_count, 2)
        self.assertEqual(parser.get_real_video_url(), 'https://cdn.example/video.mp4')

    def test_get_audio_url_sound_track_and_music(self):
        # 1. 测试 ATLAS / VIDEO 模式下的创作者原声 (soundTrack)
        parser = KuaishouParser.__new__(KuaishouParser)
        parser.page_type = "ATLAS"
        payload = {
            "photo": {
                "soundTrack": {
                    "audioUrls": [{"cdn": "hw.a.yximgs.com", "url": "https://hw.a.yximgs.com/sound.m4a"}]
                }
            }
        }
        with patch.object(parser, "_get_atlas_payload", return_value=payload):
            self.assertEqual(parser.get_audio_url(), "https://hw.a.yximgs.com/sound.m4a")

        # 2. 测试 GRAPHQL 模式下的创作者原声 (soundTrack)
        parser.page_type = "GRAPHQL"
        parser.structured_data = {
            "photo": {
                "soundTrack": {
                    "url": "https://hw.a.yximgs.com/graphql_sound.m4a"
                }
            }
        }
        self.assertEqual(parser.get_audio_url(), "https://hw.a.yximgs.com/graphql_sound.m4a")

        # 3. 测试常规背景音乐 (music)
        parser.page_type = "VIDEO"
        payload_music = {
            "photo": {
                "music": {
                    "audioUrls": ["https://hw.a.yximgs.com/bgm.mp3"]
                }
            }
        }
        with patch.object(parser, "_get_atlas_payload", return_value=payload_music):
            self.assertEqual(parser.get_audio_url(), "https://hw.a.yximgs.com/bgm.mp3")


if __name__ == "__main__":
    unittest.main()
