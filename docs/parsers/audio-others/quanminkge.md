# 全民K歌 (Quanmin K-Song) 逆向解析指南

本篇详细记录腾讯旗下 **全民K歌** K歌录音、MV 视频及伴奏音频的提取方案。

---

## 1. 平台特征与支持能力

* **平台标识**：`全民K歌`
* **支持媒体类型**：K歌 MV 视频 (MP4) / 录音音频 (M4A/MP3) / 歌曲封面与演唱者
* **常见链接形态**：
  * 播放页：`https://static-play.kg.qq.com/node/on3NDg1SU2/play_v2?s=rv8cHFpUTXw32p0l`
* **Cookie 依赖**：无需 Cookie。

---

## 2. 核心逆向流程

1. **提取歌曲 ShareID (`s`)**：从 Query 中提取 `s` 参数。
2. **H5 落地页内嵌数据解析**：
   * 请求 `play_v2` 页面，正则提取 `window.__DATA__`。
3. **提取音视频直链**：
   * 从 `playurl_video` 提取高清 MV 视频；
   * 从 `playurl` 提取纯音频录音。

---

## 3. 测试与验证

* **单元测试**：[tests/test_quanminkge_parser.py](file:///Users/leo/Projects/media-parser/tests/test_quanminkge_parser.py)
* **执行命令**：`pytest tests/test_quanminkge_parser.py`
