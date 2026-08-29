# AcFun 弹幕视频网逆向解析指南

本篇详细记录 **AcFun (A站)** 视频页面与 KSPlayer 播放器参数的逆向提取方案。

---

## 1. 平台特征与支持能力

* **平台标识**：`AcFun`
* **支持媒体类型**：高清视频流 (m3u8 / MP4) / 视频封面 / UP主信息
* **常见链接形态**：
  * 网页长链：`https://www.acfun.cn/v/ac43445963`
* **Cookie 依赖**：无需 Cookie。

---

## 2. 核心逆向流程

1. **提取 AC 号**：从 URL 中通过正则匹配 `ac\d+`。
2. **提取页面内嵌 `window.pageInfo`**：
   * 请求 A 站视频页，通过正则匹配 `window.pageInfo = ({.*?});`。
3. **解析 KSPlayer 播放器参数 (`ksPlayJson`)**：
   * 从 `currentVideoInfo.ksPlayJson` 中解析出流媒体自适应清单 `adaptationSet`。
   * 提取 `representation[0].url` 获取最高清视频播放流地址。

---

## 3. 测试与验证

* **单元测试**：[tests/test_base_parser.py](file:///Users/leo/Projects/media-parser/tests/test_base_parser.py)
* **样本验证**：`python tests/manual_verify_parsers.py --platform AcFun`
