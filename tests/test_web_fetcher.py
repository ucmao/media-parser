import unittest
from unittest.mock import Mock, patch

import requests

from utils.web_fetcher import UrlParser, WebFetcher


class UrlParserTest(unittest.TestCase):
    def test_extracts_url_from_share_text(self):
        text = "复制打开应用 https://v.douyin.com/abc123/ 查看作品"
        self.assertEqual(UrlParser.get_url(text), "https://v.douyin.com/abc123/")

    def test_get_url_handles_non_string_values(self):
        for value in (None, 1, {}, []):
            with self.subTest(value=value):
                self.assertIsNone(UrlParser.get_url(value))

    def test_preserves_only_platform_specific_query_parameters(self):
        cases = [
            ("https://haokan.baidu.com/v?vid=11&noise=x", "https://haokan.baidu.com/v?vid=11"),
            ("https://isee.weishi.qq.com/ws/app-pages/share/index.html?id=22&noise=x", "https://isee.weishi.qq.com/ws/app-pages/share/index.html?id=22"),
            ("https://www.xiaohongshu.com/explore/33?xsec_token=token&noise=x", "https://www.xiaohongshu.com/explore/33?xsec_token=token"),
            ("https://www.douyin.com/?modal_id=44&noise=x", "https://www.douyin.com?modal_id=44"),
            ("https://www.iesdouyin.com/share/video/123/?ep_id=555&noise=x", "https://www.iesdouyin.com/share/video/123?ep_id=555"),
            ("https://www.douyin.com/lvdetail/7677129845654061595?noise=x", "https://www.douyin.com/lvdetail/7677129845654061595"),
            ("https://kg.qq.com/node/play?s=66&noise=x", "https://kg.qq.com/node/play?s=66"),
            ("https://izuiyou.com/post/detail?pid=77&noise=x", "https://izuiyou.com/post/detail?pid=77"),
            ("https://weixin.qq.com/sph/AzGrUgqzFv?noise=x", "https://weixin.qq.com/sph/AzGrUgqzFv"),
            (
                "https://klingai-share.kuaishou.com/h5-app/share?creative_id=123&work_id=123&creative_type=WORK&noise=x",
                "https://klingai-share.kuaishou.com/h5-app/share?creative_id=123&work_id=123&creative_type=WORK",
            ),
            (
                "https://w13.soulsmile.cn/activity/#/web/topic/detail?postIdEcpt=post&sign=signature&signVersion=0.0.1&noise=x",
                "https://w13.soulsmile.cn/activity#/web/topic/detail?postIdEcpt=post&sign=signature&signVersion=0.0.1",
            ),
            (
                "https://music.douyin.com/qishui/share/ugc_video?ugc_video_id=123&noise=x",
                "https://music.douyin.com/qishui/share/ugc_video?ugc_video_id=123",
            ),
            (
                "https://i2.y.qq.com/n3/other/pages/details/mv.html?vid=012XViNT0znYUR&noise=x",
                "https://i2.y.qq.com/n3/other/pages/details/mv.html?vid=012XViNT0znYUR",
            ),
            (
                "https://fn.music.163.com/g/mlog/mlog-mobile/landing/mlog?id=a123&type=2&userid=456&noise=x",
                "https://fn.music.163.com/g/mlog/mlog-mobile/landing/mlog?id=a123&userid=456&type=2",
            ),
            (
                "https://music.163.com/#/song?id=3383347615&noise=x",
                "https://music.163.com/song?id=3383347615",
            ),
            ("https://pd.qq.com/s/code?b=2&noise=x", "https://pd.qq.com/s/code?b=2"),
            ("https://video.weibo.com/show?fid=1034:123&noise=x", "https://video.weibo.com/show?fid=1034%3A123"),
            (
                "https://lv.ulikecam.com/activity/lv/sharevideo?template_id=123&item_type=0&noise=x",
                "https://lv.ulikecam.com/activity/lv/sharevideo?template_id=123&item_type=0",
            ),
            (
                "https://channels.weixin.qq.com/finder-preview/pages/sph?id=AzGrUgqzFv&noise=x",
                "https://channels.weixin.qq.com/finder-preview/pages/sph?id=AzGrUgqzFv",
            ),
            (
                "https://pages.quark.cn/r/ai-studio-mobile/external-share?shareId=abc&authorId=author&channel_from=ucpro&noise=x",
                "https://pages.quark.cn/r/ai-studio-mobile/external-share?shareId=abc&authorId=author&channel_from=ucpro",
            ),
            (
                "https://activity.qianwen.com/r/ai-studio-mobile/qwen-external-share?shareId=abc&authorId=author&channel_from=qwen&noise=x",
                "https://activity.qianwen.com/r/ai-studio-mobile/qwen-external-share?shareId=abc&authorId=author&channel_from=qwen",
            ),
            (
                "https://yuanbao.tencent.com/bot/app/share/beautifulPhotos/share-id?userId=user-id&noise=x",
                "https://yuanbao.tencent.com/bot/app/share/beautifulPhotos/share-id?userId=user-id",
            ),
            (
                "https://mobile.yangkeduo.com/goods.html?goods_id=123&review_id=456&noise=x",
                "https://mobile.yangkeduo.com/goods.html?goods_id=123&review_id=456",
            ),
            (
                "https://mobile.yangkeduo.com/fyxmkief.html?feed_id=789&noise=x",
                "https://mobile.yangkeduo.com/fyxmkief.html?feed_id=789",
            ),
        ]
        for original, expected in cases:
            with self.subTest(original=original):
                self.assertEqual(UrlParser.extract_video_address(original), expected)

    def test_get_video_id_supports_query_path_and_html_suffix(self):
        cases = [
            ("https://www.doubao.com/video-sharing?video_id=video-id", "video-id"),
            ("https://klingai-share.kuaishou.com/h5-app/share?creative_id=123", "123"),
            ("https://w13.soulsmile.cn/activity#/web/topic/detail?postIdEcpt=post", "post"),
            ("https://music.douyin.com/qishui/share/ugc_video?ugc_video_id=123", "123"),
            ("https://www.douyin.com/lvdetail/7677129845654061595", "7677129845654061595"),
            ("https://www.iesdouyin.com/share/video/999?ep_id=7677129845654061595", "7677129845654061595"),
            ("https://lv.ulikecam.com/activity/lv/sharevideo?template_id=123", "123"),
            ("https://www.bilibili.com/video/BV123", "BV123"),
            ("https://www.pearvideo.com/video_123.html", "video_123"),
            ("https://mobile.yangkeduo.com/fyxmkief.html?feed_id=6960355310530660128", "6960355310530660128"),
            ("https://mobile.yangkeduo.com/goods.html?goods_id=935025706654", "935025706654"),
            ("https://mobile.yangkeduo.com/goods.html?ps=X1JcF4pgqU", "X1JcF4pgqU"),
        ]
        for url, expected in cases:
            with self.subTest(url=url):
                self.assertEqual(UrlParser.get_video_id(url), expected)

    def test_converts_only_http_urls(self):
        self.assertEqual(UrlParser.convert_to_https("http://example.com/a"), "https://example.com/a")
        self.assertEqual(UrlParser.convert_to_https("https://example.com/a"), "https://example.com/a")
        self.assertIsNone(UrlParser.convert_to_https(None))

    def test_recognizes_kuaishou_random_mobile_subdomains(self):
        self.assertEqual(
            UrlParser.get_platform("https://random-value.m.chenzhongtech.com/fw/photo/123"),
            "快手",
        )

    def test_rejects_domains_that_only_resemble_kuaishou_mobile_subdomains(self):
        unsupported_urls = [
            "https://random-value.m.chenzhongtech.com.evil.example/fw/photo/123",
            "https://random-valuem.chenzhongtech.com/fw/photo/123",
            "https://fakechenzhongtech.com/fw/photo/123",
        ]
        for url in unsupported_urls:
            with self.subTest(url=url):
                self.assertIsNone(UrlParser.get_platform(url))

    def test_recognizes_wechat_channels_domains(self):
        self.assertEqual(UrlParser.get_platform("https://weixin.qq.com/sph/AzGrUgqzFv"), "视频号")
        self.assertEqual(
            UrlParser.get_platform("https://channels.weixin.qq.com/finder-preview/pages/sph?id=abc"),
            "视频号",
        )
        self.assertEqual(
            UrlParser.get_platform("https://finder.video.qq.com/251/20302/stodownload?encfilekey=abc"),
            "视频号",
        )

    def test_recognizes_supplemented_domain_variants(self):
        cases = [
            ("https://sv.baidu.com/videoui/page/videoland?context=abc", "好看视频"),
            ("https://baijiahao.baidu.com/s?id=123", "好看视频"),
            ("https://m.baidu.com/sf/v_search?pd=video", "好看视频"),
            ("https://mbd.baidu.com/newspage/data/videolanding?nid=123", "好看视频"),
            ("https://m.toutiao.com/is/669xD9UIQfI/", "今日头条"),
            ("https://www.toutiao.com/video/123/", "今日头条"),
            ("https://qianwen.my.cn/share/chat/e16bbf94a34d4b88acd7ed1214f", "通义千问"),
            ("https://pages.tongyi.com/r/share?shareId=123", "通义千问"),
            ("https://xyq.jianying.com/s/abc", "小云雀AI"),
            ("https://jimeng.ai/mproject/123", "即梦AI"),
            ("https://www.capcut.com/template/123", "剪映"),
            ("https://yb.tencent.com/s/share-id", "腾讯元宝"),
            ("https://yuanbao.tencent.com/bot/app/share/loadingVideo/share-id", "腾讯元宝"),
        ]
        for url, expected_platform in cases:
            with self.subTest(url=url):
                self.assertEqual(UrlParser.get_platform(url), expected_platform)

    def test_recognizes_kling_share_domain(self):
        self.assertEqual(
            UrlParser.get_platform("https://klingai-share.kuaishou.com/h5-app/share?creative_id=123"),
            "可灵AI",
        )

    def test_recognizes_hailuo_domains(self):
        self.assertEqual(
            UrlParser.get_platform("https://hailuoai.com/share/ai-video/enbrdg0JlAen?source-scene=shared"),
            "海螺AI",
        )
        self.assertEqual(
            UrlParser.get_platform("https://hailuoai.video/share/ai-video/RkDkwWYZQRby"),
            "海螺AI",
        )

    def test_recognizes_soul_share_domain(self):
        self.assertEqual(UrlParser.get_platform("https://w13.soulsmile.cn/activity/"), "Soul")

    def test_recognizes_qishui_music_domains(self):
        self.assertEqual(UrlParser.get_platform("https://qishui.douyin.com/s/code/"), "汽水音乐")
        self.assertEqual(UrlParser.get_platform("https://music.douyin.com/track/123"), "汽水音乐")

    def test_recognizes_qqmusic_domains(self):
        self.assertEqual(UrlParser.get_platform("https://c6.y.qq.com/base/fcgi-bin/u?__=abc"), "QQ音乐")
        self.assertEqual(UrlParser.get_platform("https://i2.y.qq.com/n3/other/pages/details/mv.html?vid=abc"), "QQ音乐")
        self.assertEqual(UrlParser.get_platform("https://y.qq.com/n/ryqq/mv/abc"), "QQ音乐")

    def test_recognizes_netease_music_domains(self):
        self.assertEqual(UrlParser.get_platform("https://163cn.tv/abc123"), "网易云音乐")
        self.assertEqual(UrlParser.get_platform("https://music.163.com/song?id=1"), "网易云音乐")
        self.assertEqual(UrlParser.get_platform("https://fn.music.163.com/g/mlog/x"), "网易云音乐")

    def test_recognizes_kugou_music_domains(self):
        self.assertEqual(UrlParser.get_platform("https://t1.kugou.com/c/abc"), "酷狗音乐")
        self.assertEqual(UrlParser.get_platform("https://m.kugou.com/mv/?hash=abc"), "酷狗音乐")
        self.assertEqual(UrlParser.get_platform("https://m3ws.kugou.com/mv/?hash=abc"), "酷狗音乐")

    def test_recognizes_peiyinxiu_domains(self):
        self.assertEqual(UrlParser.get_platform("https://www.peiyinxiu.com/m/535482401"), "配音秀")

    def test_recognizes_pinecone_moment_domains(self):
        self.assertEqual(UrlParser.get_platform("https://m.pineconemoment.com/o/4buqAENzZFE"), "松果时刻")

    def test_extracts_kugou_mv_hash_as_video_id(self):
        self.assertEqual(
            UrlParser.get_video_id("https://m.kugou.com/mv/?hash=48da1fe5cbe4f8774f73160042377b1e"),
            "48da1fe5cbe4f8774f73160042377b1e",
        )
        self.assertEqual(
            UrlParser.get_video_id("https://www.kugou.com/mvweb/html/mv_48da1fe5cbe4f8774f73160042377b1e.html"),
            "48da1fe5cbe4f8774f73160042377b1e",
        )

    def test_recognizes_xigua_video_on_iesdouyin_domain(self):
        self.assertEqual(
            UrlParser.get_platform("https://www.iesdouyin.com/xg/video/7676450021063735414/"),
            "西瓜视频",
        )

    def test_recognizes_tencent_channel_domain(self):
        self.assertEqual(UrlParser.get_platform("https://pd.qq.com/s/code?b=2"), "腾讯频道")

    def test_recognizes_weibo_video_domain(self):
        self.assertEqual(UrlParser.get_platform("https://video.weibo.com/show?fid=1034:5336275486703690"), "微博")

    def test_recognizes_jianying_share_domain(self):
        self.assertEqual(UrlParser.get_platform("https://lv.ulikecam.com/activity/lv/sharevideo"), "剪映")

    def test_recognizes_quark_ai_share_domain(self):
        self.assertEqual(
            UrlParser.get_platform("https://pages.quark.cn/r/ai-studio-mobile/external-share?shareId=abc"),
            "夸克AI",
        )
        self.assertEqual(
            UrlParser.get_platform("https://act.quark.cn/apps/sharepages/routes/share?share_id=abc"),
            "夸克AI",
        )

    def test_recognizes_pinduoduo_domains(self):
        for domain in [
            "https://mobile.yangkeduo.com/goods.html?ps=123",
            "https://yangkeduo.com/goods.html?goods_id=123",
            "https://pinduoduo.com/goods.html?goods_id=123",
            "https://www.pinduoduo.com/goods.html?goods_id=123",
            "https://mobile.pinduoduo.com/goods.html?goods_id=123",
        ]:
            with self.subTest(domain=domain):
                self.assertEqual(UrlParser.get_platform(domain), "拼多多")


