import unittest
from unittest.mock import patch

import py_mini_racer


if not hasattr(py_mini_racer, "MiniRacer"):
    py_mini_racer.MiniRacer = object

from app import app


class FakeParser:
    def __init__(self, video_url, video_list):
        self.video_url = video_url
        self.video_list = video_list

    def get_title_content(self):
        return "测试视频"

    def get_real_video_url(self):
        return self.video_url

    def get_video_list(self):
        return self.video_list

    def get_cover_photo_url(self):
        return "https://example.com/cover.jpg"

    def get_author_info(self):
        return None

    def get_image_list(self):
        return []

    def get_audio_url(self):
        return None


class ApiVideoCompatibilityTest(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    def parse_with(self, parser):
        with patch(
            "src.api.parse.WebFetcher.fetch_redirect_url",
            return_value="https://www.douyin.com/video/123",
        ):
            with patch(
                "src.api.parse.ParserFactory.create_parser",
                return_value=parser,
            ):
                return self.client.post("/api/parse", json={"text": "https://example.com"})

    def test_single_video_keeps_legacy_response_shape(self):
        response = self.parse_with(
            FakeParser("https://example.com/video.mp4", ["https://example.com/video.mp4"])
        )

        self.assertEqual(response.status_code, 200)
        data = response.get_json()["data"]
        self.assertEqual(data["video_url"], "https://example.com/video.mp4")
        self.assertNotIn("video_list", data)

    def test_multiple_videos_include_optional_list(self):
        response = self.parse_with(
            FakeParser(None, [
                "https://example.com/video-1.mp4",
                "https://example.com/video-2.mp4",
            ])
        )

        self.assertEqual(response.status_code, 200)
        data = response.get_json()["data"]
        self.assertEqual(data["video_url"], "https://example.com/video-1.mp4")
        self.assertEqual(data["video_list"][0], data["video_url"])
        self.assertEqual(len(data["video_list"]), 2)


if __name__ == "__main__":
    unittest.main()
