# Media Parser 项目技术文档与逆向百科

欢迎查阅 **Media Parser** 开发者文档与逆向工程知识库。

本项目是一个高性能、模块化、支持 **30+ 主流媒体与 AI 内容平台** 的无水印音视频、图文及 LivePhoto 结构化解析引擎。

---

## 📚 文档导航

* 🏗️ **[系统架构与生命周期 (Architecture)](architecture.md)**：了解请求处理链路、302 跳转跟踪与 ParserFactory 自动发现机制。
* 🔍 **[通用逆向方法论 (Reverse Engineering Guide)](reverse-guide.md)**：掌握 SSR 数据提取、H5 接口伪装、JS 签名沙箱及抓包 SOP。
* 🧪 **[测试与回归验证 (Testing Guide)](testing.md)**：学习 Pytest 单元测试、Mock 构造与真实样本（Live Samples）测试。
* 📖 **平台实战指南 (Parser Guides)**：
  * **短视频与轻社区**：[抖音](parsers/short-video/douyin.md) ｜ [快手](parsers/short-video/kuaishou.md) ｜ [皮皮虾](parsers/short-video/pipixia.md) ｜ [皮皮搞笑](parsers/short-video/pipigaoxiao.md) ｜ [最右](parsers/short-video/zuiyou.md) ｜ [美拍](parsers/short-video/meipai.md) ｜ [微视](parsers/short-video/weishi.md) ｜ [绿洲](parsers/short-video/lvzhou.md)
  * **图文与综合社区**：[小红书](parsers/community/xiaohongshu.md) ｜ [微博](parsers/community/weibo.md) ｜ [知乎](parsers/community/zhihu.md) ｜ [闲鱼](parsers/community/xianyu.md) ｜ [Soul](parsers/community/soul.md)
  * **长视频与弹幕/创作**：[哔哩哔哩](parsers/video-streaming/bilibili.md) ｜ [AcFun](parsers/video-streaming/acfun.md) ｜ [新片场](parsers/video-streaming/xinpianchang.md) ｜ [好看视频](parsers/video-streaming/haokan.md) ｜ [西瓜视频](parsers/video-streaming/xigua.md) ｜ [剪映](parsers/video-streaming/jianying.md)
  * **AI 生成与大模型**：[豆包 AI](parsers/ai-generation/doubao.md) ｜ [即梦 AI](parsers/ai-generation/jimeng.md) ｜ [可灵 AI](parsers/ai-generation/kling.md) ｜ [通义千问](parsers/ai-generation/qianwen.md) ｜ [夸克 AI](parsers/ai-generation/quark-ai.md) ｜ [小云雀 AI](parsers/ai-generation/xiaoyunque.md)
  * **音频与垂直频道**：[汽水音乐](parsers/audio-others/qsmusic.md) ｜ [全民K歌](parsers/audio-others/quanminkge.md) ｜ [虎牙](parsers/audio-others/huya.md) ｜ [梨视频](parsers/audio-others/lishipin.md) ｜ [微信视频号](parsers/audio-others/wechat-channels.md) ｜ [腾讯频道](parsers/audio-others/tencent-channel.md)

---

## 📊 平台支持与测试状态矩阵

> **图例说明**：
> * ✅ **支持 / 已验证** ｜ ⚠️ **条件依赖 (如需 Cookie)** ｜ ❌ **不支持 / 无需配置**

