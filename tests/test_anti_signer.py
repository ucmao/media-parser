import unittest
from unittest.mock import Mock, patch

from utils.signer.pinduoduo.anti_signer import AntiSigner


class AntiSignerTest(unittest.TestCase):
    def test_singleton_pattern(self):
        s1 = AntiSigner()
        s2 = AntiSigner()
        self.assertIs(s1, s2)

    def test_generates_valid_anti_content_token(self):
        signer = AntiSigner()
        token = signer.get_anti_content()
        self.assertTrue(token)
        self.assertTrue(token.startswith("0as"))
        self.assertGreater(len(token), 100)

    def test_gracefully_handles_error_or_uninitialized_ctx(self):
        signer = AntiSigner()
        with patch.object(signer, "ctx", None):
            self.assertEqual(signer.get_anti_content(), "")

        mock_ctx = Mock()
        mock_ctx.call.side_effect = RuntimeError("JS runtime failure")
        with patch.object(signer, "ctx", mock_ctx):
            self.assertEqual(signer.get_anti_content(), "")


if __name__ == "__main__":
    unittest.main()
