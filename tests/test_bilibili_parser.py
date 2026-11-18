import unittest
from unittest.mock import Mock, patch

from src.parsers.bilibili_parser import BilibiliParser


class BilibiliParserTest(unittest.TestCase):
    def make_parser(self, pages=None):
        video_info = {
            "title": "测试视频",
            "pic": "https://example.com/cover.jpg",
            "owner": {"name": "测试作者", "mid": 123, "face": "//example.com/avatar.jpg"},
            "pages": pages or [{"cid": 1001}],
        }
        with patch.object(BilibiliParser, "_fetch_video_info", return_value=video_info):
            return BilibiliParser("https://www.bilibili.com/video/BV1asTR6FEWu")

    @staticmethod
    def response(url):
        response = Mock()
        response.json.return_value = {"code": 0, "data": {"durl": [{"url": url}]}}
        return response

    def test_returns_cdn_url_without_downloading_or_merging(self):
        parser = self.make_parser()
        parser.session.get = Mock(return_value=self.response("https://cdn.example/video.mp4"))

        self.assertEqual(parser.get_real_video_url(), "https://cdn.example/video.mp4")
        self.assertIsNone(parser.get_audio_url())
        parser.session.get.assert_called_once_with(
            parser.API_PLAYURL,
            params={
                "otype": "json",
                "fnver": 0,
                "fnval": 3,
                "player": 3,
                "qn": 112,
                "bvid": "BV1asTR6FEWu",
                "cid": 1001,
                "platform": "html5",
                "high_quality": 1,
            },
            headers=parser.headers,
            timeout=10,
        )

    def test_returns_every_page_for_multi_part_video_and_reuses_first_request(self):
        parser = self.make_parser(pages=[{"cid": 1001}, {"cid": 1002}])
        parser.session.get = Mock(side_effect=[
            self.response("https://cdn.example/first.mp4"),
            self.response("https://cdn.example/second.mp4"),
        ])

        self.assertEqual(parser.get_real_video_url(), "https://cdn.example/first.mp4")
        self.assertEqual(
            parser.get_video_list(),
            ["https://cdn.example/first.mp4", "https://cdn.example/second.mp4"],
        )
        self.assertEqual(parser.session.get.call_count, 2)

    def test_exposes_metadata_and_normalizes_protocol_relative_avatar(self):
        parser = self.make_parser()

        self.assertEqual(parser.get_title_content(), "测试视频")
        self.assertEqual(parser.get_cover_photo_url(), "https://example.com/cover.jpg")
        self.assertEqual(
            parser.get_author_info(),
            {"nickname": "测试作者", "author_id": "123", "avatar": "https://example.com/avatar.jpg"},
        )
        self.assertIsNone(parser.get_description())

    def test_parses_dynamic_video_url(self):
        dynamic_item = {
            "modules": {
                "module_dynamic": {
                    "major": {
                        "type": "MAJOR_TYPE_ARCHIVE",
                        "archive": {"bvid": "BV1FDbP6dEfz", "title": "动态内嵌视频"},
                    }
                }
            }
        }
        video_info = {
            "title": "动态内嵌视频",
            "pic": "https://example.com/cover.jpg",
            "owner": {"name": "动态作者", "mid": 456, "face": "https://example.com/avatar.jpg"},
            "pages": [{"cid": 2002}],
        }
        with patch.object(BilibiliParser, "_fetch_dynamic_info", return_value=dynamic_item), \
             patch.object(BilibiliParser, "_fetch_video_info", return_value=video_info):
            parser = BilibiliParser("https://t.bilibili.com/1245189054385881096?share_source=pc_native")
            self.assertEqual(parser.bvid, "BV1FDbP6dEfz")
            self.assertEqual(parser.get_title_content(), "动态内嵌视频")
            self.assertEqual(parser.get_author_info()["nickname"], "动态作者")

    def test_parses_dynamic_opus_photo_url(self):
        dynamic_item = {
            "modules": {
                "module_author": {
                    "name": "图文UP主",
                    "mid": 789,
                    "face": "//example.com/author_avatar.jpg",
                },
                "module_dynamic": {
                    "major": {
                        "type": "MAJOR_TYPE_OPUS",
                        "opus": {
                            "title": "图文动态标题",
                            "summary": {"text": "图文动态正文"},
                            "pics": [
                                {"url": "https://example.com/pic1.jpg"},
                                {"url": "https://example.com/pic2.jpg"},
                            ],
                        },
                    }
                },
            }
        }
        with patch.object(BilibiliParser, "_fetch_dynamic_info", return_value=dynamic_item):
            parser = BilibiliParser("https://t.bilibili.com/opus/1245189054385881096")
            self.assertIsNone(parser.bvid)
            self.assertEqual(parser.get_title_content(), "图文动态标题")
            self.assertEqual(parser.get_description(), "图文动态正文")
            self.assertEqual(parser.get_cover_photo_url(), "https://example.com/pic1.jpg")
            self.assertEqual(
                parser.get_author_info(),
                {"nickname": "图文UP主", "author_id": "789", "avatar": "https://example.com/author_avatar.jpg"},
            )
            self.assertEqual(
                parser.get_image_list(),
                ["https://example.com/pic1.jpg", "https://example.com/pic2.jpg"],
            )
            self.assertEqual(parser.get_video_list(), [])

    def test_parses_single_dynamic_photo_as_image(self):
        dynamic_item = {
            "modules": {
                "module_dynamic": {
                    "major": {
                        "type": "MAJOR_TYPE_DRAW",
                        "draw": {
                            "items": [
                                {"src": "https://example.com/single.jpg"},
                            ],
                        },
                    }
                }
            }
        }
        with patch.object(BilibiliParser, "_fetch_dynamic_info", return_value=dynamic_item):
            parser = BilibiliParser("https://t.bilibili.com/1245189054385881096")

            self.assertEqual(parser.get_image_list(), ["https://example.com/single.jpg"])
            self.assertEqual(parser.get_video_list(), [])
    def test_parses_bangumi_episode_url(self):
        season_data = {
            "title": "凡人修仙传",
            "cover": "https://example.com/season_cover.jpg",
            "up_info": {"uname": "哔哩哔哩国创", "mid": 98627270, "avatar": "//example.com/up.jpg"},
            "episodes": [
                {
                    "id": 1231565,
                    "bvid": "BV1vT411d7QE",
                    "cid": 1022370693,
                    "title": "1",
                    "long_title": "凡人风起天南1重制版",
                    "cover": "https://example.com/ep_cover.jpg",
                }
            ],
        }
        with patch.object(BilibiliParser, "_fetch_season_info", return_value=season_data):
            parser = BilibiliParser("https://www.bilibili.com/bangumi/play/ep1231565")
            parser.session.get = Mock(return_value=self.response("https://cdn.example/bangumi.mp4"))

            self.assertEqual(parser.bvid, "BV1vT411d7QE")
            self.assertEqual(parser.get_title_content(), "凡人修仙传 1 凡人风起天南1重制版")
            self.assertEqual(parser.get_cover_photo_url(), "https://example.com/ep_cover.jpg")
            self.assertEqual(parser.get_author_info()["nickname"], "哔哩哔哩国创")
            self.assertEqual(parser.get_author_info()["avatar"], "https://example.com/up.jpg")
            self.assertEqual(parser.get_real_video_url(), "https://cdn.example/bangumi.mp4")

    def test_fetch_video_info_uses_view_headers(self):
        mock_response = Mock()
        mock_response.json.return_value = {"code": 0, "data": {"title": "直接请求测试"}}
        mock_response.raise_for_status = Mock()

        with patch("requests.Session.get", return_value=mock_response) as mock_get:
            parser = BilibiliParser("https://www.bilibili.com/video/BV1asTR6FEWu")
            self.assertEqual(parser.view_headers["User-Agent"], "okhttp/4.9.3")
            mock_get.assert_called_with(
                parser.API_VIEW,
                params={"bvid": "BV1asTR6FEWu"},
                headers=parser.view_headers,
                timeout=10,
            )

    def test_parses_aid_url(self):
        mock_response = Mock()
        mock_response.json.return_value = {
            "code": 0,
            "data": {"title": "AV视频测试", "bvid": "BV1xx411c7mD", "pages": [{"cid": 1001}]}
        }
        mock_response.raise_for_status = Mock()

        with patch("requests.Session.get", return_value=mock_response) as mock_get:
            parser = BilibiliParser("https://www.bilibili.com/video/av117586188636547")
            self.assertEqual(parser.aid, "117586188636547")
            self.assertEqual(parser.bvid, "BV1xx411c7mD")
            mock_get.assert_called_with(
                parser.API_VIEW,
                params={"aid": "117586188636547"},
                headers=parser.view_headers,
                timeout=10,
            )

    def test_video_deleted_or_invisible_sets_terminal_error(self):
        mock_response = Mock()
        mock_response.json.return_value = {"code": 62002, "message": "稿件不可见"}
        mock_response.raise_for_status = Mock()

        with patch("requests.Session.get", return_value=mock_response):
            parser = BilibiliParser("https://www.bilibili.com/video/BV1asTR6FEWu")
            self.assertIsNotNone(parser.terminal_error)
            self.assertEqual(parser.terminal_error["error_code"], "MEDIA_DELETED_OR_PRIVATE")

    def test_dynamic_invisible_sets_terminal_error(self):
        mock_response = Mock()
        mock_response.json.return_value = {"code": 4101152, "message": "动态不可见"}
        mock_response.raise_for_status = Mock()

        with patch("requests.Session.get", return_value=mock_response):
            parser = BilibiliParser("https://t.bilibili.com/1082636825840844823")
            self.assertIsNotNone(parser.terminal_error)
            self.assertEqual(parser.terminal_error["error_code"], "MEDIA_DELETED_OR_PRIVATE")


if __name__ == "__main__":
    unittest.main()

