# 皮皮虾 (Pipixia) 逆向解析指南

本篇详细记录字节跳动旗下 **皮皮虾 (Pipixia)** 短视频与图文帖子的逆向提取方案。

---

## 1. 平台特征与支持能力

* **平台标识**：`皮皮虾`
* **支持媒体类型**：无水印视频 (MP4) / 图文帖子 / 评论区原声
* **常见链接形态**：
  * 短链接：`https://h5.pipix.com/s/lggjR-ynbpI/`
  * 移动落地页：`https://h5.pipix.com/item/6987123456789`
* **Cookie 依赖**：无需 Cookie。

---

## 2. 核心逆向流程

1. **302 跳转与 ID 提取**：请求短链获取 `Location` 头部，提取最后的纯数字 `item_id` / `cell_id`。
2. **移动端 API 抓取**：
   * 接口：`https://api.pipix.com/bds/cell/cell_comment/`
   * 参数：`cell_id={cell_id}&cell_type=1&api_version=1&aid=1319&app_name=super`
3. **无水印直链提取**：
   * 视频直链位于 `data.cell_comments[0].comment_info.item.video.video_high.url_list[0].url`。

---

## 3. 测试与验证

* **单元测试**：[tests/test_pipixia_parser.py](file:///Users/leo/Projects/media-parser/tests/test_pipixia_parser.py)
* **命令**：`pytest tests/test_pipixia_parser.py`
