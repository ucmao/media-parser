# 新片场 (Xinpianchang) 逆向解析指南

本篇详细记录影视创作人社区 **新片场** 4K/1080P 高清影视作品的抓取方案。

---

## 1. 平台特征与支持能力

* **平台标识**：`新片场`
* **支持媒体类型**：原画/高清视频 (MP4/HLS) / 作品封面 / 创作人信息
* **常见链接形态**：
  * 网页链接：`https://www.xinpianchang.com/a13792376`
* **Cookie 依赖**：无需 Cookie。

---

## 2. 核心逆向流程

1. **提取文章/视频 ID**：从 URL 中提取 `a\d+` 或 `article_id`。
2. **提取 `__NEXT_DATA__` 或播放器 API**：
   * 新片场使用 Next.js SSR 渲染，从首屏 `__NEXT_DATA__` 中解析视频播放配置；
   * 或调用新片场 API 获取 `video_url` 及多清晰度档位。

---

## 3. 测试与验证

* **单元测试**：[tests/test_xinpianchang_parser.py](file:///Users/leo/Projects/media-parser/tests/test_xinpianchang_parser.py)
* **执行命令**：`pytest tests/test_xinpianchang_parser.py`