| 序号 | 平台名称 | 支持媒体类型 | 无水印直链 | 需配置 Cookie | 逆向提取模式 | 对应指南 |
| :--- | :--- | :--- | :---: | :---: | :--- | :--- |
| 1 | **抖音** | 视频 / 图文 / LivePhoto / 音频 | ✅ | ❌ | a_bogus 签名 + 动态 ttwid | [查看指南](parsers/short-video/douyin.md) |
| 2 | **小红书** | 图文 / LivePhoto / 视频 | ✅ | ⚠️ 部分需 Cookie | SSR HTML 注入数据提取 | [查看指南](parsers/community/xiaohongshu.md) |
| 3 | **快手** | 视频 / 图文 / 音频 | ✅ | ❌ (已内置游客凭证) | GraphQL / H5 双端多路由 Fallback | [查看指南](parsers/short-video/kuaishou.md) |
| 4 | **哔哩哔哩** | 视频 (MP4) / 音频分流 | ✅ | ❌ | 官方 View + PlayURL API | [查看指南](parsers/video-streaming/bilibili.md) |
| 5 | **豆包 AI** | AI 视频生成直链 | ✅ | ✅ `DOUBAO_COOKIE` | Web Session 维持 + 任务轮询 | [查看指南](parsers/ai-generation/doubao.md) |
| 6 | **即梦 AI** | AI 视频生成直链 | ✅ | ❌ | 移动分享端接口解析 | [查看指南](parsers/ai-generation/jimeng.md) |
| 7 | **可灵 AI** | AI 视频生成直链 | ✅ | ❌ | 快手可灵 H5 分享接口 | [查看指南](parsers/ai-generation/kling.md) |
| 8 | **通义千问** | AI 图文 / 图像生成 | ✅ | ⚠️ `YUANBAO_COOKIE` | AI Studio 移动分享端抓取 | [查看指南](parsers/ai-generation/qianwen.md) |
| 9 | **夸克 AI** | AI 图文 / 图像 | ✅ | ❌ | 夸克 H5 分享路由解析 | [查看指南](parsers/ai-generation/quark-ai.md) |
| 10 | **小云雀 AI** | AI 图文 / 图像 | ✅ | ❌ | 剪映小云雀分享端 | [查看指南](parsers/ai-generation/xiaoyunque.md) |
| 11 | **微博** | 视频 / 微博正文 / 多图 | ✅ | ❌ | 移动端 H5 接口 + Base62 解码 | [查看指南](parsers/community/weibo.md) |
| 12 | **知乎** | 视频 (Video Pin) / 想法 / 问答 | ✅ | ❌ | Web API 多路由正则提取 | [查看指南](parsers/community/zhihu.md) |
| 13 | **皮皮虾** | 视频 / 图文 | ✅ | ❌ | H5 接口数据解析 | [查看指南](parsers/short-video/pipixia.md) |
| 14 | **皮皮搞笑** | 视频 | ✅ | ❌ | H5 页面 JSON 提取 | [查看指南](parsers/short-video/pipigaoxiao.md) |
| 15 | **最右** | 视频 / 图集 | ✅ | ❌ | H5 接口键值映射提取 | [查看指南](parsers/short-video/zuiyou.md) |
| 16 | **AcFun** | 视频 (m3u8/MP4) | ✅ | ❌ | KSPlayer 播放器参数还原 | [查看指南](parsers/video-streaming/acfun.md) |
| 17 | **汽水音乐** | UGC 视频 / 背景原声 | ✅ | ❌ | 字节系分享 API | [查看指南](parsers/audio-others/qsmusic.md) |
| 18 | **全民K歌** | 视频 / 伴奏音频 | ✅ | ❌ | H5 播放页正则提取 | [查看指南](parsers/audio-others/quanminkge.md) |
| 19 | **虎牙** | 视频 / 录播 | ✅ | ❌ | 移动端短链解析 | [查看指南](parsers/audio-others/huya.md) |
| 20 | **微信视频号** | 视频 | ✅ | ❌ | 视频号短链解析 | [查看指南](parsers/audio-others/wechat-channels.md) |
| 21 | **腾讯视频/频道** | 视频 | ✅ | ❌ | 企鹅频道分享解析 | [查看指南](parsers/audio-others/tencent-channel.md) |
| 22 | **西瓜视频** | 视频 | ✅ | ❌ | 字节系引擎继承解析 | [查看指南](parsers/video-streaming/xigua.md) |
| 23 | **新片场** | 高清视频 | ✅ | ❌ | Next.js SSR 播放页提取 | [查看指南](parsers/video-streaming/xinpianchang.md) |
| 24 | **好看视频** | 百度短视频 | ✅ | ❌ | 百度视频落地页提取 | [查看指南](parsers/video-streaming/haokan.md) |
| 25 | **美拍** | 视频 | ✅ | ❌ | 网页 MP4 流还原 | [查看指南](parsers/short-video/meipai.md) |
| 26 | **微视** | 腾讯微视视频 | ✅ | ❌ | 微视开放接口 | [查看指南](parsers/short-video/weishi.md) |
| 27 | **绿洲** | 新浪绿洲图文 | ✅ | ❌ | 微博绿洲 H5 提取 | [查看指南](parsers/short-video/lvzhou.md) |
| 28 | **闲鱼** | 闲鱼图文贴 | ✅ | ❌ | 淘系分享页解析 | [查看指南](parsers/community/xianyu.md) |
| 29 | **Soul** | 视频 / 瞬间 | ✅ | ❌ | Web 话题页解析 | [查看指南](parsers/community/soul.md) |
| 30 | **剪映** | 剪映模板视频 | ✅ | ❌ | 字节剪映 API | [查看指南](parsers/video-streaming/jianying.md) |
| 31 | **梨视频** | 资讯短视频 | ✅ | ❌ | 动态防盗链时间戳解密 | [查看指南](parsers/audio-others/lishipin.md) |

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
如需解析受限的小红书笔记或大模型 AI 平台（如豆包），在 `.env` 中填入对应 Cookie：
```env
DOUBAO_COOKIE="your_doubao_cookie_here"
YUANBAO_COOKIE="your_yuanbao_cookie_here"
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
