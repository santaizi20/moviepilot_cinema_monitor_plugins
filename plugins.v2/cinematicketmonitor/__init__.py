import hashlib
import json
import re
from datetime import datetime, timedelta
from typing import Any, Dict, List, Tuple
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger

from app.plugins import _PluginBase


class CinemaTicketMonitor(_PluginBase):
    """
    院线开票监控 - MoviePilot V2

    v0.3.0
    - 按影院请求排片接口，一次请求可监控多部电影
    - 使用 seqNo 识别具体场次
    - 首次运行可只建立基线，不发送历史场次通知
    - 后续仅在新增场次时通知
    - 可选通知仍未开场却从接口消失的场次
    - 支持不限 / IMAX / 杜比 / 普通厅过滤
    - 扫描时间直接使用 Cron 配置，默认每 30 分钟
    """

    plugin_name = "院线开票监控"
    plugin_desc = "监控指定影院电影新增排片，使用场次 seqNo 精确识别新增场次并通过 MoviePilot 通知。"
    plugin_icon = "cinematicketmonitor.png"
    plugin_version = "0.3.0"
    plugin_author = "santaizi20"
    author_url = "https://github.com/santaizi20/moviepilot_cinema_monitor_plugins"
    plugin_config_prefix = "cinematicketmonitor_"
    plugin_order = 30
    auth_level = 1

    _enabled = False
    _notify_new = True
    _notify_removed = False
    _baseline_first = True
    _onlyonce = False
    _test_notify = False

    _api_url = "https://apis.netstart.cn/maoyan/cinema/shows"
    _city_id = "10"
    _cinema_id = "25428"
    _cinema_name = ""
    _movie_names = ""
    _show_type = "不限"
    _cron = "*/30 * * * *"
    _timeout = 15
    _buy_url = ""

    def init_plugin(self, config: dict = None):
        """读取插件配置。"""
        config = config or {}

        self._enabled = bool(config.get("enabled", False))
        self._notify_new = bool(config.get("notify_new", True))
        self._notify_removed = bool(config.get("notify_removed", False))
        self._baseline_first = bool(config.get("baseline_first", True))
        self._onlyonce = bool(config.get("onlyonce", False))
        self._test_notify = bool(config.get("test_notify", False))

        self._api_url = str(
            config.get("api_url")
            or "https://apis.netstart.cn/maoyan/cinema/shows"
        ).strip()
        self._city_id = str(config.get("city_id") or "10").strip()
        self._cinema_id = str(config.get("cinema_id") or "25428").strip()
        self._cinema_name = str(config.get("cinema_name") or "").strip()
        self._movie_names = str(config.get("movie_names") or "").strip()
        self._show_type = str(config.get("show_type") or "不限").strip()
        self._cron = str(config.get("cron") or "*/30 * * * *").strip()
        self._buy_url = str(config.get("buy_url") or "").strip()

        try:
            self._timeout = max(3, min(60, int(config.get("timeout") or 15)))
        except (TypeError, ValueError):
            self._timeout = 15

        if self._test_notify:
            self.post_message(
                title="🎬 院线开票监控 v0.3.0",
                text=(
                    "MoviePilot V2 插件已加载。\n"
                    "通知链测试成功：MoviePilot → 已启用通知渠道。"
                ),
            )
            self._test_notify = False
            self._save_config()

    def get_state(self) -> bool:
        return self._enabled

    @staticmethod
    def get_command() -> List[Dict[str, Any]]:
        return []

    def get_api(self) -> List[Dict[str, Any]]:
        return []

    def get_service(self) -> List[Dict[str, Any]]:
        """注册 Cron 周期任务及一次性立即检查任务。"""
        services = []

        if self._enabled and self._cron:
            try:
                services.append({
                    "id": "CinemaTicketMonitor.PeriodicCheck",
                    "name": "院线开票监控定时扫描",
                    "trigger": CronTrigger.from_crontab(self._cron),
                    "func": self.check_showtimes,
                    "kwargs": {},
                })
            except Exception as err:
                self.save_data("last_result", {
                    "checked_at": self._now(),
                    "status": "ERROR",
                    "message": "Cron 表达式无效：%s" % err,
                    "details": [],
                })

        if self._onlyonce:
            services.append({
                "id": "CinemaTicketMonitor.OneShotCheck",
                "name": "院线开票监控立即扫描",
                "trigger": DateTrigger(
                    run_date=datetime.now() + timedelta(seconds=3)
                ),
                "func": self.check_showtimes,
                "kwargs": {"reset_onlyonce": True},
            })

        return services

    def get_form(self) -> Tuple[List[dict], Dict[str, Any]]:
        """MoviePilot V2 配置页。"""
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
                                "v0.3.0：按影院一次获取完整排片，"
                                "使用 seqNo 精确比较新增场次。"
                                "默认每 30 分钟扫描一次。"
                            ),
                        },
                    },
                    {
                        "component": "VRow",
                        "content": [
                            self._switch("enabled", "启用插件", 3),
                            self._switch("baseline_first", "首次仅建立基线", 3),
                            self._switch("notify_new", "新增场次通知", 3),
                            self._switch("notify_removed", "场次取消通知", 3),
                        ],
                    },
                    {
                        "component": "VRow",
                        "content": [
                            self._switch("onlyonce", "保存后立即扫描", 4),
                            self._switch("test_notify", "测试 v0.3.0 通知", 4),
                            self._text(
                                "cron",
                                "扫描 Cron",
                                "*/30 * * * *",
                                4,
                            ),
                        ],
                    },
                    {
                        "component": "VRow",
                        "content": [
                            self._text(
                                "api_url",
                                "排片接口地址",
                                "https://apis.netstart.cn/maoyan/cinema/shows",
                                12,
                            ),
                        ],
                    },
                    {
                        "component": "VRow",
                        "content": [
                            self._text("city_id", "城市 ID", "10", 3),
                            self._text("cinema_id", "影院 ID", "25428", 3),
                            self._text(
                                "cinema_name",
                                "影院名称（可选）",
                                "留空时使用接口返回名称",
                                6,
                            ),
                        ],
                    },
                    {
                        "component": "VRow",
                        "content": [
                            self._text(
                                "movie_names",
                                "监控电影",
                                "奥德赛；多部电影用逗号或换行分隔",
                                8,
                            ),
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 4},
                                "content": [{
                                    "component": "VSelect",
                                    "props": {
                                        "model": "show_type",
                                        "label": "放映类型",
                                        "items": ["不限", "IMAX", "杜比", "普通"],
                                    },
                                }],
                            },
                        ],
                    },
                    {
                        "component": "VRow",
                        "content": [
                            self._text(
                                "buy_url",
                                "购票跳转地址（可选）",
                                "收到通知时附带的购票页面地址",
                                8,
                            ),
                            self._text(
                                "timeout",
                                "请求超时（秒）",
                                "15",
                                4,
                            ),
                        ],
                    },
                ],
            }
        ], {
            "enabled": False,
            "baseline_first": True,
            "notify_new": True,
            "notify_removed": False,
            "onlyonce": False,
            "test_notify": False,
            "api_url": "https://apis.netstart.cn/maoyan/cinema/shows",
            "city_id": "10",
            "cinema_id": "25428",
            "cinema_name": "",
            "movie_names": "",
            "show_type": "不限",
            "cron": "*/30 * * * *",
            "buy_url": "",
            "timeout": 15,
        }

    def get_page(self) -> List[dict]:
        """插件详情页展示最近一次扫描状态。"""
        result = self.get_data("last_result") or {}

        if not result:
            return [{
                "component": "VAlert",
                "props": {
                    "type": "info",
                    "variant": "tonal",
                    "text": (
                        "院线开票监控 v0.3.0 已加载。\n"
                        "配置电影后，可勾选“保存后立即扫描”建立首次基线。"
                    ),
                },
            }]

        status = result.get("status", "UNKNOWN")
        alert_type = {
            "OK": "success",
            "BASELINE": "info",
            "PARTIAL": "warning",
            "ERROR": "error",
        }.get(status, "info")

        lines = [
            "当前版本：0.3.0（MoviePilot V2）",
            "最近扫描：%s" % result.get("checked_at", "-"),
            "影院：%s" % result.get("cinema_name", self._cinema_name or "-"),
            "状态：%s" % status,
            "摘要：%s" % result.get("message", "-"),
        ]

        for detail in result.get("details", [])[:12]:
            lines.append(detail)

        return [{
            "component": "VAlert",
            "props": {
                "type": alert_type,
                "variant": "tonal",
                "text": "\n".join(lines),
            },
        }]

    def stop_service(self):
        """本插件仅使用 MoviePilot 公共服务调度器。"""
        pass

    def check_showtimes(self, reset_onlyonce: bool = False):
        """执行一次影院排片扫描。"""
        try:
            movie_names = self._parse_movie_names(self._movie_names)
            if not movie_names:
                raise ValueError("请至少填写一部监控电影")
            if not self._api_url:
                raise ValueError("未配置排片接口地址")
            if not self._cinema_id:
                raise ValueError("未配置影院 ID")
            if not self._city_id:
                raise ValueError("未配置城市 ID")

            payload = self._fetch_cinema_showtimes()

            if not isinstance(payload, dict):
                raise ValueError("接口返回不是 JSON 对象")

            if payload.get("code") not in (None, 0):
                raise ValueError(
                    "接口返回错误 code=%s, errMsg=%s"
                    % (payload.get("code"), payload.get("errMsg", ""))
                )

            data = payload.get("data") or {}
            if not isinstance(data, dict):
                raise ValueError("接口返回缺少 data 对象")

            actual_cinema_name = str(
                data.get("cinemaName") or self._cinema_name or self._cinema_id
            )
            movies = data.get("movies") or []
            if not isinstance(movies, list):
                raise ValueError("接口返回 data.movies 不是数组")

            movie_map = {}
            for movie in movies:
                if not isinstance(movie, dict):
                    continue
                name = str(movie.get("nm") or "").strip()
                if name:
                    movie_map[self._normalize_name(name)] = movie

            config_signature = self._config_signature(movie_names)
            state = self.get_data("movie_state") or {}

            # 监控关键配置发生变化时，按新配置重新建立基线。
            if state.get("config_signature") != config_signature:
                previous_movies = {}
                config_changed = True
            else:
                previous_movies = state.get("movies") or {}
                config_changed = False

            next_movies = dict(previous_movies)
            details = []
            found_count = 0
            missing_names = []
            total_new = 0
            total_removed = 0
            baseline_count = 0

            for configured_name in movie_names:
                key = self._normalize_name(configured_name)
                movie = movie_map.get(key)

                if not movie:
                    missing_names.append(configured_name)
                    details.append("未找到：%s" % configured_name)
                    # 临时未返回该电影时保留旧基线，不清空。
                    continue

                found_count += 1
                actual_movie_name = str(movie.get("nm") or configured_name)
                sessions = self._extract_sessions(movie)
                sessions = self._filter_sessions(sessions)

                current = {
                    session["key"]: session
                    for session in sessions
                }

                old_entry = previous_movies.get(key)
                old_sessions = (
                    old_entry.get("sessions", {})
                    if isinstance(old_entry, dict)
                    else {}
                )

                first_for_movie = not bool(old_entry) or config_changed

                if first_for_movie and self._baseline_first:
                    new_sessions = []
                    removed_sessions = []
                    baseline_count += len(current)
                    details.append(
                        "%s：建立基线 %d 场"
                        % (actual_movie_name, len(current))
                    )
                else:
                    new_keys = sorted(set(current) - set(old_sessions))
                    removed_keys = sorted(set(old_sessions) - set(current))

                    new_sessions = [
                        current[k] for k in new_keys
                    ]
                    removed_sessions = [
                        old_sessions[k]
                        for k in removed_keys
                        if self._should_notify_removed(old_sessions[k])
                    ]

                    total_new += len(new_sessions)
                    total_removed += len(removed_sessions)

                    if new_sessions:
                        details.append(
                            "%s：新增 %d 场"
                            % (actual_movie_name, len(new_sessions))
                        )
                    elif not removed_sessions:
                        details.append(
                            "%s：无新增，共 %d 场"
                            % (actual_movie_name, len(current))
                        )

                    if removed_sessions:
                        details.append(
                            "%s：取消/消失 %d 场"
                            % (actual_movie_name, len(removed_sessions))
                        )

                # 新电影若关闭“首次仅建基线”，第一次看到的全部当前场次都作为新增。
                if first_for_movie and not self._baseline_first:
                    new_sessions = list(current.values())
                    removed_sessions = []
                    total_new += len(new_sessions)
                    details.append(
                        "%s：首次发现 %d 场"
                        % (actual_movie_name, len(new_sessions))
                    )

                if self._notify_new and new_sessions:
                    self._notify_new_sessions(
                        actual_movie_name,
                        actual_cinema_name,
                        new_sessions,
                        old_sessions,
                    )

                if self._notify_removed and removed_sessions:
                    self._notify_removed_sessions(
                        actual_movie_name,
                        actual_cinema_name,
                        removed_sessions,
                    )

                next_movies[key] = {
                    "name": actual_movie_name,
                    "movie_id": movie.get("id"),
                    "show_count": movie.get("showCount"),
                    "sessions": current,
                    "updated_at": self._now(),
                }

            self.save_data("movie_state", {
                "config_signature": config_signature,
                "cinema_id": self._cinema_id,
                "cinema_name": actual_cinema_name,
                "movies": next_movies,
                "updated_at": self._now(),
            })

            if found_count == 0:
                status = "PARTIAL"
                message = "本次未找到任何监控电影"
            elif config_changed and self._baseline_first:
                status = "BASELINE"
                message = "已按当前配置建立新基线"
            elif total_new or total_removed:
                status = "OK"
                message = "新增 %d 场，取消/消失 %d 场" % (
                    total_new,
                    total_removed,
                )
            elif missing_names:
                status = "PARTIAL"
                message = "扫描完成，部分电影未找到"
            else:
                status = "OK"
                message = "扫描完成，无新增场次"

            self.save_data("last_result", {
                "checked_at": self._now(),
                "status": status,
                "cinema_name": actual_cinema_name,
                "message": message,
                "details": details,
            })

        except Exception as err:
            self.save_data("last_result", {
                "checked_at": self._now(),
                "status": "ERROR",
                "cinema_name": self._cinema_name or self._cinema_id,
                "message": str(err),
                "details": [],
            })
        finally:
            if reset_onlyonce:
                self._onlyonce = False
                self._save_config()

    def _fetch_cinema_showtimes(self) -> Dict[str, Any]:
        """一次请求获取整个影院当前开放的排片。"""
        params = {
            "cinemaId": self._cinema_id,
            "ci": self._city_id,
            "channelId": "4",
        }
        separator = "&" if "?" in self._api_url else "?"
        url = self._api_url + separator + urlencode(params)

        request = Request(
            url,
            headers={
                "User-Agent": "MoviePilot-CinemaTicketMonitor/0.3.0",
                "Accept": "application/json,text/plain,*/*",
            },
            method="GET",
        )

        with urlopen(request, timeout=self._timeout) as response:
            body = response.read()
            charset = response.headers.get_content_charset() or "utf-8"

        return json.loads(body.decode(charset, errors="replace"))

    def _extract_sessions(self, movie: Dict[str, Any]) -> List[Dict[str, Any]]:
        """从 movie.shows[].plist[] 提取具体场次。"""
        result = []

        for show in movie.get("shows") or []:
            if not isinstance(show, dict):
                continue

            show_date = str(show.get("showDate") or "")

            for item in show.get("plist") or []:
                if not isinstance(item, dict):
                    continue

                seq_no = str(item.get("seqNo") or "").strip()
                dt = str(item.get("dt") or show_date).strip()
                tm = str(item.get("tm") or "").strip()
                hall = str(item.get("th") or "").strip()
                show_type = str(item.get("tp") or "").strip()
                lang = str(item.get("lang") or "").strip()

                # seqNo 为首选唯一标识；极端情况下缺失则使用关键字段生成备用 ID。
                if seq_no:
                    key = seq_no
                else:
                    fallback = "|".join([
                        dt,
                        tm,
                        hall,
                        show_type,
                        lang,
                    ])
                    key = "fallback-" + hashlib.sha1(
                        fallback.encode("utf-8")
                    ).hexdigest()

                result.append({
                    "key": key,
                    "seqNo": seq_no,
                    "dt": dt,
                    "tm": tm,
                    "th": hall,
                    "tp": show_type,
                    "lang": lang,
                    "ticketStatus": item.get("ticketStatus"),
                    "vipPrice": str(item.get("vipPrice") or ""),
                })

        # 按唯一 key 去重
        unique = {}
        for session in result:
            unique[session["key"]] = session

        return list(unique.values())

    def _filter_sessions(
        self,
        sessions: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """按配置的放映类型过滤。"""
        filter_type = (self._show_type or "不限").strip().lower()

        if filter_type in ("", "不限"):
            return sessions

        result = []
        for session in sessions:
            text = (
                str(session.get("tp") or "")
                + " "
                + str(session.get("th") or "")
            ).lower()

            is_imax = "imax" in text
            is_dolby = "杜比" in text or "dolby" in text

            if filter_type == "imax" and is_imax:
                result.append(session)
            elif filter_type == "杜比" and is_dolby:
                result.append(session)
            elif filter_type == "普通" and not is_imax and not is_dolby:
                result.append(session)

        return result

    def _notify_new_sessions(
        self,
        movie_name: str,
        cinema_name: str,
        sessions: List[Dict[str, Any]],
        old_sessions: Dict[str, Dict[str, Any]],
    ):
        """按日期分组发送新增排片通知。"""
        sessions = sorted(
            sessions,
            key=lambda x: (
                x.get("dt", ""),
                x.get("tm", ""),
                x.get("th", ""),
            ),
        )

        old_dates = {
            str(item.get("dt") or "")
            for item in old_sessions.values()
        }

        grouped = {}
        for session in sessions:
            grouped.setdefault(
                session.get("dt") or "日期未知",
                []
            ).append(session)

        lines = ["影院：%s" % cinema_name]

        for date_key in sorted(grouped):
            if date_key not in old_dates:
                lines.append("")
                lines.append("🆕 新增排片日期：%s" % date_key)
            else:
                lines.append("")
                lines.append("日期：%s" % date_key)

            for session in grouped[date_key]:
                desc = self._session_line(session)
                lines.append(desc)

        lines.append("")
        lines.append("共新增 %d 场" % len(sessions))

        if self._buy_url:
            lines.append("购票：%s" % self._buy_url)

        self.post_message(
            title="🎬《%s》新增排片" % movie_name,
            text="\n".join(lines),
        )

    def _notify_removed_sessions(
        self,
        movie_name: str,
        cinema_name: str,
        sessions: List[Dict[str, Any]],
    ):
        """发送仍未开场但从接口中消失的场次提醒。"""
        sessions = sorted(
            sessions,
            key=lambda x: (
                x.get("dt", ""),
                x.get("tm", ""),
                x.get("th", ""),
            ),
        )

        lines = [
            "影院：%s" % cinema_name,
            "",
            "以下场次已从当前排片接口中消失：",
        ]

        for session in sessions:
            lines.append(self._session_line(session))

        lines.append("")
        lines.append("共 %d 场" % len(sessions))

        self.post_message(
            title="⚠️《%s》场次变化" % movie_name,
            text="\n".join(lines),
        )

    @staticmethod
    def _session_line(session: Dict[str, Any]) -> str:
        """格式化一条场次信息。"""
        time_text = str(session.get("tm") or "--:--")
        type_text = str(session.get("tp") or "").strip()
        hall_text = str(session.get("th") or "").strip()
        price = str(session.get("vipPrice") or "").strip()

        parts = [time_text]
        if type_text:
            parts.append(type_text)
        if hall_text:
            parts.append(hall_text)
        if price:
            parts.append("影城卡¥%s" % price)

        return "  " + " | ".join(parts)

    @staticmethod
    def _parse_movie_names(value: str) -> List[str]:
        """逗号、中文逗号、分号、换行均可分隔多部电影。"""
        if not value:
            return []

        names = re.split(r"[,，;；\n\r]+", value)
        result = []
        seen = set()

        for name in names:
            name = name.strip()
            if not name:
                continue
            normalized = CinemaTicketMonitor._normalize_name(name)
            if normalized in seen:
                continue
            seen.add(normalized)
            result.append(name)

        return result

    @staticmethod
    def _normalize_name(name: str) -> str:
        return re.sub(r"\s+", "", str(name or "")).lower()

    def _config_signature(self, movie_names: List[str]) -> str:
        """关键监控配置变化时自动重建基线。"""
        raw = json.dumps({
            "api_url": self._api_url,
            "city_id": self._city_id,
            "cinema_id": self._cinema_id,
            "movie_names": [
                self._normalize_name(x)
                for x in movie_names
            ],
            "show_type": self._show_type,
        }, ensure_ascii=False, sort_keys=True)

        return hashlib.sha256(
            raw.encode("utf-8")
        ).hexdigest()

    @staticmethod
    def _should_notify_removed(session: Dict[str, Any]) -> bool:
        """
        仅对仍未开场的场次发送“取消/消失”提醒，
        避免正常过期的历史场次被误报为取消。
        """
        dt = str(session.get("dt") or "").strip()
        tm = str(session.get("tm") or "").strip()

        if not dt:
            return False

        try:
            if tm:
                session_time = datetime.strptime(
                    dt + " " + tm,
                    "%Y-%m-%d %H:%M",
                )
            else:
                session_time = datetime.strptime(
                    dt,
                    "%Y-%m-%d",
                ) + timedelta(days=1)

            return session_time > datetime.now()
        except Exception:
            return False

    def _save_config(self):
        return self.update_config({
            "enabled": self._enabled,
            "notify_new": self._notify_new,
            "notify_removed": self._notify_removed,
            "baseline_first": self._baseline_first,
            "onlyonce": self._onlyonce,
            "test_notify": self._test_notify,
            "api_url": self._api_url,
            "city_id": self._city_id,
            "cinema_id": self._cinema_id,
            "cinema_name": self._cinema_name,
            "movie_names": self._movie_names,
            "show_type": self._show_type,
            "cron": self._cron,
            "timeout": self._timeout,
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
    def _text(
        model: str,
        label: str,
        placeholder: str,
        md: int
    ) -> dict:
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
    def _now() -> str:
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
