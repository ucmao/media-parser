import unittest
from unittest.mock import Mock, patch

from src.parsers.zuiyou_parser import ZuiyouParser


class ZuiyouParserTest(unittest.TestCase):
    @patch("src.parsers.zuiyou_parser.random.choice", return_value="test-agent")
    def test_extracts_title_and_author_from_post_detail(self, _user_agent):
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {
            "data": {
                "post": {
                    "content": "测试最右作品",
                    "member": {
                        "id": 42,
                        "name": "测试作者",
                        "avatar_urls": {"origin": {"urls": ["https://image.example.com/avatar.jpg"]}},
                    },
                }
            }
        }

        with patch("requests.Session.post", return_value=response) as post:
            parser = ZuiyouParser("https://share.xiaochuankeji.cn/hybrid/share/post?pid=123")

        post.assert_called_once_with(
            "https://share.xiaochuankeji.cn/planck/share/post/detail_h5",
            headers=parser.headers,
            json={"h_av": "5.2.13.011", "pid": 123},
            timeout=10,
        )
        self.assertEqual(parser.get_title_content(), "测试最右作品")
        self.assertEqual(
            parser.get_author_info(),
            {"nickname": "测试作者", "author_id": "42", "avatar": "https://image.example.com/avatar.jpg"},
        )

    def test_skips_request_without_post_id(self):
        with patch("requests.Session.post") as post:
            parser = ZuiyouParser("https://share.xiaochuankeji.cn/hybrid/share/post")

        post.assert_not_called()
        self.assertEqual(parser.data, {})


if __name__ == "__main__":
    unittest.main()
