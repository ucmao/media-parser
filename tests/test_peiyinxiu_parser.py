import unittest
from unittest.mock import Mock, patch

from src.parsers.peiyinxiu_parser import PeiyinxiuParser


class PeiyinxiuParserTest(unittest.TestCase):
    URL = "https://www.peiyinxiu.com/m/535482401"

    @patch("src.parsers.base_parser.requests.Session.get")
    def test_parses_public_work_page(self, get):
        response = Mock()
        response.raise_for_status.return_value = None
        response.text = '''
            <div id="wlui" data-fid="535482401" data-uid="186214518"></div>
            <div class="athorName"><span>@DY_苏苏</span></div>
            <img class="userHead" src="//img7.peiyinxiu.com/avatar/test.jpg">
            <div class="filmName" data-title="七夕节你怎么过？">七夕节你怎么过？</div>
            <script>PlayByShowplay.play({filmurl: 'https://video7.peiyinxiu.com/download/test.mp4', filmimg: 'https://img7.peiyinxiu.com/test.jpg'});</script>
        '''
        get.return_value = response
        parser = PeiyinxiuParser(self.URL)
        self.assertEqual(parser.get_title_content(), "七夕节你怎么过？")
        self.assertEqual(parser.get_author_info(), {"nickname": "DY_苏苏", "author_id": "186214518", "avatar": "https://img7.peiyinxiu.com/avatar/test.jpg"})
        self.assertEqual(parser.get_cover_photo_url(), "https://img7.peiyinxiu.com/test.jpg")
        self.assertEqual(parser.get_real_video_url(), "https://video7.peiyinxiu.com/download/test.mp4")

    @patch("src.parsers.base_parser.requests.Session.get")
    def test_handles_missing_media(self, get):
        response = Mock()
        response.raise_for_status.return_value = None
        response.text = '<div id="wlui" data-uid="1"></div>'
        get.return_value = response
        self.assertIsNone(PeiyinxiuParser(self.URL).get_real_video_url())


if __name__ == "__main__":
    unittest.main()
