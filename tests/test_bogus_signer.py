import unittest
from unittest.mock import Mock, patch

from utils.signer.bytedance.bogus_signer import BogusSigner


class BogusSignerTest(unittest.TestCase):
    def test_ms_token_generation_length(self):
        with patch("utils.signer.bytedance.bogus_signer.MiniRacer"):
            with patch("builtins.open", unittest.mock.mock_open(read_data="function sign() {}")):
                signer = BogusSigner()
                token_107 = signer.get_ms_token(107)
                self.assertEqual(len(token_107), 107)
                token_32 = signer.get_ms_token(32)
                self.assertEqual(len(token_32), 32)

    def test_signer_sign_delegation(self):
        mock_ctx = Mock()
        mock_ctx.call.return_value = "mock_signed_value"
        with patch("utils.signer.bytedance.bogus_signer.MiniRacer", return_value=mock_ctx):
            with patch("builtins.open", unittest.mock.mock_open(read_data="")):
                signer = BogusSigner()
                signer.x_bogus_ctx = mock_ctx
                signer.a_bogus_ctx = mock_ctx

                xbogus = signer.get_xbogus("https://www.douyin.com/aweme/v1/web/aweme/detail/?aid=6383", "custom-ua")
                self.assertEqual(xbogus, "mock_signed_value")
                mock_ctx.call.assert_called_with("sign", "aid=6383", "custom-ua")

                abogus = signer.get_abogus("https://www.douyin.com/aweme/v1/web/aweme/detail/?aid=6383", "custom-ua")
                self.assertEqual(abogus, "mock_signed_value")
                mock_ctx.call.assert_called_with("generate_a_bogus", "aid=6383", "custom-ua")


if __name__ == "__main__":
    unittest.main()
