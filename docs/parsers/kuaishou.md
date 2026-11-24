# 快手 (Kuaishou) 逆向解析指南

本篇详细记录快手短视频、图文图集（ATLAS）的多路由容灾抓取机制、GraphQL 接口降级与防风控策略。

---

## 1. 平台特征与支持能力

* **平台标识**：`快手`
* **支持媒体类型**：
  * 无水印高清短视频 (MP4 / DASH 媒体流)
  * 高清图文图集 (ATLAS 原图 / WebP 图集)
  * 背景音乐音频 (Audio)
* **常见链接形态**：
  * App 短链：`https://v.kuaishou.com/xxxx`
  * 移动端 H5 落地页：`https://v.m.chenzhongtech.com/fw/photo/3xbr5pi8hxi4e6s`（含 `*.m.chenzhongtech.com` 随机子域名）
  * PC 网页长链：`https://www.kuaishou.com/short-video/3xbr5pi8hxi4e6s`
* **Cookie 依赖与配置**：
  * 支持免 Cookie 匿名多路由探测与 GraphQL 接口提取。
  * 若目标视频触发快手反爬校验（返回 `result: 2` 或 `ANTICRAWL_DEFAULT`），系统支持动态加载 `KUAISHOU_COOKIE` 凭证（可在 `configs/business_config.json` 的 `platform_cookies.kuaishou` 或环境变量 `KUAISHOU_COOKIE` 中配置）。
  * 触发风控且未配置有效 Cookie 时统一返回 `KUAISHOU_COOKIE_REQUIRED` 错误码。

---

## 2. 核心逆向方案：双端多路由 Fallback + GraphQL 降级容灾

