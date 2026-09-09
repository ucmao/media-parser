# RESTful API 接口与协议规范 (API Specification)

本文档详细说明 **Media Parser** 提供的核心开放解析接口协议、鉴权机制、统一响应模型与全局错误码定义。

---

## 1. 接口基础信息

* **接口路径**：`POST /api/v1/parse` 或 `POST /api/parse`
* **支持格式**：`application/json` 或 `application/x-www-form-urlencoded`
* **字符编码**：`UTF-8`

### 1.1 鉴权方式 (API Key)
服务在开启鉴权时，支持以下两种传参方式：
1. **HTTP 请求头 (推荐)**：
   ```http
   Authorization: Bearer YOUR_API_KEY
   ```
2. **Query 参数 (备用)**：
   ```http
   POST /api/v1/parse?key=YOUR_API_KEY
   ```

---

## 2. 请求参数定义

| 参数名 | 类型 | 必填 | 默认值 | 说明 |
| :--- | :--- | :---: | :---: | :--- |
| `text` 或 `url` | String | **是** | - | 待解析的分享文本或链接（支持直接粘贴包含中文文案的整段分享文本，系统会自动从中提取有效 URL） |

### 请求示例
```bash
curl -X POST "http://localhost:5000/api/v1/parse" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer mp_xxxxxx" \
  -d '{
    "text": "7.22 复制打开抖音，看看【测试的作品】https://v.douyin.com/iLxxxx/"
  }'
```

---

## 3. 统一响应模型 (Data Contract)

所有接口统一采用如下标准 JSON 响应结构：

```json
{
  "retcode": 200,
  "retdesc": "成功",
  "succ": true,
  "data": { ... },
  "error_code": "..."
}
```

### 3.1 字段含义

| 字段 | 类型 | 说明 |
| :--- | :--- | :--- |
| `retcode` | Integer | HTTP 语义状态码（如 200 成功，400 业务错误，401/403 鉴权失败，429 限流，500 服务端异常） |
| `retdesc` | String | 人类可读的结果描述或官方拦截提示 |
| `succ` | Boolean | 请求与解析是否成功 (`true` / `false`) |
| `data` | Object / null | 解析成功时为解析结果对象，失败时为 `null` |
| `error_code` | String (可选) | 机器可读的全局唯一错误枚举代号（仅在失败时提供） |

### 3.2 成功响应示例 (`retcode: 200`)
```json
{
  "retcode": 200,
  "retdesc": "成功",
  "succ": true,
  "data": {
    "platform": "抖音",
    "video_id": "7616399587141737704",
    "title": "作品文案标题",
    "desc": "作品完整描述/AI对话正文",
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
  }
}
```

---

## 4. 全局错误码定义 (Error Codes)

在解析或鉴权失败时，响应体中包含 `error_code` 字段，调用方可依据此字段进行自动化分支判断：

| `retcode` | `error_code` | `retdesc` 描述 | 说明与处理建议 |
| :---: | :--- | :--- | :--- |
| **400** | `MEDIA_DELETED_OR_PRIVATE` | `因作品权限或已被删除，无法观看...` | 作品已被作者删除、设置为仅自己可见、朋友可见或日常权限限制（终态不可重试） |
| **400** | `NO_MEDIA_IN_CONTENT` | `该分享内容仅包含文本对话，未包含图片或视频资源` | 豆包等 AI 对话分享仅有文字问答，无多媒体附件 |
| **400** | `XIAOHONGSHU_COOKIE_REQUIRED` | `解析失败：该链接需要小红书登录 Cookie 校验...` | 小红书触发安全反爬校验，需在环境配置有效 Cookie |
| **400** | `PINDUODUO_COOKIE_REQUIRED` | `解析失败：该链接需要拼多多登录 Cookie 校验...` | 拼多多 dsp 接口需 Cookie 凭据 |
| **400** | `WECHAT_CHANNELS_COOKIE_REQUIRED` | `解析失败：该链接需要配置腾讯元宝 YUANBAO_COOKIE 凭证...` | 微信视频号解析通道凭据失效 |
| **400** | `MEDIA_NOT_FOUND` | `提取媒体内容失败，请检查链接或稍后重试` | 未能从目标页面提取到有效音视频或图集 |
| **400** | `INVALID_TEXT` | `请提供包含分享链接的文本` | 请求参数 `text`/`url` 为空 |
| **400** | `TEXT_TOO_LONG` | `分享文本不能超过 2048 个字符` | 请求文本超长 |
| **400** | `URL_NOT_FOUND` | `未找到有效的分享链接` | 文本中未能提取到有效的 HTTP/HTTPS URL |
| **400** | `REDIRECT_FAILED` | `无法访问或识别该分享链接` | 短链接 302 重定向失败或网络不通 |
| **400** | `PLATFORM_NOT_SUPPORTED` | `该链接尚未支持提取` | 暂未支持解析的域名平台 |
| **401** | `API_KEY_REQUIRED` | `请提供 API Key` | 缺少 Authorization 鉴权头 |
| **401** | `INVALID_API_KEY` | `API Key 无效` | Key 不存在或已被废弃 |
| **402** | `INSUFFICIENT_CREDITS` | `账号解析积分已耗尽，请联系管理员充值` | 当前用户积分余额不足 |
| **403** | `API_KEY_DISABLED` | `API Key 或账号已停用` | 当前账号或 Key 处于停用状态 |
| **403** | `ACCOUNT_EXPIRED` | `账号尚未开通或已到期` | 账号有效期已过 |
| **403** | `DEMO_DISABLED` | `在线体验暂未开放` | 管理员关闭了未登录前台体验 |
| **429** | `RATE_LIMITED` | `请求过于频繁，当前账号限制为 {N} QPS` | 超出当前账号或 Key 的 QPS 上限 |
| **429** | `PLATFORM_RATE_LIMITED` | `{platform} 接口请求过于频繁` | 超出该平台被单独设定的 QPS 上限 |
| **503** | `API_DISABLED` | `API 服务已暂停` | 全局维护中 |
| **503** | `PLATFORM_DISABLED` | `{platform} 接口维护中` | 该平台在管理后台被单独禁用 |
| **500** | `INTERNAL_ERROR` | `功能太火爆啦，请稍后再试` | 服务端未捕获异常兜底 |
