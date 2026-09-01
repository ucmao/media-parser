# Media Parser 项目技术文档与逆向百科

欢迎查阅 **Media Parser** 开发者文档与逆向工程知识库。

本项目是一个高性能、模块化、支持 **44 个主流媒体与 AI 内容平台** 的无水印音视频、图文及 LivePhoto 结构化解析引擎。

---

## 📚 文档导航

* 🏗️ **[系统架构与生命周期 (Architecture)](architecture.md)**：了解请求处理链路、302 跳转跟踪与 ParserFactory 自动发现机制。
* 🔍 **[通用逆向方法论 (Reverse Engineering Guide)](reverse-guide.md)**：掌握 SSR 数据提取、H5 接口伪装、JS 签名沙箱及抓包 SOP。
* 🧪 **[测试与回归验证 (Testing Guide)](testing.md)**：学习 Pytest 单元测试、Mock 构造与真实样本（Live Samples）测试。
* 📖 **平台实战指南 (Parser Guides)**：
  * **短视频与轻社区**：[抖音](parsers/douyin.md) ｜ [快手](parsers/kuaishou.md) ｜ [今日头条](parsers/xigua.md) ｜ [皮皮虾](parsers/pipixia.md) ｜ [皮皮搞笑](parsers/pipigaoxiao.md) ｜ [最右](parsers/zuiyou.md) ｜ [美拍](parsers/meipai.md) ｜ [微视](parsers/weishi.md) ｜ [绿洲](parsers/lvzhou.md) ｜ [番茄小说/红果短剧/红果漫剧](parsers/fanqie.md)
  * **图文与综合社区**：[小红书](parsers/xiaohongshu.md) ｜ [微信公众号](parsers/wechat-mp.md) ｜ [微博](parsers/weibo.md) ｜ [知乎](parsers/zhihu.md) ｜ [闲鱼](parsers/xianyu.md) ｜ [Soul](parsers/soul.md)
  * **长视频与弹幕/创作**：[哔哩哔哩](parsers/bilibili.md) ｜ [AcFun](parsers/acfun.md) ｜ [新片场](parsers/xinpianchang.md) ｜ [好看视频](parsers/haokan.md) ｜ [西瓜视频](parsers/xigua.md) ｜ [剪映](parsers/jianying.md) ｜ [快影](parsers/kwaiying.md)
  * **AI 生成与大模型**：[豆包 AI](parsers/doubao.md) ｜ [腾讯元宝](parsers/yuanbao.md) ｜ [即梦 AI](parsers/jimeng.md) ｜ [可灵 AI](parsers/kling.md) ｜ [海螺 AI](parsers/hailuo.md) ｜ [通义千问](parsers/qianwen.md) ｜ [夸克 AI](parsers/quark-ai.md) ｜ [小云雀 AI](parsers/xiaoyunque.md)
  * **音频与垂直频道**：[汽水音乐](parsers/qsmusic.md) ｜ [QQ音乐](parsers/qqmusic.md) ｜ [网易云音乐](parsers/netease-music.md) ｜ [酷狗音乐](parsers/kugou-music.md) ｜ [配音秀](parsers/peiyinxiu.md) ｜ [全民K歌](parsers/quanminkge.md) ｜ [虎牙](parsers/huya.md) ｜ [梨视频](parsers/lishipin.md) ｜ [微信视频号](parsers/wechat-channels.md) ｜ [腾讯频道](parsers/tencent-channel.md)

---

## 📊 平台支持与测试状态矩阵

> **图例说明**：
> * 🟢 **免配置**：无需提供任何 Cookie 或账号凭证，拉起服务即可直接解析。
> * ⚠️ **部分依赖**：绝大部分内容免登录，极少部分敏感/受限内容需在环境配置 Cookie。
> * 🔐 **必须配置**：平台强校验登录态，需在 `.env` 中提供对应 Cookie 后使用。

