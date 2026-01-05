<div align="center">
<img src="static/images/logo.png" width="120" height="auto" alt="Media Parser Logo">

# 🚀 Media Parser 后端(parse-ucmao-backend)

**基于 Python 的高性能多平台视频解析与自动化管理系统**

[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE) [![Python Version](https://img.shields.io/badge/python-3.7+-blue.svg)](https://www.python.org/) [![MySQL](https://img.shields.io/badge/database-MySQL-orange.svg)](https://www.mysql.com/) [![Support](https://img.shields.io/badge/support-8+%20Platforms-brightgreen.svg)](#💾-支持的平台矩阵)

<p align="center">
<a href="#-立即体验">在线体验</a> •
<a href="#-核心解析逻辑">解析逻辑</a> •
<a href="#-快速开始">部署指南</a> •
<a href="[https://github.com/ucmao/parse-ucmao-backend/issues](https://github.com/ucmao/parse-ucmao-backend/issues)">提交Bug</a>
</p>

Media Parser是一款专为短视频创作者打造的**自动化解析工具**。




通过“智能识别 -> 绕过水印 -> 提取地址 -> 快捷下载”的闭环，助你高效获取无水印素材。

</div>

---

## 📱 立即体验

为了方便快速了解系统功能，我们提供了全套解决方案：

* **🌐 项目门户**: [https://parse.ucmao.cn/](https://parse.ucmao.cn/) (扫码引导页)
* **⚙️ 管理后台**: [https://parse.ucmao.cn/admin/](https://parse.ucmao.cn/admin/) (默认: `admin` / `admin123`)
* **🧩 小程序端**: 扫描下方太阳码进行体验

<p align="center">
<img src="static/images/qr_code.jpg" width="180" alt="Media Parser太阳码">
</p>

> **协作提示**：本仓库提供核心解析逻辑与 RESTful API。如需构建完整应用，请配合前端仓库使用： [https://github.com/ucmao/parse-ucmao-mp](https://github.com/ucmao/parse-ucmao-mp)

---

## 💎 核心解析逻辑

* **多平台智能适配**：内置 `DownloaderFactory` 工厂模式，自动识别链接来源并分配对应解析器。
* **深度无水印提取**：封装 `WebFetcher` 高效抓取逻辑，精准绕过平台限制获取视频真实地址。
* **用户与权限系统**：集成微信登录鉴权，记录查询日志与视频访问频次，支持运营数据统计。
* **灵活分发接口**：提供标准 RESTful 接口，可轻松对接小程序、Web 端或第三方自动化脚本。

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
| `code` | (Login 接口) 微信登录凭证 | `wx_login_code` |
| `video_url` | (Download 接口) 视频原始地址 | `http://...` |

---

## 🚀 快速开始

### 0. 环境要求

* **Python**: 3.7 及以上版本
* **MySQL**: 5.7 或 8.0+

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

# 微信小程序登录配置
WECHAT_APP_ID = your_wechat_app_id_here
WECHAT_APP_SECRET = your_wechat_app_secret_here

# MYSQL 数据库配置
DB_HOST = localhost
DB_PORT = 3306
DB_NAME = parse_ucmao
DB_USER = root
DB_PASSWORD = your_password_here

# 管理后台配置 (可选)
ADMIN_USER = admin
ADMIN_PASSWORD = admin123

```

### 4. 初始化数据库

```bash
# 导入表结构（脚本会自动创建数据库 parse_ucmao）
mysql -u root -p < schema.sql

```

### 5. 启动应用

**开发模式：**

```bash
python app.py

```

**生产模式 (Gunicorn)：**

```bash
gunicorn -w 4 -b 0.0.0.0:5001 app:app

```

---

## 📂 项目结构

```text
parse-ucmao-backend/
├── app.py                # 程序入口
├── configs/              # 核心配置与业务常量
├── src/
│   ├── api/             # 路由层：API 接口处理
│   ├── database/        # 数据层：MySQL CRUD 封装
│   ├── downloaders/     # 核心：各平台视频解析实现
│   └── downloader_factory.py # 工厂模式实现
├── static/              # 静态资源
├── utils/               # 通用工具函数 (网络请求等)
├── schema.sql           # 数据库初始化脚本
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
