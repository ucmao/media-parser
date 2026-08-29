# 最右 (Zuiyou) 逆向解析指南

本篇详细记录 **最右 (Zuiyou)** 搞笑视频与神评帖子的接口抓取方案。

---

## 1. 平台特征与支持能力

* **平台标识**：`最右`
* **支持媒体类型**：高清视频 (MP4) / 帖子正文 / 作者信息
* **常见链接形态**：
  * 分享落地页：`https://share.xiaochuankeji.cn/hybrid/share/post?pid=423835942&vid=2542343457`
* **Cookie 依赖**：无需 Cookie。

---

## 2. 核心逆向流程

1. **提取帖子 PID**：从分享链接的 Query 中提取 `pid`。
2. **核心接口**：
   * 接口：`POST https://share.xiaochuankeji.cn/planck/share/post/detail_h5`
   * 请求头：`Referer: https://share.xiaochuankeji.cn/`
   * 载荷：`{"h_av": "5.2.13.011", "pid": pid}`
3. **视频键值映射提取**：
   * 从 `data.post.imgs[0].id` 获得 `video_key`。
   * 通过 `data.post.videos[video_key].url` 取得最终播放直链。

---

## 3. 测试与验证

* **单元测试**：[tests/test_zuiyou_parser.py](file:///Users/leo/Projects/media-parser/tests/test_zuiyou_parser.py)
* **执行命令**：`pytest tests/test_zuiyou_parser.py`
