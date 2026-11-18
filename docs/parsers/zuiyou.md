# 最右 (Zuiyou) 逆向解析指南

本篇详细记录 **最右 (Zuiyou)** 搞笑视频与神评图文帖子的接口抓取与多画质原图解析方案。

---

## 1. 平台特征与支持能力

* **平台标识**：`最右`
* **支持媒体类型**：高清视频 (MP4) / 多图图集 (原图 / WebP) / 实况图 (Live Photo 封面 + 动态片段) / 封面 / 帖子正文 / 作者信息
* **常见链接形态**：
  * 短链接：`https://s.izuiyou.com/s/ABCDEF` 或 `https://s.izuiyou.com/...`
  * 分享落地页：`https://share.xiaochuankeji.cn/hybrid/share/post?pid=423835942&vid=2542343457`
  * 图文帖子页：`https://share.xiaochuankeji.cn/hybrid/share/post?pid=419346905`
* **Cookie 依赖**：无需 Cookie。

---

## 2. 核心逆向流程

1. **提取帖子 PID**：从分享链接的 Query 中提取 `pid`。
2. **核心接口**：
   * 接口：`POST https://share.xiaochuankeji.cn/planck/share/post/detail_h5`
   * 请求头：`Referer: https://share.xiaochuankeji.cn/`
   * 载荷：`{"h_av": "5.2.13.011", "pid": pid}`
3. **视频、图集与实况混合提取**：
   * **动态媒体与时长划分**：
     * 接口中 `data.post.videos` 存放所有动态媒体（包括主视频与实况图短片段）。
     * 最右实况图动态片段时长实测为 1~3 秒，而帖子主视频通常在 15 秒以上。
     * 解析器设定 `LIVE_PHOTO_MAX_DURATION = 5` 秒作为阈值区分两者。
   * **主视频提取 (`get_real_video_url`)**：
     * 遍历动态媒体，过滤掉时长 $\le 5$ 秒的实况片段，提取真正的主视频播放直链。
   * **图集与实况提取 (`get_image_list`)**：
     * 遍历 `data.post.imgs` 列表：
       * **普通静态图片**（未命中 `videos`）：按画质优先级 `origin` (原图无损) -> `origin_webp` -> `540` -> `360` 提取图片直链字符串。
       * **实况图**（命中 `videos` 且时长 $\le 5$ 秒）：提取高清封面与动态片段 MP4 直链，封装为 `{"url": 封面, "live_photo_url": 动态片段}`。
       * **主视频封面帧**（命中 `videos` 且时长 $> 5$ 秒）：跳过，避免将视频抽帧混入图集。

---

## 3. 测试与验证

* **单元测试**：[tests/test_zuiyou_parser.py](file:///Users/leo/Projects/media-parser/tests/test_zuiyou_parser.py)
* **执行命令**：
  ```bash
  python -m unittest tests/test_zuiyou_parser.py
  ```

