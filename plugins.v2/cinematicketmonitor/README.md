# 院线开票监控 v0.2.0（MoviePilot V2）

这是 MoviePilot V2 专用实现。

## 这次修复

上一版 `0.2.0` 的完整功能只放进了 `plugins.v3`，因此 MoviePilot V2 仍加载 `0.1.0`。

本版已经将：

- `plugin_version = 0.2.0`
- 完整 HTTP/JSON 监控能力
- `get_service()` 定时任务
- `save_data()` 状态持久化
- `post_message()` 通知

全部放进：

```text
plugins.v2/cinematicketmonitor/__init__.py
```

## 升级验证

升级后配置页应出现：

- 开票时通知
- 场次变化也通知
- 保存后立即检查
- 测试 v0.2.0 通知
- Cron
- 数据源 URL
- 请求头 JSON
- JSON 路径
- 开票关键字
- 未开票关键字
- 电影名称
- 影院名称
- 监控日期
- 购票跳转 URL

如果仍只有三个字段，则仍在运行 0.1.0。
