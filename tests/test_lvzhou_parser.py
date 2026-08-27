import unittest
from unittest.mock import Mock, patch

from src.parsers.lvzhou_parser import LvzhouParser


class LvzhouParserTest(unittest.TestCase):
    @patch("src.parsers.lvzhou_parser.random.choice", return_value="test-agent")
    def test_extracts_title_author_and_images_from_share_page(self, _user_agent):
        response = Mock()
        response.raise_for_status.return_value = None
        response.text = '''
            <div class="media"><img src="https://image.example.com/cover.jpg"></div>
            <div class="user"><a class="avatar"><img src="https://image.example.com/avatar.jpg"></a>
            <div class="nickname">测试作者</div></div>
            <div class="main-content"><div class="status-text">测试绿洲作品</div></div>
        '''
        with patch("requests.Session.get", return_value=response):
            parser = LvzhouParser("https://oasis.weibo.cn/v1/h5/share?sid=123")

        self.assertEqual(parser.get_title_content(), "测试绿洲作品")
        self.assertEqual(parser.get_cover_photo_url(), "https://image.example.com/cover.jpg")
        self.assertEqual(parser.get_image_list(), ["https://image.example.com/cover.jpg"])
        self.assertEqual(
            parser.get_author_info(),
            {"nickname": "测试作者", "author_id": "", "avatar": "https://image.example.com/avatar.jpg"},
        )

    def test_returns_empty_values_when_request_fails(self):
        with patch("requests.Session.get", side_effect=Exception("network error")):
            parser = LvzhouParser("https://oasis.weibo.cn/v1/h5/share?sid=123")

        self.assertEqual(parser.get_title_content(), None)
        self.assertEqual(parser.get_author_info(), {})


if __name__ == "__main__":
    unittest.main()
