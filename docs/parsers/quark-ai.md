# 夸克 AI (Quark AI) 逆向解析指南

本篇详细记录阿里巴巴旗下 **夸克 AI (Quark AI)** 分享作品的解析方案与复用继承架构。

---

## 1. 平台特征与支持能力

* **平台标识**：`夸克AI`
* **支持媒体类型**：
  * AI 创作图集 (PNG/JPEG)
  * AI 生成内容与提示词
* **常见链接形态**：
  * 分享落地页：`https://act.quark.cn/apps/sharepages/routes/share?biz_id=ai_chat_v2&share_id=3aeb87e5f7214ecbb54881903cd02a23`
* **Cookie 依赖**：无需 Cookie。

---

## 2. 架构设计：底层复用与平台隔离

阿里巴巴旗下夸克 AI 的分享页面底层与通义千问（Qwen）共享相同的 **AI Studio** 基础设施与前端渲染协议（均采用 `window.__INITIAL_PROPS__` 注入方式）。

为了减少重复代码并维持整洁的代码库，[QuarkAIParser](file:///Users/leo/Projects/media-parser/src/parsers/quark_ai_parser.py) 采用了 **继承复用** 模式：

```python
from src.parser_factory import register_parser
from src.parsers.qianwen_parser import QianwenParser

@register_parser("夸克AI")
class QuarkAIParser(QianwenParser):
    """夸克 AI 与通义千问分享页使用相同的数据结构，完全复用核心解析逻辑。"""
```

---

## 3. 测试与验证

* **单元测试**：[tests/test_quark_ai_parser.py](file:///Users/leo/Projects/media-parser/tests/test_quark_ai_parser.py)
* **执行测试**：
  ```bash
  pytest tests/test_quark_ai_parser.py
  python tests/manual_verify_parsers.py --platform 夸克AI
  ```