| 序号 | 平台名称 | 支持媒体类型 | 无水印直链 | 配置门槛 (Cookie 依赖) | 逆向提取模式 | 对应指南 |
| :--- | :--- | :--- | :---: | :---: | :--- | :--- |
| 1 | **抖音** | 视频 / 图文 / LivePhoto / 音频 / 字幕 / 合集 | ✅ 支持 | 🟢 免配置 | a_bogus 签名 + 动态 ttwid + SSR 容灾兜底 | [查看指南](parsers/douyin.md) |
| 2 | **小红书** | 图文 / LivePhoto / 视频 | ✅ 支持 | ⚠️ 部分需 Cookie | SSR HTML 注入数据提取 | [查看指南](parsers/xiaohongshu.md) |
| 3 | **快手** | 视频 / 图文 / 音频 | ✅ 支持 | 🟢 免配置 (内置游客凭证) | GraphQL / H5 双端多路由 Fallback | [查看指南](parsers/kuaishou.md) |
| 4 | **哔哩哔哩** | 视频 (MP4) / 音频分流 | ✅ 支持 | 🟢 免配置 | 官方 View + PlayURL API | [查看指南](parsers/bilibili.md) |
| 5 | **豆包 AI** | AI 视频生成直链 | ✅ 支持 | 🔐 需 `DOUBAO_COOKIE` | Web Session 维持 + 任务轮询 | [查看指南](parsers/doubao.md) |
| 6 | **即梦 AI** | AI 视频生成直链 | ✅ 支持 | 🟢 免配置 | 移动分享端接口解析 | [查看指南](parsers/jimeng.md) |
| 7 | **可灵 AI** | AI 视频生成直链 | ✅ 支持 | 🟢 免配置 | 快手可灵 H5 分享接口 | [查看指南](parsers/kling.md) |
| 8 | **海螺 AI** | AI 视频直链 / Prompt / 参考帧 | ✅ 支持 | 🟢 免配置 | Next.js Flight SSR 流式渲染解析 | [查看指南](parsers/hailuo.md) |
| 9 | **通义千问** | AI 图文 / 图像生成 | ✅ 支持 | ⚠️ 需 `YUANBAO_COOKIE` | AI Studio 移动分享端抓取 | [查看指南](parsers/qianwen.md) |
| 10 | **夸克 AI** | AI 图文 / 图像 | ✅ 支持 | 🟢 免配置 | 夸克 H5 分享路由解析 | [查看指南](parsers/quark-ai.md) |
| 11 | **小云雀 AI** | AI 图文 / 图像 | ✅ 支持 | 🟢 免配置 | 剪映小云雀分享端 | [查看指南](parsers/xiaoyunque.md) |
| 12 | **腾讯元宝** | AI 生图 / 图片编辑 / AI 视频 | ⚠️ 含原生水印 | 🟢 公开分享免配置 | Next.js SSR 对话数据提取 | [查看指南](parsers/yuanbao.md) |
| 13 | **微博** | 视频 / 微博正文 / 多图 | ✅ 支持 | 🟢 免配置 | 移动端 H5 接口 + Base62 解码 | [查看指南](parsers/weibo.md) |
| 14 | **知乎** | 视频 (Video Pin) / 想法 / 问答 | ✅ 支持 | 🟢 免配置 | Web API 多路由正则提取 | [查看指南](parsers/zhihu.md) |
| 15 | **皮皮虾** | 视频 / 图文 | ✅ 支持 | 🟢 免配置 | H5 接口数据解析 | [查看指南](parsers/pipixia.md) |
| 16 | **皮皮搞笑** | 视频 | ✅ 支持 | 🟢 免配置 | H5 页面 JSON 提取 | [查看指南](parsers/pipigaoxiao.md) |
| 17 | **最右** | 视频 / 图集 | ✅ 支持 | 🟢 免配置 | H5 接口键值映射提取 | [查看指南](parsers/zuiyou.md) |
| 18 | **AcFun** | 视频 (m3u8/MP4) | ✅ 支持 | 🟢 免配置 | KSPlayer 播放器参数还原 | [查看指南](parsers/acfun.md) |
| 19 | **汽水音乐** | UGC 视频 / 背景原声 | ✅ 支持 | 🟢 免配置 | 字节系分享 API | [查看指南](parsers/qsmusic.md) |
| 20 | **全民K歌** | 视频 / 伴奏音频 | ✅ 支持 | 🟢 免配置 | H5 播放页正则提取 | [查看指南](parsers/quanminkge.md) |
| 21 | **虎牙** | 视频 / 录播 | ✅ 支持 | 🟢 免配置 | 移动端短链解析 | [查看指南](parsers/huya.md) |
| 22 | **微信视频号** | 视频 | ✅ 支持 | 🟢 免配置 | 视频号短链解析 | [查看指南](parsers/wechat-channels.md) |
| 23 | **腾讯视频/频道** | 视频 | ✅ 支持 | 🟢 免配置 | 企鹅频道分享解析 | [查看指南](parsers/tencent-channel.md) |
| 24 | **西瓜视频** | 视频 | ✅ 支持 | 🟢 免配置 | 字节系引擎继承解析 | [查看指南](parsers/xigua.md) |
| 25 | **今日头条** | 视频 / 微头条视频 | ✅ 支持 | 🟢 免配置 | 字节系引擎继承解析 | [查看指南](parsers/xigua.md) |
| 26 | **新片场** | 高清视频 | ✅ 支持 | 🟢 免配置 | Next.js SSR 播放页提取 | [查看指南](parsers/xinpianchang.md) |
| 27 | **好看视频** | 百度短视频 | ✅ 支持 | 🟢 免配置 | 百度视频落地页提取 | [查看指南](parsers/haokan.md) |
| 28 | **美拍** | 视频 | ✅ 支持 | 🟢 免配置 | 网页 MP4 流还原 | [查看指南](parsers/meipai.md) |
| 29 | **微视** | 腾讯微视视频 | ✅ 支持 | 🟢 免配置 | 微视开放接口 | [查看指南](parsers/weishi.md) |
| 30 | **绿洲** | 新浪绿洲图文 | ✅ 支持 | 🟢 免配置 | 微博绿洲 H5 提取 | [查看指南](parsers/lvzhou.md) |
| 31 | **闲鱼** | 闲鱼图文贴 | ✅ 支持 | 🟢 免配置 | 淘系分享页解析 | [查看指南](parsers/xianyu.md) |
| 32 | **Soul** | 视频 / 瞬间 | ✅ 支持 | 🟢 免配置 | Web 话题页解析 | [查看指南](parsers/soul.md) |
| 33 | **剪映 / CapCut** | 模板视频 / Web协作视频 | ✅ 支持 | 🟢 免配置 | 字节剪映 & CapCut 协作 API | [查看指南](parsers/jianying.md) |
| 34 | **梨视频** | 资讯短视频 | ✅ 支持 | 🟢 免配置 | 动态防盗链时间戳解密 | [查看指南](parsers/lishipin.md) |
| 35 | **快影** | 模板视频 / 原声音乐 | ✅ 支持 | 🟢 免配置 | 快影 OpenAPI + 动态签名 | [查看指南](parsers/kwaiying.md) |
| 36 | **微信公众号** | 视频 / 文章插图图集 / 音频 | ✅ 支持 | 🟢 免配置 | SSR 正文解析 + 1080P 视频流提取与原画升级 | [查看指南](parsers/wechat-mp.md) |
| 37 | **拼多多** | 多多视频 / 商品图集 / 实物原图 | ✅ 支持 | 🟡 视频需 Cookie / 商品免配置 | anti-content 动态验签 + 307 素材提取 | [查看指南](parsers/pinduoduo.md) |
| 38 | **番茄小说** | 短剧视频 | ✅ 支持 | 🟢 免配置 | H5 推广页 HTML 提取 | [查看指南](parsers/fanqie.md) |
| 39 | **红果短剧** | 短剧视频 | ✅ 支持 | 🟢 免配置 | H5 推广页 HTML 提取 | [查看指南](parsers/fanqie.md) |
| 40 | **红果漫剧** | 漫剧/短剧视频 | ✅ 支持 | 🟢 免配置 | H5 推广页 HTML 提取 | [查看指南](parsers/fanqie.md) |
| 41 | **QQ音乐** | MV / 分享视频 / 多档 MP4 | ✅ 支持 | 🟢 免配置 | SSR 元数据 + MusicU 播放接口 | [查看指南](parsers/qqmusic.md) |
| 42 | **网易云音乐** | MV / Mlog / 歌曲 / 动态图集与 LivePhoto | ✅ 支持 | 🟢 公开内容免配置 | SSR / Event 数据 + 公开播放接口 | [查看指南](parsers/netease-music.md) |
| 43 | **酷狗音乐** | MV / 免费歌曲 / 多档 MP4 | ✅ 支持 | 🟢 公开内容免配置 | H5 公开接口签名 + 分享页数据 | [查看指南](parsers/kugou-music.md) |
| 44 | **配音秀** | 配音作品视频 (MP4) | ✅ 支持 | 🟢 公开内容免配置 | 作品页初始化数据提取 | [查看指南](parsers/peiyinxiu.md) |

