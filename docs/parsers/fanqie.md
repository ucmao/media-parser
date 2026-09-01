# 番茄小说 / 红果短剧 / 红果漫剧 / 木叶短剧逆向解析指南

本篇详细记录 **番茄小说**、**红果短剧**、**红果漫剧**与**木叶短剧**推广落地页的逆向提取方案及 Referer 防盗链注意事项。

---

## 1. 平台特征与支持能力

* **支持平台标识**：`番茄小说` / `红果短剧` / `红果漫剧` / `木叶短剧`
* **支持媒体类型**：高清视频 (MP4) / 剧集封面 / 剧集标题
* **常见链接形态**：
  * 红果短剧：`https://novelquickapp.com/s/xCkhRnNOiTc/`
  * 番茄小说：`https://changdunovel.com/t/byybBzZfKbg/`
  * 红果漫剧：`https://kylin.hainanyuyue.com/s/bR1qzzEd1A0/`
  * 木叶短剧：`https://hainanyuyue.com/`
* **Cookie 依赖**：无需 Cookie

---

## 2. 核心逆向流程

1. **重定向追踪**：短链 302 重定向至字节跳动 `video-animation-share` 推广落地页 (`/ug/pages/video-animation-share?...`)。
2. **提取 HTML 内嵌 JSON 结构**：
   * 页面脚本中包含 `window._ROUTER_DATA` 结构化对象；
   * 从 `loaderData['video-animation-share_page']['pageData']['series_data']` 提取 `title` 与 `play_url`；
   * 备选兜底：解析 HTML `<meta property="og:url">` 与 `<meta property="og:image">`。

---

## 3. ⚠️ 重要发现：CDN Referer 防盗链机制

字节跳动短剧 CDN 域名（`qznovel.com` / `fqnovel.com` / `qznovelvod.com`）开启了严格的 **Referer 防盗链校验**。

### 表现与排查结论
* **带第三方 Referer 访问**（如从第三方网页直接点击链接）：CDN 返回 **HTTP 403 Forbidden**，导致浏览器/播放器显示“无法播放”。
* **无 Referer 访问 (No Referer)**：CDN 返回 **HTTP 200 OK**，视频可 100% 正常播放与下载。

### 客户端/前端接入注意事项
前端在渲染或提供视频播放/下载链接时，需确保剥离 Referer Header：
```html
<!-- 全局 Head 禁用 Referer 发送 -->
<meta name="referrer" content="no-referrer">

<!-- 或在 video 标签显式声明 referrerpolicy -->
<video src="parsed_video_url" referrerpolicy="no-referrer" controls></video>
```
