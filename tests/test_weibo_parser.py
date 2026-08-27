import unittest

from src.parsers.weibo_parser import WeiboParser


class WeiboParserTest(unittest.TestCase):
    def test_extracts_numeric_id_from_video_fid(self):
        parser = WeiboParser.__new__(WeiboParser)
        parser.real_url = "https://video.weibo.com/show?fid=1034%3A5336275486703690"
        self.assertEqual(parser._extract_id(), "5336275486703690")

    def test_extracts_numeric_id_from_redirected_video_page(self):
        parser = WeiboParser.__new__(WeiboParser)
        parser.real_url = "https://weibo.com/tv/show/1034:5336275486703690"
        self.assertEqual(parser._extract_id(), "5336275486703690")

    def test_extracts_video_oid_from_redirected_video_page(self):
        parser = WeiboParser.__new__(WeiboParser)
        parser.real_url = "https://weibo.com/tv/show/1034:5336275486703690"
        self.assertEqual(parser._extract_video_oid(), "1034:5336275486703690")

    def test_video_component_fields(self):
        parser = WeiboParser.__new__(WeiboParser)
        parser.post_data = {
            "title": "公开微博视频",
            "author": "测试作者",
            "author_id": 1,
            "cover_image": "//example.com/cover.jpg",
            "urls": {"高清 1080P": "//example.com/video.mp4"},
        }
        self.assertEqual(parser.get_real_video_url(), "https://example.com/video.mp4")
        self.assertEqual(parser.get_cover_photo_url(), "https://example.com/cover.jpg")
        self.assertEqual(parser.get_title_content(), "公开微博视频")
        self.assertEqual(parser.get_author_info()["nickname"], "测试作者")


if __name__ == "__main__":
    unittest.main()
