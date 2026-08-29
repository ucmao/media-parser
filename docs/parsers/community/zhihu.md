# 知乎 (Zhihu) 逆向解析指南

本篇详细记录知乎问答（Answer）、专栏文章（Article）、视频（Zvideo）与想法（Pin / Video Pin）的多形态解析方案。

---

## 1. 平台特征与支持能力

* **平台标识**：`知乎`
* **支持媒体类型**：
  * 知乎视频 (MP4) 与 Video Pin
  * 专栏文章 / 想法图集
  * 问答回答正文与作者信息
* **常见链接形态**：
  * 想法：`https://www.zhihu.com/pin/2066168388699807826`
  * 视频：`https://www.zhihu.com/zvideo/12345678`
  * 问答：`https://www.zhihu.com/question/123/answer/456`
* **Cookie 依赖**：无需 Cookie。

---

## 2. 核心逆向流程

### 2.1 多形态路由分发 (`_extract_content_id`)
通过正则表达式自动识别链接类型：
* `answer` ➔ `api.zhihu.com/answers/{id}`
* `zvideo` ➔ `api.zhihu.com/videos/{id}`
* `pin` ➔ `api.zhihu.com/pins/{id}`
* `article` ➔ `api.zhihu.com/articles/{id}`

### 2.2 媒体提取规则
* **视频提取**：从 `attachment.video` 或 `video_info` 中解析清晰度播放列表 `playlist`，优先挑选 `HD` / `SD` 直链。
* **图文提取**：从正文 HTML 中通过 BeautifulSoup 提取 `<img>` 标签的 `data-original` 或 `data-actualsrc` 原图。

---

## 3. 测试与验证

* **单元测试**：[tests/test_zhihu_parser.py](file:///Users/leo/Projects/media-parser/tests/test_zhihu_parser.py)
* **执行命令**：`pytest tests/test_zhihu_parser.py`
