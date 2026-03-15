<div align="center">
<img src="static/images/logo.png" width="120" height="auto" alt="Media Parser Logo">

# 🚀 Media Parser 后端(parse-ucmao-backend)

**基于 Python 的高性能多平台视频解析与自动化管理系统（Starter 极简版）**

[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE) [![Python Version](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/) [![Support](https://img.shields.io/badge/support-8+%20Platforms-brightgreen.svg)](#💾-支持的平台矩阵)

<p align="center">
<a href="#-立即体验">在线体验</a> •
<a href="#-核心解析逻辑">解析逻辑</a> •
<a href="#-快速开始">部署指南</a> •
<a href="#-联系作者">联系作者</a>
</p>

Media Parser是一款专为短视频创作者打造的**自动化解析工具**。

<p align="center">
  <img src="static/images/Interface.webp" width="600" alt="Media Parser 后端管理界面预览">
</p>

通过“智能识别 -> 绕过水印 -> 提取地址 -> 快捷下载”的闭环，助你高效获取无水印素材。

</div>

---

## 📱 立即体验

为了方便快速了解系统功能，我们提供了全套解决方案：

* **🌐 项目门户**: [https://parse.ucmao.cn/](https://parse.ucmao.cn/) (扫码引导页)
* **⚙️ 管理后台**: [https://parse.ucmao.cn/admin/](https://parse.ucmao.cn/admin/)
    * 演示者: `guest` / `guest123` （仅查看权限，部分功能需部署后使用）
* **🧩 小程序端**: 扫描下方太阳码进行体验

<p align="center">
<img src="static/images/qr_code.jpg" width="180" alt="Media Parser太阳码">
</p>

> **协作提示**：本仓库提供核心解析逻辑与 RESTful API。如需构建完整应用，请配合前端仓库使用： [https://github.com/ucmao/parse-ucmao-mp](https://github.com/ucmao/parse-ucmao-mp)

---

## 💎 核心解析逻辑

* **多平台智能适配**：内置 `DownloaderFactory` 工厂模式，自动识别链接来源并分配对应解析器。
* **深度无水印提取**：封装 `WebFetcher` 高效抓取逻辑，精准绕过平台限制获取视频真实地址。
* **纯粹解析 API**：极简版只保留了最核心的 JSON 解析服务，无数据库依赖，无鉴权门槛，非常适合开发者快速提取原型直接使用！

---

## 💾 支持的平台矩阵

| 平台名称 | 识别状态 | 平台名称     | 识别状态 |
| --- | --- |----------| --- |
| **抖音** | ✅ 完美支持 | **小红书**  | ✅ 完美支持 |
| **快手** | ✅ 完美支持 | **哔哩哔哩** | ✅ 完美支持 |
| **皮皮搞笑** | ✅ 完美支持 | **好看视频** | ✅ 完美支持 |
| **微视** | ✅ 完美支持 | **梨视频**  | ✅ 完美支持 |

---

## 🔌 API 核心接口说明

**解析接口**：`POST /api/parse`

| 参数 | 描述 | 示例值 |
| --- | --- | --- |
| `text` | 视频分享链接/包含链接的文本 | `https://v.douyin.com/...` |

---

## 🚀 快速开始

### 0. 环境要求

* **Python**: 3.8 及以上版本

### 1. 获取源码

```bash
git clone https://github.com/ucmao/parse-ucmao-backend.git
cd parse-ucmao-backend

```

### 2. 安装依赖

```bash
pip install -r requirements.txt

```

### 3. 环境配置 (.env)

在项目根目录下创建 `.env` 文件（参考 `.env.example`）：

```ini
# 核心域名
DOMAIN = your_domain_here
# 用于加密 Session
SECRET_KEY =your_secret_key

# 微信小程序登录配置 (若自行扩展需要用到)
WECHAT_APP_ID = your_wechat_app_id_here
WECHAT_APP_SECRET = your_wechat_app_secret_here

# 服务端下载缓存配置
# 仅缓存不超过该大小的小文件，单位：MB，默认 15
MAX_CACHE_SIZE_MB = 15

```

### 4. 启动应用

**开发模式：**

```bash
python app.py

```

**生产模式 (Gunicorn)：**

```bash
gunicorn -w 4 -b 0.0.0.0:5001 app:app

```

## 📂 项目结构

```text
parse-ucmao-backend/
├── app.py                # 程序入口
├── configs/              # 核心配置与业务常量
├── src/
│   ├── api/             # 路由层：API 接口处理仅保留核心 parse.py
│   ├── downloaders/     # 核心：各平台视频解析实现
│   └── downloader_factory.py # 工厂模式实现
├── static/              # 静态资源保存位置
├── utils/               # 通用工具函数 (网络请求等)
└── tests/               # 自动化测试用例
```

---

## 📩 联系作者

如果您在安装、使用过程中遇到问题，或有定制需求，请通过以下方式联系：

* **微信 (WeChat)**：csdnxr
* **QQ**：294323976
* **邮箱 (Email)**：leoucmao@gmail.com
* **Bug反馈**：[GitHub Issues](https://github.com/ucmao/parse-ucmao-backend/issues)

---

## ⚖️ 开源协议 & 免责声明

1. 本项目基于 **[MIT LICENSE](LICENSE)** 协议开源。
2. **免责声明**：本项目仅用于学习交流和技术研究。严禁用于任何非法目的。因滥用本项目造成的后果，由使用者自行承担。

**Media Parser** - 高效解析，赋能创作。

---
