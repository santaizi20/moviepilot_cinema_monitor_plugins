from typing import Any, Dict, List, Optional, Tuple

from app.plugins import _PluginBase


class CinemaTicketMonitor(_PluginBase):
    """MoviePilot V2 兼容的基础通知链验证版。"""

    plugin_name = "院线开票监控"
    plugin_desc = "电影院开票监控插件；V2 保留基础通知链验证能力。"
    plugin_icon = "cinematicketmonitor.png"
    plugin_version = "0.1.0"
    plugin_author = "santaizi20"
    author_url = "https://github.com/santaizi20/moviepilot_cinema_monitor_plugins"
    plugin_config_prefix = "cinematicketmonitor_"
    plugin_order = 30
    auth_level = 1

    _enabled: bool = False
    _test_notify: bool = False
    _message: str = "MoviePilot → WxPusher 通知链测试成功。"

    def init_plugin(self, config: Optional[dict] = None) -> None:
        config = config or {}
        self._enabled = bool(config.get("enabled", False))
        self._test_notify = bool(config.get("test_notify", False))
        self._message = str(config.get("message") or "MoviePilot → WxPusher 通知链测试成功。")
        if self._test_notify:
            self.post_message(title="🎬 院线开票监控测试", text=self._message)
            self._test_notify = False
            self.update_config({
                "enabled": self._enabled,
                "test_notify": False,
                "message": self._message,
            })

    def get_state(self) -> bool:
        return self._enabled

    @staticmethod
    def get_command() -> List[Dict[str, Any]]:
        return []

    def get_api(self) -> List[Dict[str, Any]]:
        return []

    def get_form(self) -> Tuple[List[dict], Dict[str, Any]]:
        return [{
            "component": "VForm",
            "content": [
                {"component": "VSwitch", "props": {"model": "enabled", "label": "启用插件"}},
                {"component": "VSwitch", "props": {"model": "test_notify", "label": "保存后发送一次测试通知"}},
                {"component": "VTextField", "props": {"model": "message", "label": "测试通知内容"}},
            ],
        }], {
            "enabled": False,
            "test_notify": False,
            "message": "MoviePilot → WxPusher 通知链测试成功。",
        }

    def get_page(self) -> List[dict]:
        return [{
            "component": "VAlert",
            "props": {
                "type": "info",
                "variant": "tonal",
                "text": "V2 当前保留 v0.1.0 基础链路验证版；完整监控功能优先支持 V3。",
            },
        }]

    def stop_service(self) -> None:
        return
