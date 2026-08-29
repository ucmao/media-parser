<div align="center">
<img src="static/images/logo.png" width="360" height="auto" alt="Media-Parser Logo">

**基于 Python 的多平台媒体原生本地解析系统**

[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE) [![Python Version](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/) [![Flask](https://img.shields.io/badge/Framework-Flask-000000?logo=flask&logoColor=white)](https://flask.palletsprojects.com/) [![Docker](https://img.shields.io/badge/Docker-Ready-2496ED?logo=docker&logoColor=white)](#-部署指南) [![Support](https://img.shields.io/badge/support-33%20Platforms-brightgreen.svg)](#-支持的平台矩阵)

<p align="center">
<a href="#-核心解析逻辑">解析逻辑</a> •
<a href="#-支持的平台矩阵">支持平台</a> •
<a href="#-部署指南">部署指南</a> •
<a href="#-项目结构">项目结构</a> •
<a href="#-开发者文档与逆向百科">开发文档</a> •
<a href="#-api-核心接口说明">接口文档</a> •
<a href="#-联系作者">联系作者</a>
</p>

媒体解析去水印是一款专为短视频创作者与开发者打造的**原生本地解析工具**。

通过“智能识别 -> 本地抓取 -> 提取地址 -> 快捷下载”的闭环，助你高效获取无水印素材。

**100%本地原生实现，不依赖外部API，不封装第三方解析库，核心逆向逻辑完全开源。**

</div>

---

## 💎 核心解析逻辑

* **多平台智能适配**：内置 `ParserFactory` 工厂模式，自动识别链接来源并分配对应解析器。
* **原生本地解析**：解析逻辑直接内置在项目代码中，由各平台 Parser 本地发起请求并提取真实媒体地址。
* **零外部API依赖**：无需对接任何第三方代解析接口或 SaaS 中转服务，部署后即可独立稳定运行。
* **开箱即用API**：提供标准化的 JSON 数据接口，无冗余数据库依赖，适合快速对接业务或二次开发。

## ✨ 项目特点

* **本地可控**：所有请求链路与解析规则均在本地代码中，方便调试、维护与定制。
* **部署简单**：安装依赖或使用 Docker 即可一键运行，不需要额外申请第三方 API 账号或密钥。
* **便于扩展**：各平台对应独立 Parser，遵循统一的返回数据结构，新增平台轻松快捷。

---

## 💾 支持的平台矩阵

| 平台名称 | 作者 | 标题 | 封面 | 视频 | 图集 | 音频 | 字幕 | 实况 |
| --- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **抖音** | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| **小红书** | ✓ | ✓ | ✓ | ✓ | ✓ | | | ✓ |
| **视频号** | ✓ | ✓ | ✓ | ✓ | | | | |
| **微信公众号** | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | | |
| **快手** | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | | |
| **哔哩哔哩** | ✓ | ✓ | ✓ | ✓ | | ✓ | | |
| **豆包** | ✓ | ✓ | ✓ | ✓ | ✓ | | | |
| **即梦AI** | ✓ | ✓ | ✓ | ✓ | | | | |
| **小云雀AI** | ✓ | ✓ | ✓ | ✓ | ✓ | | | |
| **可灵AI** | ✓ | ✓ | ✓ | ✓ | | | | |
| **夸克AI** | ✓ | ✓ | ✓ | ✓ | ✓ | | | |
| **通义千问** | ✓ | ✓ | ✓ | ✓ | ✓ | | | |
| **闲鱼** | | ✓ | ✓ | | ✓ | | | |
| **Soul** | ✓ | ✓ | ✓ | ✓ | ✓ | | | |
| **汽水音乐** | ✓ | ✓ | ✓ | ✓ | | ✓ | ✓ | |
| **腾讯频道** | ✓ | ✓ | ✓ | ✓ | | | | |
| **剪映 / CapCut** | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | | |
| **快影** | ✓ | ✓ | ✓ | ✓ | | ✓ | | |
| **皮皮搞笑** | ✓ | ✓ | ✓ | ✓ | | | | |
| **微视** | ✓ | ✓ | ✓ | ✓ | | | | |
| **AcFun** | ✓ | ✓ | ✓ | ✓ | | | | |
| **西瓜视频** | ✓ | ✓ | ✓ | ✓ | | | | |
| **绿洲** | ✓ | ✓ | ✓ | ✓ | ✓ | | | |
| **皮皮虾** | ✓ | ✓ | ✓ | ✓ | | | | |
| **全民K歌** | | ✓ | ✓ | ✓ | | | | |
| **新片场** | ✓ | ✓ | ✓ | ✓ | | | | |
| **好看视频** | ✓ | ✓ | ✓ | ✓ | | | | |
| **梨视频** | ✓ | ✓ | ✓ | ✓ | | | | |
| **微博** | ✓ | ✓ | ✓ | ✓ | ✓ | | | |
| **知乎** | ✓ | ✓ | ✓ | ✓ | ✓ | | | |
| **虎牙** | | ✓ | ✓ | ✓ | | | | |
| **美拍** | ✓ | ✓ | ✓ | ✓ | | | | |
| **最右** | ✓ | ✓ | | ✓ | | | | |

---

## 🚀 部署指南

### Cookie 配置（Docker 与Python 环境运行通用）

大多数平台无需登录态即可解析；如需完整解析豆包视频或视频号视频，请先复制环境变量示例文件：

```bash
cp .env.example .env
```

然后在本地 `.env` 中按需填写 Cookie：

1. **豆包解析需要豆包 Cookie**：建议粘贴浏览器中的完整 Cookie，至少包含 `sessionid_ss=字段值`。未配置或 Cookie 已过期时，仍可解析公开分享中的图片，但无法获取视频。
2. **视频号解析需要腾讯元宝 Cookie**：建议粘贴浏览器中的完整 Cookie，至少包含 `hy_user=字段值; hy_token=字段值`。未配置或 Cookie 已过期时，仍可解析标题、作者等公开字段，但无法获取视频。

### Docker 部署（推荐）

通过 Docker Compose 快捷构建并启动服务；如需解析豆包或视频号视频，请先按上方说明配置 `.env`：

```bash
# 1. 获取源码
git clone https://github.com/ucmao/media-parser.git
cd media-parser

# 2. 构建并启动服务
docker-compose up -d --build

# 3. 查看日志与运行状态
docker-compose logs -f web
```

服务默认监听 `8051` 端口，启动后直接访问 [http://localhost:8051](http://localhost:8051)。

---

### Python 环境运行

适用于调试、二次开发或直接在宿主机运行。推荐 **Python 3.10+**（兼容 Python 3.8+）；如需解析豆包或视频号视频，请先按上方说明配置 `.env`。

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 启动服务
python app.py
```

## 📂 项目结构

```text
media-parser/
├── app.py                     # 应用入口 (Flask Web 服务与 API 启动)
├── configs/                   # 核心配置 (域名平台映射、日志配置等)
├── docs/                      # 逆向百科与开发文档
│   ├── architecture.md        # 系统分层架构与生命周期设计
│   ├── reverse-guide.md       # 通用逆向方法论 (抓包/SSR/JS签名提取)
│   ├── testing.md             # 完整测试规范与回归手册
│   └── parsers/               # 33 个平台的独立逆向分析文档
├── src/                       # 核心业务逻辑
│   ├── api/                   # RESTful API 路由 (/api/parse, /api/health)
│   ├── web/                   # Demo 体验页与交互蓝图
│   ├── parsers/               # 33 个平台解析器实现 (核心解析逻辑)
│   └── parser_factory.py      # 工厂分发器 (解析器动态发现与自动注册)
├── utils/                     # 底层工具库与逆向支持
│   ├── signer/                # JS 签名沙箱引擎 (a_bogus, x_bogus 等算法执行)
│   └── web_fetcher.py         # 智能 URL 识别、重定向追踪与请求封装
├── tests/                     # 完备的双层测试体系
│   ├── live_parser_samples.json # 33 平台真实多形态在线样本库
│   ├── manual_verify_parsers.py # 命令行交互式冒烟与健康检查工具
│   └── test_*_parser.py         # 各平台 Mock 自动化单元测试
├── static/ & templates/       # Web 演示页面前端静态资源
└── docker-compose.yml         # 容器化一键部署编排
```

## 📖 开发者文档与逆向百科

本项目提供了详尽的技术架构与全平台逆向分析手册，详细内容请查阅 **[`docs/`](docs/)** 目录：

* 🏗️ **[系统架构与生命周期设计](docs/architecture.md)**：分层设计、302 追踪与 `ParserFactory` 动态发现机制。
* 🔍 **[通用逆向方法论](docs/reverse-guide.md)**：SSR 数据提取、H5 接口伪装、JS 签名沙箱及抓包 SOP。
* 🧪 **[测试体系与回归验证](docs/testing.md)**：Pytest 单元测试、Mock 与线上真实样例回归。
* 📚 **[平台逆向指南索引](docs/index.md)**：包含抖音、快手、小红书、B站等全部 33 个平台的独立技术文档。

---

## 🧪 解析有效性测试

本项目拥有完备的测试体系，包括基础单元测试与基于真实样本库的在线回归测试：

### 1. 真实样本交互式验证
样例测试库见 [`tests/live_parser_samples.json`](tests/live_parser_samples.json)，用于实时验证 33 个平台解析器的有效性与多形态覆盖：

```bash
# 快速冒烟测试（每个平台测 1 条最具代表性的链接，极速完成健康检查）
python3 tests/manual_verify_parsers.py --limit 1

# 全量回归验证（覆盖多形态真实用例）
python3 tests/manual_verify_parsers.py

# 仅验证单个或指定平台（如：小云雀AI）
python3 tests/manual_verify_parsers.py --platform "小云雀AI"
```

### 2. 自动化单元测试
```bash
# 运行全部单元测试
pytest

# 运行真实线上样例自动化回归
pytest tests/test_live_parser_samples.py -s
```

---

## 🔌 API 核心接口说明

### 1. 服务健康检查

* **接口路径**：`GET /api/health`
* **接口描述**：供容器编排（Docker Compose/K8s）、反向代理或监控系统探针检测服务存活状态。
* **返回示例**：
  ```json
  {
    "status": "ok"
  }
  ```

---

### 2. 媒体解析接口

* **接口路径**：`POST /api/parse`
* **接口描述**：传入包含分享链接的文本，智能提取多媒体直链与图文信息。

#### 请求参数 (Request Body)
格式: `application/json`

| 参数名 | 类型 | 必填 | 描述 | 限制与示例 |
| --- | --- | --- | --- | --- |
| `text` | `string` | 是 | 视频分享链接或包含链接的文本短语 | 最长 2000 字符，如 `"https://v.douyin.com/..."` |

#### 返回说明 (Response)
格式: `application/json`

成功响应示例：
```json
{
  "retcode": 200,
  "retdesc": "成功",
  "data": {
    "video_id": "7123...",
    "platform": "抖音",
    "title": "视频标题内容",
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

失败响应示例：
```json
{
  "retcode": 400,
  "retdesc": "该链接尚未支持提取 / 解析失败",
  "data": null,
  "error_code": "PLATFORM_NOT_SUPPORTED",
  "succ": false
}
```

---

## 📩 联系作者

如果您在安装、使用过程中遇到问题，或有定制需求，请通过以下方式联系：

* **微信**：csdnxr
* **QQ**：294323976
* **邮箱**：leoucmao@gmail.com
* **Bug反馈**：[GitHub Issues](https://github.com/ucmao/media-parser/issues)

---

## ⚖️ 开源协议 & 免责声明

1. 本项目基于 **[MIT LICENSE](LICENSE)** 协议开源。
2. **免责声明**：本项目仅用于学习交流和技术研究。严禁用于任何非法目的。因滥用本项目造成的后果，由使用者自行承担。

---
