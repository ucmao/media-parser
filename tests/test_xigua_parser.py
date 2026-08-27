import unittest

from src.parsers.douyin_parser import DouyinParser
from src.parsers.xigua_parser import XiguaParser


class XiguaParserTest(unittest.TestCase):
    def test_reuses_douyin_parser(self):
        self.assertTrue(issubclass(XiguaParser, DouyinParser))


if __name__ == "__main__":
    unittest.main()
