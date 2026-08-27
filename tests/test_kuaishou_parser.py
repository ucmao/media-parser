import unittest
from unittest.mock import patch

from configs.general_constants import USER_AGENT_M
from src.parsers.kuaishou_parser import KuaishouParser


class KuaishouParserHeadersTest(unittest.TestCase):
    def test_builds_headers_with_configured_mobile_user_agent(self):
        parser = KuaishouParser.__new__(KuaishouParser)

        with patch("src.parsers.kuaishou_parser.random.choice", return_value="mobile-user-agent") as choice:
            headers = parser._build_mobile_headers()

        choice.assert_called_once_with(USER_AGENT_M)
        self.assertEqual(headers["User-Agent"], "mobile-user-agent")
        self.assertEqual(headers["referer"], "https://v.m.chenzhongtech.com/")


if __name__ == "__main__":
    unittest.main()
