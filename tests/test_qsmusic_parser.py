import json
import unittest
from unittest.mock import Mock, patch

from src.parsers.qsmusic_parser import QSMusicParser


class QSMusicParserTest(unittest.TestCase):
    def test_maps_router_video_data(self):
        router_data = {"loaderData": {"ugc_video_page": {"videoOptions": {
            "videoName": "测试汽水作品",
            "artistName": "测试音乐人",
            "artistThumbAvatarArr": ["https://image.example.com/avatar.jpg"],
            "coverURL": "https://image.example.com/cover.jpg",
            "url": "https://v3-dy-o.zjcdn.com/video_mp4/work.mp4",
        }}}}
        response = Mock(url="https://music.douyin.com/qishui/share/ugc_video?ugc_video_id=123")
        response.text = f"<script>_ROUTER_DATA = {json.dumps(router_data)};</script>"

        with patch("requests.Session.get", return_value=response):
            parser = QSMusicParser("https://qishui.douyin.com/s/code/")

        self.assertEqual(parser.get_title_content(), "测试汽水作品")
        self.assertEqual(parser.get_real_video_url(), "https://v3-dy-o.zjcdn.com/video_mp4/work.mp4")
        self.assertEqual(parser.get_cover_photo_url(), "https://image.example.com/cover.jpg")
        self.assertEqual(parser.get_author_info()["nickname"], "测试音乐人")

    def test_maps_track_audio_data(self):
        router_data = {"loaderData": {"track_page": {"trackOptions": {
            "name": "测试歌曲",
            "artists": [{"user_info": {"nickname": "歌手", "id": 42}}],
            "album": {"cover_url": {"url": "https://image.example.com/album.jpg"}},
            "audio_url": "https://audio.example.com/song.mp3",
        }}}}
        response = Mock(url="https://music.douyin.com/track/123")
        response.text = f"<script>_ROUTER_DATA = {json.dumps(router_data)};</script>"

        with patch("requests.Session.get", return_value=response):
            parser = QSMusicParser("https://music.douyin.com/track/123")

        self.assertEqual(parser.get_audio_url(), "https://audio.example.com/song.mp3")
        self.assertEqual(parser.get_real_video_url(), None)
        self.assertEqual(parser.get_author_info()["author_id"], "42")


if __name__ == "__main__":
    unittest.main()
