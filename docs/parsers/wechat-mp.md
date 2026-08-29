# 微信公众号 (WeChat Official Accounts) 逆向解析指南

本篇详细记录腾讯旗下 **微信公众号 (mp.weixin.qq.com)** 文章图文、高清插图图集与内嵌音频/媒体的原生解析方案。

---

## 1. 平台特征与支持能力

* **平台标识**：`微信公众号`
* **支持媒体类型**：超高清正文插图图集 (无损画质) / 封面图 / 文章标题 / 公众号作者与 `gh_` 标识 / 内嵌语音 (MP3) / 内嵌视频
* **支持域名**：
  * `mp.weixin.qq.com`（公众号文章详情页与分享短链）
* **常见链接形态**：
  * **文章长链/短链**：`https://mp.weixin.qq.com/s/CoQ8GG6f7lD7EADUey13BA`
  * **历史参数链**：`https://mp.weixin.qq.com/s?__biz=MzA5...&mid=...&idx=1&sn=...`
* **Cookie 依赖**：🟢 免配置（开箱即用）。

---

## 2. 核心逆向流程

### 1. 抓取文章 SSR 页面
公众号文章页面采用服务端渲染 (SSR)，直接发送标准请求即可获取完整文章 HTML 与内嵌的 Javascript 全局上下文。

### 2. 提取文章核心元数据
* **标题 (`title`)**：优先从内嵌 JS 变量 `var msg_title = '...'` 中提取，并做 HTML Entity 解码；备选从 `<meta property="og:title">` 或 `h1#activity-name` 提取。
* **公众号作者 (`nickname` / `author_id`)**：从 `var nickname = '...'` 和 `var user_name = 'gh_...'` 提取。
* **文章封面 (`cover_url`)**：从 `var msg_cdn_url = '...'` 或 `<meta property="og:image">` 提取。

### 3. 原画画质插图提取与无损升级算法
* 微信正文图片默认使用带尺寸压缩的缩略路径（如 `/640?wx_fmt=png` 或 `/300?wx_fmt=jpeg`）；
* **解析器自动将 CDN 路径的尺寸切片升级为 `/0?`**（即原始无损画质）：
  ```python
  full_res_url = re.sub(r'/(?:640|300|0)\?', '/0?', img_src)
  ```

### 4. 语音/音频资源提取
* 从正文 `<mpvoice voice_encode_fileid="..." name="...">` 标签提取语音文件 ID；
* 组装微信原生音频直链：`https://res.wx.qq.com/voice/getvoice?mediaid={voice_encode_fileid}`。

---

## 3. 测试与验证

* **专属单元测试**：[tests/test_wechat_mp_parser.py](file:///Users/leo/Projects/media-parser/tests/test_wechat_mp_parser.py)
* **执行命令**：
  ```bash
  python3 -m unittest tests/test_wechat_mp_parser.py
  python3 tests/manual_verify_parsers.py --platform 微信公众号
  ```
