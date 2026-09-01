# QQ 音乐解析指南

## 支持范围

- `c6.y.qq.com/base/fcgi-bin/u` 分享短链
- `i2.y.qq.com/n3/other/pages/details/mv.html?vid=...` MV / 分享视频页
- `y.qq.com/n/ryqq/mv/{vid}` 桌面端 MV 地址
- 标题、封面、上传者或歌手信息
- 多档公开 MP4 地址，默认把最高可用清晰度作为 `video_url`

当前接入针对反馈库中实际出现的 QQ 音乐 MV / 分享视频。普通歌曲的完整音频受会员、版权区域和登录态控制，暂不把试听或会员流伪装成可下载音频。

## 解析流程

1. 跟随 `c6.y.qq.com` 的 302 跳转，保留落地页的 `vid`。
2. 读取分享页 `window.__ssrFirstPageData__`，补充标题、封面与上传者。
3. 调用 QQ 音乐 `musicu.fcg` 的 MV 信息和播放地址模块。
4. 过滤接口中不可播放的档位，按 `filetype` 从高到低排序并去重。
5. API 返回时统一将 `http://` 媒体地址升级为 HTTPS。

## 返回字段

| 字段 | 来源 |
| --- | --- |
| `video_id` | 分享页查询参数 `vid` 或桌面端 MV 路径 |
| `title` | SSR / MV 信息接口中的 `name` |
| `cover_url` | `cover_pic` 或 `first_frame_pic` |
| `author` | 分享上传者，缺失时回退到歌手 |
| `video_url` | 最高可用 MP4 档位 |
| `video_list` | 两档及以上时返回全部可用清晰度 |

## 限制

- 私密、下架、付费或地区受限 MV 可能不返回播放地址。
- 播放 URL 带有效期签名，应在解析后及时使用，不建议长期缓存。
- 普通歌曲音频不在当前支持范围内。

## 验证

```bash
python3 -m unittest tests.test_qqmusic_parser
python3 tests/manual_verify_parsers.py --platform "QQ音乐" --limit 2
```
