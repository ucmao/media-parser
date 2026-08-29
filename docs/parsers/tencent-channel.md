# 腾讯频道 / 腾讯视频 (Tencent Channel) 逆向解析指南

本篇详细记录 **腾讯频道 / 腾讯视频** 分享视频的解析方案。

---

## 1. 平台特征与支持能力

* **平台标识**：`腾讯频道` / `腾讯视频`
* **支持媒体类型**：高清视频 (MP4) / 封面图 / 视频标题与作者
* **常见链接形态**：
  * 频道分享：`https://pd.qq.com/s/9df0az124?b=2`
* **Cookie 依赖**：无需 Cookie。

---

## 2. 核心逆向流程

1. **302 跟随跳转与参数提取**：请求短链解析频道或视频的唯一 Key。
2. **企鹅开放接口与元数据提取**：
   * 调用企鹅开放平台接口，解析高清 MP4 视频直链及封面。

---

## 3. 测试与验证

* **单元测试**：[tests/test_tencent_channel_parser.py](file:///Users/leo/Projects/media-parser/tests/test_tencent_channel_parser.py)
* **执行命令**：`pytest tests/test_tencent_channel_parser.py`
