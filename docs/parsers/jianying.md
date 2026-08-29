# 剪映 / CapCut 逆向解析指南

本篇详细记录字节跳动旗下 **剪映 (Jianying)** 移动端模板视频以及 **CapCut (剪映网页/协作版 `capcut.cn`)** 协作审阅视频的原生解析方案。

---

## 1. 平台特征与支持能力

* **平台标识**：`剪映`
* **支持媒体类型**：高清模板视频 (MP4) / 协作审阅视频 / 高清封面图 / 标题 / 创作者信息
* **支持域名**：
  * `lv.ulikecam.com`（剪映移动端模板分享）
  * `www.capcut.cn` / `capcut.cn`（CapCut 网页版/桌面协作分享）
* **常见链接形态**：
  * **剪映移动端模板长链**：`https://lv.ulikecam.com/activity/lv/sharevideo?template_id=7631885529415568665`
  * **CapCut 协作审阅分享**：`https://www.capcut.cn/share/7678345113499604249?t=1`
* **Cookie 依赖**：🟢 免配置（开箱即用）。

---

## 2. 核心逆向流程

### 分支 A：剪映移动端模板分享 (`lv.ulikecam.com`)
1. **提取 Template ID**：从 URL Query 参数提取 `template_id` 与 `item_type`。
2. **计算接口签名 (Sign)**：
   $$\text{sign} = \text{MD5}("9e2c|mplates|0||" + \text{timestamp} + "||11ac")$$
3. **请求模板详情**：
   - 接口：`POST https://lv-api.ulikecam.com/lv/v1/web/replicate/multi_get_templates`
   - 入参：`{"sdk_version": "100.0.0", "id": [template_id], "scene": "share", "item_type": item_type}`
4. **提取媒体直链**：从 `data.templates[0]` 中直接提取 `video_url`、`cover_url` 与作者信息。

---

### 分支 B：CapCut 网页协作分享 (`capcut.cn/share/:id`)
CapCut 协作分享采用独特的两阶段版本聚合与切片防盗链机制：

1. **第一阶段：Cluster 版本聚合查询**：
   - 接口：`POST https://www.capcut.cn/lv/v1/coordination/cluster_list`
   - 签名算法：$$\text{sign} = \text{MD5}("9e2c|" + \text{url.slice}(-7) + "|7||" + \text{timestamp} + "||11ac")$$
   - 入参：`{"share_id": target_id, "password": ""}`
   - 提取出项目最新版本对应的子 `share_id`（`share_info_list[0].share_id`）。

2. **第二阶段：媒体详情与纯净流提取**：
   - 接口：`POST https://www.capcut.cn/lv/v1/coordination/share_detail_query`
   - 入参：`{"share_id": inner_share_id}`
   - **关键防盗链处理**：
     - `data.video` 字段为 WebAssembly AES 切片混淆流，直接播放会黑屏；
     - **解析器优先提取 `data.normal_video` 中的标准 H.264 MP4 直链**（`player_720p.main_url` / `player_480p.main_url`），实现 0 解码错误的开箱即播。

---

## 3. 测试与验证

* **单元测试**：[tests/test_jianying_parser.py](file:///Users/leo/Projects/media-parser/tests/test_jianying_parser.py)
* **真实样本验证**：
  ```bash
  python3 tests/manual_verify_parsers.py --platform 剪映
  ```

