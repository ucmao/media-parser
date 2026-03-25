from src.parsers.xiaohongshu_parser import XiaohongshuParser
from src.parsers.douyin_parser import DouyinParser
from src.parsers.kuaishou_parser import KuaishouParser
from src.parsers.bilibili_parser import BilibiliParser
from src.parsers.haokan_parser import HaokanParser
from src.parsers.weishi_parser import WeishiParser
from src.parsers.lishipin_parser import LishipinParser
from src.parsers.pipigaoxiao_parser import PipigaoxiaoParser
from src.parsers.acfun_parser import AcfunParser
from src.parsers.instagram_parser import InstagramParser
from src.parsers.tiktok_parser import TiktokParser
from src.parsers.twitter_parser import TwitterParser
from src.parsers.weibo_parser import WeiboParser
from src.parsers.xigua_parser import XiguaParser
from src.parsers.youtube_parser import YoutubeParser
from src.parsers.zhihu_parser import ZhihuParser
from src.parsers.doupai_parser import DoupaiParser
from src.parsers.huya_parser import HuyaParser
from src.parsers.lvzhou_parser import LvzhouParser
from src.parsers.meipai_parser import MeipaiParser
from src.parsers.pipixia_parser import PipixiaParser
from src.parsers.quanmin_parser import QuanminParser
from src.parsers.quanminkge_parser import QuanminkgeParser
from src.parsers.sixroom_parser import SixroomParser
from src.parsers.xinpianchang_parser import XinpianchangParser
from src.parsers.zuiyou_parser import ZuiyouParser

class ParserFactory:
    platform_to_parser = {
        "小红书": XiaohongshuParser,
        "抖音": DouyinParser,
        "快手": KuaishouParser,
        "哔哩哔哩": BilibiliParser,
        "好看视频": HaokanParser,
        "微视": WeishiParser,
        "梨视频": LishipinParser,
        "皮皮搞笑": PipigaoxiaoParser,
        "AcFun": AcfunParser,
        "Instagram": InstagramParser,
        "TikTok": TiktokParser,
        "Twitter": TwitterParser,
        "微博": WeiboParser,
        "西瓜视频": XiguaParser,
        "YouTube": YoutubeParser,
        "知乎": ZhihuParser,
        "逗拍": DoupaiParser,
        "虎牙": HuyaParser,
        "绿洲": LvzhouParser,
        "美拍": MeipaiParser,
        "皮皮虾": PipixiaParser,
        "全民小视频": QuanminParser,
        "全民K歌": QuanminkgeParser,
        "六间房": SixroomParser,
        "新片场": XinpianchangParser,
        "最右": ZuiyouParser
    }

    @staticmethod
    def create_parser(platform, real_url):
        parser_class = ParserFactory.platform_to_parser.get(platform)

        return parser_class(real_url)

