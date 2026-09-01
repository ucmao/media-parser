# 网易云音乐解析指南

## 支持范围

- `163cn.tv` 分享短链
- `fn.music.163.com` 的 MV 与 Mlog 分享页
- `music.163.com/mv?id=...` 与 `music.163.com/song?id=...`
- `music.163.com/event?id=...` 和 `y.music.163.com/m/event?id=...`
- MV / 动态视频多清晰度、免费歌曲完整音频、歌词、图集与 LivePhoto

## 分类解析

### MV

通过公开的 MV 详情接口获取标题、封面、歌手及带时效签名的 `brs` 播放地址，按 1080P、720P、480P 等清晰度降序输出。

### Mlog 动态视频

读取分享页的 `window.__INITIAL_PROPS__`，从 `mlogInfo.resource.content.video.urlInfos` 获取多档签名视频，并提取发布者、封面和正文。

### Event 动态

旧版 Event 分享需要访问桌面落地页并解析 `event-data`：

- `pics[].originUrl` 作为原图；
- `videoOriginalUrl` / `videoUrl` 作为 LivePhoto 动态部分；
- 关联免费歌曲继续请求完整音频与 LRC 歌词；
- Event 内的视频资源进入 `video_url` / `video_list`。

### 普通歌曲

歌曲详情通过公开接口获取；只有接口明确返回完整播放 URL 时才填写 `audio_url`。会员、付费、下架或区域受限歌曲不会把试听片段伪装成完整音频。

## 返回字段

| 字段 | 内容 |
| --- | --- |
| `video_id` | MV、Mlog、Event 或歌曲 ID |
| `title` | MV 名、动态标题或歌曲名 |
| `author` | 歌手或动态发布者 |
| `cover_url` | MV 封面、视频帧、专辑图或动态首图 |
| `video_url` | 最高可用清晰度视频 |
| `video_list` | 多档视频地址 |
| `audio_url` | 可公开播放的完整歌曲音频 |
| `subtitles` | LRC 转换后的时间轴歌词 |
| `image_list` | 动态原图及可选 `live_photo_url` |

## 限制

- 音频和视频 URL 带短期签名，应在解析后及时使用。
- 会员、付费、下架、私密或区域受限内容可能仅返回元数据。
- 已删除的旧 Event 无法恢复其媒体内容。

## 验证

```bash
python3 -m unittest tests.test_netease_music_parser
python3 tests/manual_verify_parsers.py --platform "网易云音乐"
```
