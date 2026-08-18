import hashlib
import json
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
from urllib.request import Request, urlopen

from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger

from app.plugins import _PluginBase


class CinemaTicketMonitor(_PluginBase):
    """
    院线开票监控 - MoviePilot V2

    v0.2.0:
    - 定时检查 HTTP/HTTPS 数据源
    - 支持 JSON 路径提取
    - 支持开票/未开票关键字
    - WAITING -> OPEN 时通知
    - OPEN 后内容变化可再次通知
    - 继续使用 MoviePilot post_message()，由 WxPusher 等通知渠道转发
    """

    plugin_name = "院线开票监控"
    plugin_desc = "监控影院/票务 HTTP 或 JSON 数据源，发现开票或场次变化后通过 MoviePilot 通知。"
    plugin_icon = "cinematicketmonitor.png"
    plugin_version = "0.2.0"
    plugin_author = "santaizi20"
    author_url = "https://github.com/santaizi20/moviepilot_cinema_monitor_plugins"
    plugin_config_prefix = "cinematicketmonitor_"
    plugin_order = 30
    auth_level = 1

    _enabled = False
    _notify = True
    _notify_changes = True
    _onlyonce = False
    _test_notify = False

    _cron = "*/5 * * * *"
    _source_url = ""
    _headers_json = ""
    _json_path = ""
    _open_keywords = ""
    _closed_keywords = ""
    _timeout = 15

    _movie_name = ""
    _cinema_name = ""
    _date_label = ""
    _buy_url = ""

    def init_plugin(self, config: dict = None):
        """读取并应用插件配置。"""
        config = config or {}

        self._enabled = bool(config.get("enabled", False))
        self._notify = bool(config.get("notify", True))
        self._notify_changes = bool(config.get("notify_changes", True))
        self._onlyonce = bool(config.get("onlyonce", False))
        self._test_notify = bool(config.get("test_notify", False))

        self._cron = str(config.get("cron") or "*/5 * * * *").strip()
        self._source_url = str(config.get("source_url") or "").strip()
        self._headers_json = str(config.get("headers_json") or "").strip()
        self._json_path = str(config.get("json_path") or "").strip()
        self._open_keywords = str(config.get("open_keywords") or "").strip()
        self._closed_keywords = str(config.get("closed_keywords") or "").strip()

        try:
            self._timeout = max(3, min(60, int(config.get("timeout") or 15)))
        except (TypeError, ValueError):
            self._timeout = 15

        self._movie_name = str(config.get("movie_name") or "").strip()
        self._cinema_name = str(config.get("cinema_name") or "").strip()
        self._date_label = str(config.get("date_label") or "").strip()
        self._buy_url = str(config.get("buy_url") or "").strip()

        if self._test_notify:
            self.post_message(
                title="🎬 院线开票监控 v0.2.0",
                text="MoviePilot V2 插件升级成功，通知链正常。"
            )
            self._test_notify = False
            self._save_config()

    def get_state(self) -> bool:
        """返回启用状态。"""
        return self._enabled

    @staticmethod
    def get_command() -> List[Dict[str, Any]]:
        """当前版本无远程命令。"""
        return []

    def get_api(self) -> List[Dict[str, Any]]:
        """当前版本无额外 API。"""
        return []

    def get_service(self) -> List[Dict[str, Any]]:
        """注册周期检查和一次性立即检查服务。"""
        services = []

        if self._enabled and self._cron:
            try:
                services.append({
                    "id": "CinemaTicketMonitor.PeriodicCheck",
                    "name": "院线开票监控定时检查",
                    "trigger": CronTrigger.from_crontab(self._cron),
                    "func": self.check_source,
                    "kwargs": {},
                })
            except Exception as err:
                self.save_data("last_result", {
                    "checked_at": self._now(),
                    "status": "ERROR",
                    "message": "Cron 表达式无效：%s" % err,
                    "preview": "",
                })

        if self._onlyonce:
            services.append({
                "id": "CinemaTicketMonitor.OneShotCheck",
                "name": "院线开票监控立即检查",
                "trigger": DateTrigger(run_date=datetime.now() + timedelta(seconds=3)),
                "func": self.check_source,
                "kwargs": {"reset_onlyonce": True},
            })

        return services

    def get_form(self) -> Tuple[List[dict], Dict[str, Any]]:
        """返回 V2 Vuetify 配置页面。"""
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
                                "v0.2.0（MoviePilot V2）：已支持 HTTP/JSON 数据源定时监控。"
                                "请仅使用你有权自动访问的数据源。"
                            ),
                        },
                    },
                    {
                        "component": "VRow",
                        "content": [
                            self._switch("enabled", "启用插件", 3),
                            self._switch("notify", "开票时通知", 3),
                            self._switch("notify_changes", "场次变化也通知", 3),
                            self._switch("onlyonce", "保存后立即检查", 3),
                        ],
                    },
                    {
                        "component": "VRow",
                        "content": [
                            self._switch("test_notify", "测试 v0.2.0 通知", 4),
                            self._text("cron", "检查周期（Cron）", "*/5 * * * *", 4),
                            self._text("timeout", "请求超时（秒）", "15", 4),
                        ],
                    },
                    {
                        "component": "VRow",
                        "content": [
                            self._text("movie_name", "电影名称", "例如：疯狂动物城2", 4),
                            self._text("cinema_name", "影院名称", "例如：上海影城", 4),
                            self._text("date_label", "监控日期", "例如：2026-11-20", 4),
                        ],
                    },
                    {
                        "component": "VRow",
                        "content": [
                            self._text(
                                "source_url",
                                "数据源 URL",
                                "https://example.com/api/showtimes",
                                12,
                            ),
                        ],
                    },
                    {
                        "component": "VRow",
                        "content": [
                            self._text(
                                "headers_json",
                                "请求头 JSON（可选）",
                                '{"Authorization":"Bearer xxx"}',
                                12,
                            ),
                        ],
                    },
                    {
                        "component": "VRow",
                        "content": [
                            self._text(
                                "json_path",
                                "JSON 路径（可选）",
                                "例如：data.showtimes；留空则判断完整响应",
                                12,
                            ),
                        ],
                    },
                    {
                        "component": "VRow",
                        "content": [
                            self._text(
                                "open_keywords",
                                "开票关键字（可选，英文逗号分隔）",
                                "例如：可购票,选座",
                                6,
                            ),
                            self._text(
                                "closed_keywords",
                                "未开票关键字（可选，英文逗号分隔）",
                                "例如：暂无场次,敬请期待",
                                6,
                            ),
                        ],
                    },
                    {
                        "component": "VRow",
                        "content": [
                            self._text(
                                "buy_url",
                                "购票跳转 URL（可选）",
                                "收到通知时附带的购票地址",
                                12,
                            ),
                        ],
                    },
                ],
            }
        ], {
            "enabled": False,
            "notify": True,
            "notify_changes": True,
            "onlyonce": False,
            "test_notify": False,
            "cron": "*/5 * * * *",
            "timeout": 15,
            "movie_name": "",
            "cinema_name": "",
            "date_label": "",
            "source_url": "",
            "headers_json": "",
            "json_path": "",
            "open_keywords": "",
            "closed_keywords": "",
            "buy_url": "",
        }

    def get_page(self) -> List[dict]:
        """显示最近检查结果。"""
        result = self.get_data("last_result") or {}

        if not result:
            text = (
                "院线开票监控 v0.2.0 已加载。\n"
                "尚未执行数据源检查，可在配置页勾选“保存后立即检查”。"
            )
            alert_type = "info"
        else:
            status = result.get("status", "UNKNOWN")
            alert_type = {
                "OPEN": "success",
                "WAITING": "info",
                "UNKNOWN": "warning",
                "ERROR": "error",
            }.get(status, "info")

            lines = [
                "当前版本：0.2.0（MoviePilot V2）",
                "最近检查：%s" % result.get("checked_at", "-"),
                "状态：%s" % status,
                "电影：%s" % (self._movie_name or "-"),
                "影院：%s" % (self._cinema_name or "-"),
                "日期：%s" % (self._date_label or "-"),
                "摘要：%s" % result.get("message", "-"),
            ]
            if result.get("preview"):
                lines.append("响应预览：%s" % result.get("preview"))
            text = "\n".join(lines)

        return [{
            "component": "VAlert",
            "props": {
                "type": alert_type,
                "variant": "tonal",
                "text": text,
            },
        }]

    def stop_service(self):
        """仅使用宿主公共服务调度器，无自行创建的资源需要释放。"""
        pass

    def check_source(self, reset_onlyonce: bool = False):
        """执行一次数据源检查。"""
        try:
            if not self._source_url:
                raise ValueError("未配置数据源 URL")

            raw_text, parsed_json = self._fetch_source()
            target = self._resolve_target(raw_text, parsed_json)
            status, reason = self._judge_status(target)

            canonical = self._canonical_text(target)
            current_hash = hashlib.sha256(
                canonical.encode("utf-8", errors="ignore")
            ).hexdigest()

            previous = self.get_data("monitor_state") or {}
            previous_status = previous.get("status")
            previous_hash = previous.get("hash")

            content_changed = bool(
                previous_hash and previous_hash != current_hash
            )
            first_open = status == "OPEN" and previous_status != "OPEN"
            open_changed = (
                status == "OPEN"
                and previous_status == "OPEN"
                and content_changed
                and self._notify_changes
            )

            checked_at = self._now()
            self.save_data("monitor_state", {
                "status": status,
                "hash": current_hash,
                "checked_at": checked_at,
            })

            preview = self._preview(canonical)
            self.save_data("last_result", {
                "checked_at": checked_at,
                "status": status,
                "message": reason,
                "preview": preview,
            })

            if self._notify and (first_open or open_changed):
                self._send_notice(
                    reason=reason,
                    changed=open_changed,
                    preview=preview,
                )

        except Exception as err:
            self.save_data("last_result", {
                "checked_at": self._now(),
                "status": "ERROR",
                "message": str(err),
                "preview": "",
            })
        finally:
            if reset_onlyonce:
                self._onlyonce = False
                self._save_config()

    def _fetch_source(self):
        """GET 请求数据源。"""
        headers = {
            "User-Agent": "MoviePilot-CinemaTicketMonitor/0.2.0",
            "Accept": "application/json,text/plain,text/html,*/*",
        }

        if self._headers_json:
            extra = json.loads(self._headers_json)
            if not isinstance(extra, dict):
                raise ValueError("请求头 JSON 必须是对象")
            for key, value in extra.items():
                headers[str(key)] = str(value)

        request = Request(self._source_url, headers=headers, method="GET")
        with urlopen(request, timeout=self._timeout) as response:
            body = response.read()
            charset = response.headers.get_content_charset() or "utf-8"

        raw_text = body.decode(charset, errors="replace")

        try:
            parsed_json = json.loads(raw_text)
        except Exception:
            parsed_json = None

        return raw_text, parsed_json

    def _resolve_target(self, raw_text: str, parsed_json: Any):
        """按 dot-path 提取 JSON 节点。"""
        if not self._json_path:
            return parsed_json if parsed_json is not None else raw_text

        if parsed_json is None:
            raise ValueError("已配置 JSON 路径，但返回内容不是有效 JSON")

        current = parsed_json
        parts = [x.strip() for x in self._json_path.split(".") if x.strip()]

        for part in parts:
            if isinstance(current, dict):
                if part not in current:
                    raise KeyError("JSON 路径不存在：%s" % self._json_path)
                current = current[part]
            elif isinstance(current, list) and part.isdigit():
                index = int(part)
                if index >= len(current):
                    raise IndexError("JSON 数组索引越界：%s" % part)
                current = current[index]
            else:
                raise KeyError("无法继续解析 JSON 路径：%s" % self._json_path)

        return current

    def _judge_status(self, target: Any):
        """判断目标内容当前是否代表开票。"""
        canonical = self._canonical_text(target)
        lower_text = canonical.lower()

        open_keywords = self._split_keywords(self._open_keywords)
        closed_keywords = self._split_keywords(self._closed_keywords)

        open_hits = [
            kw for kw in open_keywords if kw.lower() in lower_text
        ]
        closed_hits = [
            kw for kw in closed_keywords if kw.lower() in lower_text
        ]

        if open_keywords:
            if open_hits:
                return "OPEN", "命中开票关键字：%s" % ", ".join(open_hits)
            if closed_hits:
                return "WAITING", "命中未开票关键字：%s" % ", ".join(closed_hits)
            return "UNKNOWN", "未命中任何开票/未开票关键字"

        if closed_hits:
            return "WAITING", "命中未开票关键字：%s" % ", ".join(closed_hits)

        if self._is_nonempty(target):
            return "OPEN", "目标数据非空"

        return "WAITING", "目标数据为空"

    def _send_notice(self, reason: str, changed: bool, preview: str):
        """通过 MoviePilot 统一通知链发消息。"""
        title = "🎟️ 场次更新提醒" if changed else "🎬 开票提醒"
        lines = []

        if self._movie_name:
            lines.append("电影：%s" % self._movie_name)
        if self._cinema_name:
            lines.append("影院：%s" % self._cinema_name)
        if self._date_label:
            lines.append("日期：%s" % self._date_label)

        lines.append("状态：%s" % reason)

        if preview:
            lines.append("数据：%s" % preview)

        if self._buy_url:
            lines.append("购票：%s" % self._buy_url)

        self.post_message(
            title=title,
            text="\n".join(lines),
        )

    def _save_config(self):
        """保存插件配置。"""
        return self.update_config({
            "enabled": self._enabled,
            "notify": self._notify,
            "notify_changes": self._notify_changes,
            "onlyonce": self._onlyonce,
            "test_notify": self._test_notify,
            "cron": self._cron,
            "timeout": self._timeout,
            "movie_name": self._movie_name,
            "cinema_name": self._cinema_name,
            "date_label": self._date_label,
            "source_url": self._source_url,
            "headers_json": self._headers_json,
            "json_path": self._json_path,
            "open_keywords": self._open_keywords,
            "closed_keywords": self._closed_keywords,
            "buy_url": self._buy_url,
        })

    @staticmethod
    def _switch(model: str, label: str, md: int) -> dict:
        return {
            "component": "VCol",
            "props": {"cols": 12, "md": md},
            "content": [{
                "component": "VSwitch",
                "props": {
                    "model": model,
                    "label": label,
                },
            }],
        }

    @staticmethod
    def _text(model: str, label: str, placeholder: str, md: int) -> dict:
        return {
            "component": "VCol",
            "props": {"cols": 12, "md": md},
            "content": [{
                "component": "VTextField",
                "props": {
                    "model": model,
                    "label": label,
                    "placeholder": placeholder,
                },
            }],
        }

    @staticmethod
    def _split_keywords(value: str):
        return [x.strip() for x in value.split(",") if x.strip()]

    @staticmethod
    def _canonical_text(value: Any) -> str:
        if isinstance(value, (dict, list)):
            return json.dumps(value, ensure_ascii=False, sort_keys=True)
        if value is None:
            return ""
        return str(value)

    @staticmethod
    def _is_nonempty(value: Any) -> bool:
        if value is None:
            return False
        if isinstance(value, (list, dict, tuple, set)):
            return len(value) > 0
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return value != 0
        return bool(str(value).strip())

    @staticmethod
    def _preview(text: str, limit: int = 240) -> str:
        compact = " ".join(text.split())
        if len(compact) <= limit:
            return compact
        return compact[:limit] + "..."

    @staticmethod
    def _now() -> str:
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
