# 抖音 (Douyin) 逆向解析指南

本篇详细记录抖音平台短视频、图文笔记与 LivePhoto 的完整逆向提取方案、签名机制及踩坑经验。

---

## 1. 平台特征与支持能力

* **平台标识**：`抖音`
* **支持媒体类型**：
  * 无水印高清视频 (MP4)
  * 高清图文图集 (JPEG/PNG)
  * 动态实况照片 (LivePhoto 动态视频流)
  * 背景音乐原声 (Audio MP3)
* **常见链接形态**：
  * 短链接：`https://v.douyin.com/Nid-fFF_sdI/`
  * 网页端视频长链：`https://www.douyin.com/video/7616399587141737704`
  * 网页端图文长链：`https://www.douyin.com/note/7616399587141737704`
* **Cookie 依赖**：无需用户登录 Cookie，系统内置**动态 TTWID 游客凭证注册与缓存**。

---

## 2. 链路追踪与 ID 提取

1. **302 重定向**：通过 `WebFetcher.fetch_redirect_url` 跟随短链 302 跳转至标准长链接。
2. **ID 提取**：使用 `UrlParser.get_video_id` 匹配数字 ID（`aweme_id`）。

---

## 3. 核心逆向方案 (Web API + a_bogus 签名)

### 3.1 核心请求定义
* **接口地址**：
  ```text
  https://www.douyin.com/aweme/v1/web/aweme/detail/?device_platform=webapp&aid=6383&channel=channel_pc_web&aweme_id={aweme_id}&msToken={ms_token}&a_bogus={a_bogus}
  ```
* **必备请求头**：
  * `User-Agent`：必须与签名计算时传入的 UA 保持严格一致（见 [BogusSigner](file:///Users/leo/Projects/media-parser/utils/signer/bytedance/bogus_signer.py)）。
  * `Referer`：`https://www.douyin.com/video/{aweme_id}?previous_page=web_code_link`
  * `Cookie`：`ttwid={ttwid}`

### 3.2 动态 TTWID 获取机制
抖音 Web 端详情接口要求必须携带有效的 `ttwid`。我们在 [DouyinParser](file:///Users/leo/Projects/media-parser/src/parsers/douyin_parser.py) 中实现了自动注册与类级别内存缓存：
```python
# 向字节注册接口发送请求获取合法游客凭证
url = "https://ttwid.bytedance.com/ttwid/union/register/"
data = {
    "region": "cn",
    "aid": 6383,
    "need_t": 1,
    "service": "www.douyin.com",
    "domain": ".douyin.com"
}
resp = session.post(url, json=data)
ttwid = resp.cookies.get('ttwid')
```

### 3.3 签名计算 (a_bogus)
通过 `py_mini_racer` 在 Google V8 引擎中执行提取的前端混淆脚本，计算 `a_bogus` 防篡改签名：
```python
from utils.signer.bytedance.bogus_signer import BogusSigner

signer = BogusSigner()
abogus = signer.get_abogus(play_url, signer.user_agent)
```

---

## 4. 字段提取与去水印规则

### 4.1 视频提取 (无水印源站流)
在返回的 `aweme_detail.video.bit_rate[0].play_addr.url_list` 中包含多个 CDN 节点：
* `url_list[0]`：主 CDN
* `url_list[1]`：备用 CDN
* `url_list[2]`：源站 CDN（通常为最纯净、最高清流）

### 4.2 图文与 LivePhoto 提取
* ⚠️ **防坑警示**：`download_url_list` 包含带官方水印的图片；**必须提取 `url_list[-1]`**（末尾项通常为无水印最高清原图）。
* **LivePhoto 识别**：若单张图片对象包含 `img['video']['play_addr']`，则说明该图为苹果实况动态照片，提取该视频流即为 LivePhoto 动画。

---

## 5. 常见踩坑记录 (Gotchas)

1. **TTWID 失效导致返回空详情**：
   * *现象*：接口 HTTP 状态码返回 200，但 JSON 中缺少 `aweme_detail` 字段。
   * *解法*：代码中内置重试机制，初次失败立即清空 `_TTWID_CACHE` 并重新获取。
2. **User-Agent 不匹配导致签名校验失败**：
   * *现象*：接口返回参数错误或 403。
   * *原因*：`BogusSigner` 生成 `a_bogus` 时参与哈希计算的 UA 与实际发起 HTTP 请求的 UA 不一致。

---

## 6. 测试与验证

* **单元测试文件**：[tests/test_bogus_signer.py](file:///Users/leo/Projects/media-parser/tests/test_bogus_signer.py)
* **执行测试**：
  ```bash
  pytest tests/test_bogus_signer.py
  python tests/manual_verify_parsers.py --platform 抖音
  ```
