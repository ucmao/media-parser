# 腾讯微视 (Weishi) 逆向解析指南

本篇详细记录腾讯旗下 **微视 (Weishi)** 短视频的抓取方案。

---

## 1. 平台特征与支持能力

* **平台标识**：`微视`
* **支持媒体类型**：无水印视频 (MP4) / 封面图 / 标题
* **常见链接形态**：
  * 分享页：`https://video.weishi.qq.com/5D41bben`
* **Cookie 依赖**：无需 Cookie。

---

## 2. 核心逆向流程

1. **Feed ID 提取**：从短链接路径中提取 `feed_id`（如 `5D41bben`）。
2. **微视开放接口**：
   * 接口：`https://h5.weishi.qq.com/trpc.weishi.weishi_h5_proxy.weishi_h5_proxy/wspersonalfeed`
   * 或调用微视分享落地页获取内置 JSON 状态。
3. **视频提取**：从 `data.feeds[0].video_url` 提取纯净 MP4 直链。

---

## 3. 测试与验证

* **样本验证**：`python tests/manual_verify_parsers.py --platform 微视`