---

## ⚡ 快速开始

### 1. 安装依赖
```bash
# 建议使用 Python 3.10+
pip install -r requirements.txt
```

### 2. 环境变量配置 (可选)
复制 `.env.example` 为 `.env`：
```bash
cp .env.example .env
```
根据需求在 `.env` 中按需配置：
```env
# 1. 抖音放映厅长视频风控通行证 (可选，仅 1% 的 /lvdetail/ 长片需要，非个人登录信息)
DOUYIN_COOKIE="s_v_web_id=verify_xxx; __ac_nonce=xxx;"

# 2. 豆包 AI 视频无水印权限凭证 (可选，用于获取 1080P 原始无水印视频)
DOUBAO_COOKIE="sessionid_ss=your_doubao_sessionid_ss"

# 3. 腾讯元宝 Cookie (可选，用于提取视频号原始流，涉及个人账号登录态，建议使用闲置小号)
YUANBAO_COOKIE="hy_user=xxx; hy_token=yyy;"

# 4. 拼多多 Cookie (可选，用于多多视频原画视频解析)
PINDUODUO_COOKIE="PDDAccessToken=xxx;"
```

### 3. 运行服务
```bash
# 开发环境启动 (端口 8051)
python app.py

# 访问 Web 演示前台：http://127.0.0.1:8051/
# 测试健康检查：http://127.0.0.1:8051/api/health
```

---

## ⚖️ 免责声明 (Disclaimer)

本项目所有代码和文档仅用于**网络技术研究、接口逆向工程学习与防御性安全交流**。
使用者请遵守各目标平台的《用户服务协议》与相关法律法规，不得用于任何形式的商业盈利抓取或恶意攻击行为。因使用本工具造成的任何直接或间接法律责任由使用者自行承担。
