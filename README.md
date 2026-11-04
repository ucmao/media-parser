<div align="center">
<img src="static/images/logo.png" width="360" height="auto" alt="Media-Parser Logo">

**基于 Python 的多平台媒体原生本地解析系统**

[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE) [![Python Version](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/) [![Flask](https://img.shields.io/badge/Framework-Flask-000000?logo=flask&logoColor=white)](https://flask.palletsprojects.com/) [![Docker](https://img.shields.io/badge/Docker-Ready-2496ED?logo=docker&logoColor=white)](#-部署指南) [![Support](https://img.shields.io/badge/support-50%20Platforms-brightgreen.svg)](#-支持的平台矩阵)

<p align="center">
<a href="#-交流群">交流群</a> •
<a href="#-核心特性">核心特性</a> •
<a href="#-支持的平台矩阵">支持平台</a> •
<a href="#-项目原则与免责声明">项目原则</a> •
<a href="#-部署指南">部署指南</a> •
<a href="#-api-接口">API 接口</a> •
<a href="#-自动化测试与健康自检">测试自检</a> •
<a href="#-联系作者">联系作者</a>
</p>

Media-Parser是一款专为短视频创作者与开发者打造的**100%原生本地解析工具**。

通过“智能识别 -> 本地抓取 -> 提取地址 -> 快捷下载”的闭环，助你高效获取无水印素材。

**不依赖外部API，不套壳第三方库，无浏览器开销，纯底层协议与算法逆向。**

<br>

<div id="-交流群">
  <img src="static/images/wechat-qrcode.jpg" width="180" alt="微信交流二维码"><br>
  <sub>💬 <b>扫码添加作者微信</b>（备注 <code>media-parser</code> 拉你入群交流）</sub>
</div>

</div>

---

## ✨ 核心特性

* **极速轻量**：纯 HTTP 网络协议与底层算法逆向，免启动 Chromium/Playwright 等笨重浏览器，内存占用极低（<100MB），毫秒级极速响应。
* **原生自主**：100% 本地代码闭环抓取，零外部商用 API 或第三方代解析依赖，数据链路自主可控，杜绝断流与隐私泄露风险。
* **插件化解耦**：内置 `ParserFactory` 模块自动发现与工厂分发机制，50 个平台独立解耦，遵循统一的数据契约，新增与维护平台极度轻松（详见 [📖 系统架构与生命周期](docs/architecture.md)）。
* **开箱即用**：提供标准 JSON 接口、Web 体验页与轻量运营控制台，默认内置 SQLite，Docker Compose 一键构建。
* **访问控制**：支持客户注册、管理员配置有效期与积分、API Key 管理、全局与单平台开关、用户总量/单个密钥/平台全局三级 QPS 限流和调用日志。

---

## 💾 支持的平台矩阵

| 平台名称 | 作者 | 标题 | 文案 | 封面 | 视频 | 图集 | 多视频 | 实况 | 音频 | 字幕 | 逆向思路 |
| --- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **抖音** | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | [查看](docs/parsers/douyin.md) |
| **小红书** | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |  | ✓ |  |  | [查看](docs/parsers/xiaohongshu.md) |
| **视频号** | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |  |  | ✓ |  | [查看](docs/parsers/wechat-channels.md) |
| **微信公众号** | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |  | ✓ |  | [查看](docs/parsers/wechat-mp.md) |
| **快手** | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |  |  | ✓ |  | [查看](docs/parsers/kuaishou.md) |
| **哔哩哔哩** | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |  |  |  | [查看](docs/parsers/bilibili.md) |
| **豆包** | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |  | ✓ |  | [查看](docs/parsers/doubao.md) |
| **即梦AI** | ✓ | ✓ | ✓ | ✓ | ✓* | ✓ | ✓ |  |  |  | [查看](docs/parsers/jimeng.md) |
| **小云雀AI** | ✓ | ✓ | ✓ | ✓* | ✓* | ✓ |  |  |  |  | [查看](docs/parsers/xiaoyunque.md) |
| **可灵AI** | ✓ | ✓ |  | ✓ | ✓ |  |  |  |  |  | [查看](docs/parsers/kling.md) |
| **海螺AI** | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |  |  |  |  | [查看](docs/parsers/hailuo.md) |
| **夸克AI** | ✓ | ✓ |  | ✓ | ✓ | ✓ |  |  |  |  | [查看](docs/parsers/quark-ai.md) |
| **通义千问** | ✓ | ✓ |  | ✓ | ✓ | ✓ | ✓ |  |  |  | [查看](docs/parsers/qianwen.md) |
| **腾讯元宝** | ✓ | ✓ |  | ✓ | ✓* | ✓ | ✓ |  |  |  | [查看](docs/parsers/yuanbao.md) |
| **闲鱼** | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |  |  |  |  | [查看](docs/parsers/xianyu.md) |
| **拼多多** | ✓ | ✓ |  | ✓ | ✓ | ✓ |  |  | ✓ |  | [查看](docs/parsers/pinduoduo.md) |
| **Soul** | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |  |  |  |  | [查看](docs/parsers/soul.md) |
| **汽水音乐** | ✓ | ✓ |  | ✓ | ✓ |  |  |  | ✓ | ✓ | [查看](docs/parsers/qsmusic.md) |
| **QQ音乐** | ✓ | ✓ |  | ✓ | ✓ |  | ✓ |  | ✓ | ✓ | [查看](docs/parsers/qqmusic.md) |
| **网易云音乐** | ✓ | ✓ |  | ✓ | ✓ | ✓ |  |  | ✓ | ✓ | [查看](docs/parsers/netease-music.md) |
| **酷狗音乐** | ✓ | ✓ |  | ✓ | ✓ |  |  |  | ✓ |  | [查看](docs/parsers/kugou-music.md) |
| **配音秀** | ✓ | ✓ |  | ✓ | ✓ |  |  |  |  |  | [查看](docs/parsers/peiyinxiu.md) |
| **松果时刻** | ✓ | ✓ |  | ✓ | ✓ | ✓ | ✓ |  | ✓ |  | [查看](docs/parsers/pinecone-moment.md) |
| **腾讯频道** | ✓ | ✓ |  | ✓ | ✓ |  |  |  |  |  | [查看](docs/parsers/tencent-channel.md) |
| **剪映 / CapCut** | ✓ | ✓ |  | ✓ | ✓ | ✓ |  |  | ✓ |  | [查看](docs/parsers/jianying.md) |
| **快影** | ✓ | ✓ | ✓ | ✓ | ✓ |  |  |  | ✓ |  | [查看](docs/parsers/kwaiying.md) |
| **皮皮搞笑** | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |  |  |  |  | [查看](docs/parsers/pipigaoxiao.md) |
| **微视** | ✓ | ✓ |  | ✓ | ✓ |  |  |  |  |  | [查看](docs/parsers/weishi.md) |
| **AcFun** | ✓ | ✓ |  | ✓ | ✓ |  |  |  |  |  | [查看](docs/parsers/acfun.md) |
| **西瓜视频** | ✓ | ✓ | ✓ | ✓ | ✓ |  |  |  |  |  | [查看](docs/parsers/xigua.md) |
| **今日头条** | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |  |  |  |  | [查看](docs/parsers/toutiao.md) |
| **绿洲** | ✓ | ✓ |  | ✓ | ✓ | ✓ |  |  |  |  | [查看](docs/parsers/lvzhou.md) |
| **皮皮虾** | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |  |  |  |  | [查看](docs/parsers/pipixia.md) |
| **全民K歌** |   | ✓ |  | ✓ | ✓ |  |  |  |  |  | [查看](docs/parsers/quanminkge.md) |
| **新片场** | ✓ | ✓ |  | ✓ | ✓ |  | ✓ |  |  |  | [查看](docs/parsers/xinpianchang.md) |
| **好看视频** | ✓ | ✓ |  | ✓ | ✓ |  |  |  |  |  | [查看](docs/parsers/haokan.md) |
| **梨视频** | ✓ | ✓ |  | ✓ | ✓ |  |  |  |  |  | [查看](docs/parsers/lishipin.md) |
| **微博** | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |  | ✓ |  |  | [查看](docs/parsers/weibo.md) |
| **知乎** | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |  |  |  |  | [查看](docs/parsers/zhihu.md) |
| **虎牙** |   | ✓ |  | ✓ | ✓ |  |  |  |  |  | [查看](docs/parsers/huya.md) |
| **美拍** | ✓ | ✓ |  | ✓ | ✓ |  |  |  |  |  | [查看](docs/parsers/meipai.md) |
| **最右** | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |  | ✓ |  |  | [查看](docs/parsers/zuiyou.md) |
| **番茄小说** | ✓ | ✓ |  | ✓ | ✓ |  |  |  |  |  | [查看](docs/parsers/fanqie.md) |
| **红果短剧** | ✓ | ✓ |  | ✓ | ✓ |  |  |  |  |  | [查看](docs/parsers/fanqie.md) |
| **红果漫剧** | ✓ | ✓ |  | ✓ | ✓ |  |  |  |  |  | [查看](docs/parsers/fanqie.md) |
| **得物** | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |  |  |  |  | [查看](docs/parsers/dewu.md) |
| **网易LOFTER** | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |  |  |  |  | [查看](docs/parsers/lofter.md) |
| **星绘AI** | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |  |  |  |  | [查看](docs/parsers/butterflyai.md) |
| **央视** | ✓ | ✓ |  | ✓ | ✓ |  |  |  |  |  | [查看](docs/parsers/cctv.md) |
| **央视频** | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |  |  |  |  | [查看](docs/parsers/yangshipin.md) |

<sub>注：带 `*` 的项表示该素材保留官方原生水印，未带 `*` 的项均为纯净无水印素材。</sub>
> **Cookie凭据配置**：绝大多数平台支持免登录匿名解析；如需配置小红书、视频号等平台凭证，可参考 [`.env.example`](.env.example)，详细方法见 [📖 平台Cookie配置指南](docs/cookie-config.md)。
>
> **动态代理配置**：配置 `DYNAMIC_PROXY_API_URL` 后，Cookie 校验失败可自动触发平台级 15 分钟代理访问，并按有效期提前储备代理。详见 [📖 动态代理配置说明](docs/proxy-retry.md)。
>
> **逆向与抓包SOP**：各平台详细技术分析与抓包规范，请查阅 [📖 平台逆向指南索引](docs/index.md) 与 [📖 通用逆向方法论](docs/reverse-guide.md)。

---

## 🚀 部署指南

### 1. 运行模式选择

系统支持两种部署形态，根据你的实际使用场景按需选择：

| 运行模式 | 配置参数 | 适用场景 | 特性与说明 |
| :--- | :--- | :--- | :--- |
| **纯API微服务模式** | `API_ONLY=true` | 内部微服务、Bot/下载器后端、本地集成 | **开箱即用，免鉴权**：彻底关闭Web前后端，全接口无需API Key直接调用，零数据库开销，适合高并发与多容器扩展。 |
| **完整运营SaaS模式** | `API_ONLY=false`（默认） | 独立自建站点、发卡运营、多用户管理 | **带Web前后台**：提供前台体验页、用户中心、管理后台，支持API Key鉴权、积分扣除与多级QPS限流。 |

---

### 2. Docker Compose 部署（推荐）

```bash
# 1. 获取源码
git clone https://github.com/ucmao/media-parser.git
cd media-parser

# 2. （可选）配置环境变量与平台 Cookie
cp .env.example .env
# 若作为纯微服务运行，只需在 .env 中设置 API_ONLY=true
# 若需配置小红书/视频号等 Cookie 凭证，直接在 .env 中填入对应字段

# 3. 构建并启动服务
docker compose up -d --build

# 4. 查看日志与运行状态
docker compose logs -f web
```

**启动后的使用指引**：
- **微服务模式**：无需任何初始化，服务就绪后直接调用接口即可。
- **运营模式**：首次部署请访问 `http://localhost:8051/auth/setup` 创建管理员账号，初始化完成后入口自动关闭。数据默认持久化在 `./data` 目录。

---

### 3. Python 本地运行

适用于调试与二次开发，推荐 **Python 3.10+**：

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 启动服务
python app.py
```

---

## 🔌 API 接口

### 1. 接口调用方式

#### 方式 A：免鉴权调用（微服务模式）
无需申请或传递 API Key，直接传入分享链接即可解析：

```bash
curl 'http://localhost:8051/api/v1/parse?url=https://v.douyin.com/xxx/'
```

#### 方式 B：API Key 鉴权调用（运营模式）
在 URL 参数中附带后台生成的 API Key 即可调用：

```bash
curl 'http://localhost:8051/api/v1/parse?key=mp-xxx&url=https://v.douyin.com/xxx/'
```

> **提示**：接口同样完整支持 `POST` 请求（支持 JSON / Form 表单）及 `Authorization: Bearer <API_KEY>` 请求头鉴权，详细协议见 [📖 API接口与协议规范
](docs/api.md)。

---

### 2. 返回数据规范

接口以统一的 JSON 格式返回标题、正文文案、作者信息及提取出的多媒体资源（视频、图集、实况图、音频等）：

```json
{
  "retcode": 200,
  "retdesc": "成功",
  "data": {
    "video_id": "7123...",
    "platform": "抖音",
    "title": "视频标题内容",
    "desc": "视频文案内容",
    "video_url": "https://... (主视频地址)",
    "video_list": [
      "https://... (仅多视频/合集内容额外返回，首项与 video_url 相同)"
    ],
    "audio_url": "https://... (背景音乐/独立音频地址)",
    "cover_url": "https://... (高清封面地址)",
    "author": {
      "nickname": "作者昵称",
      "author_id": "作者ID",
      "avatar": "https://..."
    },
    "image_list": [
      "https://... (普通图集地址)",
      {
        "url": "https://... (实况图封面地址)",
        "live_photo_url": "https://... (实况图视频原件地址)"
      }
    ],
    "subtitles": [
      { "start": 0.64, "end": 2.12, "text": "文案/字幕内容" }
    ]
  },
  "succ": true
}
```

失败时会返回稳定的错误码：

```json
{
  "retcode": 400,
  "retdesc": "该链接尚未支持提取 / 解析失败",
  "data": null,
  "error_code": "PLATFORM_NOT_SUPPORTED",
  "succ": false
}
```

默认响应还会附带可由管理员配置或关闭的 `_tip` 服务信息字段。

> **接口说明**：标准对接建议统一使用 `/api/v1/parse`。在运营模式下，`/api/parse` 仅供网站首页在线体验（受 IP 频控限制）；在微服务模式下，`/api/v1/parse` 与 `/api/parse` 均为完全免鉴权的解析接口。

---

## 🧪 自动化测试与健康自检

本项目拥有完备的双层测试体系（Mock 单元测试 + 基于 [`tests/live_parser_samples.json`](tests/live_parser_samples.json) 的 300+ 条真实在线样本库回归）。遇到解析异常或日常部署验证时，可一键运行 50 平台健康自检：

```bash
# 50 平台极速冒烟测试（读取样本库，每个平台测 1 条最具代表性的链接，秒级完成）
python3 tests/manual_verify_parsers.py --limit 1

# 仅验证单个或指定平台（如：小云雀AI / 抖音）
python3 tests/manual_verify_parsers.py --platform "小云雀AI"
```

> 更多单测规范与 Mock 机制，请查阅 [📖 测试体系与回归验证](docs/testing.md)。

---

## 📩 联系作者

如果您在安装、使用过程中遇到问题，或有交流与定制需求，请通过以下方式联系：

<div align="center">
  <img src="static/images/wechat-qrcode.jpg" width="160" alt="微信二维码"><br>
  <sub>💬 <b>扫码添加作者微信</b>（备注 <code>media-parser</code> 拉你入群交流）</sub>
</div>

* **微信**：csdnxr
* **QQ**：294323976
* **邮箱**：leoucmao@gmail.com
* **Bug反馈**：[GitHub Issues](https://github.com/ucmao/media-parser/issues)

---

## 🛡️ 项目原则与免责声明

### 1. 核心设计原则与边界红线
本项目定位为**网络传输协议分析、Web逆向工程教学与研究**，严格恪守以下原则与红线：
* **仅限公开UGC内容**：仅解析普通用户公开发布的短视频、图集素材，不支持任何私密、好友可见等未公开内容。
* **拒绝VIP付费破解**：不解析任何会员专享、单点付费、付费短剧等收费内容；系统不依赖亦不索取任何付费VIP Cookie。
* **不支持版权长视频**：专注于短视频生态，坚决不做任何爱优腾芒、Netflix、电影、电视剧等长视频版权内容的嗅探与破解。
* **无破坏性协议分析**：不破坏任何DRM加密流，不从事任何黑产或恶意绕过行为。如遇平台接口调整或合规要求，将主动调整或下线对应解析模块。

### 2. 开源协议 & 法律合规
* 本项目基于 **[MIT LICENSE](LICENSE)** 协议开源。
* **免责声明**：本项目所有代码和文档仅用于网络技术研究、接口逆向工程学习与防御性安全交流。使用者请遵守各目标平台的《用户服务协议》与相关法律法规，不得用于任何形式的商业侵权抓取或恶意攻击行为。因使用本工具造成的任何直接或间接法律责任由使用者自行承担。
