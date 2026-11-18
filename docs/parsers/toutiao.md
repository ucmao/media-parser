# 今日头条 (Toutiao) 逆向解析指南

本篇详细记录字节跳动旗下 **今日头条 (Toutiao)** 视频、中长视频、微头条图文及长文文章的逆向解析方案。

---

## 1. 平台特征与支持能力

* **平台标识**：`今日头条`
* **支持媒体类型**：高清视频 (MP4，最高 1080P/720P) / 微头条图文图集 / 长文正文内嵌配图 / 封面图 / 标题与清洗正文 / 创作者信息
* **常见链接形态**：
  * 短链接：`https://m.toutiao.com/is/fLrXD62Zo2U/` 或 `https://m.toutiao.com/is/geu37y7CA4w/`
  * 推广/分享链接：`https://adshare.toutiao.com/s/...` 或 `https://adshare.toutiao.com/...`
  * 网页链接：`https://www.toutiao.com/video/7680960670263493172/` 或 `https://www.toutiao.com/article/7680960670263493172/`
  * 移动端落地页：`https://m.toutiao.com/video/7680960670263493172/` 或 `https://m.toutiao.com/i7680960670263493172/`
  * 微头条：`https://m.toutiao.com/w/1876628745217031/`（短链解析后通常落到该形态）
* **Cookie 依赖**：🟢 免配置，无需任何 Cookie 即可直接匿名解析。

---

## 2. 核心逆向流程与架构设计

今日头条视频涵盖两种内容形态：

### 2.1 头条原生中长视频 / 资讯视频 (`aid=13`)
1. **移动端 SSR 数据提取**：
   * 携带移动端 `User-Agent` 请求移动落地页（如 `https://m.toutiao.com/video/{item_id}/` 或 `https://m.toutiao.com/i{item_id}/`）。
   * 提取页面中的 `<script id="RENDER_DATA">` 标签，进行 URL 解码与 JSON 解析。
   * 读取 `articleInfo` 节点中的标题 `title`、封面 `posterUrl`、作者信息 `mediaUser`。
2. **ByteDance VOD 鉴权解密**：
   * 从 `articleInfo` 中获取 `playAuthTokenV2` 凭证，Base64 解码得到包含 AWS4-HMAC-SHA256 签名参数的 `GetPlayInfoToken`。
   * 请求字节跳动官方 VOD 调度接口：`https://vod.bytedanceapi.com/?{GetPlayInfoToken}`。
   * 从返回的 `PlayInfoList` 列表中，按 `Bitrate` 码率降序优选最高清晰度的 MP4 直链。

### 2.2 抖音联通短视频 / Feed 流视频 (`aid=1128`)
* 当头条 SSR 页面为纯短视频形态时，自动回退并调用抖音移动 Feed 核心接口（`api5-normal-c-hl.amemv.com/aweme/v1/feed/`）及 PC Web 兜底接口，实现 100% 覆盖。

### 2.3 微头条图文 (`articleType=weitoutiao`)
微头条落地页（`https://m.toutiao.com/w/{gid}/`）的 `articleInfo` 节点只包含 `gid`、`groupSource` 等元信息，正文、配图与作者全部挂在 `articleInfo.thread.threadBase` 下：

| 字段 | 含义 |
| :--- | :--- |
| `threadBase.content` / `richContent` | 正文（纯文本 / HTML） |
| `threadBase.largeImageList` | 配图列表，元素 `url` 为可直接下载的图片地址 |
| `threadBase.user.info` | 作者昵称 `name` 与头像 `avatarUrl` |
| `seoTDK.title` | 页面标题（正文截断 + `-今日头条` 后缀） |

`ToutiaoParser._normalize_article()` 负责把 `threadBase` 归一化进 `articleInfo`（`title` / `content` / `mediaUser` / `threadImageList`），后续取值方法与视频形态共用；`get_image_list()` 同时会收集正文 HTML 中 `<img>` 的 `src` 或 `data-src`，覆盖图文长文配图。

> 若只读取 `articleInfo.title` / `articleInfo.content`，微头条会因两字段缺失而返回 `MEDIA_NOT_FOUND`。

```python
from src.parser_factory import register_parser
from src.parsers.douyin_parser import DouyinParser

@register_parser("今日头条")
class ToutiaoParser(DouyinParser):
    """今日头条分享解析器，支持移动端 SSR + ByteDance VOD 调度及抖音链路兜底。"""
```

---

## 3. 测试与验证

* **单元测试**：[tests/test_toutiao_parser.py](file:///Users/leo/Projects/media-parser/tests/test_toutiao_parser.py)
* **执行命令**：`python3 -m unittest tests/test_toutiao_parser.py`
