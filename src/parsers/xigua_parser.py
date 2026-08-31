from src.parser_factory import register_parser
"""西瓜视频分享解析器。"""

from src.parsers.douyin_parser import DouyinParser


@register_parser("西瓜视频", "今日头条")
class XiguaParser(DouyinParser):
    """西瓜视频及今日头条分享页复用抖音作品详情解析。"""
