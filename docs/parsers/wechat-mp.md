# 微信公众号 (WeChat Official Accounts) 逆向解析指南

本篇详细记录腾讯旗下 **微信公众号 (mp.weixin.qq.com)** 文章图文、高清插图图集、内嵌音频与 1080P 视频流的原生解析方案。

---

## 1. 平台特征与支持能力

* **平台标识**：`微信公众号`
* **支持媒体类型**：
  * **超高清正文插图图集**：自动升级为无损原始画质 (`/0?`)，过滤内置 emoji 图标
  * **文章封面图** (`cover_url`)
  * **1080P 超清视频直链 / 多视频列表** (`video_url` / `video_list`)：支持公众号视频动态与正文内嵌多视频（自动按视频 ID 分组并为每个视频提取最高画质流）
  * **内嵌语音播报 / 音频直链** (`audio_url`)
  * **文章标题与发布者信息**：包含文章/视频标题、公众号作者昵称、`gh_` 标识及官方头像
* **支持域名**：
  * `mp.weixin.qq.com`（公众号文章详情页、视频动态页与分享短链）
* **常见链接形态**：
  * **文章长链/短链**：`https://mp.weixin.qq.com/s/LqZUts7aWOz7D7W_jIEXsA`
  * **多视频文章长链**：`https://mp.weixin.qq.com/s/aNmLs3qJVhFGcgtGxAVlig`
  * **视频消息动态**：`https://mp.weixin.qq.com/s/GQiMB7CC6r7wil54I0TMwQ`
  * **历史参数长链**：`https://mp.weixin.qq.com/s?__biz=MzA5...&mid=...&idx=1&sn=...`
  * **视频详情落地页**：`https://mp.weixin.qq.com/s?__biz=...&mid=...&idx=1&sn=...&t=pages/video_detail_new&vid=...`
  * **音频详情落地页**：`https://mp.weixin.qq.com/s?__biz=...&mid=...&idx=1&sn=...&t=pages/audio_detail&voice_id=...`
  * **带校验和参数长链**：`https://mp.weixin.qq.com/s?__biz=...&mid=...&idx=1&sn=...&chksm=...`
* **Cookie 依赖**：🟢 免配置（开箱即用）。

---

## 2. 核心逆向流程

### 1. 抓取文章 SSR 页面
公众号文章页面采用服务端渲染 (SSR)，直接发送标准桌面/移动端请求即可获取完整文章 HTML 与内嵌的 Javascript 全局上下文。

### 2. 提取文章核心元数据
* **标题 (`title`)**：优先从内嵌 JS 变量 `var msg_title = '...'` 或 `title: '...'` 中提取，并做 HTML Entity 解码；备选从 `<meta property="og:title">` 或 `h1#activity-name` 提取。
* **公众号作者与头像 (`author`)**：
  * **昵称**：从 `var nickname = '...'` 或 `nick_name: '...'` 提取；
  * **ID**：从 `var user_name = 'gh_...'` 或 `user_name: '...'` 提取；
  * **头像**：从 `round_head_img` 或 `ori_head_img_url` 提取。
* **文章封面 (`cover_url`)**：从 `var msg_cdn_url = '...'`、`cdn_url: '...'` 或 `<meta property="og:image">` 提取。

### 3. 原画画质插图提取与无损升级算法
* 微信正文图片默认使用带尺寸压缩的缩略路径（如 `/640?wx_fmt=png` 或 `/300?wx_fmt=jpeg`）；
* **解析器自动将 CDN 路径的尺寸切片升级为 `/0?`**（即原始无损画质），并自动过滤表情图标：
  ```python
  full_res_url = re.sub(r'/(?:640|300|0)\?', '/0?', img_src)
  ```

### 4. 多视频流提取与清晰度择优算法
公众号视频动态或正文内嵌的多个视频在页面 JS 变量 `video_page_info` 或 `videoPageInfos` / `video_page_infos` 的 `mp_video_trans_info` 中包含了多档转码格式（如 1080P 超清、720P 高清、480P 流畅等）：
1. 扫描页面中所有的转码规格列表，提取所有 `mpvideo.qpic.cn` 视频流；
2. **多视频按唯一文件指纹分组**：基于视频文件的唯一标识（`file_id`）将不同清晰度的分发流归类到各自的内嵌视频；
3. **独立打分择优**：对每个视频的各个清晰度依据 `video_quality_level`、分辨率（`width * height`）以及 `filesize` 进行多维度打分，**自动为每个视频挑选最高分辨率（如 1080×1920 超清）的 MP4 直链**；
4. **全量聚合返回**：将文章中包含的全部视频直链按正文顺序聚合至 `video_list`，同时 `video_url` 指向首个视频。

