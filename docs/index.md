# Media Parser 项目技术文档与逆向百科

欢迎查阅 **Media Parser** 开发者文档与逆向工程知识库。

本项目是一个高性能、模块化、支持 **30+ 主流媒体与 AI 内容平台** 的无水印音视频、图文及 LivePhoto 结构化解析引擎。

---

## 📚 文档导航

* 🏗️ **[系统架构与生命周期 (Architecture)](architecture.md)**：了解请求处理链路、302 跳转跟踪与 ParserFactory 自动发现机制。
* 🔍 **[通用逆向方法论 (Reverse Engineering Guide)](reverse-guide.md)**：掌握 SSR 数据提取、H5 接口伪装、JS 签名沙箱及抓包 SOP。
* 🧪 **[测试与回归验证 (Testing Guide)](testing.md)**：学习 Pytest 单元测试、Mock 构造与真实样本（Live Samples）测试。
* 📖 **平台实战指南 (Parser Guides)**：
  * **短视频与轻社区**：[抖音](parsers/douyin.md) ｜ [快手](parsers/kuaishou.md) ｜ [皮皮虾](parsers/pipixia.md) ｜ [皮皮搞笑](parsers/pipigaoxiao.md) ｜ [最右](parsers/zuiyou.md) ｜ [美拍](parsers/meipai.md) ｜ [微视](parsers/weishi.md) ｜ [绿洲](parsers/lvzhou.md)
  * **图文与综合社区**：[小红书](parsers/xiaohongshu.md) ｜ [微博](parsers/weibo.md) ｜ [知乎](parsers/zhihu.md) ｜ [闲鱼](parsers/xianyu.md) ｜ [Soul](parsers/soul.md)
  * **长视频与弹幕/创作**：[哔哩哔哩](parsers/bilibili.md) ｜ [AcFun](parsers/acfun.md) ｜ [新片场](parsers/xinpianchang.md) ｜ [好看视频](parsers/haokan.md) ｜ [西瓜视频](parsers/xigua.md) ｜ [剪映](parsers/jianying.md)
  * **AI 生成与大模型**：[豆包 AI](parsers/doubao.md) ｜ [即梦 AI](parsers/jimeng.md) ｜ [可灵 AI](parsers/kling.md) ｜ [通义千问](parsers/qianwen.md) ｜ [夸克 AI](parsers/quark-ai.md) ｜ [小云雀 AI](parsers/xiaoyunque.md)
  * **音频与垂直频道**：[汽水音乐](parsers/qsmusic.md) ｜ [全民K歌](parsers/quanminkge.md) ｜ [虎牙](parsers/huya.md) ｜ [梨视频](parsers/lishipin.md) ｜ [微信视频号](parsers/wechat-channels.md) ｜ [腾讯频道](parsers/tencent-channel.md)

---

## 📊 平台支持与测试状态矩阵

> **图例说明**：
> * 🟢 **免配置**：无需提供任何 Cookie 或账号凭证，拉起服务即可直接解析。
> * ⚠️ **部分依赖**：绝大部分内容免登录，极少部分敏感/受限内容需在环境配置 Cookie。
> * 🔐 **必须配置**：平台强校验登录态，需在 `.env` 中提供对应 Cookie 后使用。

