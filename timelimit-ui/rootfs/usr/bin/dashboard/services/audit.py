"""The audit log of changes made through the dashboard (plan E12, FR-1100, FR-1101, Q12).

Every change goes through ``ChangeService.push``, which records one entry per action here: the action type, the
child and category it concerns, the result and the time. Entries without a child (password changes, settings,
test section) are shown in Settings, the others in the tab "Changes" of the child. Entries older than 30 days
are removed whenever a new one is written (and whenever the log is read). Nothing secret is stored: only ids,
titles and names, never passwords, hashes or integrity values.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from dashboard.domain.clock import Clock
from dashboard.domain.errors import DashboardError, ErrorCode
from dashboard.repository.audit import RETENTION_DAYS
from dashboard.repository.cache import Scope
from dashboard.services.profiles import ServerProfiles
from dashboard.sync.backend import Backend

CONFIRMED = "confirmed"
NOT_CONFIRMED = "not_confirmed"
FAILED = "failed"
_SAFE_DETAIL_KEYS = ("title", "name", "userType", "ruleId", "childId")


class AuditService:
    def __init__(
        self, backend: Backend, profiles: ServerProfiles, clock: Clock
    ) -> None:
        self._backend = backend
        self._profiles = profiles
        self._clock = clock

    def _now_ms(self) -> int:
        return int(self._clock.now().timestamp() * 1000)

    def purge(self) -> int:
        cutoff = self._now_ms() - int(
            timedelta(days=RETENTION_DAYS).total_seconds() * 1000
        )
        return self._backend.audit.purge_older_than(cutoff)

    # -- writing ----------------------------------------------------------------------------------------------------
    def record(
        self,
        action: str,
        *,
        child_id: str | None = None,
        category_id: str | None = None,
        detail: dict[str, Any] | None = None,
    ) -> None:
        url = self._profiles.url()
        if not url:
            return
        self._backend.audit.append(
            url,
            at=self._now_ms(),
            action=action,
            child_id=child_id,
            category_id=category_id,
            detail=detail,
        )
        self.purge()

    def describe(self, actions: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """For each action: type, child, category and a few safe details, read from the cache *before* the push."""
        scope = self._scope_or_none()
        found = []
        for original in actions:
            nested = original.get("rule")
            action = {**original, **nested} if isinstance(nested, dict) else original
            child_id, category_id = self._owner(scope, action)
            detail = {
                k: action[k]
                for k in _SAFE_DETAIL_KEYS
                if isinstance(action.get(k), (str, int))
            }
            found.append(
                {
                    "action": str(original.get("type", "")),
                    "child_id": child_id,
                    "category_id": category_id,
                    "detail": detail,
                }
            )
        return found

    def record_all(
        self, described: list[dict[str, Any]], result: str, code: str | None = None
    ) -> None:
        for item in described:
            detail = {**item["detail"], "result": result}
            if code:
                detail["code"] = code
            self.record(
                item["action"],
                child_id=item["child_id"],
                category_id=item["category_id"],
                detail=detail,
            )

    def _owner(
        self, scope: Scope | None, action: dict[str, Any]
    ) -> tuple[str | None, str | None]:
        if scope is None:
            return None, None
        cache = self._backend.cache
        category_id = action.get("categoryId")
        rule_id = action.get("ruleId")
        if isinstance(rule_id, str) and not isinstance(category_id, str):
            for category in cache.categories(scope):
                if any(
                    r.data.get("ruleId") == rule_id
                    for r in cache.rules(scope, str(category.data["categoryId"]))
                ):
                    category_id = str(category.data["categoryId"])
                    break
        child_id = action.get("childId")
        if isinstance(child_id, str):
            return child_id, category_id if isinstance(category_id, str) else None
        if isinstance(category_id, str):
            owner = next(
                (
                    str(c.data.get("childId"))
                    for c in cache.categories(scope)
                    if c.data.get("categoryId") == category_id
                ),
                None,
            )
            return owner, category_id
        user_id = action.get("userId")
        if isinstance(user_id, str):
            if action.get("userType") == "child":
                return user_id, None
            user = next(
                (u for u in cache.users(scope) if u.data.get("id") == user_id), None
            )
            if user is not None and user.data.get("type") == "child":
                return user_id, None
        return None, None

    # -- reading ----------------------------------------------------------------------------------------------------
    def entries(self, child_id: str | None) -> dict[str, Any]:
        """Newest first. With a child: that child's entries; without: the entries that belong to no child."""
        url = self._profiles.url()
        if not url:
            raise DashboardError(
                ErrorCode.NOT_LINKED, "This dashboard is not linked to a family yet."
            )
        self.purge()
        scope = self._scope_or_none()
        titles = (
            {
                str(c.data["categoryId"]): str(c.data.get("title", ""))
                for c in self._backend.cache.categories(scope)
            }
            if scope
            else {}
        )
        rows = self._backend.audit.entries(
            url, child_id=child_id, without_child=child_id is None
        )
        return {
            "status": "ok",
            "entries": [
                {
                    "id": e.id,
                    "at": e.at,
                    "action": e.action,
                    "result": str(e.detail.get("result", CONFIRMED)),
                    "category_id": e.category_id,
                    "category_title": titles.get(e.category_id or "", ""),
                    "detail": {k: v for k, v in e.detail.items() if k != "result"},
                }
                for e in rows
            ],
        }

    def _scope_or_none(self) -> Scope | None:
        url = self._profiles.url()
        return self._backend.scope(url) if url else None
