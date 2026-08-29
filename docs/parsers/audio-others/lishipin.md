# 梨视频 (PearVideo) 逆向解析指南

本篇详细记录 **梨视频** 资讯短视频与动态防盗链时间戳解密方案。

---

## 1. 平台特征与支持能力

* **平台标识**：`梨视频`
* **支持媒体类型**：高清资讯视频 (MP4) / 封面图 / 视频标题与作者
* **常见链接形态**：
  * 网页链接：`https://www.pearvideo.com/video_1805408`
* **Cookie 依赖**：无需 Cookie。

---

## 2. 核心逆向流程

1. **提取 Video ID**：从 URL 中提取数字 ID（如 `1805408`）。
2. **防盗链 API 请求**：
   * 接口：`GET https://www.pearvideo.com/videoStatus.jsp?contId={video_id}`
   * 必备 Header：`Referer: https://www.pearvideo.com/video_{video_id}`
3. **动态 URL 拼接替换**：
   * 接口返回伪装的 `srcUrl`，需根据系统时间戳将 URL 中的临时 hash 替换为 `cont-{video_id}` 即可还原真实可播放的 MP4 地址。

---

## 3. 测试与验证

* **样本验证**：`python tests/manual_verify_parsers.py --platform 梨视频`
