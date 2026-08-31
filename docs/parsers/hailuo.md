# 海螺AI (Hailuo AI / MiniMax) 逆向解析指南

本篇详细记录 MiniMax 旗下大模型 **海螺AI (Hailuo AI)** 视频与作品分享的接口抓取机制与参数解析。

---

## 1. 平台特征与支持能力

* **平台标识**：`海螺AI`
* **支持媒体类型**：
  * AI 生成高清视频 (MP4，去「海螺AI × MINIMAX」品牌图文大标)
  * 视频生成封面图与 Prompt 提示词描述
  * 图生视频的原始参考帧图片列表 (`image_list`)
  * 创作者 ID 与作品 ID
* **常见链接形态**：
  * 国内主站：`https://hailuoai.com/share/ai-video/{share_id}?source-scene=shared`
  * 国际域名：`https://hailuoai.video/share/ai-video/{share_id}`
* **Cookie 依赖**：无需 Cookie，公开页面流式直出。

---

## 2. 核心逆向流程

### 2.1 Next.js Flight SSR 流式渲染解析
海螺AI 分享落地页使用 Next.js App Router 进行流式服务端渲染（Streaming SSR）。在服务端返回的 HTML 中，内嵌了多个 `self.__next_f.push([1, "..."])` 代码块。

通过解码 Flight 格式数据流并递归遍历 AST 树节点，可直接定位到 `videoAsset` 节点：
* `id`：视频作品内部数字 ID。
* `desc` / `title`：生成视频时用户输入的 Prompt 提示词。
* `coverURL` / `promptImgURL`：视频高清封面与提示词关联图片。
* `userIDStr`：创作者用户编号。
* `originFiles`：生成视频所引用的原始参考图（如首尾帧图片）。

### 2.2 视频直链与去水印策略
在 `videoAsset` 中，服务端预渲染并提供了多个版本的下载流：
1. **`videoURLs.downloadURLWithAIWatermark`**（首选推荐）：
   - **完全去除了「海螺AI × MINIMAX」品牌图文大标**；
   - 仅保留符合法规监管的极浅半透明「AI生成」角标，为公开接口下的最佳纯净直链。
2. **`downloadURL`**：
   - 官方标准下载直链，通常与 `downloadURLWithAIWatermark` 相同。
3. **`videoURL`**（网页默认播放流）：
   - 包含品牌大标与 AI 生成双重水印，作为回退备用。

### 2.3 JSON-LD (Schema.org) 兜底
如果页面流式节点发生重构，解析器会自动回退到页面自带的 `<script type="application/ld+json">` 中的 `VideoObject` 结构进行解析。

---

## 3. 测试与验证

* **单元测试**：[tests/test_hailuo_parser.py](file:///Users/leo/Projects/media-parser/tests/test_hailuo_parser.py)
* **执行测试**：
  ```bash
  .venv/bin/python -m unittest tests/test_hailuo_parser.py
  .venv/bin/python tests/manual_verify_parsers.py --platform 海螺AI
  ```
