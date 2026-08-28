from src.parsers.qianwen_parser import QianwenParser


class QuarkAIParser(QianwenParser):
    """夸克 AI Studio 外部分享作品解析器。

    夸克 AI 与通义千问分享页使用相同的 ``__INITIAL_PROPS__`` 数据结构；
    复用已验证的解析逻辑，同时保留独立的平台标识，便于调用端展示和统计。
    """

