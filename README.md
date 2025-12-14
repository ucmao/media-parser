
# Media Parser 后端服务（parse-ucmao-backend）

**基于 Python 的高性能多平台视频解析与下载 RESTful API 服务。**

> 本仓库提供核心的视频解析逻辑和API接口。如果你需要小程序前端代码，请参考[前端仓库链接](https://github.com/ucmao/parse-ucmao-mp)

## ✨ 主要特性

  * 🎥 **多平台解析**：支持抖音、快手、小红书、B站等 **8+** 主流短视频平台。
  * 📥 **核心 API**：提供易于集成的 RESTful API 接口，用于解析和下载视频。
  * 🔐 **用户系统**：基于微信登录的轻量级用户管理与权限系统。
  * 📊 **数据记录**：记录用户查询日志、视频访问记录，支持数据统计。
  * 🐍 **技术栈**：使用 **Python 3.7+** 和 **MySQL 5.7+** 构建。

## 📱 立即体验与总览 ✨

欢迎扫码体验本项目的实际功能和效果。

|                                        扫码体验正式版                                        | 后端服务仓库 |
|:-------------------------------------------------------------------------------------:|:---:|
| ![Media Parser太阳码](qr_code.jpg)<br>🚀 [Media Parser前端服务](https://github.com/ucmao/parse-ucmao-mp) | 当前仓库 |

## 🌐 支持的平台列表

| 平台名称 | 支持状态 | 平台名称 | 支持状态 |
| :--- | :--- | :--- | :--- |
| **抖音** | ✅ | **哔哩哔哩** | ✅ |
| **快手** | ✅ | **好看视频** | ✅ |
| **小红书**| ✅ | **梨视频** | ✅ |
| **皮皮搞笑** | ✅ | **微视** | ✅ |

-----

## 🚀 快速启动

### 环境要求

  * Python 3.7+
  * MySQL 5.7+

### 1\. 配置项目

1.  **克隆项目**

    ```bash
    git clone https://github.com/ucmao/parse-ucmao-backend.git
    cd parse-ucmao-backend
    ```

2.  **安装依赖**

    ```bash
    pip install -r requirements.txt
    ```

3.  **配置环境变量 (重要)**

      * 复制示例文件：`cp .env.example .env`
      * **编辑 `.env` 文件**：替换所有 `your_..._here` 占位符为你自己的值。
      * **注意：`.env` 文件包含敏感信息（App Secret, DB 密码），请勿提交到 Git。**

    `.env.example` 示例内容：

    ```env
    # 核心域名
    DOMAIN=your_domain_here

    # 微信小程序登录配置
    WECHAT_APP_ID=your_wechat_app_id_here
    WECHAT_APP_SECRET=your_wechat_app_secret_here

    # MySQL数据库配置
    DB_HOST=localhost
    DB_PORT=3306
    DB_USER=root
    DB_PASSWORD=password
    DB_NAME=parse_ucmao

    # 审核模式开关
    AUDIT_MODE=false
    ```

### 2\. 初始化数据库

本项目不包含任何敏感数据，但需要初始化表结构。

1.  **准备 Schema 文件：**

      * 确保 **`schema.sql`** 文件位于后端项目根目录下。该脚本包含创建数据库和所有表结构的 SQL 语句，并兼容 **MySQL 5.7**。

2.  **导入 Schema (表结构)：**

      * 使用你在 `.env` 文件中配置的 `DB_USER` 和 `DB_NAME`（默认是 `parse_ucmao`）。
      * 运行以下命令导入表结构，它会**自动创建数据库和所有需要的表**：

    <!-- end list -->

    ```bash
    mysql -u DB_USER -p DB_NAME < schema.sql

    # 示例 (如果用户是 root 且数据库名为 parse_ucmao):
    # mysql -u root -p parse_ucmao < schema.sql
    ```

> **注意：** 首次运行时，脚本会尝试创建数据库 `parse_ucmao`。如果数据库已存在，它将跳过创建，直接导入表结构。

### 3\. 启动应用

```bash
# 开发模式 (快速启动)
python app.py

# 生产环境 (推荐使用 Gunicorn 等 WSGI 服务器)
gunicorn -w 4 -b 0.0.0.0:5001 app:app
```

-----

## 💻 API 接口文档

本项目提供了简洁的 RESTful API 接口，供前端小程序或 Web 端调用。

| 接口 | 方法 | 描述 | 请求体示例 |
| :--- | :--- | :--- | :--- |
| `/api/login` | `POST` | 微信用户登录与鉴权 | `{"code": "wx_login_code"}` |
| `/api/parse` | `POST` | **核心视频解析接口** | `{"text": "视频分享链接"}` |
| `/api/download` | `POST` | 获取视频的真实下载地址 | `{"video_url": "视频真实地址"}` |

-----

## 📁 项目结构

```
parse-ucmao-backend/
├── configs/              # 核心配置，如日志、业务常量
├── src/                 # 主要业务逻辑源代码
│   ├── api/             # API 接口路由处理
│   ├── database/        # 数据库连接和操作封装
│   ├── downloaders/     # 核心：各平台视频解析器实现
│   └── downloader_factory.py # 下载器工厂模式
├── static/              # 静态资源
├── tests/               # 测试文件
├── utils/               # 通用工具函数
├── .env.example         # 环境变量示例文件 (不含密钥)
├── schema.sql           # 数据库表结构初始化脚本
├── app.py               # 应用入口
└── requirements.txt     # Python 依赖列表
```

-----

## 🧠 核心模块

### DownloaderFactory (设计模式)

实现下载器工厂模式，根据传入的 URL 自动识别平台，并创建对应的下载器实例，是实现多平台兼容性的关键。

### WebFetcher

封装了网络请求逻辑，负责安全、高效地获取网页内容，并提取所需信息。

### DataStorageManager

负责用户数据、视频库信息和查询日志的 CRUD (增删改查) 操作，与 MySQL 数据库交互。

-----

## 🛠️ 开发与贡献

### 添加新平台支持

1.  在 `src/downloaders/` 目录下创建新的下载器类，继承自 `BaseDownloader`。
2.  实现解析所需的 `get_title_content()`、`get_real_video_url()` 等核心方法。
3.  在 `configs/general_constants.py` 中注册新平台的域名映射。

### 运行测试

```bash
python -m pytest tests/
```

-----

## ⚖️ 许可证

本项目采用 **MIT License** 开放源代码，详情请参阅 [LICENSE](LICENSE) 文件。

## 贡献与联系

欢迎通过 [Issue](https://github.com/ucmao/parse-ucmao-backend/issues) 提交 Bug 报告或功能建议，并通过 Pull Request 贡献代码。

  * **Email**: leoucmao@gmail.com
  * **GitHub**: [@ucmao](https://github.com/ucmao)

-----

**免责声明**：本项目仅用于学习和技术研究目的，请勿用于任何违反法律法规的行为。任何因滥用本项目造成的后果，由使用者自行承担。

-----
