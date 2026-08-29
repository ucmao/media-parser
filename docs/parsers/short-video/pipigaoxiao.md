# 皮皮搞笑 (Pipigaoxiao) 逆向解析指南

本篇详细记录 **皮皮搞笑** 帖子短视频与搞笑内容的逆向提取方案。

---

## 1. 平台特征与支持能力

* **平台标识**：`皮皮搞笑`
* **支持媒体类型**：无水印视频 (MP4) / 帖子标题 / 封面
* **常见链接形态**：
  * 移动分享页：`https://h5.pipigx.com/pp/post/815491325984?pid=815491325984&type=post`
* **Cookie 依赖**：无需 Cookie。

---

## 2. 核心逆向流程

1. **ID 提取**：从 Query 参数或 Path 中提取 `pid` / `post_id`。
2. **H5 数据接口**：
   * 接口：`POST https://api.pipigx.com/ppapi/cell/detail`
   * 或直接在 H5 落地页 HTML 中提取内嵌 JSON。
3. **视频直链提取**：从 `post.video.video_download_url` 或 `post.video.video_url` 中提取 MP4 直链。

---

## 3. 测试与验证

* **样本验证**：`python tests/manual_verify_parsers.py --platform 皮皮搞笑`
