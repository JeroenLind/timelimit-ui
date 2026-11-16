"""Used time per category: today against the limit, and a history per day (plan E9, FR-600, FR-601).

The server reports used time per category per day. The dashboard copies those totals into its own table on
every pull (``Cache.record_own_used_time``), so the history grows to 30 days from the first use (Q10) and is lost
on a cache reset (Q10b). Days are counted from the epoch in the child's time zone, as the server does.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from dashboard.domain.bitmask import day_of_epoch
from dashboard.domain.clock import Clock
from dashboard.domain.errors import DashboardError, ErrorCode
from dashboard.repository.cache import Scope
from dashboard.services.children import _zone
from dashboard.services.profiles import ServerProfiles
from dashboard.sync.backend import Backend

HISTORY_DAYS = 30
EPOCH = date(1970, 1, 1)


class UsageService:
    def __init__(
        self, backend: Backend, profiles: ServerProfiles, clock: Clock
    ) -> None:
        self._backend = backend
        self._profiles = profiles
        self._clock = clock

    def usage(self, child_id: str) -> dict[str, Any]:
        scope = self._scope()
        cache = self._backend.cache
        child = next(
            (
                u
                for u in cache.users(scope)
                if u.data.get("id") == child_id
                and u.data.get("type") == "child"
                and u.on_server
            ),
            None,
        )
        if child is None:
            raise DashboardError(ErrorCode.NOT_FOUND, "This child is not known.")
        zone = _zone(str(child.data.get("timeZone") or "UTC"))
        today = day_of_epoch(self._clock.now(), zone)
        weekday = (EPOCH + timedelta(days=today)).weekday()
        days = list(range(today - HISTORY_DAYS + 1, today + 1))
        categories: list[dict[str, Any]] = []
        for item in cache.categories(scope, child_id):
            if not item.on_server:
                continue
            cid = str(item.data["categoryId"])
            totals = {
                **cache.own_used_time(scope, cid),
                **cache.used_time_by_day(scope, cid),
            }
            extra_day = int(item.data.get("extraTimeDay", -1))
            categories.append(
                {
                    "id": cid,
                    "title": str(item.data.get("title", "")),
                    "used_today_ms": totals.get(today, 0),
                    "limit_today_ms": _limit_today_ms(cache.rules(scope, cid), weekday),
                    "extra_time_ms": int(item.data.get("extraTime", 0))
                    if extra_day in (-1, today)
                    else 0,
                    "history": [
                        {
                            "date": (EPOCH + timedelta(days=d)).isoformat(),
                            "used_ms": totals.get(d, 0),
                        }
                        for d in days
                    ],
                }
            )
        categories.sort(key=lambda c: c["title"].casefold())
        return {
            "status": "ok",
            "today": (EPOCH + timedelta(days=today)).isoformat(),
            "categories": categories,
        }

    def _scope(self) -> Scope:
        scope = self._backend.scope(self._profiles.url())
        if scope is None:
            raise DashboardError(
                ErrorCode.NOT_LINKED, "This dashboard is not linked to a family yet."
            )
        return scope


def _limit_today_ms(rules: list[Any], weekday: int) -> int | None:
    """The strictest daily limit among the rules that apply on this weekday (windows and sessions are not counted)."""
    limits = [
        int(r.data.get("maxTime", 0))
        for r in rules
        if r.on_server and int(r.data.get("dayMask", 0)) >> weekday & 1
    ]
    return min(limits) if limits else None
