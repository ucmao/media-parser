# 拼多多 (Pinduoduo) 逆向解析指南

本篇详细记录 **拼多多 (Pinduoduo)** 旗下多多视频、商品短链与评价秀素材的逆向解析方案。

---

## 1. 平台特征与支持能力

* **平台标识**：`拼多多`
* **支持媒体类型**：
  * **多多视频**：无水印 MP4 原画视频 / 视频封面大图 / 视频标题 / 作者昵称与头像
  * **商品实物短链 / 评价秀**：商品实物高清原图 (JPEG/PNG) / 商品名称与评价ID
  * **纯普通商品详情页**：⚠️ *由于拼多多官方近期架构调整，移除了已登录 SSR 数据并对纯商品 API 启用了强风控降级，纯商品页面目前无法稳定直接提取（建议优先使用实物/评价秀分享短链或多多视频）*
* **常见链接形态**：
  * 多多视频：`https://mobile.yangkeduo.com/fyxmkief.html?feed_id=6960355310530660128&goods_id=...`
  * 实物/评价短链：`https://mobile.yangkeduo.com/goods.html?ps=6K2Mc4rjNT`（307 重定向携带 `_oak_share_url`）
  * 评价分享：`https://mobile.yangkeduo.com/mall_quality_assurance.html?_t_timestamp=review_detail&goods_id=...&review_id=...`
  * 普通商品链接：`https://mobile.yangkeduo.com/goods.html?goods_id=...` 或纯商品 `ps=` 短链
* **Cookie 依赖**：
  * **多多视频 (`feed_id`)**：需要 Cookie 凭据。**只需配置单一字段 `PDDAccessToken=xxx`**（或移动端完整 Cookie）至环境变量 `PINDUODUO_COOKIE` 或管理后台即可，结合 `anti-content` 验签即可稳定解析。未配置或失效时接口返回 `PINDUODUO_COOKIE_REQUIRED`。
  * **商品实物短链 / 评价秀 (`_oak_share_url`)**：无需 Cookie，直接提取高清原图素材。
  * **纯普通商品详情页**：拼多多已关闭服务端 SSR 注入且接口下发风控降级，仅配置 Cookie 无法绕过设备指纹校验。

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

### 2.4 商品详情页解析现状与风控机制
1. **SSR 机制改版**：
   * 原实现通过请求商品详情页 HTML，正则匹配内联脚本 `window.rawData` 并从 `store.initDataObj.goods` 提取轮播图及视频。
   * **最新变动**：拼多多目前对移动端 `goods.html` 全面启用了防爬与架构升级：未登录访问时固定返回 `initDataObj: {"needLogin": true}`；已登录访问时服务端改用 CSR（客户端异步渲染），直接返回 `window.rawData = null;`，已彻底移除 HTML 内联商品数据。
2. **异步接口风控降级 (`700002`)**：
   * 前端异步商品接口为 `api/oak/integration/render`。
   * 当使用脚本环境调用时，即使携带有效 `PDDAccessToken` 与 `anti-content`，拼多多服务端也会识别非真实设备指纹并返回 `"encrypt_status": 1`，前端源码处理逻辑为：
     ```javascript
     if (1 === t?.encrypt_status) {
         var n = new Error("风控加密数据触发降级");
         throw n.errorCode = 700002, n;
     }
     ```
     触发该风控降级后，接口会将商品主图、价格、标题等核心字段置空。
3. **解析策略建议**：
   * 优先使用拼多多 App 内的**“带图评价分享”**或**“好物圈实物卡片分享”**，利用 307 重定向中的 `_oak_share_url` 提取高清大图；
   * 视频类内容建议直接使用**“多多视频”**链接，配合 `PINDUODUO_COOKIE="PDDAccessToken=xxx;"` 即可稳定解析。

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
