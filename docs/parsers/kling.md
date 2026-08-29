# 快手可灵 AI (Kling) 逆向解析指南

本篇详细记录快手旗下大模型 **可灵 AI (Kling AI)** 视频与创意作品分享的接口抓取机制与参数解析。

---

## 1. 平台特征与支持能力

* **平台标识**：`可灵AI`
* **支持媒体类型**：
  * AI 生成高清视频 (MP4)
  * 视频生成封面与 Prompt 描述
  * 创作者昵称与作品 ID
* **常见链接形态**：
  * 分享落地页：`https://klingai-share.kuaishou.com/h5-app/share?work_id=305387532165182&creative_id=305387532165182&creative_type=WORK`
* **Cookie 依赖**：无需 Cookie，支持公开查询。

---

## 2. 核心逆向流程

### 2.1 创意作品参数提取 (`_extract_creative`)
从传入链接的 Query String 中提取两个核心参数：
* `creative_id` (或 `work_id`)：作品唯一数字编号。
* `creative_type`：作品类型（默认为 `WORK`）。

### 2.2 核心查询接口
* **接口地址**：
  `GET https://klingai-share.kuaishou.com/app/creatives/query`
* **Query 参数**：
  * `creativeId={creative_id}`
  * `creativeType={creative_type}`
* **必备请求头**：
  * `User-Agent`：移动端 UA (如 iPhone Safari)
  * `Referer`：`https://klingai-share.kuaishou.com/`

---

## 3. 数据提取规则

在返回的 JSON 数据中：
* **视频无水印直链**：
  位于 `data.playUrl` 或 `data.works[0].resource.url`。
* **封面图**：
  位于 `data.coverUrl` 或 `data.works[0].resource.coverUrl`。
* **Prompt 标题**：
  位于 `data.prompt` 或 `data.title`。

---

## 4. 常见踩坑记录 (Gotchas)

1. **Query 字段命名多变**：
   * 部分版本分享出来的参数为 `work_id`，新版本为 `creative_id`。代码中采用 fallback 容错兼容逻辑。
2. **纯纯数字 ID 兼容**：
   * 解析器支持直接传入数字 ID 字符串，自动识别为 `creative_id` 并构造请求。

---

## 5. 测试与验证

* **单元测试**：[tests/test_kling_parser.py](file:///Users/leo/Projects/media-parser/tests/test_kling_parser.py)
* **执行测试**：
  ```bash
  pytest tests/test_kling_parser.py
  python tests/manual_verify_parsers.py --platform 可灵AI
  ```
