import unittest
from unittest.mock import Mock, patch

from src.parsers.pipixia_parser import PipixiaParser


class PipixiaParserTest(unittest.TestCase):
    @patch("src.parsers.pipixia_parser.random.choice", return_value="test-agent")
    def test_falls_back_to_share_page_title_and_extracts_author(self, _user_agent):
        redirect = Mock(headers={"location": "https://h5.pipix.com/ppx/item/123"})
        api_response = Mock()
        api_response.raise_for_status.return_value = None
        api_response.json.return_value = {
            "data": {"cell_comments": [{"comment_info": {"item": {
                "content": "",
                "author": {
                    "id": 42,
                    "name": "测试作者",
                    "avatar": {"download_list": [{"url": "https://image.example.com/avatar.jpg"}]},
                },
            }}}]}
        }
        page = Mock(text='<meta property="og:title" content="测试皮皮虾作品 - 皮皮虾">')
        page.raise_for_status.return_value = None

        with patch("requests.Session.get", side_effect=[redirect, api_response, page]):
            parser = PipixiaParser("https://h5.pipix.com/s/share-id/")

        self.assertEqual(parser.get_title_content(), "测试皮皮虾作品")
        self.assertEqual(
            parser.get_author_info(),
            {"nickname": "测试作者", "author_id": "42", "avatar": "https://image.example.com/avatar.jpg"},
        )

    def test_returns_empty_data_when_redirect_has_no_item_id(self):
        response = Mock(headers={"location": ""})
        with patch("requests.Session.get", return_value=response) as get:
            parser = PipixiaParser("https://h5.pipix.com/s/share-id/")

        get.assert_called_once()
        self.assertEqual(parser.data, {})


if __name__ == "__main__":
    unittest.main()
