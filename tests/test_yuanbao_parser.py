import json
import unittest
from unittest.mock import Mock, patch

from src.parsers.yuanbao_parser import YuanbaoParser


def make_next_page(page_props, title="用户和元宝的对话"):
    payload = {
        "props": {"pageProps": page_props},
        "page": "/s/[shareId]",
    }
    return (
        f"<html><head><title>{title}</title></head><body>"
        '<script id="__NEXT_DATA__" type="application/json">'
        f"{json.dumps(payload, ensure_ascii=False)}"
        "</script></body></html>"
    )


class YuanbaoParserTest(unittest.TestCase):
    def _response(self, page_props):
        response = Mock()
        response.raise_for_status.return_value = None
        response.url = "https://yb.tencent.com/s/testShareId"
        response.text = make_next_page(page_props)
        return response

    def test_parses_generated_image_from_chat_share(self):
        page_props = {
            "fullChatShareData": {
                "chat": {
                    "convs": [
                        {
                            "speaker": "human",
                            "userId": "user-1",
                            "displayPrompt": "帮我生成一张海报",
                            "role": {
                                "name": "测试用户",
                                "imageUrl": "https://avatar.example.com/user.jpg",
                            },
                        },
                        {
                            "speaker": "ai",
                            "speechesV2": [
                                {
                                    "extra": {
                                        "replaces": [
                                            {
                                                "multimedias": [
                                                    {
                                                        "type": "loadingImage",
                                                        "mediaType": "image",
                                                        "url": "https://cos.example.com/preview.jpg",
                                                        "downloadUrl": "https://cos.example.com/original.jpg",
                                                        "thumbnailUrl": "https://cos.example.com/thumb.jpg",
                                                    }
                                                ]
                                            }
                                        ]
                                    }
                                }
                            ],
                        },
                    ],
                    "shareCardInfo": {
                        "title": "[图片]帮我生成一张海报",
                        "imageFrom": "loadingImage",
                        "coverUrl": "https://cos.example.com/card.jpg",
                    },
                }
            }
        }

        with patch("requests.Session.get", return_value=self._response(page_props)):
            parser = YuanbaoParser("https://yb.tencent.com/s/testShareId")

        self.assertEqual(parser.get_title_content(), "帮我生成一张海报")
        self.assertEqual(parser.get_image_list(), ["https://cos.example.com/original.jpg"])
        self.assertEqual(parser.get_cover_photo_url(), "https://cos.example.com/thumb.jpg")
        self.assertIsNone(parser.get_real_video_url())
        self.assertEqual(
            parser.get_author_info(),
            {
                "nickname": "测试用户",
                "author_id": "user-1",
                "avatar": "https://avatar.example.com/user.jpg",
            },
        )

    def test_parses_generated_video_and_cover(self):
        page_props = {
            "fullChatShareData": {
                "chat": {
                    "convs": [
                        {"speaker": "human", "displayPrompt": "让画面下雪"},
                        {
                            "speaker": "ai",
                            "speechesV2": [
                                {
                                    "extra": {
                                        "replaces": [
                                            {
                                                "multimedias": [
                                                    {
                                                        "type": "loadingVideo",
                                                        "mimeType": "video/mp4",
                                                        "url": "https://cos.example.com/video.mp4",
                                                        "downloadUrl": "https://cos.example.com/video-original.mp4",
                                                        "cover": "https://cos.example.com/video-cover.jpg",
                                                    }
                                                ]
                                            }
                                        ]
                                    }
                                }
                            ],
                        },
                    ],
                    "shareCardInfo": {
                        "title": "[图片]帮我生成视频：让画面下雪",
                        "imageFrom": "loadingVideo",
                    },
                }
            }
        }

        with patch("requests.Session.get", return_value=self._response(page_props)):
            parser = YuanbaoParser("https://yb.tencent.com/s/testShareId")

        self.assertEqual(parser.get_real_video_url(), "https://cos.example.com/video-original.mp4")
        self.assertEqual(parser.get_video_list(), ["https://cos.example.com/video-original.mp4"])
        self.assertEqual(parser.get_cover_photo_url(), "https://cos.example.com/video-cover.jpg")
        self.assertEqual(parser.get_image_list(), [])

    def test_deleted_share_returns_empty_media(self):
        with patch(
            "requests.Session.get",
            return_value=self._response({"isShareDel": True, "shareId": "deleted"}),
        ):
            parser = YuanbaoParser("https://yb.tencent.com/s/deleted")

        self.assertEqual(parser.get_image_list(), [])
        self.assertEqual(parser.get_video_list(), [])
        self.assertIsNone(parser.get_real_video_url())


if __name__ == "__main__":
    unittest.main()
