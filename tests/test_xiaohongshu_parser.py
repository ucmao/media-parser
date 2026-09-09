import unittest
from src.parsers.xiaohongshu_parser import XiaohongshuParser


class XiaohongshuParserTest(unittest.TestCase):
    def test_extract_note_from_pc_initial_state(self):
        html = '<script>window.__INITIAL_STATE__ = {"note": {"firstNoteId": "note123", "noteDetailMap": {"note123": {"note": {"title": "PC\u6807\u9898", "desc": "PC\u63cf\u8ff0", "user": {"nickname": "PC\u7528\u6237", "userId": "u123", "avatar": "http://avatar.jpg"}, "imageList": [{"urlDefault": "http://img1.jpg"}]}}}}}</script>'
        parser = XiaohongshuParser.__new__(XiaohongshuParser)
        note = parser._extract_note_from_html(html)
        self.assertIsNotNone(note)
        self.assertEqual(note.get("title"), "PC标题")
        self.assertEqual(note.get("desc"), "PC描述")
        parser.note_data = note
        self.assertEqual(parser.get_author_info()["nickname"], "PC用户")
        self.assertEqual(parser.get_cover_photo_url(), "http://img1.jpg")

    def test_extract_note_from_mobile_initial_state(self):
        html = '<script>window.__INITIAL_STATE__ = {"noteData": {"data": {"noteData": {"title": "\u79fb\u52a8\u7aef\u6807\u9898", "desc": "\u79fb\u52a8\u7aef\u63cf\u8ff0", "user": {"nickName": "\u79fb\u52a8\u7aef\u7528\u6237", "userId": "u456", "avatar": "http://m_avatar.jpg"}, "imageList": [{"url": "http://m_img1.jpg", "livePhoto": true, "stream": {"h264": [{"masterUrl": "http://live.mp4"}]}}]}}}}</script>'
        parser = XiaohongshuParser.__new__(XiaohongshuParser)
        note = parser._extract_note_from_html(html)
        self.assertIsNotNone(note)
        self.assertEqual(note.get("title"), "移动端标题")
        parser.note_data = note
        self.assertEqual(parser.get_author_info()["nickname"], "移动端用户")
        self.assertEqual(parser.get_cover_photo_url(), "http://m_img1.jpg")
        images = parser.get_image_list()
        self.assertEqual(len(images), 1)
        self.assertEqual(images[0]["live_photo_url"], "http://live.mp4")


    def test_extract_deleted_or_private_note_sets_terminal_error(self):
        html = '<script>window.__INITIAL_STATE__ = {"note": {"firstNoteId": "note_deleted", "noteDetailMap": {"note_deleted": {"note": {}}}}}</script>'
        parser = XiaohongshuParser.__new__(XiaohongshuParser)
        parser.terminal_error = None
        note = parser._extract_note_from_html(html)
        self.assertIsNone(note)
        self.assertIsNotNone(parser.terminal_error)
        self.assertIn("私密", parser.terminal_error["detail_msg"])


if __name__ == "__main__":
    unittest.main()
