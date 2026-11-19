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

    def test_extract_note_with_js_constructs(self):
        html = '<script>window.__INITIAL_STATE__ = {"note": {"firstNoteId": "note123", "noteDetailMap": {"note123": {"note": {"title": "JS\u6d4b\u8bd5", "desc": "JS\u63cf\u8ff0", "user": {"nickname": "JS\u7528\u6237"}, "imageList": []}}}}, "extra": undefined, "mapStore": new Map([]), "setStore": new Set(["a"])}</script>'
        parser = XiaohongshuParser.__new__(XiaohongshuParser)
        note = parser._extract_note_from_html(html)
        self.assertIsNotNone(note)
        self.assertEqual(note.get("title"), "JS测试")

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
        self.assertEqual(images[0]["live_photo_url"], "https://live.mp4")

    def test_clean_image_url(self):
        parser = XiaohongshuParser.__new__(XiaohongshuParser)
        # fileId in dict
        img_dict = {
            "fileId": "1040g008324p66r2m7k705p3a1qinu9068tutcco",
            "urlDefault": "http://sns-webpic-qc.xhscdn.com/202609102130/94e7f036b636/1040g008324p66r2m7k705p3a1qinu9068tutcco!h5_1080jpg"
        }
        self.assertEqual(parser._clean_image_url(img_dict), "https://sns-img-qc.xhscdn.com/1040g008324p66r2m7k705p3a1qinu9068tutcco?imageView2/2/w/1920/format/jpg")

        # URL string with watermark style suffix
        watermarked_url = "http://sns-webpic-qc.xhscdn.com/202609102130/94e7f036b6363190c6e37270adc2b04f/1040g008324p66r2m7k705p3a1qinu9068tutcco!h5_1080jpg"
        self.assertEqual(parser._clean_image_url(watermarked_url), "https://sns-img-qc.xhscdn.com/1040g008324p66r2m7k705p3a1qinu9068tutcco?imageView2/2/w/1920/format/jpg")

    def test_get_real_video_url_unwatermarked(self):
        parser = XiaohongshuParser.__new__(XiaohongshuParser)
        # Test prioritizing consumer.originVideoKey
        parser.note_data = {
            "video": {
                "consumer": {"originVideoKey": "pre_post/1040g2t0324k7p9o3go005q1il9f2nou295lutc0"},
                "mediaV2": '{"video": {"opaque1": {"hd_screencast_stream": "http://sns-video-v2.xhscdn.com/stream/1/110/301/hd_clean.mp4"}}}',
            }
        }
        self.assertEqual(parser.get_real_video_url(), "https://sns-video-bd.xhscdn.com/pre_post/1040g2t0324k7p9o3go005q1il9f2nou295lutc0")

        # Test prioritizing mediaV2 screencast stream when originVideoKey is absent
        parser.note_data = {
            "video": {
                "mediaV2": '{"video": {"opaque1": {"hd_screencast_stream": "http://sns-video-v2.xhscdn.com/stream/1/110/301/hd_clean.mp4"}}}',
                "media": {
                    "stream": {
                        "h264": [{"streamType": 259, "streamDesc": "MINI_APP_259", "masterUrl": "http://sns-video-v2.xhscdn.com/stream/watermarked.mp4"}]
                    }
                }
            }
        }
        self.assertEqual(parser.get_real_video_url(), "https://sns-video-v2.xhscdn.com/stream/1/110/301/hd_clean.mp4")

        # Test prioritizing unwatermarked streamType 258 over 259
        parser.note_data = {
            "video": {
                "media": {
                    "stream": {
                        "h264": [
                            {"streamType": 259, "streamDesc": "MINI_APP_259", "masterUrl": "http://sns-video-v2.xhscdn.com/stream/watermarked.mp4"},
                            {"streamType": 258, "streamDesc": "X264_MP4", "masterUrl": "http://sns-video-v2.xhscdn.com/stream/clean_258.mp4"}
                        ]
                    }
                }
            }
        }
        self.assertEqual(parser.get_real_video_url(), "https://sns-video-v2.xhscdn.com/stream/clean_258.mp4")

    def test_cookie_injection_in_headers(self):
        from unittest.mock import Mock, patch
        import os

        resp = Mock()
        resp.status_code = 200
        resp.url = "https://www.xiaohongshu.com/explore/123"
        resp.text = '<script>window.__INITIAL_STATE__ = {"note": {"firstNoteId": "123", "noteDetailMap": {"123": {"note": {"title": "带Cookie标题", "imageList": []}}}}}</script>'

        with patch("requests.Session.get", return_value=resp) as mock_get:
            with patch.dict(os.environ, {"XIAOHONGSHU_COOKIE": "a1=test_cookie_value;", "XHS_COOKIE": ""}):
                parser = XiaohongshuParser("https://www.xiaohongshu.com/explore/123")
                self.assertEqual(parser.get_title_content(), "带Cookie标题")
                call_headers = mock_get.call_args[1]["headers"]
                self.assertEqual(call_headers.get("Cookie"), "a1=test_cookie_value;")

    def test_login_redirect_sets_terminal_error(self):
        from unittest.mock import Mock, patch
        import os

        resp = Mock()
        resp.status_code = 200
        resp.url = "https://www.xiaohongshu.com/login"
        resp.text = '<html><head><title>登录</title></head></html>'

        with patch("requests.Session.get", return_value=resp):
            with patch.dict(os.environ, {"XIAOHONGSHU_COOKIE": "", "XHS_COOKIE": ""}):
                parser = XiaohongshuParser("https://www.xiaohongshu.com/explore/456")
                self.assertIsNotNone(parser.terminal_error)
                self.assertIn("需在后台系统设置中配置小红书 Cookie", parser.terminal_error["detail_msg"])


    def _parser_for_final_url(self, final_url):
        from unittest.mock import Mock, patch
        import os
        resp = Mock(status_code=200, url=final_url, text="<html></html>")
        with patch("requests.Session.get", return_value=resp):
            with patch.dict(os.environ, {"XIAOHONGSHU_COOKIE": "", "XHS_COOKIE": ""}):
                return XiaohongshuParser("https://www.xiaohongshu.com/discovery/item/69fc84830000000023016c37")

    def test_security_404_is_risk_control_not_deleted(self):
        parser = self._parser_for_final_url(
            "https://www.xiaohongshu.com/404?source=/404/sec_mRapqfwO?redirectPath=x&error_code=300031&error_msg=x"
        )
        self.assertEqual(parser.terminal_error["error_code"], "XIAOHONGSHU_COOKIE_REQUIRED")
        self.assertIn("风控", parser.terminal_error["detail_msg"])

    def test_mobile_security_404_is_risk_control(self):
        parser = self._parser_for_final_url(
            "https://www.xiaohongshu.com/404/sec_dgXCGSbw?source=xhs_sec_server&originalUrl=x"
        )
        self.assertEqual(parser.terminal_error["error_code"], "XIAOHONGSHU_COOKIE_REQUIRED")

    def test_plain_404_is_still_deleted(self):
        parser = self._parser_for_final_url("https://www.xiaohongshu.com/404?source=note")
        self.assertNotIn("error_code", parser.terminal_error)
        self.assertIn("删除", parser.terminal_error["detail_msg"])

if __name__ == "__main__":
    unittest.main()


