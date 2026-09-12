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


if __name__ == "__main__":
    unittest.main()


