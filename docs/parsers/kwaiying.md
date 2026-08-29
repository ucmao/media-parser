# 快影 (Kwaiying) 逆向解析指南

本篇详细记录快手科技旗下 **快影 (Kwaiying)** 剪辑 App 模板分享与作品分享的原生解析方案。

---

## 1. 平台特征与支持能力

* **平台标识**：`快影`
* **支持媒体类型**：高清模板视频 (MP4) / 封面图 / 标题文案 / 创作者信息 / 背景音乐 (MP3)
* **支持域名**：
  * `share.kwaiying.com`（快影 App H5 模板分享）
  * `kwaiying.com` / `www.kwaiying.com`
* **常见链接形态**：
  * **快影模板分享长链**：`https://share.kwaiying.com/share/template/index.html?id=8467216&userId=702561542395651960`
* **Cookie 依赖**：🟢 免配置（开箱即用）。

---

## 2. 核心逆向流程

### 1. 提取 Template ID
从 URL query 参数（`id` / `templateId`）中解析出模板 ID（例如 `8467216`）。

### 2. 动态计算客户端签名 (Sign & Nonce)
快影 OpenAPI 接口校验 `timestamp`、12 位随机数 `nonce` 以及基于混淆密钥 `yiuhjkbvhbjisjchgdnx38uejd` 计算的签名：

```python
import hashlib, random, re, time

def get_kwaiying_sign(key="yiuhjkbvhbjisjchgdnx38uejd"):
    now_ms = int(time.time() * 1000)
    nonce = random.randint(100000000000, 999999999999)
    hex_str = "".join([hex(ord(c))[2:] for c in key])
    digits_only = re.sub(r"[a-fA-F]", "", hex_str)[:16]
    a = int(digits_only)
    s = (a ^ now_ms) | a
    sign_val = hashlib.md5(str(nonce ^ s).encode("utf-8")).hexdigest()
    return {"timestamp": now_ms, "nonce": nonce, "sign": sign_val}
```

### 3. 请求模板详情接口
* **请求方式**：`GET`
* **接口地址**：`https://api.kmovie.gifshow.com/rest/n/kmovie/app/resource/getTemplateById`
* **Query 参数**：`templateId`, `timestamp`, `nonce`, `sign`
* **Headers**：
  ```http
  User-Agent: Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X)...
  Origin: https://share.kwaiying.com
  Referer: https://share.kwaiying.com/share/template/index.html?id=...
  ```

### 4. 提取媒体数据
* **视频直链**：`data.resource.videoUrl`（无水印标准 MP4）
* **封面图**：`data.resource.templateBean.coverUrl`
* **标题描述**：`data.resource.name` 或 `data.resource.templateBean.description`
* **创作者**：`data.resource.user.nickName`、`data.resource.user.userId` 及 `data.resource.user.iconUrlList[0]`
* **背景原声**：`data.resource.music.url`

---

## 3. 测试与验证

* **专属单元测试**：[tests/test_kwaiying_parser.py](file:///Users/leo/Projects/media-parser/tests/test_kwaiying_parser.py)
* **执行命令**：
  ```bash
  python3 -m unittest tests/test_kwaiying_parser.py
  python3 tests/manual_verify_parsers.py --platform 快影
  ```
