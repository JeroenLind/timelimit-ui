"""What the settings screen shows and changes, the notices on every page and the debug export (plan E1).

FR-102: an ``apiLevel`` outside the tested range only gives a notice, it never blocks.
TR-402: the debug export is the log file as written (masked at info level and higher, unmasked only at
debug level) plus the settings; the device token is never added by this module.
"""

from __future__ import annotations

import json
from collections import deque
from dataclasses import fields as dataclass_fields
from typing import Any

from dashboard.config import Settings
from dashboard.domain.clock import Clock
from dashboard.services.link import SESSION_INVALID, LinkService
from dashboard.services.profiles import ServerProfiles
from dashboard.sync.backend import Backend

TESTED_API_LEVELS = (7, 9)  # Q7
DASHBOARD_VERSION = "1.0.0"
LOG_TAIL_LINES = 500
SHOWN_TIMINGS = (
    "health_timeout",
    "health_interval",
    "backoff_initial",
    "backoff_max",
    "sync_target",
    "poll_interval",
    "retry_delay",
    "retry_count",
    "browser_timeout",
    "server_timeout",
)


class SettingsService:
    def __init__(
        self,
        settings: Settings,
        backend: Backend,
        profiles: ServerProfiles,
        link: LinkService,
        clock: Clock,
    ) -> None:
        self._settings = settings
        self._backend = backend
        self._profiles = profiles
        self._link = link
        self._clock = clock

    # -- reading ---------------------------------------------------------------------------------------------------------
    def _meta(self, name: str) -> str:
        scope = self._backend.scope(self._profiles.url())
        return self._backend.cache.meta(scope, name) if scope else ""

    def api_level(self) -> int | None:
        raw = self._meta("api_level")
        return int(raw) if raw.isdigit() else None

    def view(self) -> dict[str, Any]:
        selection = self._profiles.selection()
        url = self._profiles.url()
        last_sync = self._meta("last_sync_ms")
        level = self.api_level()
        return {
            "server": {
                **(selection.to_json() if selection else {"mode": "none", "url": ""}),
                "test_server": self._profiles.test_server() if url else False,
            },
            "link": self._link.view(),
            "dashboard_version": DASHBOARD_VERSION,
            "api_level": level,
            "tested_api_levels": list(TESTED_API_LEVELS),
            "version_warning": level is not None and level not in TESTED_API_LEVELS,
            "last_sync": int(last_sync) if last_sync.isdigit() else None,
            "live": self._backend.live_state(url) if url else None,
            "timings": {k: getattr(self._settings, k) for k in SHOWN_TIMINGS},
            "log_level": self._settings.log_level,
        }

    def notices(self) -> list[dict[str, Any]]:
        """Short messages for every page (a banner each); never blocking."""
        found: list[dict[str, Any]] = []
        if self._link.state() == SESSION_INVALID:
            found.append({"code": "SESSION_INVALID"})
        level = self.api_level()
        if level is not None and level not in TESTED_API_LEVELS:
            found.append({"code": "VERSION_UNTESTED", "api_level": level})
        return found

    # -- changing --------------------------------------------------------------------------------------------------------
    def select_server(
        self, mode: str, protocol: str, address: str, port: int | None
    ) -> None:
        before = self._profiles.url()
        self._profiles.select(mode, protocol, address, port)
        if self._profiles.url() != before:
            self._link.reset_login()
            self._backend.start_live(self._profiles.url())

    def set_test_server(self, enabled: bool) -> None:
        self._profiles.set_test_server(enabled)

    # -- the debug export ----------------------------------------------------------------------------------------
    def debug_export(self) -> str:
        view = self.view()
        view["link"] = {k: v for k, v in view["link"].items() if k != "login_mail"}
        try:
            with self._settings.log_file.open(
                encoding="utf-8", errors="replace"
            ) as handle:
                tail = list(deque(handle, maxlen=LOG_TAIL_LINES))
        except OSError:
            tail = []
        header = {
            "exported_at": self._clock.now().isoformat(),
            "log_level": self._settings.log_level,
            "unmasked": self._settings.log_level == "DEBUG",
            "settings": view,
            "defaults": {
                f.name: str(getattr(self._settings, f.name))
                for f in dataclass_fields(self._settings)
                if f.name not in {"data_dir"}
            },
        }
        return json.dumps(header, indent=2, ensure_ascii=False) + "\n\n" + "".join(tail)
