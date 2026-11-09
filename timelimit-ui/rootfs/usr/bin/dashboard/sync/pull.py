"""Pull with version exchange (plan B3, FR-201, FR-202, TR-103).

One pull sends every version the cache holds (``CacheRepository.client_status``), the server answers with
only what differs, and :func:`apply_server_status` writes every part of the answer to the cache in one
transaction. A full resync (``shouldDoFullSync``, FR-202) first forgets all versions and sets a notice
flag the UI shows once.

Tasks are not stored in v1 (decision R2). Finding: without a tasks version the server sends the task
lists of every category on every pull (client level 3 and up); they are empty here and ignored.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from dashboard.client.server import TimeLimitClient
from dashboard.domain.secret import Secret
from dashboard.repository.cache import CacheRepository, Scope
from dashboard.repository.db import Database

log = logging.getLogger(__name__)

NOTICE_FULL_RESYNC = "full_resync_notice"


@dataclass
class PullResult:
    """What one pull changed; the SSE hub (B6) and the UI use ``changed`` to refresh the right parts."""

    scope: Scope
    changed: set[str] = field(default_factory=set)
    api_level: int = 0
    full_version_until: int = 0
    full_resync: bool = False


class InconsistentServerAnswer(Exception):
    """The answer mentions a category whose base data never arrived; a full resync repairs that."""


def apply_server_status(
    cache: CacheRepository, scope: Scope, status: dict[str, Any]
) -> set[str]:
    """Write every part of a ``ServerDataStatus`` to the cache. Returns the names of the parts that arrived.

    Order matters: categories exist before their apps, rules and used times are stored. Applying the same
    answer twice gives the same cache (the ``set_*`` methods replace).
    """
    changed: set[str] = set()
    if "devices" in status:
        cache.set_devices(
            scope, status["devices"]["data"], status["devices"]["version"]
        )
        changed.add("devices")
    if "users" in status:
        cache.set_users(scope, status["users"]["data"], status["users"]["version"])
        changed.add("users")
    if status.get("rmCategories"):
        cache.remove_categories(scope, status["rmCategories"])
        changed.add("categories")
    if status.get("categoryBase"):
        cache.set_category_base(scope, status["categoryBase"])
        changed.add("categories")
    try:
        for entry in status.get("categoryApp", []):
            cache.set_category_apps(
                scope, entry["categoryId"], entry["apps"], entry["version"]
            )
            changed.add("category_apps")
        for entry in status.get("rules", []):
            cache.set_category_rules(
                scope, entry["categoryId"], entry["rules"], entry["version"]
            )
            changed.add("rules")
        for entry in status.get("usedTimes", []):
            cache.set_category_used_times(
                scope, entry["categoryId"], entry["times"], entry["version"]
            )
            changed.add("used_time")
    except LookupError as error:
        raise InconsistentServerAnswer(str(error)) from error
    for entry in status.get("apps", []):
        cache.set_installed_apps(
            scope, entry["deviceId"], entry["apps"], entry["version"]
        )
        changed.add("installed_apps")
    cache.set_meta(scope, "api_level", str(status["apiLevel"]))
    cache.set_meta(scope, "full_version_until", str(status["fullVersion"]))
    return changed


class Puller:
    def __init__(
        self, client: TimeLimitClient, cache: CacheRepository, db: Database
    ) -> None:
        self._client = client
        self._cache = cache
        self._db = db

    def pull(
        self, profile_key: str, device_token: Secret, family_id: str
    ) -> PullResult:
        """One pull. Raises ``DashboardError`` (unreachable, timeout, invalid session) from the client."""
        scope = self._cache.activate(profile_key, family_id)
        try:
            return self._pull_once(scope, device_token, full_resync=False)
        except InconsistentServerAnswer:
            log.warning("pull answer was inconsistent; doing a full resync")
            return self.full_resync(profile_key, device_token, family_id)

    def full_resync(
        self, profile_key: str, device_token: Secret, family_id: str
    ) -> PullResult:
        """Forget all versions, pull everything once and leave a notice (FR-202)."""
        scope = self._cache.activate(profile_key, family_id)
        self._cache.forget_versions(scope)
        result = self._pull_once(scope, device_token, full_resync=True)
        self._cache.set_meta(scope, NOTICE_FULL_RESYNC, "1")
        return result

    def take_resync_notice(self, scope: Scope) -> bool:
        """True once after a full resync, then False until the next one."""
        if self._cache.meta(scope, NOTICE_FULL_RESYNC) != "1":
            return False
        self._cache.set_meta(scope, NOTICE_FULL_RESYNC, "")
        return True

    def _pull_once(
        self, scope: Scope, device_token: Secret, *, full_resync: bool
    ) -> PullResult:
        status = self._cache.client_status(scope)
        answer = self._client.pull_status(device_token, status)
        with self._db.transaction():
            changed = apply_server_status(self._cache, scope, answer)
        return PullResult(
            scope=scope,
            changed=changed,
            api_level=int(answer["apiLevel"]),
            full_version_until=int(answer["fullVersion"]),
            full_resync=full_resync,
        )
