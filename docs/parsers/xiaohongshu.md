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
  * 笔记封面 (自动从 cover 或首图提取)
* **常见链接形态**：
  * 短链接：`http://xhslink.com/o/xxxx` 或 `http://xhslink.com/a/xxxx`
  * 网页发现长链：`https://www.xiaohongshu.com/discovery/item/6a8fbccc000000002a03825a`
  * 网页探索长链：`https://www.xiaohongshu.com/explore/6a8fbccc000000002a03825a`
* **Cookie 依赖**：🟢 公开普通笔记及移动分享均免配置 Cookie。

---

## 2. 核心逆向方案 (SSR HTML 状态注入 + 双 UA 自适应回退)

小红书 Web/H5 页面采用 Nuxt / Vue SSR 服务端渲染。页面加载时，首屏所有笔记详情、高清媒体流及作者信息均已经内嵌在 HTML 的 `window.__INITIAL_STATE__` 变量中。

### 2.1 请求配置与 URL 参数保留
* **请求方式**：`GET` 目标解析长链接
* **关键查询参数保留**：短链 302 重定向后必须保留 `xsec_token`、`xsec_source`、`source`、`xhsshare`、`app_platform` 等核心参数（在 [utils/web_fetcher.py](file:///Users/leo/Projects/media-parser/utils/web_fetcher.py) 的 `UrlParser.extract_video_address` 中维护），缺少来源签名参数会导致服务端返回 404 或拦截。
* **双 UA 自适应机制**：
  * **App 端分享短链**（含 `app_platform=android` 等）：优先使用 **Mobile User-Agent** 访问以获取移动端 H5 页面。
  * **PC 桌面端长链**（含 `source=webshare` 等）：优先使用 **PC User-Agent** 访问。
  * **自动回退**：若首选 UA 遭遇 302/404 或拦截，解析器自动切换为备用 UA 再次发起请求。

### 2.2 正则状态提取与结构兼容
```python
import re, json

# 1. 正则提取并清洗 :undefined 为 :null
pattern = re.compile(r'window\.__INITIAL_STATE__\s*=\s*(\{.*?\})</script>', re.DOTALL)
match = pattern.search(html_content) or re.search(r'window\.__INITIAL_STATE__\s*=\s*(\{.*\})', html_content, re.DOTALL)

if match:
    json_str = re.sub(r':\s*undefined\b', ':null', match.group(1))
    full_data = json.loads(json_str)

    # 2. 兼容 PC 桌面端数据结构
    first_note_id = full_data.get('note', {}).get('firstNoteId')
    if first_note_id:
        note_data = full_data['note']['noteDetailMap'].get(first_note_id, {}).get('note', {})

    # 3. 兼容移动端 H5 数据结构
    if not note_data:
        note_data = full_data.get('noteData', {}).get('data', {}).get('noteData', {})
```

---

## 3. 字段提取与 LivePhoto 解析

### 3.1 视频笔记提取
* 视频直链位于：`note_data.video.media.stream.h264[0].masterUrl` 或 `note_data.video.stream.h264[0].masterUrl`。
* 字符转义处理：将 Unicode 斜杠 `\\u002F` 替换为标准 `/`。

### 3.2 图文与 LivePhoto 提取
* 遍历 `note_data.imageList`：
  * **原图直链**：按优先级提取 `image.urlDefault` -> `image.url` -> `image.infoList[-1].url`。
  * **实况动图 (LivePhoto)**：检查 `image.get('livePhoto') == True`，若为真，则提取 `image.stream.h264[0].masterUrl` 作为实况动图关联的动态视频流。

### 3.3 封面与作者提取
* **封面**：优先读取 `note_data.cover.urlDefault` / `url`，若为空则以 `imageList[0]` 兜底。
* **作者**：兼容读取 `user.nickname` / `user.nickName` 及 `user.userId`。

---

## 4. 常见踩坑与反爬对抗 (Gotchas)

1. **App 分享短链在 PC UA 下重定向到 `/explore?undertake_note_error=该内容暂时无法查看` (错误码 -510001)**：
   * *原因*：小红书服务端对 App 端生成的分享链接（带有 `app_platform=android&xsec_source=app_share` 等参数）进行设备特征校验，PC UA 访问会被判定为非移动环境并重定向到探索页。
   * *解法*：在 [src/parsers/xiaohongshu_parser.py](file:///Users/leo/Projects/media-parser/src/parsers/xiaohongshu_parser.py) 中启用双 UA 自动降级重试机制，对 App 分享链接自动采用移动端 User-Agent 请求，无需 Cookie 即可获取完整 H5 状态树。
2. **缺少 `xsec_source` 导致 H5 页面返回 404/安全校验**：
   * *原因*：在 URL 清洗阶段若仅保留 `xsec_token` 而丢弃了 `xsec_source`，移动端 H5 接口会因缺少渠道来源标识而拒绝渲染笔记数据。
   * *解法*：在 [utils/web_fetcher.py](file:///Users/leo/Projects/media-parser/utils/web_fetcher.py) 的 `UrlParser.extract_video_address` 中完整保留 `xsec_token`, `xsec_source`, `source`, `xhsshare`, `app_platform` 等核心参数。
3. **字符转义与 `undefined` 序列化**：
   * HTML 内嵌的 JS 对象常包含 `:undefined`，直接 `json.loads` 会抛出异常，需统一正则替换为 `:null`。

---

## 5. 测试与验证

* **真实样本验证**：
  ```bash
  python tests/manual_verify_parsers.py --platform 小红书
  ```
* **单元测试**：
  ```bash
  python -m unittest tests/test_xiaohongshu_parser.py
  ```
