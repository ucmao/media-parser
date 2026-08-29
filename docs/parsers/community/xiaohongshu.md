# 小红书 (Xiaohongshu) 逆向解析指南

本篇详细记录小红书平台图文笔记、视频笔记与 LivePhoto 的完整逆向提取方案及反爬对抗经验。

---

## 1. 平台特征与支持能力

* **平台标识**：`小红书`
* **支持媒体类型**：
  * 高清图文图集 (无水印 WebP/JPEG)
  * 实况照片 (LivePhoto 动态视频流)
  * 视频笔记 (H264 Master MP4 流)
  * 笔记正文与作者信息
* **常见链接形态**：
  * 短链接：`http://xhslink.com/a/xxxx`
  * 网页发现长链：`https://www.xiaohongshu.com/discovery/item/6a8fbccc000000002a03825a`
  * 网页探索长链：`https://www.xiaohongshu.com/explore/6a8fbccc000000002a03825a`
* **Cookie 依赖**：公开普通笔记无需 Cookie；部分强受限笔记或高频调用建议在 `.env` 中提供 Cookie。

---

## 2. 核心逆向方案 (SSR HTML 状态注入)

小红书 Web 页面采用 Nuxt / Vue SSR 服务端渲染。页面加载时，首屏所有笔记详情、高清媒体流及作者信息均已经内嵌在 HTML 的 `window.__INITIAL_STATE__` 变量中。

### 2.1 请求配置
* **请求方式**：`GET` 目标长链接
* **必备请求头**：
  * `User-Agent`: 现代 PC 浏览器 UA
  * `Referer`: `https://www.xiaohongshu.com/`

### 2.2 正则状态提取
```python
import re, json

pattern = re.compile(r'window\.__INITIAL_STATE__\s*=\s*(\{.*\})', re.DOTALL)
json_str = BaseParser.parse_html_data(html_content, pattern)

if json_str:
    full_data = json.loads(json_str)
    first_note_id = full_data.get('note', {}).get('firstNoteId')
    note_data = full_data['note']['noteDetailMap'].get(first_note_id, {}).get('note', {})
```

---

## 3. 字段提取与 LivePhoto 解析

### 3.1 视频笔记提取
* 视频直链位于：`note_data.video.media.stream.h264[0].masterUrl`
* 字符转义处理：将 Unicode 斜杠 `\\u002F` 替换为标准 `/`。

### 3.2 图文与 LivePhoto 提取
* 遍历 `note_data.imageList`：
  * **原图直链**：提取 `urlDefault` 字段。
  * **实况动图 (LivePhoto)**：检查 `image.get('livePhoto') == True`，若为真，则提取 `image.stream.h264[0].masterUrl` 作为实况动图关联的视频流。

---

## 4. 常见踩坑与反爬对抗 (Gotchas)

1. **重定向至登录页 (`/login`) 或 404**：
   * *原因*：小红书对单一 IP 频次较高的请求，或者未带参数的特定私密笔记会强制要求登录。
   * *解法*：在 [src/api/parse.py](file:///Users/leo/Projects/media-parser/src/api/parse.py) 中针对小红书内置了 3 次自适应重试机制（`_fetch_with_retry`）；若持续失败，则友好提示用户配置 Cookie。
2. **字符转义问题**：
   * JSON 字符串中经常包含 JSON 编码的斜杠 `\u002F`，必须统一格式化清洗。

---

## 5. 测试与验证

* **真实样本验证**：
  ```bash
  python tests/manual_verify_parsers.py --platform 小红书
  ```