| 序号 | 平台名称 | 支持媒体类型 | 无水印直链 | 配置门槛 (Cookie 依赖) | 逆向提取模式 | 对应指南 |
| :--- | :--- | :--- | :---: | :---: | :--- | :--- |
| 1 | **抖音** | 视频 / 图文 / LivePhoto / 音频 | ✅ 支持 | 🟢 免配置 | a_bogus 签名 + 动态 ttwid | [查看指南](parsers/douyin.md) |
| 2 | **小红书** | 图文 / LivePhoto / 视频 | ✅ 支持 | ⚠️ 部分需 Cookie | SSR HTML 注入数据提取 | [查看指南](parsers/xiaohongshu.md) |
| 3 | **快手** | 视频 / 图文 / 音频 | ✅ 支持 | 🟢 免配置 (内置游客凭证) | GraphQL / H5 双端多路由 Fallback | [查看指南](parsers/kuaishou.md) |
| 4 | **哔哩哔哩** | 视频 (MP4) / 音频分流 | ✅ 支持 | 🟢 免配置 | 官方 View + PlayURL API | [查看指南](parsers/bilibili.md) |
| 5 | **豆包 AI** | AI 视频生成直链 | ✅ 支持 | 🔐 需 `DOUBAO_COOKIE` | Web Session 维持 + 任务轮询 | [查看指南](parsers/doubao.md) |
| 6 | **即梦 AI** | AI 视频生成直链 | ✅ 支持 | 🟢 免配置 | 移动分享端接口解析 | [查看指南](parsers/jimeng.md) |
| 7 | **可灵 AI** | AI 视频生成直链 | ✅ 支持 | 🟢 免配置 | 快手可灵 H5 分享接口 | [查看指南](parsers/kling.md) |
| 8 | **通义千问** | AI 图文 / 图像生成 | ✅ 支持 | ⚠️ 需 `YUANBAO_COOKIE` | AI Studio 移动分享端抓取 | [查看指南](parsers/qianwen.md) |
| 9 | **夸克 AI** | AI 图文 / 图像 | ✅ 支持 | 🟢 免配置 | 夸克 H5 分享路由解析 | [查看指南](parsers/quark-ai.md) |
| 10 | **小云雀 AI** | AI 图文 / 图像 | ✅ 支持 | 🟢 免配置 | 剪映小云雀分享端 | [查看指南](parsers/xiaoyunque.md) |
| 11 | **微博** | 视频 / 微博正文 / 多图 | ✅ 支持 | 🟢 免配置 | 移动端 H5 接口 + Base62 解码 | [查看指南](parsers/weibo.md) |
| 12 | **知乎** | 视频 (Video Pin) / 想法 / 问答 | ✅ 支持 | 🟢 免配置 | Web API 多路由正则提取 | [查看指南](parsers/zhihu.md) |
| 13 | **皮皮虾** | 视频 / 图文 | ✅ 支持 | 🟢 免配置 | H5 接口数据解析 | [查看指南](parsers/pipixia.md) |
| 14 | **皮皮搞笑** | 视频 | ✅ 支持 | 🟢 免配置 | H5 页面 JSON 提取 | [查看指南](parsers/pipigaoxiao.md) |
| 15 | **最右** | 视频 / 图集 | ✅ 支持 | 🟢 免配置 | H5 接口键值映射提取 | [查看指南](parsers/zuiyou.md) |
| 16 | **AcFun** | 视频 (m3u8/MP4) | ✅ 支持 | 🟢 免配置 | KSPlayer 播放器参数还原 | [查看指南](parsers/acfun.md) |
| 17 | **汽水音乐** | UGC 视频 / 背景原声 | ✅ 支持 | 🟢 免配置 | 字节系分享 API | [查看指南](parsers/qsmusic.md) |
| 18 | **全民K歌** | 视频 / 伴奏音频 | ✅ 支持 | 🟢 免配置 | H5 播放页正则提取 | [查看指南](parsers/quanminkge.md) |
| 19 | **虎牙** | 视频 / 录播 | ✅ 支持 | 🟢 免配置 | 移动端短链解析 | [查看指南](parsers/huya.md) |
| 20 | **微信视频号** | 视频 | ✅ 支持 | 🟢 免配置 | 视频号短链解析 | [查看指南](parsers/wechat-channels.md) |
| 21 | **腾讯视频/频道** | 视频 | ✅ 支持 | 🟢 免配置 | 企鹅频道分享解析 | [查看指南](parsers/tencent-channel.md) |
| 22 | **西瓜视频** | 视频 | ✅ 支持 | 🟢 免配置 | 字节系引擎继承解析 | [查看指南](parsers/xigua.md) |
| 23 | **新片场** | 高清视频 | ✅ 支持 | 🟢 免配置 | Next.js SSR 播放页提取 | [查看指南](parsers/xinpianchang.md) |
| 24 | **好看视频** | 百度短视频 | ✅ 支持 | 🟢 免配置 | 百度视频落地页提取 | [查看指南](parsers/haokan.md) |
| 25 | **美拍** | 视频 | ✅ 支持 | 🟢 免配置 | 网页 MP4 流还原 | [查看指南](parsers/meipai.md) |
| 26 | **微视** | 腾讯微视视频 | ✅ 支持 | 🟢 免配置 | 微视开放接口 | [查看指南](parsers/weishi.md) |
| 27 | **绿洲** | 新浪绿洲图文 | ✅ 支持 | 🟢 免配置 | 微博绿洲 H5 提取 | [查看指南](parsers/lvzhou.md) |
| 28 | **闲鱼** | 闲鱼图文贴 | ✅ 支持 | 🟢 免配置 | 淘系分享页解析 | [查看指南](parsers/xianyu.md) |
| 29 | **Soul** | 视频 / 瞬间 | ✅ 支持 | 🟢 免配置 | Web 话题页解析 | [查看指南](parsers/soul.md) |
| 30 | **剪映** | 剪映模板视频 | ✅ 支持 | 🟢 免配置 | 字节剪映 API | [查看指南](parsers/jianying.md) |
| 31 | **梨视频** | 资讯短视频 | ✅ 支持 | 🟢 免配置 | 动态防盗链时间戳解密 | [查看指南](parsers/lishipin.md) |

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
