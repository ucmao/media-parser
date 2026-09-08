import json
import unittest
import urllib.parse
from unittest.mock import patch

from src.parsers.douyin_parser import DouyinParser
from src.parsers.toutiao_parser import ToutiaoParser


class ToutiaoParserTest(unittest.TestCase):
    def test_reuses_douyin_parser(self):
        self.assertTrue(issubclass(ToutiaoParser, DouyinParser))

    @patch("src.parsers.douyin_parser.DouyinParser.fetch_html_data")
    def test_toutiao_mobile_ssr_parsing(self, mock_douyin_fetch):
        mock_douyin_fetch.return_value = None

        sample_article_info = {
            "title": "测试今日头条视频",
            "content": "今日头条视频正文",
            "posterUrl": "https://p3.toutiaoimg.com/test_cover.jpg",
            "mediaUser": {
                "screenName": "测试创作者",
                "avatarUrl": "https://sf1.toutiaostatic.com/avatar.jpg"
            },
            "playAuthTokenV2": "eyJHZXRQbGF5SW5mb1Rva2VuIjoiQWN0aW9uPUdldFBsYXlJbmZvJnZpZGVvX2lkPXYwMjAifQ=="
        }

        vod_response_data = {
            "ResponseMetadata": {"Action": "GetPlayInfo"},
            "Result": {
                "Data": {
                    "CoverUrl": "https://p3.toutiaoimg.com/test_cover.jpg",
                    "PlayInfoList": [
                        {
                            "Definition": "720p",
                            "Bitrate": 1000000,
                            "MainPlayUrl": "https://v26.toutiaovod.com/video_720p.mp4"
                        },
                        {
                            "Definition": "360p",
                            "Bitrate": 500000,
                            "MainPlayUrl": "https://v26.toutiaovod.com/video_360p.mp4"
                        }
                    ]
                }
            }
        }

        with patch.object(ToutiaoParser, "_fetch_toutiao_mobile_ssr") as mock_ssr:
            mock_ssr.return_value = {
                "toutiao_article_info": sample_article_info,
                "vod_data": vod_response_data["Result"]["Data"]
            }
            parser = ToutiaoParser("https://www.toutiao.com/video/7680960670263493172")

            self.assertEqual(parser.get_title_content(), "测试今日头条视频")
            self.assertEqual(parser.get_description(), "今日头条视频正文")
            self.assertEqual(parser.get_cover_photo_url(), "https://p3.toutiaoimg.com/test_cover.jpg")
            self.assertEqual(parser.get_author_info(), {
                "author": "测试创作者",
                "avatar": "https://sf1.toutiaostatic.com/avatar.jpg"
            })
            self.assertEqual(parser.get_real_video_url(), "https://v26.toutiaovod.com/video_720p.mp4")
            self.assertEqual(parser.get_video_list(), ["https://v26.toutiaovod.com/video_720p.mp4"])

    @patch("src.parsers.douyin_parser.DouyinParser.fetch_html_data")
    def test_description_strips_html_and_preserves_paragraphs(self, mock_douyin_fetch):
        mock_douyin_fetch.return_value = None

        with patch.object(ToutiaoParser, "_fetch_toutiao_mobile_ssr") as mock_ssr:
            mock_ssr.return_value = {
                "toutiao_article_info": {
                    "content": (
                        "<p>第一段&nbsp;<strong>重点</strong></p>"
                        "<p>第二段<br>换行 &amp; 更多</p>"
                        "<script>alert('不应返回')</script>"
                    )
                },
                "vod_data": None,
            }
            parser = ToutiaoParser("https://www.toutiao.com/video/7680960670263493172")

            self.assertEqual(parser.get_description(), "第一段 重点\n第二段\n换行 & 更多")

    def test_description_returns_none_for_empty_or_non_string_content(self):
        self.assertIsNone(ToutiaoParser._clean_description("<p> &nbsp; </p>"))
        self.assertIsNone(ToutiaoParser._clean_description(None))


if __name__ == "__main__":
    unittest.main()
