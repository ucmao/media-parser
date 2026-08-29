# 汽水音乐 (Qishui Music) 逆向解析指南

本篇详细记录字节跳动旗下 **汽水音乐** UGC 视频与背景原声音频的提取方案。

---

## 1. 平台特征与支持能力

* **平台标识**：`汽水音乐`
* **支持媒体类型**：高清 UGC 视频 (MP4) / 歌曲完整音频 (MP3) / 专辑封面 / 歌曲名称与作者
* **常见链接形态**：
  * 分享短链：`https://qishui.douyin.com/s/iX21ep91/`
* **Cookie 依赖**：无需 Cookie。

---

## 2. 核心逆向流程

1. **302 跳转获取真实 Item ID**：跟随短链跳转至 `qishui.douyin.com/track/...` 或 `video/...`。
2. **字节系音乐接口调用**：
   * 请求汽水音乐 Web 端曲目详情接口。
3. **媒体分离提取**：
   * `audio_url`：提取无损或高码率音频直链；
   * `video_url`：提取 UGC 伴随视频直链。

---

## 3. 测试与验证

* **单元测试**：[tests/test_qsmusic_parser.py](file:///Users/leo/Projects/media-parser/tests/test_qsmusic_parser.py)
* **执行命令**：`pytest tests/test_qsmusic_parser.py`
