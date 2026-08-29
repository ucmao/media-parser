# 微博 (Weibo) 逆向解析指南

本篇详细记录新浪微博长微博图集、博文视频（包含 `1034:xxx` 视频流）的逆向提取与 Base62 ID 转换算法。

---

## 1. 平台特征与支持能力

* **平台标识**：`微博`
* **支持媒体类型**：
  * 微博无水印短视频 (MP4)
  * 多图与高清 Live 图集 (JPEG/PNG)
  * 微博正文内容与博主信息
* **常见链接形态**：
  * 视频页：`https://video.weibo.com/show?fid=1034:5336219874426938`
  * 网页长链：`https://weibo.com/1234567890/Mabcdef`
* **Cookie 依赖**：无需登录 Cookie。

---

## 2. 核心算法与逆向流程

### 2.1 微博 Base62 转换算法 (`mid_to_id`)
微博长链中的字符串 ID（如 `Mabcdef`）为 Base62 编码。在请求数据前，解析器通过 `base62_decode` 将其还原为数据库中的真实纯数字 `id`。

### 2.2 视频流与图文分支提取
* **分支 1 (视频专页 `fid=1034:xxx`)**：
  * 接口：`https://weibo.com/tv/api/component/page`
  * 直接提取 1080P/720P 高清播放流。
* **分支 2 (标准微博动态 `statuses/show`)**：
  * 从 `page_info.media_info.playback_list` 获取不同分辨率的 MP4 直链；
  * 从 `pic_infos` 遍历提取 `large` 或 `original` 档位高清原图。

---

## 3. 测试与验证

* **单元测试**：[tests/test_weibo_parser.py](file:///Users/leo/Projects/media-parser/tests/test_weibo_parser.py)
* **执行命令**：`pytest tests/test_weibo_parser.py`
