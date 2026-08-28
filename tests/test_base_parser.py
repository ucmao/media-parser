import re
import unittest

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

if __name__ == "__main__":
    unittest.main()
