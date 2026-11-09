"""Push parent actions, confirm them, roll back what the server did not accept (plan B4).

Rules (FR-200, FR-203, FR-204, FR-209, TR-304):

* Actions are built by :mod:`dashboard.domain.actions`; this module only numbers, sends and checks.
* Sequence numbers are reserved from the persistent counter *just before each request*. A reserved number
  is consumed even when the request fails: the server may have seen it, and a reused number is ignored
  silently. Actions that were never sent (a later batch after a failure) burn no numbers.
* At most 25 actions per request (the Android app does the same; the server accepts 50).
* The server answers 200 even for an action it dropped and only sets ``shouldDoFullSync``. An action is
  **confirmed only when no batch asked for a full sync**. Otherwise the cache is replaced by a full resync
  (that is the rollback) and ``ACTION_NOT_CONFIRMED`` is raised.
* After a confirmed push the dashboard pulls at once, so the cache shows the result.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from dashboard.client.server import TimeLimitClient
from dashboard.domain.actions import MAX_ACTIONS_PER_REQUEST, parent_item
from dashboard.domain.errors import DashboardError, ErrorCode
from dashboard.repository.links import LinkRepository
from dashboard.sync.pull import Puller, PullResult

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class PushResult:
    sent: int
    batches: int
    first_sequence: int
    pull: PullResult


class Pusher:
    def __init__(
        self, client: TimeLimitClient, links: LinkRepository, puller: Puller
    ) -> None:
        self._client = client
        self._links = links
        self._puller = puller

    def push(
        self,
        profile_key: str,
        parent_user_id: str,
        actions: list[dict[str, Any]],
        *,
        second_hash: str | None = None,
    ) -> PushResult:
        """Send ``actions`` in order; raises ``ACTION_NOT_CONFIRMED`` when the server dropped any.

        ``second_hash`` is only given for the few actions that need the password method (FR-901).
        Network errors surface as ``SERVER_UNREACHABLE`` / ``SERVER_TIMEOUT`` from the client.
        """
        if not actions:
            raise ValueError("nothing to push")
        link = self._links.get(profile_key)
        if link is None:
            raise DashboardError(
                ErrorCode.NOT_LINKED, "This dashboard is not linked to a family yet."
            )
        first_sequence = -1
        asked_full_sync = False
        batches = 0
        for start in range(0, len(actions), MAX_ACTIONS_PER_REQUEST):
            batch = actions[start : start + MAX_ACTIONS_PER_REQUEST]
            items = []
            for action in batch:
                number = self._links.reserve_sequence(profile_key)
                first_sequence = number if first_sequence < 0 else first_sequence
                items.append(
                    parent_item(
                        action,
                        number,
                        parent_user_id,
                        own_device_id=link.own_device_id,
                        second_hash=second_hash,
                    )
                )
            batches += 1
            if self._client.push_actions(link.device_token, items):
                asked_full_sync = True
        if asked_full_sync:
            log.warning(
                "server asked for a full sync after a push; rolling back by resync"
            )
            self._puller.full_resync(profile_key, link.device_token, link.family_id)
            raise DashboardError(
                ErrorCode.ACTION_NOT_CONFIRMED,
                "The server did not accept the change. The data was reloaded from the server.",
            )
        pulled = self._puller.pull(profile_key, link.device_token, link.family_id)
        return PushResult(
            sent=len(actions),
            batches=batches,
            first_sequence=first_sequence,
            pull=pulled,
        )
