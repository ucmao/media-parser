# 虎牙 (Huya) 逆向解析指南

本篇详细记录 **虎牙直播 / 虎牙短视频** 录播与视频切片的抓取方案。

---

## 1. 平台特征与支持能力

* **平台标识**：`虎牙`
* **支持媒体类型**：高清视频 (MP4/HLS) / 封面图 / 视频标题
* **常见链接形态**：
  * 短链接：`https://hy.fan/v3cwMK`
* **Cookie 依赖**：无需 Cookie。

---

## 2. 核心逆向流程

1. **302 跳转提取视频 ID**：跟随短链跳转至虎牙视频真实落地页。
2. **提取视频播放流**：
   * 从落地页 HTML 中提取 `<video>` 源或调用虎牙短视频接口获取 MP4 直链。

---

## 3. 测试与验证

* **单元测试**：[tests/test_huya_parser.py](file:///Users/leo/Projects/media-parser/tests/test_huya_parser.py)
* **执行命令**：`pytest tests/test_huya_parser.py`
