# moviepilot_cinema_monitor_plugins

MoviePilot V2「院线开票监控」插件仓库。

## 当前版本

**CinemaTicketMonitor v0.3.0**

本版本已从通用 URL 监控器升级为真正的影院新增排片监控器。

### 已实现

- 按影院一次请求完整排片
- 同影院支持同时监控多部电影
- 使用 `seqNo` 作为场次唯一标识
- 第一次只建立基线，不发送已有排片
- 后续新增场次微信通知
- 新增日期自动标记
- IMAX / 杜比 / 普通 / 不限过滤
- Cron 自定义扫描时间，默认每 30 分钟
- 可选“场次取消通知”
- MoviePilot `post_message()` → WxPusher

## 更新

将本压缩包解压到 Git 仓库根目录，覆盖旧文件：

```bash
git add -A
git commit -m "update CinemaTicketMonitor to v0.3.0"
git push
```

然后在 MoviePilot V2 插件市场刷新仓库并升级到 `0.3.0`。

## 建议第一次配置

```text
城市 ID：10
影院 ID：25428
影院名称：寰映影城（大融城激光IMAX店）
监控电影：奥德赛
放映类型：不限
Cron：*/30 * * * *
首次仅建立基线：开启
新增场次通知：开启
场次取消通知：关闭
```
