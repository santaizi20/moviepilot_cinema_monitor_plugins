# moviepilot_cinema_monitor_plugins

MoviePilot「院线开票监控」插件仓库。

## 当前版本

- MoviePilot V3：`0.2.0`
- MoviePilot V2：`0.1.0`（基础通知链验证版）

## v0.2.0 功能

- HTTP/HTTPS 数据源定时检查
- JSON 路径提取
- 开票/未开票关键字判断
- 数据从空到非空自动判断开票
- 状态变化微信通知（通过 MoviePilot → WxPusher）
- 已开票后的场次变化提醒
- 最近一次检查状态和响应预览
- 立即检查一次
- 测试通知

## 目录

```text
.
├── icons/
├── plugins.v2/
├── plugins.v3/
├── tests/
├── package.v2.json
├── package.v3.json
└── SHA256SUMS.txt
```

## 更新方式

解压覆盖仓库根目录后：

```bash
git add .
git commit -m "update CinemaTicketMonitor to v0.2.0"
git push
```

MoviePilot 刷新插件市场后应显示 `0.2.0` 更新。
