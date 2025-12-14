from src.downloaders.xiaohongshu_downloader import XiaohongshuDownloader
from src.downloaders.douyin_downloader import DouyinDownloader
from src.downloaders.kuaishou_downloader import KuaishouDownloader
from src.downloaders.bilibili_downloader import BilibiliDownloader
from src.downloaders.haokan_downloader import HaokanDownloader
from src.downloaders.weishi_downloader import WeishiDownloader
from src.downloaders.lishipin_downloader import LishipinDownloader
from src.downloaders.pipigaoxiao_downloader import PipigaoxiaoDownloader


class DownloaderFactory:
    platform_to_downloader = {
        "小红书": XiaohongshuDownloader,
        "抖音": DouyinDownloader,
        "快手": KuaishouDownloader,
        "哔哩哔哩": BilibiliDownloader,
        "好看视频": HaokanDownloader,
        "微视": WeishiDownloader,
        "梨视频": LishipinDownloader,
        "皮皮搞笑": PipigaoxiaoDownloader
    }

    @staticmethod
    def create_downloader(platform, real_url):
        downloader_class = DownloaderFactory.platform_to_downloader.get(platform)

        return downloader_class(real_url)

