# 闲鱼 (Xianyu) 逆向解析指南

本篇详细记录阿里巴巴旗下 **闲鱼** 二手商品与帖子图文的解析方案。

---

## 1. 平台特征与支持能力

* **平台标识**：`闲鱼`
* **支持媒体类型**：商品高清大图 (JPEG/PNG) / 宝贝标题与描述
* **常见链接形态**：
  * 口令/短链：`https://e.tb.cn/h.87fj9SNrqHW8kfC?tk=y1E5Tb4wkGd`
  * 商品长链：`https://2.taobao.com/item.htm?id=123456789`
* **Cookie 依赖**：无需 Cookie。

---

## 2. 核心逆向流程

1. **302 跳转获取真实 itemId**：请求淘口令或短链，从最终 Location 或 HTML 中解析商品 `id`。
2. **移动端 H5 状态提取**：
   * 请求闲鱼 H5 详情页。
   * 解析 HTML 中注入的商品元数据与相册大图列表，去除缩略图裁剪参数以获取原图。

---

## 3. 测试与验证

* **单元测试**：[tests/test_xianyu_parser.py](file:///Users/leo/Projects/media-parser/tests/test_xianyu_parser.py)
* **执行命令**：`pytest tests/test_xianyu_parser.py`
