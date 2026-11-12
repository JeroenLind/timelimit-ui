"""Children overview and child detail, read from the cache only (plan E2, FR-700..702).

"Today" is the child's own date: the day of the epoch in the child's time zone (the server counts used
time and extra time per such day). Used time of a child is the sum over the categories without a parent
category, because the app reports the time of an app to its category and to every parent category too.

The server sends no "last connection" of a device to parents, so a device shows model, name, current
user and the moment it was added.
"""

from __future__ import annotations

from datetime import tzinfo
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from dashboard.domain.bitmask import day_of_epoch
from dashboard.domain.clock import Clock
from dashboard.domain.errors import DashboardError, ErrorCode
from dashboard.repository.cache import CachedItem, Scope
from dashboard.services.profiles import ServerProfiles
from dashboard.sync.backend import Backend

STATUS_OK = "ok"
STATUS_TEMP_BLOCKED = "temp_blocked"
STATUS_LIMITS_DISABLED = "limits_disabled"


def _zone(name: str) -> tzinfo:
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError, OSError):
        return ZoneInfo("UTC")


class ChildrenService:
    def __init__(
        self, backend: Backend, profiles: ServerProfiles, clock: Clock
    ) -> None:
        self._backend = backend
        self._profiles = profiles
        self._clock = clock

    def _scope(self) -> Scope | None:
        return self._backend.scope(self._profiles.url())

    # -- helpers -------------------------------------------------------------------------------------------------
    def _children(self, scope: Scope) -> list[CachedItem]:
        users = self._backend.cache.users(scope)
        return sorted(
            (u for u in users if u.data.get("type") == "child"),
            key=lambda u: str(u.data.get("name", "")).lower(),
        )

    def _category_view(
        self, scope: Scope, item: CachedItem, today: int, now_ms: int
    ) -> dict[str, Any]:
        data = item.data
        cid = str(data["categoryId"])
        cache = self._backend.cache
        extra_day = int(data.get("extraTimeDay", -1))
        extra = int(data.get("extraTime", 0)) if extra_day in (-1, today) else 0
        block_end = int(data.get("tempBlockTime", 0))
        blocked = bool(data.get("tempBlocked")) and (
            block_end == 0 or block_end > now_ms
        )
        return {
            "id": cid,
            "title": data.get("title", ""),
            "parent_id": data.get("parentCategoryId", "") or "",
            "sort": int(data.get("sort", 0)),
            "on_server": item.on_server,
            "used_today_ms": cache.used_time_by_day(scope, cid).get(today, 0),
            "extra_time_ms": extra,
            "temp_blocked": blocked,
            "temp_blocked_until": block_end if blocked and block_end else None,
            "limits_disabled": int(data.get("dlu", 0)) > now_ms,
            "app_count": len(cache.category_apps(scope, cid)),
            "rule_count": len(cache.rules(scope, cid)),
        }

    def _child_summary(
        self, scope: Scope, child: CachedItem, now_ms: int
    ) -> tuple[dict[str, Any], list[dict[str, Any]], int]:
        data = child.data
        zone = _zone(str(data.get("timeZone") or "UTC"))
        today = day_of_epoch(self._clock.now(), zone)
        categories = [
            self._category_view(scope, c, today, now_ms)
            for c in self._backend.cache.categories(scope, str(data["id"]))
        ]
        known = {c["id"] for c in categories}
        top = [c for c in categories if c["parent_id"] not in known]
        status = STATUS_OK
        if int(data.get("disableLimitsUntil", 0)) > now_ms or any(
            c["limits_disabled"] for c in top
        ):
            status = STATUS_LIMITS_DISABLED
        if any(c["temp_blocked"] for c in categories):
            status = STATUS_TEMP_BLOCKED
        devices = [
            d
            for d in self._backend.cache.devices(scope)
            if d.data.get("currentUserId") == data["id"]
        ]
        summary = {
            "id": str(data["id"]),
            "name": data.get("name", ""),
            "on_server": child.on_server,
            "time_zone": str(data.get("timeZone") or "UTC"),
            "status": status,
            "used_today_ms": sum(c["used_today_ms"] for c in top),
            "category_count": len(categories),
            "device_count": len(devices),
        }
        return summary, categories, today

    # -- the two views ---------------------------------------------------------------------------------------------
    def overview(self) -> dict[str, Any]:
        scope = self._scope()
        if scope is None:
            return {"children": []}
        now_ms = int(self._clock.now().timestamp() * 1000)
        children = [
            self._child_summary(scope, c, now_ms)[0] for c in self._children(scope)
        ]
        return {"children": children}

    def detail(self, child_id: str) -> dict[str, Any]:
        scope = self._scope()
        child = next(
            (c for c in self._children(scope) if c.data["id"] == child_id)
            if scope
            else (),
            None,
        )
        if scope is None or child is None:
            raise DashboardError(ErrorCode.NOT_FOUND, "This child is not known.")
        now_ms = int(self._clock.now().timestamp() * 1000)
        summary, categories, today = self._child_summary(scope, child, now_ms)
        order = _tree_order(categories)
        devices = [
            {
                "id": d.data.get("deviceId", ""),
                "name": d.data.get("name", ""),
                "model": d.data.get("model", ""),
                "added_at": d.data.get("addedAt"),
                "on_server": d.on_server,
            }
            for d in self._backend.cache.devices(scope)
            if d.data.get("currentUserId") == child_id
        ]
        return {
            "child": summary,
            "today": today,
            "categories": order,
            "devices": devices,
        }


def _tree_order(categories: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Parents before their sub-categories, siblings by ``sort`` then title; adds ``depth``."""
    known = {c["id"] for c in categories}
    children: dict[str, list[dict[str, Any]]] = {}
    for category in categories:
        parent = category["parent_id"] if category["parent_id"] in known else ""
        children.setdefault(parent, []).append(category)
    ordered: list[dict[str, Any]] = []

    def walk(parent: str, depth: int, seen: frozenset[str]) -> None:
        for category in sorted(
            children.get(parent, []), key=lambda c: (c["sort"], c["title"].lower())
        ):
            if category["id"] in seen:
                continue
            ordered.append({**category, "depth": depth})
            walk(category["id"], depth + 1, seen | {category["id"]})

    walk("", 0, frozenset())
    return ordered
