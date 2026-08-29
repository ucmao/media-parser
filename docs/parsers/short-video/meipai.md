# 美拍 (Meipai) 逆向解析指南

本篇详细记录 **美拍** 短视频的网页提取与解密方案。

---

## 1. 平台特征与支持能力

* **平台标识**：`美拍`
* **支持媒体类型**：无水印视频 (MP4) / 封面图 / 视频标题
* **常见链接形态**：
  * 视频页：`http://www.meipai.com/video/533/6777602107506448933`
* **Cookie 依赖**：无需 Cookie。

---

## 2. 核心逆向流程

1. **HTML 提取**：请求美拍落地页 HTML 内容。
2. **Base64 / 混淆解密**：
   * 早期美拍将视频地址编码在 `data-video` 属性中，结合特定的 Base64 替换字典解码为真实 MP4 直链。
3. **备用正则匹配**：直接从 HTML 中匹配 `video` 标签或 `mp4` 源地址。

---

## 3. 测试与验证

* **单元测试**：[tests/test_meipai_parser.py](file:///Users/leo/Projects/media-parser/tests/test_meipai_parser.py)
* **执行命令**：`pytest tests/test_meipai_parser.py`
