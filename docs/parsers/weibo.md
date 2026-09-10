# 微博 (Weibo) 逆向解析指南

本篇详细记录新浪微博长微博图集、博文视频（包含 `1034:xxx` 视频流与 `1022:xxx` 直播回放流）的逆向提取与 Base62 ID 转换算法。

---

## 1. 平台特征与支持能力

* **平台标识**：`微博`
* **支持媒体类型**：
  * 微博无水印短视频 (MP4)
  * 微博直播与回放视频 (MP4/HLS)
  * 多图与高清 Live 图集 (JPEG/PNG)
  * 微博正文内容与博主信息
* **常见链接形态**：
  * 视频页：`https://video.weibo.com/show?fid=1034:5336219874426938`
  * 直播/回放页：`https://weibo.com/l/wblive/p/show/1022:2321325311149536575703`
  * 网页长链：`https://weibo.com/1234567890/Mabcdef`
* **Cookie 依赖**：无需登录 Cookie（内置自动生成临时 Visitor 访客会话）。

---

## 2. 核心算法与逆向流程

### 2.1 微博 Base62 转换算法 (`mid_to_id`)
微博长链中的字符串 ID（如 `Mabcdef`）为 Base62 编码。在请求数据前，解析器通过 `base62_decode` 将其还原为数据库中的真实纯数字 `id`。

### 2.2 视频流、直播回放与图文分支提取
* **分支 1 (视频专页 `1034:xxx` 与直播回放 `1022:xxx`)**：
  * 识别 `fid=1034:...`、`/tv/show/1034:...` 以及 `/l/wblive/p/show/1022:...`；
  * 初始化访客凭证后，针对视频先调用组件接口 `https://weibo.com/tv/api/component` (`Component_Play_Playinfo`)；
  * 针对微博直播（`1022:...`）链接，若组件接口未返回媒体数据，进一步请求 `https://weibo.com/l/!/2/wblive/room/show_pc_live.json?live_id=1022:...` 提取直播/回放地址（`replay_origin_url` / `live_origin_hls_url`）、封面及主播信息。
* **分支 2 (标准微博动态 `statuses/show`)**：
  * 从 `page_info.media_info.playback_list` 获取不同分辨率的 MP4 直链；
  * 从 `pic_infos` 遍历提取 `large` 或 `original` 档位高清原图。

---

## 3. 测试与验证

* **单元测试**：[tests/test_weibo_parser.py](file:///Users/leo/Projects/media-parser/tests/test_weibo_parser.py)
* **执行命令**：`pytest tests/test_weibo_parser.py`
