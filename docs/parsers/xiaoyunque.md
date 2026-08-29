# 小云雀 AI (Xiaoyunque) 逆向解析指南

本篇详细记录字节跳动剪映旗下 **小云雀 AI (xiaoyunque.jianying.com)** 分享作品的接口抓取机制与参数解析。

---

## 1. 平台特征与支持能力

* **平台标识**：`小云雀AI`
* **支持媒体类型**：
  * AI 创作图集 (PNG/JPEG)
  * 提示词 Prompt、封面与作者信息
* **常见链接形态**：
  * 分享短链：`https://xiaoyunque.jianying.com/s/z_7nWGLGruM/`
* **Cookie 依赖**：公开短链**无需配置 Cookie**。

---

## 2. 核心逆向流程

### 2.1 短链解析与落地页跳转
通过发起 GET 请求跟踪 302 跳转，从小云雀长链接中提取 Query 参数字典 `qdict`。

### 2.2 核心数据接口
* **接口地址**：
  `GET/POST https://xiaoyunque.jianying.com/luckycat/cn/jianying/campaign/v1/pippit/share/landing_page`
* **请求头**：
  * `User-Agent`: 现代浏览器 UA
  * `Accept`: `application/json, text/plain, */*`
* **提取数据**：
  * 从返回的 `data.item_info` 或 `data.share_info` 中提取高清图集 URL 与封面。

---

## 3. 测试与验证

* **单元测试**：[tests/test_xiaoyunque_parser.py](file:///Users/leo/Projects/media-parser/tests/test_xiaoyunque_parser.py)
* **执行测试**：
  ```bash
  pytest tests/test_xiaoyunque_parser.py
  python tests/manual_verify_parsers.py --platform 小云雀AI
  ```
