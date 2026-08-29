# 通义千问 (Qwen) 逆向解析指南

本篇详细记录阿里巴巴 **通义千问 (Qwen)** AI Studio 及移动分享作品的 `__INITIAL_PROPS__` SSR 数据提取方案。

---

## 1. 平台特征与支持能力

* **平台标识**：`通义千问`
* **支持媒体类型**：
  * AI 创作图集 / 扩图 / 文生图 (PNG/JPEG)
  * AI 生成视频 (MP4)
  * 提示词 Prompt、标题与作者信息
* **常见链接形态**：
  * 移动分享长链：`https://activity.qianwen.com/r/ai-studio-mobile/qwen-external-share?shareId=ZeeOedXncnGlElkluRMA&authorId=OjTAcGHgZgye...`
* **Cookie 依赖**：公开外部分享**无需 Cookie**。

---

## 2. 核心逆向方案：`__INITIAL_PROPS__` 提取与反序列化

通义千问的分享落地页使用 React SSR，所有作品和图片 CDN 地址均直接挂载在 `window.__INITIAL_PROPS__` 全局脚本变量中。

### 2.1 提取与双重 URL 解码流程
```python
# 1. 定位 script 中的 window.__INITIAL_PROPS__
marker = "window.__INITIAL_PROPS__"
pos = html_text.find(marker)
sub = html_text[pos + len(marker):].lstrip(" =")
sub = sub[:sub.find("</script>")].rstrip().rstrip(";")

# 2. 解析 JSON
data = json.loads(sub)
raw_initial = data.get("initialData", {})

# 3. 处理 URL 编码与嵌套 JSON
if isinstance(raw_initial, str) and raw_initial.startswith("%"):
    raw_initial = urllib.parse.unquote(raw_initial)
    raw_initial = json.loads(raw_initial)
```

---

## 3. 字段提取规则

* **生成图像列表**：
  * 从 `initial_data.images` 或 `initial_data.resultList` 遍历提取 CDN 高清图片地址。
* **生图 Prompt**：
  * 提取 `initial_data.prompt` 或 `initial_data.title`。
* **作者信息**：
  * 提取 `initial_data.author` 对象的昵称与头像。

---

## 4. 常见踩坑记录 (Gotchas)

1. **`initialData` 双重编码**：
   * 某些版本的前端模板将 `initialData` 先做了 `encodeURIComponent`，因此在 `json.loads` 之前必须进行 `urllib.parse.unquote`，否则直接反序列化会报错。
2. **图文与视频多态结构**：
   * 部分 AI 助手生成的是短视频，部分是 4 宫格图集，解析器中通过类型自适应兼容两种结构。

---

## 5. 测试与验证

* **单元测试**：[tests/test_qianwen_parser.py](file:///Users/leo/Projects/media-parser/tests/test_qianwen_parser.py)
* **执行测试**：
  ```bash
  pytest tests/test_qianwen_parser.py
  python tests/manual_verify_parsers.py --platform 通义千问
  ```
