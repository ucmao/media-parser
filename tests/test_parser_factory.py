import unittest
from unittest.mock import patch

from configs.general_constants import DOMAIN_TO_NAME
from src.parser_factory import ParserFactory


class DummyParser:
    def __init__(self, url):
        self.url = url


class ParserFactoryTest(unittest.TestCase):
    def test_every_configured_platform_has_a_parser(self):
        configured_platforms = set(DOMAIN_TO_NAME.values())
        self.assertTrue(configured_platforms)
        self.assertEqual(configured_platforms - set(ParserFactory.platform_to_parser), set())

    def test_creates_the_registered_parser(self):
        with patch.dict(ParserFactory.platform_to_parser, {"测试平台": DummyParser}, clear=True):
            parser = ParserFactory.create_parser("测试平台", "https://example.com/1")
        self.assertIsInstance(parser, DummyParser)
        self.assertEqual(parser.url, "https://example.com/1")

    def test_unknown_platform_raises_readable_error(self):
        with self.assertRaisesRegex(ValueError, "不支持的平台：不存在"):
            ParserFactory.create_parser("不存在", "https://example.com/1")


if __name__ == "__main__":
    unittest.main()
