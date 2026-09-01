import json
import unittest
from unittest.mock import Mock, patch

from src.parsers.kugou_music_parser import KugouMusicParser


class KugouMusicParserTest(unittest.TestCase):
    MV_URL = "https://m.kugou.com/mv/?hash=48da1fe5cbe4f8774f73160042377b1e"

    @staticmethod
    def response(*, text="", payload=None):
        response = Mock()
        response.text = text
        response.json.return_value = payload or {}
        response.raise_for_status.return_value = None
        return response

    @patch("src.parsers.base_parser.requests.Session.get")
    def test_parses_mv_and_orders_highest_quality_first(self, get):
        get.return_value = self.response(
            payload={
                "errcode": 0,
                "songname": "山海串烧",
                "singer": "长啸",
                "id": 1915905,
                "mvicon": "http://imge.kugou.com/mv/{size}/cover.jpg",
                "mvdata": {
                    "sq": {"downurl": "https://mv.kugou.com/1080.mp4"},
                    "le": {"downurl": "https://mv.kugou.com/480.mp4"},
                },
            }
        )
        parser = KugouMusicParser(self.MV_URL)
        self.assertEqual(parser.get_title_content(), "山海串烧")
        self.assertEqual(parser.get_author_info()["nickname"], "长啸")
        self.assertEqual(parser.get_cover_photo_url(), "http://imge.kugou.com/mv/400/cover.jpg")
        self.assertEqual(parser.get_video_list(), ["https://mv.kugou.com/1080.mp4", "https://mv.kugou.com/480.mp4"])
        params = get.call_args.kwargs["params"]
        self.assertEqual(params["hash"], "48da1fe5cbe4f8774f73160042377b1e")
        self.assertTrue(params["signature"])

    @patch("src.parsers.base_parser.requests.Session.get")
    def test_returns_free_song_audio_but_not_paid_preview(self, get):
        song = {"song_info": {"data": {"songName": "免费歌曲", "pay_type": 0, "url": "https://sharefs.kugou.com/song.mp3", "authors": [{"author_name": "歌手", "author_id": 7}]}}}
        get.return_value = self.response(text=f"<script>var phpParam = {json.dumps(song, ensure_ascii=False)};</script>")
        parser = KugouMusicParser("https://m.kugou.com/share/song.html?chain=test")
        self.assertEqual(parser.get_audio_url(), "https://sharefs.kugou.com/song.mp3")
        self.assertEqual(parser.get_author_info()["nickname"], "歌手")

        paid = {"song_info": {"data": {"songName": "付费歌曲", "pay_type": 3, "error": "需要付费", "url": "https://sharefs.kugou.com/preview.mp3"}}}
        get.return_value = self.response(text=f"<script>var phpParam = {json.dumps(paid, ensure_ascii=False)};</script>")
        parser = KugouMusicParser("https://m.kugou.com/share/song.html?chain=paid")
        self.assertIsNone(parser.get_audio_url())

    def test_rejects_missing_mv_hash(self):
        parser = KugouMusicParser("https://m.kugou.com/mv/")
        self.assertIsNone(parser.get_real_video_url())

    @patch("src.parsers.base_parser.requests.Session.get")
    def test_supports_desktop_mv_redirect_path(self, get):
        get.return_value = self.response(payload={})
        parser = KugouMusicParser(
            "https://www.kugou.com/mvweb/html/mv_48da1fe5cbe4f8774f73160042377b1e.html"
        )
        self.assertEqual(parser.media_type, "mv")
        self.assertEqual(parser.content_id, "48da1fe5cbe4f8774f73160042377b1e")


if __name__ == "__main__":
    unittest.main()
