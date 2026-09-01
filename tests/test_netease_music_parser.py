import html
import json
import unittest
from unittest.mock import Mock, patch

from src.parsers.netease_music_parser import NeteaseMusicParser


class NeteaseMusicParserTest(unittest.TestCase):
    @staticmethod
    def response(*, text="", payload=None, url="https://music.163.com/"):
        response = Mock()
        response.text = text
        response.url = url
        response.json.return_value = payload or {}
        response.raise_for_status.return_value = None
        return response

    @staticmethod
    def initial_html(key, value):
        payload = {key: value, "isServerError": False}
        return f"<script>window.__INITIAL_PROPS__ = {json.dumps(payload, ensure_ascii=False)}\n</script>"

    @patch("src.parsers.base_parser.requests.Session.get")
    def test_parses_mv_with_highest_quality_first(self, get):
        get.return_value = self.response(
            payload={
                "code": 200,
                "data": {
                    "id": 34781314,
                    "name": "透明爱人",
                    "cover": "http://p1.music.126.net/cover.jpg",
                    "artistName": "白鹿",
                    "artistId": 12603258,
                    "artists": [{"id": 12603258, "name": "白鹿"}],
                    "brs": {
                        "480": "http://vod.126.net/480.mp4",
                        "1080": "http://vod.126.net/1080.mp4",
                        "720": "http://vod.126.net/720.mp4",
                    },
                },
            }
        )
        parser = NeteaseMusicParser(
            "https://fn.music.163.com/g/mlog/mlog-mobile/landing/mv?id=34781314"
        )
        self.assertEqual(parser.get_title_content(), "透明爱人")
        self.assertEqual(parser.get_author_info()["nickname"], "白鹿")
        self.assertEqual(parser.get_real_video_url(), "http://vod.126.net/1080.mp4")
        self.assertEqual(len(parser.get_video_list()), 3)

    @patch("src.parsers.base_parser.requests.Session.get")
    def test_parses_mlog_signed_video_and_profile(self, get):
        mlog = {
            "resource": {
                "content": {
                    "title": "动态视频",
                    "image": [],
                    "video": {
                        "coverUrl": "http://p1.music.126.net/mlog-cover.jpg",
                        "urlInfos": [
                            {"resolution": 360, "url": "http://vod.126.net/360.mp4"},
                            {"resolution": 1080, "url": "http://vod.126.net/1080.mp4"},
                        ],
                    },
                },
                "profile": {
                    "userId": 123,
                    "nickname": "云村用户",
                    "avatarUrl": "http://p1.music.126.net/avatar.jpg",
                },
            }
        }
        get.return_value = self.response(text=self.initial_html("mlogInfo", mlog))
        parser = NeteaseMusicParser(
            "https://fn.music.163.com/g/mlog/mlog-mobile/landing/mlog?id=a123&type=2"
        )
        self.assertEqual(parser.get_title_content(), "动态视频")
        self.assertEqual(parser.get_author_info()["author_id"], "123")
        self.assertEqual(parser.get_real_video_url(), "http://vod.126.net/1080.mp4")

    @patch("src.parsers.base_parser.requests.Session.get")
    def test_parses_event_images_livephotos_and_free_song(self, get):
        event = {
            "user": {
                "userId": 456,
                "nickname": "动态作者",
                "avatarUrl": "http://p1.music.126.net/event-avatar.jpg",
            },
            "json": json.dumps(
                {
                    "title": "动态标题",
                    "msg": "动态正文",
                    "song": {"id": 3383347615, "name": "念张师"},
                    "videoData": None,
                },
                ensure_ascii=False,
            ),
            "pics": [
                {
                    "originUrl": "http://p1.music.126.net/photo.jpg",
                    "videoOriginalUrl": "http://vod.126.net/live.mov",
                }
            ],
        }
        event_html = (
            '<textarea name="txt" id="event-data" style="display:none;">'
            + html.escape(json.dumps(event, ensure_ascii=False))
            + "</textarea>"
        )

        def side_effect(url, **kwargs):
            if "/event" in url:
                return self.response(text=event_html)
            if "/song/detail/" in url:
                return self.response(
                    payload={
                        "songs": [
                            {
                                "id": 3383347615,
                                "name": "念张师",
                                "album": {"picUrl": "http://p1.music.126.net/album.jpg"},
                                "artists": [{"id": 1, "name": "歌手"}],
                            }
                        ]
                    }
                )
            if "/player/url" in url:
                return self.response(payload={"data": [{"url": "http://m801.music.126.net/song.mp3"}]})
            return self.response(payload={"lrc": {"lyric": "[00:01.50]第一句\n[00:03.00]第二句"}})

        get.side_effect = side_effect
        parser = NeteaseMusicParser(
            "https://music.163.com/event?id=37613855054&uid=13685426555"
        )
        self.assertEqual(parser.get_title_content(), "动态标题")
        self.assertEqual(parser.get_audio_url(), "http://m801.music.126.net/song.mp3")
        self.assertEqual(parser.get_image_list()[0]["live_photo_url"], "http://vod.126.net/live.mov")
        self.assertEqual(parser.get_subtitles()[0], {"start": 1.5, "text": "第一句"})

    @patch("src.parsers.base_parser.requests.Session.get")
    def test_paid_song_does_not_return_fake_audio(self, get):
        def side_effect(url, **kwargs):
            if "/song/detail/" in url:
                return self.response(
                    payload={
                        "songs": [
                            {
                                "id": 472137906,
                                "name": "时差",
                                "album": {"picUrl": "http://p1.music.126.net/album.jpg"},
                                "artists": [{"id": 1, "name": "鹿晗"}],
                            }
                        ]
                    }
                )
            return self.response(payload={"data": [{"url": None}], "lrc": {}})

        get.side_effect = side_effect
        parser = NeteaseMusicParser("https://music.163.com/song?id=472137906")
        self.assertEqual(parser.get_title_content(), "时差")
        self.assertIsNone(parser.get_audio_url())

    @patch("src.parsers.base_parser.requests.Session.get")
    def test_invalid_song_id_fails_cleanly(self, get):
        parser = NeteaseMusicParser("https://music.163.com/song?id=invalid")
        get.assert_not_called()
        self.assertIsNone(parser.get_audio_url())


if __name__ == "__main__":
    unittest.main()
