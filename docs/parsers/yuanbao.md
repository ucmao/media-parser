# 腾讯元宝逆向解析指南

本篇记录腾讯元宝公开对话分享中的 AI 生图、图片编辑和 AI 视频媒体提取方案。

---

## 1. 平台特征与支持能力

* **平台标识**：`腾讯元宝`
* **支持媒体类型**：AI 生成图片、图片编辑结果、AI 生成视频及封面
* **常见链接形态**：
  * 对话短链：`https://yb.tencent.com/s/{shareId}`
  * 独立图片分享：`https://yuanbao.tencent.com/bot/app/share/beautifulPhotos/{shareId}?userId={userId}`
  * 独立视频分享：`https://yb.tencent.com/s/bot/app/share/loadingVideo/{shareId}`
* **Cookie 依赖**：公开对话分享无需 Cookie；独立分享页接口受限时可选复用 `YUANBAO_COOKIE`。

> [!NOTE]
> **水印说明**：
> 腾讯元宝在混元大模型完成图像/视频生成并导出文件时，系统已将“元宝”标识水印直接渲染写入文件图像中。官方目前无论在网页版、App 还是后端 API 中均未暴露无水印导出通道（登录用户本人点击下载同样带水印）。
> 本解析器提取的是腾讯云 COS 存储桶中保存的**最高清晰度官方原画直链**（保留官方原生水印），适合素材归档、文本/标题提取及媒体信息解析。


---

## 2. 核心逆向方案

元宝公开对话页使用 Next.js SSR。页面中的 `script#__NEXT_DATA__` 包含 `props.pageProps.fullChatShareData`，无需执行 JavaScript 即可取得分享内容。

主要数据路径如下：

```text
fullChatShareData.chat.convs[]
  └── speechesV2[].extra.replaces[].multimedias[]
      ├── type / mediaType / mimeType
      ├── downloadUrl / url / resourceUrl
      ├── cover / coverUrl
      └── thumbnailUrl / previewUrl
```

解析器只收集 `speaker == "ai"` 的多媒体结果，避免把用户上传的参考图误认为生成结果。媒体地址优先级为 `downloadUrl`、`url`、`resourceUrl`，视频封面优先使用 `downloadCoverUrl`、`cover`、`coverUrl`、`thumbnailUrl`。

---

## 3. 标题与作者

* 标题优先读取 `chat.shareCardInfo.title`，并移除开头的 `[图片]` 或 `[视频]` 标记。
* 标题缺失时回退到首条用户 `displayPrompt` 或 `speech`。
* 作者优先读取 `chat.userInfo`，再回退到用户对话记录中的 `role` 与 `userId`。

---

## 4. 独立分享页兜底

独立图片/视频页面可能直接在 `pageProps.shareDetailData` 中提供媒体信息。若首屏只有 `shareId`，解析器会尽力请求公开接口：

```text
POST https://yb.tencent.com/api/share/general_share_detail
```

该接口可能因内容过期、风控或分享被删除而返回空结果。普通 `/s/{shareId}` 对话分享的 SSR 路径更稳定，应作为主要支持形态。

---

## 5. 测试与验证

```bash
pytest tests/test_yuanbao_parser.py tests/test_web_fetcher.py tests/test_parser_factory.py
python3 tests/manual_verify_parsers.py --platform 腾讯元宝
```

真实样例覆盖 AI 生图和 AI 视频两种形态，记录在 `tests/live_parser_samples.json`。