快手不同公开路由的封控力度和可用性波动较大。在 [KuaishouParser](file:///Users/leo/Projects/media-parser/src/parsers/kuaishou_parser.py) 中，我们设计了**双端请求、多路由自适应降级重试与 GraphQL 兜底机制**：

```mermaid
flowchart TD
    Start["获取快手视频 ID"] --> Route1["尝试路由 1: 原始落地页 (移动端 UA 优先)"]
    Route1 --> Check1{"是否有效状态 (非 result:2)?"}
    Check1 -->|"是"| Success["解析成功，提取无水印媒体"]
    Check1 -->|"否 (命中风控)"| Route2["降级路由 1 (桌面端 UA + Cookie 兜底)"]
    Route2 --> Check2{"校验成功?"}
    Check2 -->|"是"| Success
    Check2 -->|"否"| Route3["自动降级路由 2: chenzhongtech 移动端网关"]
    Route3 --> Check3{"校验成功?"}
    Check3 -->|"是"| Success
    Check3 -->|"否"| Route4["降级路由 3: 官方 GraphQL API (visionVideoDetail)"]
    Route4 --> Check4{"GraphQL 请求成功?"}
    Check4 -->|"是"| Success
    Check4 -->|"否 (触发风控)"| Fail["返回 KUAISHOU_COOKIE_REQUIRED 提示配置 Cookie"]
```

### 2.1 候选路由构建 (`_candidate_urls`)
* 优先使用 302 重定向后的原生落地页（兼容快手随机生成的 `*.m.chenzhongtech.com` 泛子域名）。
* 备用使用移动端专用解析网关：`https://v.m.chenzhongtech.com/fw/photo/{video_id}`。
* PC 端直链：`https://www.kuaishou.com/short-video/{video_id}`。

### 2.2 GraphQL API 兜底通道 (`_try_graphql_api`)
* 请求网关：`https://www.kuaishou.com/graphql`
* 操作名：`visionVideoDetail`
* 查询字段：
  ```graphql
  query visionVideoDetail($photoId: String, $type: String, $page: String, $webPageArea: String) {
    visionVideoDetail(photoId: $photoId, type: $type, page: $page, webPageArea: $webPageArea) {
      status
      type
      author { id name headerUrl }
      photo {
        id caption coverUrl photoUrl
        mainMvUrls { url }
        manifest { adaptationSet { representation { url backupUrl } } }
        atlas { cdn cdnList list }
      }
    }
  }
  ```

### 2.4 动态代理兼容与 Cookie 隔离说明
在系统启用动态代理（配置 `DYNAMIC_PROXY_API_URL`，详见 [动态代理配置说明](../proxy-retry.md)）时，快手解析器具备以下针对性的会话隔离与容灾逻辑：
* **结构与参数保留**：完整保留移动端/桌面端顺序、候选 URL 列表、GraphQL 请求体与回退、每条路径请求头、默认重定向行为、5 秒请求超时以及媒体字段提取规则。
* **Session Cookie 严格隔离**：快手会话在每次顶层请求前后清空服务端 Cookie，保持独立 `requests.get/post` 不跨调用保存 Cookie 的行为（但同一调用内部的重定向仍保留 Cookie）。配置 Cookie 显式传入，请求头不写入 Session 公共字典，避免 Cookie 在多用户请求或多代理 IP 间共享污染。
* **多路径切换逻辑**：直连模式下允许早期路径被拦截后由后续路径补救成功，只有所有路径最终均失败时才触发平台级代理窗口。代理模式检测到当前 IP 访问失败时将立即终止该 IP 的后续尝试并自动进行轮换。

---

## 3. 数据提取与无水印保障

快手 CDN 视频流与图集资源为创作者原始上传的母带文件，不包含平台动态烧录的水印：

### 3.1 视频数据提取
* **标准字段 (`mainMvUrls` / `photoUrl`)**：
  * GraphQL 与 H5 载体中提取 `photo.mainMvUrls[0].url` 或 `photo.photoUrl`。
* **流媒体备用**：从流媒体清单 `manifest.adaptationSet` 中提取备用流（`representation.url` / `backupUrl`）或 m3u8 切片。

### 3.2 图集 (ATLAS) 提取
* 快手图文内容在数据结构中标识为 `ATLAS`，图片路径列表位于 `photo.atlas.list` 或 `ext_params.atlas`。
* 优先选择 WebP 高清格式，结合 CDN 域名（`atlas.cdn` / `atlas.cdnList`）拼接完整大图 URL。

### 3.3 音频与作品原声提取 (Audio / soundTrack)
* **创作者作品原声 (`photo.soundTrack`)**：针对使用创作者自带原声的作品，从 `soundTrack.audioUrls` 提取高保真独立音频直链（M4A 格式，如 `https://*.a.yximgs.com/bs2/ost/...m4a`）。
* **背景音乐 (`photo.music`)**：针对引用公开音乐库的作品，从 `photo.music.audioUrls` 提取 MP3/M4A 播放直链。
* **老版图集背景音乐 (`atlas.music`)**：针对图集内嵌音频，结合 `atlas.musicCdnList` 拼接完整音频下载地址。

---

## 4. 常见踩坑记录 (Gotchas)

1. **User-Agent 导致的风控差异**：
   * 桌面端 UA 易触发 `{"result":2}` 拦截；移动端 UA (`USER_AGENT_M`) 稳定性更强。
2. **硬编码 Cookie 过期问题**：
   * 必须通过 `get_platform_cookie("kuaishou")` 动态读取环境与配置文件中的 Cookie，避免旧版失效硬编码字符串导致被反爬标记。
3. **随机跳转域名**：
   * 短链重定向可能会跳转到 `*.m.chenzhongtech.com` 随机子域名，需基于 `video_id` 规范化构建候选路由。

---

## 5. 测试与验证

* **单元测试**：[tests/test_kuaishou_parser.py](file:///Users/leo/Projects/media-parser/tests/test_kuaishou_parser.py)
* **执行命令**：
  ```bash
  python3 -m unittest tests/test_kuaishou_parser.py
  python3 -m unittest discover tests
  ```
