# Soul 逆向解析指南

本篇详细记录 **Soul App** 瞬间、话题与广场短视频/图文的接口解析方案。

---

## 1. 平台特征与支持能力

* **平台标识**：`Soul`
* **支持媒体类型**：无水印视频 (MP4) / 瞬间高清图集 / 音频瞬间 / 正文与作者
* **常见链接形态**：
  * 话题分享：`https://w13.soulsmile.cn/activity/#/web/topic/detail?postIdEcpt=djB4RGY...`
* **Cookie 依赖**：无需 Cookie。

---

## 2. 核心逆向流程

1. **提取加密帖子标识 (`postIdEcpt`)**：从分享 URL 的 Query 中提取 `postIdEcpt` 及签名版本。
2. **Web 话题详情接口**：
   * 接口：`https://api-h5.soulapp.cn/html6/v2/post/detail`
   * 参数：`postIdEcpt={postIdEcpt}`
3. **数据提取**：
   * 视频：提取 `data.attachments[].video.url` 或 `data.videoUrl`。
   * 图集：提取 `data.attachments[].image.url`。

---

## 3. 测试与验证

* **单元测试**：[tests/test_soul_parser.py](file:///Users/leo/Projects/media-parser/tests/test_soul_parser.py)
* **执行命令**：`pytest tests/test_soul_parser.py`
