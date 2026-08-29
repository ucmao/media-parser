import importlib
import pkgutil
from typing import Dict, Type
import src.parsers
from src.parsers.base_parser import BaseParser


class ParserFactory:
    platform_to_parser: Dict[str, Type[BaseParser]] = {}
    _discovered = False

    @classmethod
    def register(cls, platform: str, parser_class: Type[BaseParser]):
        """显式注册一个 Parser 类。"""
        cls.platform_to_parser[platform] = parser_class

    @classmethod
    def _discover(cls):
        """自动扫描并载入 src.parsers 下的所有解析器模块。"""
        if cls._discovered:
            return
        cls._discovered = True
        package = src.parsers
        for _, module_name, _ in pkgutil.iter_modules(package.__path__):
            if module_name != "base_parser" and not module_name.startswith("_"):
                importlib.import_module(f"src.parsers.{module_name}")

    @classmethod
    def get_parser_class(cls, platform: str):
        cls._discover()
        return cls.platform_to_parser.get(platform)

    @classmethod
    def create_parser(cls, platform: str, real_url: str):
        cls._discover()
        parser_class = cls.platform_to_parser.get(platform)
        if parser_class is None:
            raise ValueError(f"不支持的平台：{platform}")
        return parser_class(real_url)


def register_parser(*platform_names: str):
    """用于装饰器注册 Parser 的方法。

    示例:
        @register_parser("抖音")
        class DouyinParser(BaseParser):
            ...
    """
    def decorator(cls):
        for name in platform_names:
            ParserFactory.register(name, cls)
        return cls
    return decorator


# 确保在需要时通过 get_parser_class/create_parser 懒加载发现解析器

