import unittest
from unittest.mock import Mock, patch

from src.parsers.quark_ai_parser import QuarkAIParser


class QuarkAIParserTest(unittest.TestCase):
    def test_parses_external_share_video_and_cover(self):
        page_html = """
        <script>
        window.__INITIAL_PROPS__ = {
          "initialData": {
            "data": {
              "title": "夸克 AI 视频",
              "playInfo": {"url": "https://quark-aistudio-cdn.quark.cn/video.mp4?auth_key=abc"},
              "image": {
                "url": "https://quark-aistudio-cdn.quark.cn/cover.jpg?auth_key=abc",
                "width": 1280,
                "height": 718
              }
            }
          }
        };
        </script>
        """
        response = Mock()
        response.raise_for_status.return_value = None
        response.text = page_html

        with patch("requests.Session.get", return_value=response):
            parser = QuarkAIParser(
                "https://pages.quark.cn/r/ai-studio-mobile/external-share?shareId=test"
            )

        self.assertEqual(parser.get_title_content(), "夸克 AI 视频")
        self.assertEqual(parser.get_real_video_url(), "https://quark-aistudio-cdn.quark.cn/video.mp4?auth_key=abc")
        self.assertEqual(parser.get_video_list(), ["https://quark-aistudio-cdn.quark.cn/video.mp4?auth_key=abc"])
        self.assertEqual(parser.get_cover_photo_url(), "https://quark-aistudio-cdn.quark.cn/cover.jpg?auth_key=abc")
        self.assertEqual(parser.get_image_list(), ["https://quark-aistudio-cdn.quark.cn/cover.jpg?auth_key=abc"])

    def test_parses_act_quark_chat_share(self):
        page_html = """
        <script>
        window.__INITIAL_PROPS__ = {
          "version": "1.0.0",
          "initialData": "%7B%22title%22%3A%22%E5%88%86%E6%9E%90%E5%9B%BE%E7%89%87%E5%86%85%E5%AE%B9%22%2C%22session%22%3A%7B%22title%22%3A%22%E7%94%9F%E6%88%90%E8%A7%86%E9%A2%91%22%2C%22record_list%22%3A%5B%7B%22query%22%3A%22%E6%8C%89%E9%A1%BA%E5%BA%8F%E7%94%9F%E6%88%90%E8%A7%86%E9%A2%91%22%2C%22response_messages%22%3A%5B%7B%22meta_data%22%3A%7B%22resource_infos%22%3A%5B%7B%22url%22%3A%22https%3A%2F%2Fworkspace-zb-cdn.quark.cn%2Fvideo.mp4%3Fauth_key%3D123%22%7D%2C%7B%22url%22%3A%22https%3A%2F%2Fworkspace-zb-cdn.quark.cn%2Fimage.jpg%3Fauth_key%3D123%22%7D%5D%7D%7D%5D%7D%5D%7D%7D"
        };
        </script>
        """
        response = Mock()
        response.raise_for_status.return_value = None
        response.text = page_html

        with patch("requests.Session.get", return_value=response):
            parser = QuarkAIParser(
                "https://act.quark.cn/apps/sharepages/routes/share?biz_id=ai_chat_v2&env=prod&share_id=test"
            )

        self.assertEqual(parser.get_title_content(), "分析图片内容")
        self.assertEqual(parser.get_real_video_url(), "https://workspace-zb-cdn.quark.cn/video.mp4?auth_key=123")
        self.assertEqual(parser.get_video_list(), ["https://workspace-zb-cdn.quark.cn/video.mp4?auth_key=123"])
        self.assertEqual(parser.get_cover_photo_url(), "https://workspace-zb-cdn.quark.cn/image.jpg?auth_key=123")
        self.assertEqual(parser.get_image_list(), ["https://workspace-zb-cdn.quark.cn/image.jpg?auth_key=123"])


if __name__ == "__main__":
    unittest.main()

