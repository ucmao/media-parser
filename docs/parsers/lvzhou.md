# 绿洲 (Lvzhou) 逆向解析指南

本篇详细记录新浪微博旗下 **绿洲 (Oasis)** 图文与生活帖子的逆向提取方案。

---

## 1. 平台特征与支持能力

* **平台标识**：`绿洲`
* **支持媒体类型**：高清图集 (JPEG/PNG) / 动态正文 / 作者信息
* **常见链接形态**：
  * 移动分享：`https://oasis.weibo.cn/v1/h5/share?sid=4641407099208582`
* **Cookie 依赖**：无需 Cookie。

---

## 2. 核心逆向流程

1. **提取 SID**：从 Query 参数中提取绿洲动态的唯一编号 `sid`。
2. **HTML SSR 解析**：
   * 请求绿洲 H5 分享页。
   * 解析 HTML 中的正文与图片相册列表，提取最高清大图 CDN 链接。

---

## 3. 测试与验证

* **单元测试**：[tests/test_lvzhou_parser.py](file:///Users/leo/Projects/media-parser/tests/test_lvzhou_parser.py)
* **执行测试**：`pytest tests/test_lvzhou_parser.py`
