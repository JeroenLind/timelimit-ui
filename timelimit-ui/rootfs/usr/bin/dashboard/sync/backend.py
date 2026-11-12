"""Everything that outlives a request: database, repositories, sync worker and live sync (plan E1).

One :class:`Backend` per app. It knows nothing about which server is selected; callers pass the server
URL (the profile key is that URL). Live sync runs for at most one profile at a time, the active one.
"""

from __future__ import annotations

from dashboard.client.server import TimeLimitClient
from dashboard.config import Settings
from dashboard.domain.clock import Clock
from dashboard.logs import fields, get_logger
from dashboard.repository.cache import CacheRepository, Scope
from dashboard.repository.db import Database
from dashboard.repository.links import LinkRepository
from dashboard.repository.session_file import SessionFile
from dashboard.repository.settings_store import SettingsRepository
from dashboard.sync.hub import EventHub
from dashboard.sync.linking import Linker
from dashboard.sync.live import STATE_OK, LiveSync
from dashboard.sync.pull import Puller, PullResult
from dashboard.sync.push import Pusher
from dashboard.sync.worker import SyncWorker

log = get_logger("backend")


class Backend:
    def __init__(self, settings: Settings, hub: EventHub, clock: Clock) -> None:
        self.settings = settings
        self.clock = clock
        self.hub = hub
        self.db = Database(settings.data_dir / "dashboard.db")
        self.session_file = SessionFile(settings.data_dir / "session.json")
        self.links = LinkRepository(self.db, self.session_file)
        self.cache = CacheRepository(self.db)
        self.store = SettingsRepository(self.db)
        self.worker = SyncWorker(
            retries=settings.retry_count, retry_delay=settings.retry_delay
        )
        self.worker.start()
        self._live: LiveSync | None = None
        self._live_url = ""

    # -- building blocks for one server ----------------------------------------------------------------------------
    def client(self, url: str, timeout: float | None = None) -> TimeLimitClient:
        return TimeLimitClient(url, timeout=timeout or self.settings.server_timeout)

    def puller(self, url: str) -> Puller:
        return Puller(self.client(url), self.cache, self.db, self.clock)

    def pusher(self, url: str) -> Pusher:
        return Pusher(self.client(url), self.links, self.puller(url))

    def linker(self, url: str) -> Linker:
        return Linker(
            client=self.client(url),
            links=self.links,
            cache=self.cache,
            db=self.db,
            profile_key=url,
            clock=self.clock,
        )

    def scope(self, url: str) -> Scope | None:
        link = self.links.get(url)
        return Scope(url, link.family_id) if link else None

    # -- live sync -------------------------------------------------------------------------------------------------------
    def start_live(self, url: str) -> None:
        """(Re)start live sync for ``url`` when it has a link; stops the one of another server first."""
        self.stop_live()
        link = self.links.get(url) if url else None
        if link is None:
            return
        puller = self.puller(url)

        def pull() -> PullResult:
            return puller.pull(url, link.device_token, link.family_id)

        live = LiveSync(
            server_url=url,
            device_token=link.device_token,
            pull=pull,
            worker=self.worker,
            hub=self.hub,
            poll_interval=self.settings.poll_interval,
            backoff_initial=self.settings.backoff_initial,
            backoff_max=self.settings.backoff_max,
        )
        live.start()
        self._live, self._live_url = live, url
        log.info("live sync started", extra=fields(server=url))

    def stop_live(self, timeout: float = 0.5) -> None:
        """Stop live sync. A request must not wait for a socket that is still connecting: the threads see
        the stop flag and end by themselves (they do nothing once it is set)."""
        live, self._live, self._live_url = self._live, None, ""
        if live is not None:
            live.stop(timeout)

    def live_state(self, url: str) -> dict[str, object]:
        live = self._live if self._live_url == url else None
        return {
            "running": live is not None,
            "socket": bool(live and live.socket_connected),
            "state": live.state if live else STATE_OK,
        }

    def close(self) -> None:
        self.stop_live(timeout=5.0)
        self.worker.stop()
        self.db.close()
