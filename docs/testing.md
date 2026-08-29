# 测试体系与回归验证指南 (Testing Guide)

本项目拥有完备的多层级测试体系，涵盖**单元测试 (Unit Tests)**、**API 契约测试 (Contract Tests)**、**真实网络样本回归 (Live Regression Tests)** 以及 **交互式手动验证工具**。

---

## 🧪 测试套件分层

```text
tests/
├── test_api_contract.py            # API 统一契约与错误码断言测试
├── test_api_video_compat.py        # 兼容性测试
├── test_parser_factory.py          # 解析器自动注册与工厂路由测试
├── test_web_fetcher.py             # 302跳转与URL正则提取测试
├── test_*_parser.py                # 各平台专属的单元测试
├── live_parser_samples.json        # 真实线上验证样本库 (30+ 平台活跃样例)
├── test_live_parser_samples.py     # 自动化执行样本库回归测试
└── manual_verify_parsers.py        # 命令行交互式/全量人工排查脚本
```

---

## 🚀 常用测试命令

### 1. 运行所有基础单元测试
用于日常开发与 CI 流程，速度极快（使用 Mock 或本地逻辑）：
```bash
pytest
```

### 2. 运行指定平台的测试
调试某个特定解析器时使用：
```bash
# 测试抖音解析器
pytest tests/test_douyin_parser.py -v

# 测试小红书解析器
pytest tests/test_xiaohongshu_parser.py -v

# 测试 B 站解析器
pytest tests/test_bilibili_parser.py -v
```

### 3. 运行真实线上样例回归测试 (Live Tests)
通过 [tests/live_parser_samples.json](file:///Users/leo/Projects/media-parser/tests/live_parser_samples.json) 中的真实链接，发起实际网络请求测试各大平台的可用性：
```bash
pytest tests/test_live_parser_samples.py -s
```

### 4. 运行交互式手动验证脚本
[tests/manual_verify_parsers.py](file:///Users/leo/Projects/media-parser/tests/manual_verify_parsers.py) 提供了一个美观的终端报告：
```bash
# 全量验证所有平台当前线上可用状态
python tests/manual_verify_parsers.py --all

# 验证单个平台 (例如：抖音)
python tests/manual_verify_parsers.py --platform 抖音
```

---

## 📝 如何为新平台添加测试用例？

当你开发了一个新的解析器（例如 `NewPlatformParser`）时，请按以下两步补齐测试：

### 步骤 1：添加专属单元测试 (`tests/test_newplatform_parser.py`)
```python
import pytest
from src.parsers.newplatform_parser import NewPlatformParser

def test_newplatform_parser_success(monkeypatch):
    # 构造假数据或测试实例
    parser = NewPlatformParser("https://example.com/item/12345")
    assert parser.get_title_content() is not None
```

### 步骤 2：在 `tests/live_parser_samples.json` 登记真实测试样例
```json
{
  "platform": "新平台",
  "url": "https://example.com/share/xxxx",
  "media_types": ["video"],
  "expected_fields": ["video", "cover", "title", "author"],
  "note": "2026-08-29 已验证"
}
```
登记后，自动化回归测试脚本将自动纳入该平台的持续健康检查。
