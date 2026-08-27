import re
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import requests

from src.parsers.base_parser import BaseParser


class BaseParserTest(unittest.TestCase):
    def test_default_subtitles_are_none(self):
        self.assertIsNone(BaseParser("https://example.com").get_subtitles())

    def test_parse_html_data_extracts_json_and_replaces_undefined(self):
        html = '<script>window.DATA = {"value": undefined};</script>'
        result = BaseParser.parse_html_data(
            html,
            re.compile(r"window\.DATA\s*=\s*(\{.*\});"),
        )
        self.assertEqual(result, '{"value": null}')

    def test_download_returns_none_when_request_fails(self):
        parser = BaseParser("https://example.com")
        session = Mock()
        session.get.side_effect = requests.RequestException("network error")
        with tempfile.TemporaryDirectory() as folder:
            with patch("src.parsers.base_parser.requests.Session", return_value=session):
                result = parser.download_and_save(folder, "https://example.com/video", "mp4")
        self.assertIsNone(result)

    def test_download_writes_non_empty_chunks(self):
        parser = BaseParser("https://example.com")
        response = Mock()
        response.iter_content.return_value = [b"abc", b"", b"def"]
        session = Mock()
        session.get.return_value = response

        with tempfile.TemporaryDirectory() as folder:
            with patch("src.parsers.base_parser.requests.Session", return_value=session):
                result = parser.download_and_save(folder, "https://example.com/video", "mp4")
            self.assertEqual(Path(result).read_bytes(), b"abcdef")
            response.raise_for_status.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
