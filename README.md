<div align="center">
<img src="static/images/logo.png" width="360" height="auto" alt="媒体解析去水印 Logo">

**基于 Python 的多平台媒体原生本地解析系统（Starter 极简版）**

[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE) [![Python Version](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/) [![Support](https://img.shields.io/badge/support-8+%20Platforms-brightgreen.svg)](#💾-支持的平台矩阵)

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

| 平台名称 | 作者 | 标题 | 封面 | 视频 | 图集 | 音频 | 实况 | 平台名称          | 作者 | 标题 | 封面 | 视频 | 图集 | 音频 | 实况 |
| --- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |---------------| :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **抖音** | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | **小红书**       | ✓ | ✓ | ✓ | ✓ | ✓ | | ✓ |
| **快手** | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | | **哔哩哔哩**      | ✓ | ✓ | ✓ | ✓ | | ✓ | |
| **皮皮搞笑** | ✓ | ✓ | ✓ | ✓ | | | | **好看视频**      | ✓ | ✓ | ✓ | ✓ | | | |
| **微视** | ✓ | ✓ | ✓ | ✓ | | | | **梨视频**       | ✓ | ✓ | ✓ | ✓ | | | |
| **AcFun** | ✓ | ✓ | ✓ | ✓ | | | | **微博**        | ✓ | ✓ | ✓ | ✓ | ✓ | | |
| **西瓜视频** | ✓ | ✓ | ✓ | ✓ | | | | **知乎**        | ✓ | ✓ | ✓ | ✓ | ✓ | | |
| **逗拍** | | ✓ | ✓ | ✓ | | | | **虎牙**        | | ✓ | ✓ | ✓ | | | |
| **绿洲** | | ✓ | ✓ | ✓ | | | | **美拍**        | | ✓ | ✓ | ✓ | | | |
| **皮皮虾** | ✓ | ✓ | ✓ | ✓ | | | | **全民小视频**     | ✓ | ✓ | ✓ | ✓ | | | |
| **全民K歌** | | ✓ | ✓ | ✓ | | | | **六间房**       | | ✓ | ✓ | ✓ | | | |
| **新片场** | | ✓ | ✓ | ✓ | | | | **最右**        | ✓ | ✓ | | ✓ | | | |
| **TikTok** | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | | **YouTube** | ✓ | ✓ | ✓ | ✓ | | ✓ | |

---

## 🚀 快速开始

> 当前版本主打“原生本地解析”。只要目标平台仍可通过现有脚本抓取，就不需要额外依赖第三方解析服务。

### 1. 获取源码

```bash
git clone https://github.com/ucmao/media-parser.git
cd media-parser

```

### 2. Docker 部署 (推荐)

项目自带完整的 Dockerfile 和 docker-compose 配置文件。如果你已经安装了 Docker，一键即可拉起服务：

```bash
# 构建并后台启动容器
docker-compose up -d --build
```

容器默认运行在 `8051` 端口。启动成功后，你可以直接在浏览器中打开: 
[http://localhost:8051](http://localhost:8051)
### 3. 本地环境部署 (不使用 Docker)

#### 3.1 环境要求

* **Python**: 3.8 及以上版本

#### 3.2 安装依赖

```bash
pip install -r requirements.txt

```

#### 3.3 启动应用

**开发模式：**

```bash
python app.py

```

**生产模式 (Gunicorn)：**

```bash
gunicorn -w 4 -b 0.0.0.0:8051 app:app

```


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
  "code": 200,
  "msg": "成功",
  "data": {
    "video_id": "7123...",
    "platform": "抖音",
    "title": "视频标题内容",
    "video_url": "https://... (无水印视频真实地址)",
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
  "code": 400,
  "msg": "该链接尚未支持提取 / 解析失败",
  "data": null,
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
