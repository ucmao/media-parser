# 配音秀解析指南

## 支持范围

- 公开作品页：`https://www.peiyinxiu.com/m/{作品ID}`。

## 提取字段

可提取作品标题、作者昵称与头像、封面，以及页面公开的原始 MP4 地址。

## 实现说明

作品页初始化时直接写入 `PlayByShowplay.play` 配置；解析器从其中读取 `filmurl` 和 `filmimg`，不依赖登录态。
