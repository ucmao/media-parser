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


if __name__ == "__main__":
    unittest.main()
