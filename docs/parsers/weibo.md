# 微博 (Weibo) 逆向解析指南

本篇详细记录新浪微博长微博图集、博文视频（包含 `1034:xxx` 视频流与 `1022:xxx` 直播回放流）的逆向提取、Base62 ID 转换算法及图床无平台水印解析方案。

---

## 1. 平台特征与支持能力

* **平台标识**：`微博`
* **支持媒体类型**：
  * 微博无水印短视频 (MP4)
  * 微博直播与回放视频 (MP4/HLS)
  * 多图与高清无平台水印图集 (JPEG/PNG)
  * 微博实况图集 (Live Photo, .mov / .mp4 动图视频流)
  * 微博正文内容与博主信息
* **常见链接形态**：
  * 视频页 (数字或十六进制/字母数字混合 fid)：`https://video.weibo.com/show?fid=1034:5336219874426938` 或 `https://video.weibo.com/show?fid=1034:cba52f9b57b69ca1a0cde0c2211e1ca1`
  * 直播/回放页：`https://weibo.com/l/wblive/p/show/1022:2321325311149536575703`
  * 实况/图文博文：`https://weibo.com/6288169783/5344438765488239`
  * 网页长链：`https://weibo.com/1234567890/Mabcdef`
  * 移动端带渠道后缀：`https://m.weibo.cn/7753941940/5332536008119716/qq?wm=3333_2001`
  * 移动客户端分享链接：`https://mapp.api.weibo.cn/fx/...`
* **Cookie 依赖**：常规内容免登录 Cookie（内置自动生成临时 Visitor 访客会话，机房 IP 或高规格视频支持配置 `WEIBO_COOKIE`）。

---

## 2. 核心算法与逆向流程

### 2.1 微博 Base62 转换算法 (`mid_to_id`)
微博长链中的字符串 ID（如 `Mabcdef`）为 Base62 编码。在请求数据前，解析器通过 `base62_decode` 将其还原为数据库中的真实纯数字 `id`。
同时支持识别并提取 `m.weibo.cn/<uid>/<mid>/<channel_subpath>?...` 移动端嵌套路径中的纯数字 mid。

### 2.2 视频流、直播回放与图文分支提取
* **分支 1 (视频专页 `1034:xxx` 与直播回放 `1022:xxx`)**：
  * 识别并正则匹配 `fid=1034:<media_id>`、`/tv/show/1034:<media_id>` 以及 `/l/wblive/p/show/1022:<media_id>`，同时兼容纯数字 `media_id` 与十六进制/字母数字混合 `media_id`（如 `1034:cba52f9b57b69ca1a0cde0c2211e1ca1`）；
  * 初始化 Visitor 访客凭证获取合法 Session 状态，调用 PC 端视频组件接口 `https://weibo.com/tv/api/component` (`Component_Play_Playinfo`) 提取分辨率列表、直链 (`stream_url` / `urls`) 及博主/标题元数据；
  * 针对微博直播（`1022:...`）链接，若组件接口未返回媒体数据，进一步请求 `https://weibo.com/l/!/2/wblive/room/show_pc_live.json?live_id=1022:...` 提取直播/回放地址（`replay_origin_url` / `live_origin_hls_url`）、封面及主播信息；
  * 阻断误退化：当确认 URL 为视频专页，若组件 API 未返回有效数据，解析器直接终止查询并返回空字典，防止误将视频 `oid` 作为博文 `status_id` 传给 `m.weibo.cn/statuses/show` 触发无意义 404 异常。
* **分支 2 (标准微博动态 `statuses/show`)**：
  * 从 `page_info.media_info.playback_list` 获取不同分辨率的 MP4 直链；
  * 从 `pics` 或 `pic_ids` 遍历提取原图并做去水印前缀转换；
  * 排除超话/话题等非媒体封面（如 `type in ('topic', 'search', 'place')`），保证封面准确为首图或视频封面。

### 2.3 图床无平台水印转换 (`sinaimg.cn`)
微博新浪图床通过 URL 路径中的前缀控制图片尺寸和是否加盖平台水印：
* **带平台水印前缀**：`mw690`、`mw2000`、`large`、`woriginal`（右下角压制博主昵称）
* **无平台水印前缀**：`osj1080`、`oslarge`（Original Source，不包含平台水印）

解析器内置 `_strip_watermark_url` 转换规则，自动将图片 URL 路径前缀重写为 `osj1080`，输出无微博平台水印的高清源图。

### 2.4 微博实况 (Live Photo) 视频流提取
当博文包含 Live Photo 时，接口返回的 `pics[]` 中会包含 `type: "livephoto"` 及 `videoSrc`（或根节点 `live_photo` 列表）：
* 解析器将 `image_list` 格式化为 `[{"url": "https://wx.../osj1080/...", "live_photo_url": "https://video.weibo.com/media/play?livephoto=..."}]` 对象列表；
* `live_photo_url` 请求时会自动重定向生成带签名参数的 `.mov` 实况动态视频文件。

---

## 3. 常见踩坑记录 (Gotchas)

1. **新浪图床防盗链 (HTTP 403 Forbidden)**：
   * `*.sinaimg.cn` 启用了防盗链机制。当请求头带有第三方非微博域名的 `Referer` 时，CDN 会直接返回 403 拒绝访问。
   * **展示方案**：前端在 `<head>` 中添加全局 `<meta name="referrer" content="no-referrer">`，或在 `<img>` 标签上添加 `referrerpolicy="no-referrer"`。
   * **下载方案**：由于新浪图床未开放 CORS 头且存在防盗链，推荐前端通过后端代理中转流（附带 `Content-Disposition: attachment`）进行下载，或使用 `curl -O` 等无 Referer 方式下载。
2. **作者自加硬水印 vs 平台生成水印**：
   * 解析器去除的是**微博平台在转码分发时动态打上的昵称/LOGO 水印**。
   * 若作者在上传前已自行将文字/水印合成至图片像素中（如防盗印记），该水印属于源文件内容，无法通过图床接口解析消除。

---

## 4. 测试与验证

* **单元测试**：[tests/test_weibo_parser.py](file:///Users/leo/Projects/media-parser/tests/test_weibo_parser.py)
* **执行命令**：`python3 -m unittest tests/test_weibo_parser.py`
