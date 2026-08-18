# 院线开票监控 CinemaTicketMonitor

## v0.2.0

本版已具备真正的定时数据源监控能力，但不内置任何需要绕过平台限制的票务接口。

### 功能

- MoviePilot V3 原生 `get_service()` 定时任务
- HTTP/HTTPS GET 数据源
- 自定义请求头 JSON
- JSON 点路径提取，例如 `data.showtimes`
- 开票关键字 / 未开票关键字判断
- 若不填写开票关键字，则目标 JSON/文本非空即视为 OPEN
- `WAITING -> OPEN` 时通知
- OPEN 状态下内容变化可再次通知
- 最近一次状态与响应预览
- MoviePilot `post_message()` 通知链
- 一次性立即检查
- 测试通知

### 推荐使用方式

优先使用：

1. 影院或票务平台明确提供/授权的 API；
2. 你自己搭建的中间接口；
3. 允许自动访问的影院官网数据源。

请遵守数据源服务条款和访问频率限制。

### JSON 示例

数据源返回：

```json
{
  "data": {
    "showtimes": [
      {"time": "19:30", "hall": "IMAX"}
    ]
  }
}
```

配置：

```text
JSON 路径：data.showtimes
开票关键字：留空
```

当 `showtimes` 从空数组变成非空数组时，会触发开票通知。