### 5. 语音/音频资源提取
* 从正文 `<mpvoice voice_encode_fileid="..." name="...">` 标签提取语音文件 ID；
* 组装微信原生音频直链：`https://res.wx.qq.com/voice/getvoice?mediaid={voice_encode_fileid}`。

### 6. 参数保真与 Base64 规范化处理
微信公众号独立视频/音频页（如 `t=pages/video_detail_new&vid=...`、`t=pages/audio_detail&voice_id=...`）以及历史长链高度依赖 URL Query 参数。在预处理与清洗环节：
* **关键参数全量保留**：系统定向保留 `__biz`、`mid`、`idx`、`sn`、`chksm`、`t`、`vid`、`vidsn`、`voice_id` 等业务参数，防止因参数被过度剔除导致 404；
* **Base64 与路径符号防转义**：在重编码 URL 时指定 `safe='=/'`，避免 Base64 尾部填充等号 `=` 被错误转码为 `%3D` 或路径分隔符 `/` 被转为 `%2F` 引发微信服务反爬拦截或跳转异常。

---

## 3. 视频直链访问与状态识别注意事项

腾讯视频 CDN（`mpvideo.qpic.cn`）与公众号安全机制如下，调用或下载时需注意：

1. **防盗链校验 (Referer)**：
   * 微信 CDN 强制校验来源。浏览器直接在地址栏打开直链会触发 `403 Forbidden`。
   * 请求头必须携带：`Referer: https://mp.weixin.qq.com/`。
2. **302 重定向跟随**：
   * 请求视频直链时，微信 CDN 会返回 `HTTP 302 Found` 调度至最近的边缘节点。
   * 使用 `curl` 命令行下载时**必须添加 `-L` 参数**跟随重定向（否则将保存为 0 字节的 302 响应体）：
     ```bash
     curl -L -H "Referer: https://mp.weixin.qq.com/" -o "video.mp4" "<VIDEO_URL>"
     ```
3. **动态凭证时效性**：
   * 视频链接中的 `dis_k`、`dis_t`、`auth_key` 参数为动态限时签名，过期需重新调用解析接口获取最新链接。
4. **环境异常反爬拦截识别 (`WECHAT_MP_VERIFY_REQUIRED`)**：
   * 当微信服务端对频繁访问或特定机房 IP 触发安全验证时，页面会跳转至 `secitptpage/verify`（“环境异常，完成验证后即可继续访问”）。
   * 解析器会自动识别该拦截页并抛出标准错误码 `WECHAT_MP_VERIFY_REQUIRED`（HTTP 400），提示调用方稍后重试或切换代理 IP，避免误判为空内容。
5. **文章删除与违规终态识别 (`MEDIA_DELETED_OR_PRIVATE`)**：
   * 当微信页面包含「该内容已被发布者删除」或「此内容因违规无法查看」等提示时，解析器直接将其标记为 `MEDIA_DELETED_OR_PRIVATE` 终态错误，阻断无意义的频繁轮询。

---

## 4. 调用与下载示例

### Python 下载示例
```python
import requests

# 1. 调用解析服务
res = requests.post("http://127.0.0.1:8051/api/parse", json={
    "text": "https://mp.weixin.qq.com/s/GQiMB7CC6r7wil54I0TMwQ"
}).json()

video_url = res["data"]["video_url"]

# 2. 携带 Referer 下载 (requests 默认自动跟随 302 重定向)
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": "https://mp.weixin.qq.com/",
}
with requests.get(video_url, headers=headers, stream=True) as r:
    r.raise_for_status()
    with open("downloaded_video.mp4", "wb") as f:
        for chunk in r.iter_content(chunk_size=65536):
            f.write(chunk)
```

---

## 5. 测试与验证

* **专属单元测试**：[tests/test_wechat_mp_parser.py](file:///Users/leo/Projects/media-parser/tests/test_wechat_mp_parser.py)
* **执行命令**：
  ```bash
  python3 -m unittest tests/test_wechat_mp_parser.py
  python3 tests/manual_verify_parsers.py --platform 微信公众号
  ```

