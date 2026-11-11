"""Which server is selected, and the per-server switch "This is a test server" (plan E1, S1-S3, Q9).

The choice is stored in the database (survives restarts). Until the settings screen has stored a choice
the ``server_url`` setting (environment or config file) is used, so scripted and test setups keep working.
Every server has its own profile: link, cache, counter and test switch are keyed by the server URL.
"""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlsplit

from dashboard.config import OFFICIAL_SERVER_URL, Settings, normalize_server_url
from dashboard.domain.errors import DashboardError, ErrorCode
from dashboard.repository.settings_store import SettingsRepository

OFFICIAL = "official"
ALTERNATIVE = "alternative"
PROTOCOLS = ("http", "https")


@dataclass(frozen=True)
class ServerSelection:
    mode: str  # "official" or "alternative"
    protocol: str
    address: str
    port: int | None
    url: str

    def to_json(self) -> dict[str, object]:
        return {
            "mode": self.mode,
            "protocol": self.protocol,
            "address": self.address,
            "port": self.port,
            "url": self.url,
        }


def _from_url(url: str) -> ServerSelection:
    if url == OFFICIAL_SERVER_URL:
        return ServerSelection(OFFICIAL, "https", "api.timelimit.io", None, url)
    parts = urlsplit(url)
    return ServerSelection(
        ALTERNATIVE, parts.scheme, parts.hostname or "", parts.port, url
    )


class ServerProfiles:
    def __init__(self, store: SettingsRepository, settings: Settings) -> None:
        self._store = store
        self._settings = settings

    def selection(self) -> ServerSelection | None:
        """The active server; None while none is chosen (first start)."""
        mode = self._store.get("server.mode")
        if mode == OFFICIAL:
            return _from_url(OFFICIAL_SERVER_URL)
        if mode == ALTERNATIVE:
            url = self._store.get("server.url", "") or ""
            return _from_url(url) if url else None
        return (
            _from_url(self._settings.server_url) if self._settings.server_url else None
        )

    def url(self) -> str:
        chosen = self.selection()
        return chosen.url if chosen else ""

    def select(
        self,
        mode: str,
        protocol: str = "http",
        address: str = "",
        port: int | None = None,
    ) -> ServerSelection:
        if mode == OFFICIAL:
            self._store.set("server.mode", OFFICIAL)
            return _from_url(OFFICIAL_SERVER_URL)
        if mode != ALTERNATIVE:
            raise DashboardError(
                ErrorCode.INVALID_INPUT, "Choose the official or an alternative server."
            )
        address = (address or "").strip()
        if protocol not in PROTOCOLS:
            raise DashboardError(
                ErrorCode.INVALID_INPUT, "The protocol must be http or https."
            )
        if not address or any(c in address for c in "/@?# \t") or "://" in address:
            raise DashboardError(
                ErrorCode.INVALID_INPUT,
                "Enter only the address of the server, for example 192.168.1.5.",
            )
        if port is not None and not (isinstance(port, int) and 1 <= port <= 65535):
            raise DashboardError(
                ErrorCode.INVALID_INPUT, "The port must be a number from 1 to 65535."
            )
        raw = f"{protocol}://{address}" + (f":{port}" if port else "")
        try:
            url = normalize_server_url(raw)
        except ValueError as error:
            raise DashboardError(ErrorCode.INVALID_INPUT, str(error)) from None
        self._store.set("server.mode", ALTERNATIVE)
        self._store.set("server.url", url)
        return _from_url(url)

    # -- the test-server switch (per server) -----------------------------------------------------------------------
    def test_server(self, url: str | None = None) -> bool:
        url = self.url() if url is None else url
        stored = self._store.get(f"test_server:{url}")
        if stored is None:
            return self._settings.test_server
        return stored == "1"

    def set_test_server(self, enabled: bool, url: str | None = None) -> None:
        url = self.url() if url is None else url
        if not url:
            raise DashboardError(ErrorCode.INVALID_INPUT, "Choose a server first.")
        self._store.set(f"test_server:{url}", "1" if enabled else "0")
