"""The one way a user change reaches the server (plan E3; used by every later change feature).

A change is: refuse while the server is down (FR-1001), build the actions elsewhere (domain), push them
through the sync worker (one at a time, never repeated by the worker because the server may already
have applied them), and tell the browsers to read the cache again. Rejected actions are rolled back by
the pusher (full resync) and arrive here as ``ACTION_NOT_CONFIRMED``.
"""

from __future__ import annotations

from typing import Any

from dashboard.domain.errors import DashboardError, ErrorCode
from dashboard.services.connection import ConnectionService
from dashboard.services.profiles import ServerProfiles
from dashboard.sync.backend import Backend
from dashboard.sync.push import PushResult


class ChangeService:
    def __init__(
        self, backend: Backend, profiles: ServerProfiles, connection: ConnectionService
    ) -> None:
        self._backend = backend
        self._profiles = profiles
        self._connection = connection

    def push(
        self, actions: list[dict[str, Any]], *, second_hash: str | None = None
    ) -> PushResult:
        self._connection.require_online()
        url = self._profiles.url()
        parent = self._backend.linker(url).dashboard_parent_id() if url else None
        if parent is None:
            raise DashboardError(
                ErrorCode.NOT_LINKED, "This dashboard is not linked to a family yet."
            )
        pusher = self._backend.pusher(url)
        timeout = max(30.0, self._backend.settings.server_timeout * 10)
        parts: list[str] = []
        try:
            result = self._backend.worker.run(
                lambda: pusher.push(url, parent, actions, second_hash=second_hash),
                timeout=timeout,
            )
            parts = sorted(result.pull.changed)
            return result
        finally:
            # also after a rejected change: the rollback replaced the cache
            self._backend.hub.publish({"type": "changed", "parts": parts})
