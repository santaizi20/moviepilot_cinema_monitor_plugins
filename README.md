# CinemaTicketMonitor v0.3.1

MoviePilot V2 院线开票监控。

## v0.3.1 修复

- 修复插件“分身”实例执行扫描时报：
  `name 'CinemaTicketMonitor' is not defined`
- 电影名称解析改为 `classmethod`，不再依赖固定类名。
- 定时任务 ID 加入运行时类名和影院 ID，降低多个分身之间的任务冲突风险。

其余 v0.3.0 功能保持不变。
