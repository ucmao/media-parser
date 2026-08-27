<div align="center">
<img src="static/images/logo.png" width="360" height="auto" alt="媒体解析去水印 Logo">

**基于 Python 的多平台媒体原生本地解析系统**

[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE) [![Python Version](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/) [![Support](https://img.shields.io/badge/support-26+%20Platforms-brightgreen.svg)](#💾-支持的平台矩阵)

<p align="center">
<a href="#-核心解析逻辑">解析逻辑</a> •
<a href="#-快速开始">部署指南</a> •
<a href="#-联系作者">联系作者</a>
</p>

媒体解析去水印是一款专为短视频创作者打造的**原生本地解析工具**。

通过“智能识别 -> 本地抓取 -> 提取地址 -> 快捷下载”的闭环，助你高效获取无水印素材。

**不依赖第三方解析服务，不中转用户链接，核心解析逻辑全部在本地代码中完成。**

</div>

---

## 💎 核心解析逻辑

* **多平台智能适配**：内置 `ParserFactory` 工厂模式，自动识别链接来源并分配对应解析器。
* **原生本地解析**：解析逻辑直接内置在项目代码中，由各平台 Parser 本地发起请求并提取真实媒体地址。
* **不依赖第三方解析服务**：不接入外部“代解析 API”或 SaaS 中转服务，部署后即可独立运行。
* **纯粹解析 API**：极简版只保留最核心的 JSON 解析服务，无数据库依赖，无鉴权门槛，适合开发者快速提取原型直接使用。

## ✨ 项目特点

* **本地可控**：解析链路和请求逻辑都在仓库内，方便审计、调试和二次开发。
* **部署简单**：安装 Python 依赖后即可运行，不需要额外申请第三方解析平台账号或密钥。
* **便于扩展**：每个平台对应独立 Parser，新增平台时可沿用现有工厂模式和统一返回结构。

---

## 💾 支持的平台矩阵

| 平台名称 | 作者 | 标题 | 封面 | 视频 | 图集 | 音频 | 实况 |
| --- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **抖音** | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| **小红书** | ✓ | ✓ | ✓ | ✓ | ✓ | | ✓ |
| **视频号** | ✓ | ✓ | ✓ | ✓ | | | |
| **快手** | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | |
| **哔哩哔哩** | ✓ | ✓ | ✓ | ✓ | | ✓ | |
| **豆包** | ✓ | ✓ | ✓ | ✓ | ✓ | | |
| **即梦 AI** | ✓ | ✓ | ✓ | ✓ | | | |
| **皮皮搞笑** | ✓ | ✓ | ✓ | ✓ | | | |
| **微视** | ✓ | ✓ | ✓ | ✓ | | | |
| **AcFun** | ✓ | ✓ | ✓ | ✓ | | | |
| **西瓜视频** | ✓ | ✓ | ✓ | ✓ | | | |
| **逗拍** | | ✓ | ✓ | ✓ | | | |
| **绿洲** | | ✓ | ✓ | ✓ | | | |
| **皮皮虾** | ✓ | ✓ | ✓ | ✓ | | | |
| **全民K歌** | | ✓ | ✓ | ✓ | | | |
| **新片场** | | ✓ | ✓ | ✓ | | | |
| **好看视频** | ✓ | ✓ | ✓ | ✓ | | | |
| **梨视频** | ✓ | ✓ | ✓ | ✓ | | | |
| **微博** | ✓ | ✓ | ✓ | ✓ | ✓ | | |
| **知乎** | ✓ | ✓ | ✓ | ✓ | ✓ | | |
| **虎牙** | | ✓ | ✓ | ✓ | | | |
| **美拍** | | ✓ | ✓ | ✓ | | | |
| **全民小视频** | ✓ | ✓ | ✓ | ✓ | | | |
| **六间房** | | ✓ | ✓ | ✓ | | | |
| **最右** | ✓ | ✓ | | ✓ | | | |

---

## 🚀 快速开始

> 当前版本主打“原生本地解析”。只要目标平台仍可通过现有脚本抓取，就不需要额外依赖第三方解析服务。

### 1. 获取源码

```bash
git clone https://github.com/ucmao/media-parser.git
cd media-parser

```

### 2. Docker 快速启动（推荐）

项目自带 Dockerfile 和 Compose 配置。安装 Docker 与 Docker Compose 后，执行：

```bash
# 构建并后台启动容器
docker-compose up -d --build
```

服务默认监听 `8051` 端口。启动完成后访问 [http://localhost:8051](http://localhost:8051)。

### 3. 本地开发运行（不使用 Docker）

适用于本地调试或二次开发。

#### 环境要求

* **Python**: 3.8 及以上版本

#### 安装依赖并启动

```bash
pip install -r requirements.txt
python app.py
```

启动后访问 [http://localhost:8051](http://localhost:8051)。

## 🖥️ 服务器部署

服务器环境推荐使用 Docker Compose。它会以 Gunicorn 启动服务，并在容器重启后自动恢复运行。

### 1. 配置环境变量（可选）

如需配置平台 Cookie 或应用参数，先复制模板：

```bash
cp .env.example .env
```

```env
# 按需填写；请勿提交真实 Cookie。
# 小红书推荐流（如 xsec_source=pc_feed）遇校验时配置。
XIAOHONGSHU_COOKIE="a1=xxx;webId=xxx"

# 豆包独立 AI 视频遇校验时配置。
DOUBAO_COOKIE="your_doubao_cookie"

# 视频号获取视频直链必须配置元宝完整 Cookie（需含 hy_user、hy_token）。
YUANBAO_COOKIE="hy_user=xxx; hy_token=xxx"
```

### 2. 启动或更新服务

```bash
docker-compose up -d --build
```

### 3. 查看运行状态

```bash
docker-compose ps
docker-compose logs -f web
```

服务默认暴露 `8051` 端口。生产环境请在防火墙或反向代理中仅开放需要的访问范围。

## 📂 项目结构


```text
media-parser/
├── app.py                # 程序入口
├── configs/              # 核心配置与业务常量
├── src/
│   ├── api/             # 路由层：API 接口处理仅保留核心 parse.py
│   ├── parsers/     # 核心：各平台视频解析实现
│   └── parser_factory.py # 工厂模式实现
├── static/              # 静态资源保存位置
├── utils/               # 通用工具函数 (网络请求等)
└── tests/               # 自动化测试用例
```

---

## 🔌 API 核心接口说明

**解析接口**：`POST /api/parse`

### 请求参数 (Request Body)
格式: `application/json`

| 参数名 | 类型 | 必填 | 描述 | 示例值 |
| --- | --- | --- | --- | --- |
| `text` | `string` | 是 | 视频分享链接或包含链接的文本短语 | `"https://v.douyin.com/..."` |

### 返回说明 (Response)
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
    "audio_url": "https://... (背景音乐/音频地址)",
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
  "succ": false
}
```

`video_url` 始终表示主视频。为了保持旧客户端兼容，单视频内容不会返回 `video_list`；只有豆包对话等确实包含多段视频的内容才会额外返回：

```json
{
  "video_url": "https://.../video-1.mp4",
  "video_list": [
    "https://.../video-1.mp4",
    "https://.../video-2.mp4"
  ]
}
```

多视频响应保证 `video_url` 与 `video_list[0]` 相同。

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
