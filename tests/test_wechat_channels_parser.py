import os
import unittest
from unittest.mock import Mock, patch

from src.parsers.wechat_channels_parser import WeChatChannelsParser


class WeChatChannelsParserTest(unittest.TestCase):
    URL = "https://weixin.qq.com/sph/AzGrUgqzFv"

    @staticmethod
    def response(payload):
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = payload
        return response

    @staticmethod
    def feed_response(video_url="https://finder.video.qq.com/video.mp4"):
        return {
            "errCode": 0,
            "data": {
                "authorInfo": {
                    "nickname": "测试作者",
                    "headImgUrl": "https://wx.qlogo.cn/avatar.jpg",
                },
                "feedInfo": {
                    "description": "测试视频号作品",
                    "coverUrl": "https://finder.video.qq.com/cover.jpg",
                    "h264VideoInfo": {"videoUrl": video_url},
                },
            },
        }

    @patch.dict(os.environ, {}, clear=True)
    @patch("src.parsers.base_parser.requests.Session.post")
    def test_parses_short_link_with_public_api(self, post):
        post.return_value = self.response(self.feed_response())

        parser = WeChatChannelsParser(self.URL)

        self.assertEqual(parser.get_real_video_url(), "https://finder.video.qq.com/video.mp4")
        self.assertEqual(parser.get_title_content(), "测试视频号作品")
        self.assertEqual(parser.get_cover_photo_url(), "https://finder.video.qq.com/cover.jpg")
        self.assertEqual(parser.get_author_info()["nickname"], "测试作者")
        payload = post.call_args.kwargs["json"]
        self.assertEqual(payload, {"baseReq": {"generalToken": ""}, "shortUri": "AzGrUgqzFv"})

    @patch.dict(os.environ, {"YUANBAO_COOKIE": "hy_user=user; hy_token=token"}, clear=True)
    @patch("src.parsers.base_parser.requests.Session.post")
    def test_uses_yuanbao_cookie_when_configured(self, post):
        post.side_effect = [
            self.response({
                "data": {
                    "playable_url": "https://channels.weixin.qq.com/finder-preview/pages/feed?token=temp-token&eid=export-id"
                }
            }),
            self.response(self.feed_response()),
        ]

        parser = WeChatChannelsParser(self.URL)

        self.assertEqual(parser.get_real_video_url(), "https://finder.video.qq.com/video.mp4")
        self.assertEqual(post.call_count, 2)
        self.assertEqual(post.call_args_list[0].kwargs["headers"]["Cookie"], "hy_user=user; hy_token=token")
        self.assertEqual(
            post.call_args_list[1].kwargs["json"],
            {"baseReq": {"generalToken": "temp-token"}, "exportId": "export-id"},
        )

    @patch.dict(os.environ, {"YUANBAO_COOKIE": "hy_user=user; hy_token=expired"}, clear=True)
    @patch("src.parsers.base_parser.requests.Session.post")
    def test_falls_back_to_public_api_when_cookie_is_invalid(self, post):
        post.side_effect = [
            self.response({"msg": "登录已失效"}),
            self.response(self.feed_response()),
        ]

        parser = WeChatChannelsParser(self.URL)

        self.assertEqual(parser.get_real_video_url(), "https://finder.video.qq.com/video.mp4")
        self.assertEqual(post.call_count, 2)

    def test_normalizes_h265_when_h264_is_missing(self):
        result = self.feed_response()
        feed = result["data"]["feedInfo"]
        del feed["h264VideoInfo"]
        feed["h265VideoInfo"] = {"videoUrl": "https://finder.video.qq.com/video-h265.mp4"}

        data = WeChatChannelsParser._normalize_feed(result)

        self.assertEqual(data["video_url"], "https://finder.video.qq.com/video-h265.mp4")


if __name__ == "__main__":
    unittest.main()
