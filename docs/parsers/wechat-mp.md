# 微信公众号 (WeChat Official Accounts) 逆向解析指南

本篇详细记录腾讯旗下 **微信公众号 (mp.weixin.qq.com)** 文章图文、高清插图图集、内嵌音频与 1080P 视频流的原生解析方案。

---

## 1. 平台特征与支持能力

* **平台标识**：`微信公众号`
* **支持媒体类型**：
  * **超高清正文插图图集**：自动升级为无损原始画质 (`/0?`)，过滤内置 emoji 图标
  * **文章封面图** (`cover_url`)
  * **1080P 超清视频直链** (`video_url` / `video_list`)：支持公众号视频动态与正文内嵌视频
  * **内嵌语音播报 / 音频直链** (`audio_url`)
  * **文章标题与发布者信息**：包含文章/视频标题、公众号作者昵称、`gh_` 标识及官方头像
* **支持域名**：
  * `mp.weixin.qq.com`（公众号文章详情页、视频动态页与分享短链）
* **常见链接形态**：
  * **文章长链/短链**：`https://mp.weixin.qq.com/s/LqZUts7aWOz7D7W_jIEXsA`
  * **视频消息动态**：`https://mp.weixin.qq.com/s/GQiMB7CC6r7wil54I0TMwQ`
  * **历史参数长链**：`https://mp.weixin.qq.com/s?__biz=MzA5...&mid=...&idx=1&sn=...`
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

### 4. 视频流提取与清晰度择优算法
公众号视频动态或正文内嵌视频在页面 JS 对象 `mp_video_trans_info` 中包含了多档转码格式（如 1080P 超清、720P 高清、480P 流畅等）：
1. 扫描页面中的转码规格列表，提取所有 `mpvideo.qpic.cn` 视频流；
2. 依据 `video_quality_level`、分辨率（`width * height`）以及 `filesize` 进行多维度打分，**自动择优选择最高分辨率（如 1080×1920 超清）的 MP4 视频直链**。

### 5. 语音/音频资源提取
* 从正文 `<mpvoice voice_encode_fileid="..." name="...">` 标签提取语音文件 ID；
* 组装微信原生音频直链：`https://res.wx.qq.com/voice/getvoice?mediaid={voice_encode_fileid}`。

---

## 3. 视频直链访问与下载注意事项（防盗链与 302 重定向）

腾讯视频 CDN（`mpvideo.qpic.cn`）具有以下访问机制，下载或播放时需注意：

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

