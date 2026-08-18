from typing import Any, Dict, List, Optional, Tuple

from app.plugins import _PluginBase


class CinemaTicketMonitor(_PluginBase):
    """
    院线开票监控。

    0.1.0 为基础链路验证版本：
    1. 验证 MoviePilot 能发现并加载第三方插件；
    2. 验证插件可以调用 MoviePilot 的统一通知链；
    3. 后续版本再接入电影院排片/开票数据源。
    """

    plugin_name = "院线开票监控"
    plugin_desc = "电影院开票监控插件；当前版本用于验证插件加载及 MoviePilot 通知链。"
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
        """读取配置，并在用户勾选测试开关时发送一次通知。"""
        config = config or {}

        self._enabled = bool(config.get("enabled", False))
        self._test_notify = bool(config.get("test_notify", False))
        self._message = str(
            config.get("message")
            or "MoviePilot → WxPusher 通知链测试成功。"
        )

        if self._test_notify:
            self._send_test_notification()
            self._test_notify = False
            self._save_config()

    def get_state(self) -> bool:
        """返回插件启用状态。"""
        return self._enabled

    @staticmethod
    def get_command() -> List[Dict[str, Any]]:
        """当前版本不注册远程命令。"""
        return []

    def get_api(self) -> List[Dict[str, Any]]:
        """当前版本不注册额外 API。"""
        return []

    def get_form(self) -> Tuple[List[dict], Dict[str, Any]]:
        """返回插件配置页面及默认值。"""
        return [
            {
                "component": "VForm",
                "content": [
                    {
                        "component": "VAlert",
                        "props": {
                            "type": "info",
                            "variant": "tonal",
                            "text": (
                                "0.1.0 是基础链路验证版。"
                                "先确认插件能安装，并通过 MoviePilot 已配置的通知渠道发送测试消息。"
                            ),
                        },
                    },
                    {
                        "component": "VRow",
                        "content": [
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 6},
                                "content": [
                                    {
                                        "component": "VSwitch",
                                        "props": {
                                            "model": "enabled",
                                            "label": "启用插件",
                                        },
                                    }
                                ],
                            },
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 6},
                                "content": [
                                    {
                                        "component": "VSwitch",
                                        "props": {
                                            "model": "test_notify",
                                            "label": "保存后发送一次测试通知",
                                        },
                                    }
                                ],
                            },
                        ],
                    },
                    {
                        "component": "VRow",
                        "content": [
                            {
                                "component": "VCol",
                                "props": {"cols": 12},
                                "content": [
                                    {
                                        "component": "VTextField",
                                        "props": {
                                            "model": "message",
                                            "label": "测试通知内容",
                                            "placeholder": "MoviePilot → WxPusher 通知链测试成功。",
                                        },
                                    }
                                ],
                            }
                        ],
                    },
                ],
            }
        ], {
            "enabled": False,
            "test_notify": False,
            "message": "MoviePilot → WxPusher 通知链测试成功。",
        }

    def get_page(self) -> List[dict]:
        """返回插件详情页。"""
        return [
            {
                "component": "VAlert",
                "props": {
                    "type": "success" if self._enabled else "info",
                    "variant": "tonal",
                    "text": (
                        "院线开票监控插件已加载。\n"
                        f"插件状态：{'已启用' if self._enabled else '未启用'}\n"
                        "当前版本：0.1.0（基础链路验证版）"
                    ),
                },
            }
        ]

    def stop_service(self) -> None:
        """当前版本没有自行创建的后台资源，无需额外释放。"""
        return

    def _send_test_notification(self) -> None:
        """
        通过 MoviePilot 基类的统一通知方法发送消息。

        不直接调用 WxPusher API，因此只要 MoviePilot 内已配置并启用了
        WxPusher（或其他通知插件），消息即可由宿主统一转发。
        """
        self.post_message(
            title="🎬 院线开票监控测试",
            text=self._message,
        )

    def _save_config(self) -> bool:
        """保存当前插件配置，并复位一次性测试开关。"""
        return self.update_config({
            "enabled": self._enabled,
            "test_notify": False,
            "message": self._message,
        })