class WebFetcherTest(unittest.TestCase):
    @staticmethod
    def response(location=None, status_code=200):
        response = Mock(status_code=status_code)
        response.headers = {"location": location} if location else {}
        response.raise_for_status.return_value = None
        return response

    def test_returns_supported_url_without_redirect(self):
        with patch("utils.web_fetcher.requests.get", return_value=self.response()):
            result = WebFetcher.fetch_redirect_url("https://www.douyin.com/video/123?noise=x")
        self.assertEqual(result, "https://www.douyin.com/video/123")

    def test_passes_zhihu_url_through_without_fetching_page(self):
        url = "https://www.zhihu.com/pin/2066168388699807826?native=1"
        with patch("utils.web_fetcher.requests.get") as get:
            result = WebFetcher.fetch_redirect_url(url)
        get.assert_not_called()
        self.assertEqual(result, "https://www.zhihu.com/pin/2066168388699807826")

    def test_passes_lvzhou_url_through_without_fetching_page(self):
        url = "https://oasis.weibo.cn/v1/h5/share?sid=123456789"
        with patch("utils.web_fetcher.requests.get") as get:
            result = WebFetcher.fetch_redirect_url(url)
        get.assert_not_called()
        self.assertEqual(result, url)

    def test_passes_weibo_url_through_without_fetching_page(self):
        url = "https://weibo.com/7352202247/5335900910264179"
        with patch("utils.web_fetcher.requests.get") as get:
            result = WebFetcher.fetch_redirect_url(url)
        get.assert_not_called()
        self.assertEqual(result, url)

    def test_follows_relative_redirect(self):
        responses = [
            self.response("https://www.douyin.com/share/123"),
        ]
        with patch("utils.web_fetcher.requests.get", side_effect=responses):
            result = WebFetcher.fetch_redirect_url("https://short.example/a")
        self.assertEqual(result, "https://www.douyin.com/share/123")

    def test_accepts_kuaishou_random_mobile_subdomain_redirect(self):
        redirect_url = "https://random-value.m.chenzhongtech.com/fw/photo/123?noise=x"
        with patch(
            "utils.web_fetcher.requests.get",
            return_value=self.response(redirect_url),
        ):
            result = WebFetcher.fetch_redirect_url("https://v.kuaishou.com/short-code")
        self.assertEqual(result, "https://random-value.m.chenzhongtech.com/fw/photo/123")

    def test_follows_qqmusic_short_link_and_preserves_mv_id(self):
        redirect_url = (
            "https://i2.y.qq.com/n3/other/pages/details/mv.html"
            "?ADTAG=share&vid=012XViNT0znYUR"
        )
        with patch(
            "utils.web_fetcher.requests.get",
            return_value=self.response(redirect_url),
        ):
            result = WebFetcher.fetch_redirect_url(
                "https://c6.y.qq.com/base/fcgi-bin/u?__=eZmYFaYs9yHY"
            )
        self.assertEqual(
            result,
            "https://i2.y.qq.com/n3/other/pages/details/mv.html?vid=012XViNT0znYUR",
        )

    def test_follows_netease_short_link_and_preserves_event_id(self):
        redirect_url = "https://y.music.163.com/m/event?id=37826361829&uid=5153433584&dlt=0846"
        with patch(
            "utils.web_fetcher.requests.get",
            return_value=self.response(redirect_url),
        ):
            result = WebFetcher.fetch_redirect_url("https://163cn.tv/beBkdACV")
        self.assertEqual(
            result,
            "https://y.music.163.com/m/event?id=37826361829&uid=5153433584",
        )

    def test_follows_kugou_short_link_and_preserves_mv_hash(self):
        redirect_url = (
            "https://m.kugou.com/mv/?hash=48da1fe5cbe4f8774f73160042377b1e"
            "&kgsscty1=link&sruserid=2369252937"
        )
        with patch("utils.web_fetcher.requests.get", return_value=self.response(redirect_url)):
            result = WebFetcher.fetch_redirect_url("https://t1.kugou.com/c/gw3TdYszNaiN")
        self.assertEqual(
            result,
            "https://m.kugou.com/mv?hash=48da1fe5cbe4f8774f73160042377b1e"
            "&sruserid=2369252937&kgsscty1=link",
        )

    def test_stops_before_login_or_verification_page(self):
        for blocked_path in ("/login", "/404", "/captcha", "/verify", "/error"):
            with self.subTest(blocked_path=blocked_path):
                with patch(
                    "utils.web_fetcher.requests.get",
                    return_value=self.response(f"https://www.douyin.com{blocked_path}"),
                ):
                    result = WebFetcher.fetch_redirect_url("https://www.douyin.com/video/123")
                self.assertEqual(result, "https://www.douyin.com/video/123")

    def test_returns_none_for_unsupported_final_domain(self):
        with patch("utils.web_fetcher.requests.get", return_value=self.response()):
            self.assertIsNone(WebFetcher.fetch_redirect_url("https://unsupported.example/a"))

    def test_returns_none_after_redirect_limit(self):
        with patch(
            "utils.web_fetcher.requests.get",
            return_value=self.response("https://unsupported.example/next"),
        ):
            self.assertIsNone(WebFetcher.fetch_redirect_url("https://unsupported.example/start", max_redirects=2))

    def test_returns_none_on_request_error_or_invalid_input(self):
        with patch(
            "utils.web_fetcher.requests.get",
            side_effect=requests.RequestException("network error"),
        ):
            self.assertIsNone(WebFetcher.fetch_redirect_url("https://www.douyin.com/video/1"))
        self.assertIsNone(WebFetcher.fetch_redirect_url(None))
        self.assertIsNone(WebFetcher.fetch_redirect_url("", max_redirects=0))


if __name__ == "__main__":
    unittest.main()
