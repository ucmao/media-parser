# 拼多多 (Pinduoduo) 逆向解析指南

本篇详细记录 **拼多多 (Pinduoduo)** 旗下多多视频、商品短链与评价秀素材的逆向解析方案。

---

## 1. 平台特征与支持能力

* **平台标识**：`拼多多`
* **支持媒体类型**：
  * **多多视频**：无水印 MP4 原画视频 / 视频封面大图 / 视频标题 / 作者昵称与头像
  * **商品实物短链 / 评价秀**：商品实物高清原图 (JPEG/PNG) / 商品名称与评价ID
  * **商品详情页**：SSR 轮播图集 / 讲解视频
* **常见链接形态**：
  * 多多视频：`https://mobile.yangkeduo.com/fyxmkief.html?feed_id=6960355310530660128&goods_id=...`
  * 商品短链：`https://mobile.yangkeduo.com/goods.html?ps=6K2Mc4rjNT`
  * 评价分享：`https://mobile.yangkeduo.com/mall_quality_assurance.html?_t_timestamp=review_detail&goods_id=...&review_id=...`
  * 商品长链：`https://mobile.yangkeduo.com/goods.html?goods_id=...`
* **Cookie 依赖**：
  * **商品实物短链 (`ps=` / `_oak_share_url`)**：无需 Cookie，直接提取高清原图。
  * **多多视频 (`feed_id`)**：官方接口强风控校验，需要已登录账号的 Cookie (`PINDUODUO_COOKIE`)。浏览器模拟手机端访问 `mobile.yangkeduo.com/personal.html` 登录后复制完整 Cookie 即可（须包含 `PDDAccessToken`）；未配置时返回 `PINDUODUO_COOKIE_REQUIRED`。

---

## 2. 核心逆向流程

### 2.1 防爬签名机制 (`anti-content`)
拼多多全站 API（包括 `api/hub/dsp_detail/weak/list/get` 和 `api/oak/integration/render`）强制要求在请求头 `anti-content` 和请求体中携带动态生成的环境特征与行为验签 Token（前缀为 `0as...`）。
本项目在 [utils/signer/pinduoduo/anti_signer.py](file:///Users/leo/Projects/media-parser/utils/signer/pinduoduo/anti_signer.py) 中，通过 `py_mini_racer` 引擎加载前端指纹算法模块，在纯 Python 内存环境下约 160ms 内生成符合拼多多风控规范的有效 `anti-content`，无需外部 Node.js 进程服务。

### 2.2 多多视频 (Duoduo Video) 解析
1. 从分享链接中提取 `feed_id`。
2. 构造 `POST` 请求访问 `https://mobile.yangkeduo.com/proxy/api/api/hub/dsp_detail/weak/list/get`（备用 `https://api.pinduoduo.com/api/hub/dsp_detail/weak/list/get`）。
3. 请求头携带 `anti-content` 以及环境变量 `PINDUODUO_COOKIE`（若有）。
4. 请求体：
   ```json
   {
     "base": {
       "scene_id": "55",
       "mode": 0,
       "direction": 0,
       "list_id": "<random 10 chars>",
       "ext": "{\"feed_id_list\": [\"<feed_id>\"], \"page_from\": \"602100\", \"load_author\": true, \"load_data\": true}"
     },
     "anti_content": "<anti-content>"
   }
   ```
5. 从返回数据 `result.feeds[0].data` 中提取：
   * 视频播放直链：优先提取 `h5_auto_play_url` / `native_auto_play_url` 或 `feedMedia`（`mediaType == 1`）。
   * 高清封面图：`cover` 或 `feedMedia`（`mediaType == 2`）。
   * 作者信息：`author_info` / `authorInfo` 中的昵称、头像和作者ID。
   * 视频标题：`title` / `feedTitle` / `desc` 或挂载商品名称 `goods_v2.goods_info.goods_name`。

### 2.3 商品实物图短链提取 (`ps` 307 重定向)
1. 请求 `goods.html?ps=...` 短链，响应 307 重定向至 `mall_quality_assurance.html`。
2. 重定向 URL 查询参数中包含商品与实物素材原图：`_oak_share_url=https%3A%2F%2Fimg.pddpic.com%2F...jpeg`。
3. 对该 URL 解码后，即可直接获得高清实物原图作为封面与图集，无需依赖账号登录。

### 2.4 商品详情页 SSR 解析
1. 请求商品详情页 HTML，匹配内联脚本 `window.rawData`。
2. 从 `store.initDataObj.goods` 节点中提取 `goods_name`（标题）、`banner` / `gallery`（高清轮播大图列表）及 `video.url`（商品讲解视频）。

---

## 3. 测试与验证

* **单测验证**：
  * [tests/test_anti_signer.py](file:///Users/leo/Projects/media-parser/tests/test_anti_signer.py)
  * [tests/test_pinduoduo_parser.py](file:///Users/leo/Projects/media-parser/tests/test_pinduoduo_parser.py)
* **执行命令**：
  ```bash
  python3 -m unittest tests/test_anti_signer.py
  python3 -m unittest tests/test_pinduoduo_parser.py
  ```
