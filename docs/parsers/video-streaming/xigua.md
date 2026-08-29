# 西瓜视频 (Xigua) 逆向解析指南

本篇详细记录字节跳动旗下 **西瓜视频** 中长视频的解析与继承机制。

---

## 1. 平台特征与支持能力

* **平台标识**：`西瓜视频`
* **支持媒体类型**：高清视频 (MP4) / 封面图 / 视频标题与作者
* **常见链接形态**：
  * 分享链接：`https://v.douyin.com/Nid-fFF_sdI/`
  * 网页链接：`https://www.ixigua.com/7676450021063735414`
* **Cookie 依赖**：无需 Cookie。

---

## 2. 核心架构与继承实现

西瓜视频底层与抖音共享字节跳动的 **Aweme / TTVideo** 视频分发网络与相同的 `a_bogus` 鉴权体系。[XiguaParser](file:///Users/leo/Projects/media-parser/src/parsers/xigua_parser.py) 继承自 `DouyinParser`：

```python
from src.parser_factory import register_parser
from src.parsers.douyin_parser import DouyinParser

@register_parser("西瓜视频")
class XiguaParser(DouyinParser):
    """西瓜视频复用字节跳动核心解析与 a_bogus 签名引擎。"""
```

---

## 3. 测试与验证

* **单元测试**：[tests/test_xigua_parser.py](file:///Users/leo/Projects/media-parser/tests/test_xigua_parser.py)
* **执行命令**：`pytest tests/test_xigua_parser.py`
