"""Is the TimeLimit server reachable? (FR-1000..1003, plan A7)

The browser asks the backend, the backend probes the server with the short health timeout. The probe
never raises: an unreachable server is an ordinary state the UI shows as a banner.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

from dashboard.client.server import TimeLimitClient
from dashboard.config import Settings
from dashboard.domain.errors import DashboardError, ErrorCode
from dashboard.logs import fields, get_logger
from dashboard.services.profiles import ServerProfiles

log = get_logger("connection")

NOT_CONFIGURED = "not_configured"
UP = "up"
DOWN = "down"
SLOW_PROBE_SECONDS = (
    1.0  # an answer slower than this is logged although the server is "up"
)


@dataclass(frozen=True)
class ServerStatus:
    state: str  # "up", "down" or "not_configured"
    code: str | None = None  # the error code when the state is "down"

    def to_json(self) -> dict[str, str | None]:
        return {"state": self.state, "code": self.code}


class ConnectionService:
    def __init__(
        self, settings: Settings, profiles: ServerProfiles | None = None
    ) -> None:
        self._settings = settings
        self._profiles = profiles
        self._clients: dict[str, TimeLimitClient] = {}
        self._last: str | None = None
        self._failures = 0  # consecutive failed probes
        self._down_since: float | None = None

    def _client_for_active_server(self) -> TimeLimitClient | None:
        url = (
            self._profiles.url()
            if self._profiles is not None
            else self._settings.server_url
        )
        if not url:
            return None
        if url not in self._clients:
            self._clients[url] = TimeLimitClient(
                url, timeout=self._settings.health_timeout
            )
        return self._clients[url]

    def status(self) -> ServerStatus:
        """Probe the server now. Logs only when the state changes."""
        client = self._client_for_active_server()
        if client is None:
            return ServerStatus(NOT_CONFIGURED)
        started = time.monotonic()
        try:
            client.server_time()
            result = ServerStatus(UP)
        except DashboardError as error:
            result = ServerStatus(DOWN, error.code.value)
        elapsed = time.monotonic() - started
        self._track(result, elapsed)
        if result.state != self._last:
            log.info(
                "server state changed",
                extra=fields(state=result.state, code=result.code),
            )
            self._last = result.state
        return result

    def _track(self, result: ServerStatus, elapsed: float) -> None:
        """Extra diagnostics: failure streaks, recovery time and slow answers (all rate-limited by state)."""
        now = time.monotonic()
        if result.state == DOWN:
            self._failures += 1
            if self._down_since is None:
                self._down_since = now
            if self._failures in (1, 2, 5) or self._failures % 20 == 0:
                log.warning(
                    "probe failed",
                    extra=fields(
                        code=result.code,
                        consecutive=self._failures,
                        elapsed_ms=round(elapsed * 1000),
                    ),
                )
            return
        if self._failures:
            log.info(
                "server reachable again",
                extra=fields(
                    failed_probes=self._failures,
                    down_s=round(now - (self._down_since or now), 1),
                ),
            )
        self._failures = 0
        self._down_since = None
        if result.state == UP and elapsed > SLOW_PROBE_SECONDS:
            log.warning("slow probe", extra=fields(elapsed_ms=round(elapsed * 1000)))

    def require_online(self) -> None:
        """Gate for every change: refuse with READ_ONLY_OFFLINE while the server is down (FR-1001).

        An unconfigured server is not "offline"; a missing link is reported as NOT_LINKED elsewhere.
        """
        status = self.status()
        if status.state == DOWN:
            raise DashboardError(
                ErrorCode.READ_ONLY_OFFLINE,
                "The server cannot be reached; changes are disabled until it is back.",
            )
