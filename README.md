# moviepilot_cinema_monitor_plugins

MoviePilot 院线开票监控插件仓库。

## 目录

```text
.
├── icons/
│   └── cinematicketmonitor.png
├── plugins.v2/
│   └── cinematicketmonitor/
│       ├── __init__.py
│       └── README.md
├── plugins.v3/
│   └── cinematicketmonitor/
│       ├── __init__.py
│       └── README.md
├── package.v2.json
├── package.v3.json
└── SHA256SUMS.txt
```

## 版本说明

- MoviePilot V3：读取 `package.v3.json` + `plugins.v3/`
- MoviePilot V2：读取 `package.v2.json` + `plugins.v2/`
- 插件版本：`0.1.0`

## 第一次测试

安装“院线开票监控”后：

1. 打开插件配置；
2. 启用插件；
3. 打开“保存后发送一次测试通知”；
4. 保存；
5. 确认 WxPusher 收到 `🎬 院线开票监控测试`。

> 0.1.0 暂不采集猫眼/淘票票数据，只验证 MoviePilot 插件与通知链路。
