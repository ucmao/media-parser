# 微信视频号 (WeChat Channels) 逆向解析指南

本篇详细记录 **微信视频号** 分享短链的解析方案。

---

## 1. 平台特征与支持能力

* **平台标识**：`视频号` / `微信视频号`
* **支持媒体类型**：无水印短视频 (MP4) / 封面图 / 创作者昵称
* **常见链接形态**：
  * 视频号短链：`https://weixin.qq.com/sph/AzGrUgqzFv`
* **Cookie 依赖**：无需 Cookie。

---

## 2. 核心逆向流程

1. **302 跟随跳转**：请求视频号短链获取落地页。
2. **提取视频流与作者信息**：
   * 从 H5 落地页 HTML 或元数据中解析高清 MP4 播放地址与封面。

---

## 3. 测试与验证

* **单元测试**：[tests/test_wechat_channels_parser.py](file:///Users/leo/Projects/media-parser/tests/test_wechat_channels_parser.py)
* **执行命令**：`pytest tests/test_wechat_channels_parser.py`
