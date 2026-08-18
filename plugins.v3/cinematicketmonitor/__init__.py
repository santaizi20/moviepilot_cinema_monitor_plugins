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
    院线开票监控。

    v0.2.0:
    - 支持定时请求用户配置的 HTTP/HTTPS 数据源；
    - 支持普通文本/HTML 与 JSON 路径两种判断方式；
    - 检测 WAITING -> OPEN 状态变化；
    - 可选在已开票状态下内容变化时再次提醒；
    - 通知继续走 MoviePilot 统一 post_message() 链路。
    """

    plugin_name = "院线开票监控"
    plugin_desc = "监控授权的影院/票务数据源，发现开票或场次变化后通过 MoviePilot 通知。"
    plugin_icon = "cinematicketmonitor.png"
    plugin_version = "0.2.0"
    plugin_author = "santaizi20"
    author_url = "https://github.com/santaizi20/moviepilot_cinema_monitor_plugins"
    plugin_config_prefix = "cinematicketmonitor_"
    plugin_order = 30
    auth_level = 1

    _enabled: bool = False
    _notify: bool = True
    _notify_changes: bool = True
    _onlyonce: bool = False
    _test_notify: bool = False

    _cron: str = "*/5 * * * *"
    _source_url: str = ""
    _headers_json: str = ""
    _json_path: str = ""
    _open_keywords: str = ""
    _closed_keywords: str = ""
    _timeout: int = 15

    _movie_name: str = ""
    _cinema_name: str = ""
    _date_label: str = ""
    _buy_url: str = ""

    def init_plugin(self, config: Optional[dict] = None) -> None:
        """读取插件配置。"""
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
                title="🎬 院线开票监控测试",
                text="v0.2.0 通知链正常：MoviePilot → 已启用通知渠道。"
            )
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

    def get_service(self) -> List[Dict[str, Any]]:
        """注册定时监控及一次性检查任务。"""
        services: List[Dict[str, Any]] = []

        if self._enabled and self._cron:
            try:
                services.append({
                    "id": "CinemaTicketMonitor.PeriodicCheck",
                    "name": "院线开票监控定时检查",
                    "trigger": CronTrigger.from_crontab(self._cron),
                    "func": self.check_source,
                    "kwargs": {},
                })
            except Exception:
                # Cron 配置错误时不阻塞插件加载，错误会显示在详情页。
                self.save_data("last_result", {
                    "checked_at": self._now(),
                    "status": "ERROR",
                    "message": f"Cron 表达式无效：{self._cron}",
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
        """返回配置表单与默认配置。"""
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
                                "v0.2.0 已支持真实 HTTP/JSON 数据源监控。"
                                "请仅填写你有权访问和自动查询的数据源。"
                            ),
                        },
                    },
                    {
                        "component": "VRow",
                        "content": [
                            self._switch("enabled", "启用插件", 3),
                            self._switch("notify", "开票时通知", 3),
                            self._switch("notify_changes", "开票后内容变化也通知", 3),
                            self._switch("onlyonce", "保存后立即检查一次", 3),
                        ],
                    },
                    {
                        "component": "VRow",
                        "content": [
                            self._switch("test_notify", "保存后测试通知", 4),
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
                                "例如 data.showtimes；留空则检查完整响应文本",
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
                                "例如 可购票,选座；留空时 JSON 非空即视为开票",
                                6,
                            ),
                            self._text(
                                "closed_keywords",
                                "未开票关键字（可选，英文逗号分隔）",
                                "例如 暂无场次,敬请期待",
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
                                "通知中附带的购票页面地址",
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
        """显示最近一次监控结果。"""
        result = self.get_data("last_result") or {}
        if not result:
            return [{
                "component": "VAlert",
                "props": {
                    "type": "info",
                    "variant": "tonal",
                    "text": "尚未执行监控。配置数据源后勾选“保存后立即检查一次”。",
                },
            }]

        status = result.get("status", "UNKNOWN")
        alert_type = {
            "OPEN": "success",
            "WAITING": "info",
            "UNKNOWN": "warning",
            "ERROR": "error",
        }.get(status, "info")

        lines = [
            f"最近检查：{result.get('checked_at', '-')}",
            f"状态：{status}",
            f"电影：{self._movie_name or '-'}",
            f"影院：{self._cinema_name or '-'}",
            f"日期：{self._date_label or '-'}",
            f"摘要：{result.get('message', '-')}",
        ]
        if result.get("preview"):
            lines.append(f"响应预览：{result.get('preview')}")

        return [{
            "component": "VAlert",
            "props": {
                "type": alert_type,
                "variant": "tonal",
                "text": "\n".join(lines),
            },
        }]

    def stop_service(self) -> None:
        """本插件只使用 MoviePilot 宿主调度器，无额外后台资源。"""
        return

    def check_source(self, reset_onlyonce: bool = False) -> None:
        """执行一次数据源检查并判断是否开票。"""
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

            changed = bool(previous_hash and previous_hash != current_hash)
            first_seen_open = status == "OPEN" and previous_status != "OPEN"
            changed_while_open = (
                status == "OPEN"
                and previous_status == "OPEN"
                and changed
                and self._notify_changes
            )

            self.save_data("monitor_state", {
                "status": status,
                "hash": current_hash,
                "checked_at": self._now(),
            })

            preview = self._preview(canonical)
            self.save_data("last_result", {
                "checked_at": self._now(),
                "status": status,
                "message": reason,
                "preview": preview,
            })

            if self._notify and (first_seen_open or changed_while_open):
                self._send_open_notice(
                    reason=reason,
                    changed=changed_while_open,
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

    def _fetch_source(self) -> Tuple[str, Any]:
        """请求数据源；返回原始文本及可选 JSON 对象。"""
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

        request = Request(
            self._source_url,
            headers=headers,
            method="GET",
        )
        with urlopen(request, timeout=self._timeout) as response:
            body = response.read()
            charset = response.headers.get_content_charset() or "utf-8"

        raw_text = body.decode(charset, errors="replace")

        parsed_json = None
        try:
            parsed_json = json.loads(raw_text)
        except Exception:
            parsed_json = None

        return raw_text, parsed_json

    def _resolve_target(self, raw_text: str, parsed_json: Any) -> Any:
        """如配置 JSON 路径则提取对应字段，否则返回完整响应。"""
        if not self._json_path:
            return parsed_json if parsed_json is not None else raw_text

        if parsed_json is None:
            raise ValueError("已配置 JSON 路径，但数据源返回不是有效 JSON")

        current = parsed_json
        for part in [x.strip() for x in self._json_path.split(".") if x.strip()]:
            if isinstance(current, dict):
                if part not in current:
                    raise KeyError(f"JSON 路径不存在：{self._json_path}")
                current = current[part]
            elif isinstance(current, list) and part.isdigit():
                index = int(part)
                if index >= len(current):
                    raise IndexError(f"JSON 数组索引越界：{part}")
                current = current[index]
            else:
                raise KeyError(f"无法继续解析 JSON 路径：{self._json_path}")

        return current

    def _judge_status(self, target: Any) -> Tuple[str, str]:
        """根据关键字或非空规则判断 OPEN / WAITING / UNKNOWN。"""
        canonical = self._canonical_text(target)
        lower = canonical.lower()

        open_keywords = self._split_keywords(self._open_keywords)
        closed_keywords = self._split_keywords(self._closed_keywords)

        open_hits = [kw for kw in open_keywords if kw.lower() in lower]
        closed_hits = [kw for kw in closed_keywords if kw.lower() in lower]

        if open_keywords:
            if open_hits:
                return "OPEN", f"命中开票关键字：{', '.join(open_hits)}"
            if closed_hits:
                return "WAITING", f"命中未开票关键字：{', '.join(closed_hits)}"
            return "UNKNOWN", "未命中任何开票/未开票关键字"

        # 未配置开票关键字时，JSON/文本目标非空即视为 OPEN。
        if self._is_nonempty(target):
            if closed_hits:
                return "WAITING", f"命中未开票关键字：{', '.join(closed_hits)}"
            return "OPEN", "目标数据非空"

        return "WAITING", "目标数据为空"

    def _send_open_notice(self, reason: str, changed: bool, preview: str) -> None:
        """发送开票/场次变化通知。"""
        title = "🎟️ 场次更新提醒" if changed else "🎬 开票提醒"
        lines = []

        if self._movie_name:
            lines.append(f"电影：{self._movie_name}")
        if self._cinema_name:
            lines.append(f"影院：{self._cinema_name}")
        if self._date_label:
            lines.append(f"日期：{self._date_label}")

        lines.append(f"状态：{reason}")

        if preview:
            lines.append(f"数据：{preview}")

        if self._buy_url:
            lines.append(f"购票：{self._buy_url}")

        self.post_message(
            title=title,
            text="\n".join(lines),
        )

    def _save_config(self) -> bool:
        """保存当前配置。"""
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
                "props": {"model": model, "label": label},
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
    def _split_keywords(value: str) -> List[str]:
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
