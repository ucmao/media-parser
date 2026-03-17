from src.downloaders.xiaohongshu_downloader import XiaohongshuDownloader
from src.downloaders.douyin_downloader import DouyinDownloader
from src.downloaders.kuaishou_downloader import KuaishouDownloader
from src.downloaders.bilibili_downloader import BilibiliDownloader
from src.downloaders.haokan_downloader import HaokanDownloader
from src.downloaders.weishi_downloader import WeishiDownloader
from src.downloaders.lishipin_downloader import LishipinDownloader
from src.downloaders.pipigaoxiao_downloader import PipigaoxiaoDownloader
from src.downloaders.acfun_downloader import AcfunDownloader
from src.downloaders.instagram_downloader import InstagramDownloader
from src.downloaders.tiktok_downloader import TiktokDownloader
from src.downloaders.twitter_downloader import TwitterDownloader
from src.downloaders.weibo_downloader import WeiboDownloader
from src.downloaders.xigua_downloader import XiguaDownloader
from src.downloaders.youtube_downloader import YoutubeDownloader
from src.downloaders.zhihu_downloader import ZhihuDownloader


class DownloaderFactory:
    platform_to_downloader = {
        "小红书": XiaohongshuDownloader,
        "抖音": DouyinDownloader,
        "快手": KuaishouDownloader,
        "哔哩哔哩": BilibiliDownloader,
        "好看视频": HaokanDownloader,
        "微视": WeishiDownloader,
        "梨视频": LishipinDownloader,
        "皮皮搞笑": PipigaoxiaoDownloader,
        "AcFun": AcfunDownloader,
        "Instagram": InstagramDownloader,
        "TikTok": TiktokDownloader,
        "Twitter": TwitterDownloader,
        "微博": WeiboDownloader,
        "西瓜视频": XiguaDownloader,
        "YouTube": YoutubeDownloader,
        "知乎": ZhihuDownloader
    }

    @staticmethod
    def create_downloader(platform, real_url):
        downloader_class = DownloaderFactory.platform_to_downloader.get(platform)

        return downloader_class(real_url)

