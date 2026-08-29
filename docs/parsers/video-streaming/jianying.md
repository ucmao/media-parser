# 剪映 (Jianying) 逆向解析指南

本篇详细记录字节跳动旗下 **剪映** 模板视频与剪同款视频的解析方案。

---

## 1. 平台特征与支持能力

* **平台标识**：`剪映`
* **支持媒体类型**：高清模板视频 (MP4) / 封面图 / 模板标题
* **常见链接形态**：
  * 分享长链：`https://lv.ulikecam.com/activity/lv/sharevideo?template_id=7631885529415568665`
* **Cookie 依赖**：无需 Cookie。

---

## 2. 核心逆向流程

1. **提取 Template ID**：从 Query 参数中解析 `template_id`。
2. **调用剪映开放接口**：
   * 接口：`https://lv.ulikecam.com/activity/lv/sharevideo` 或剪映移动端模板 API。
3. **提取视频播放源**：从返回数据中提取视频直链 `video_url`。

---

## 3. 测试与验证

* **单元测试**：[tests/test_jianying_parser.py](file:///Users/leo/Projects/media-parser/tests/test_jianying_parser.py)
* **执行命令**：`pytest tests/test_jianying_parser.py`
