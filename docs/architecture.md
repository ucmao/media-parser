# 系统架构与解析生命周期设计 (Architecture)

本文档详细阐述 **Media Parser** 的内部架构分层、请求处理生命周期、工厂模式插件化发现机制以及数据响应标准。

---

## 🏛️ 整体分层架构

项目遵循模块化、高内聚、低耦合的设计原则，自底向上分为以下四层：

```mermaid
flowchart TD
    Client["客户端 / Web体验页 / API调用者"]
    
    subgraph WebLayer["1. Web 接入层 (app.py & src/api/)"]
        App["Flask App / 路由"]
        ParseAPI["POST /api/parse"]
        HealthAPI["GET /api/health"]
    end
    
    subgraph CoreLayer["2. 调度与解析引擎 (Core Engine)"]
        UrlParser["UrlParser (正则提取/平台识别)"]
        WebFetcher["WebFetcher (302重定向追踪)"]
        Factory["ParserFactory (动态发现与分发)"]
    end
    
    subgraph ParserLayer["3. 平台解析器层 (src/parsers/)"]
        BaseParser["BaseParser (基类/Session管理)"]
        Douyin["DouyinParser"]
        Kuaishou["KuaishouParser"]
        XHS["XiaohongshuParser"]
        Bili["BilibiliParser"]
        Others["... 30+ 其它解析器"]
    end
    
    subgraph UtilLayer["4. 工具与逆向支持 (utils/ & configs/)"]
        Signer["BogusSigner (mini-racer JS执行)"]
        Logger["LoggingConfig"]
        CommonUtils["make_response 标准化响应"]
    end

    Client --> App
    App --> ParseAPI
    ParseAPI --> UrlParser
    ParseAPI --> WebFetcher
    ParseAPI --> Factory
    Factory --> BaseParser
    BaseParser --> Douyin
    BaseParser --> Kuaishou
    BaseParser --> XHS
    BaseParser --> Bili
    BaseParser --> Others
    Douyin --> Signer
    ParseAPI --> CommonUtils
```

---

## 🔄 请求处理生命周期 (Lifecycle)

当客户端向 `/api/parse` 发送一段包含分享文案的文本时，完整处理流如下：

```mermaid
sequenceDiagram
    autonumber
    actor User as 客户端 (Client)
    participant API as /api/parse
    participant Fetcher as WebFetcher & UrlParser
    participant Factory as ParserFactory
    participant Parser as Platform Parser (如 DouyinParser)
    participant Output as Response Formatter

    User->>API: POST {"text": "7.22 复制打开抖音... https://v.douyin.com/xxx/"}
    API->>Fetcher: UrlParser.get_url(text) 提取原始链接
    API->>Fetcher: WebFetcher.fetch_redirect_url(url) 追踪302重定向
    Fetcher-->>API: 返回落地真实URL (Real URL)
    API->>Fetcher: UrlParser.get_platform(real_url) 识别平台名称
    API->>Factory: ParserFactory.create_parser(platform, real_url)
    Factory-->>API: 实例化对应平台解析器
    API->>Parser: 执行抓取 (_fetch_with_retry)
    Note over Parser: 提取标题、视频直链、图集、LivePhoto、音频等
    Parser-->>API: 返回原始抓取字典 content_data
    API->>Output: UrlParser.convert_to_https 统一转 HTTPS
    API->>Output: make_response(200, '成功', data_dict)
    Output-->>User: 返回标准 JSON 结构
```

---

## 🧩 插件化解析器设计 (ParserFactory)

为了便于扩展和多人协作，解析器采用 **装饰器自动注册 + 模块自动发现机制**：

### 1. 自动发现 (`_discover`)
[src/parser_factory.py](file:///Users/leo/Projects/media-parser/src/parser_factory.py) 会在模块载入时利用 `pkgutil.iter_modules` 自动扫描并动态 `import` `src/parsers/` 下所有除 `base_parser` 以外的 Python 模块。

### 2. 声明式注册 (`@register_parser`)
新增任何平台解析器时，**无需修改任何工厂类核心代码**，只需继承 `BaseParser` 并加上装饰器：

```python
from src.parser_factory import register_parser
from src.parsers.base_parser import BaseParser

@register_parser("示例平台", "示例平台别名")
class ExampleParser(BaseParser):
    def __init__(self, real_url):
        super().__init__(real_url)
        # 初始化与数据提取
        
    def get_real_video_url(self):
        return "https://..."
```

---

## 📦 统一响应格式标准 (Data Contract)

所有解析接口均通过 `utils/common_utils.py` 中的 `make_response` 返回一致的 JSON 响应体。

### 成功响应示例 (`200 OK`)
```json
{
  "code": 200,
  "msg": "成功",
  "data": {
    "platform": "抖音",
    "video_id": "7616399587141737704",
    "title": "视频文案标题",
    "video_url": "https://aweme.snssdk.com/aweme/v1/play/...",
    "cover_url": "https://p3-pc.douyinpic.com/...",
    "author": {
      "nickname": "创作者昵称",
      "author_id": "unique_id_123",
      "avatar": "https://p3.douyinpic.com/..."
    },
    "audio_url": "https://sf6-cdn-tos.douyinstatic.com/...",
    "image_list": [
      {
        "url": "https://p3-pc.douyinpic.com/image1.jpeg",
        "live_photo_url": "https://aweme.snssdk.com/aweme/v1/play/live_photo.mp4"
      }
    ],
    "video_list": []
  },
  "success": true
}
```

### 错误响应示例 (`400 / 500`)
```json
{
  "code": 400,
  "msg": "未找到有效的分享链接",
  "data": null,
  "success": false,
  "error_code": "URL_NOT_FOUND"
}
```
