"""Apps per category: the child's app list, assign and remove (plan E7, FR-403..405)."""

from __future__ import annotations

import re
from typing import Any

from dashboard.domain import actions
from dashboard.domain.errors import DashboardError, ErrorCode
from dashboard.repository.cache import Scope
from dashboard.services.changes import ChangeService
from dashboard.services.profiles import ServerProfiles
from dashboard.sync.backend import Backend

_PACKAGE = re.compile(r"^[A-Za-z0-9_.:\-]{1,200}$")


def _invalid(message: str) -> DashboardError:
    return DashboardError(ErrorCode.INVALID_INPUT, message, "packages")


class AppsService:
    def __init__(
        self, backend: Backend, profiles: ServerProfiles, changes: ChangeService
    ) -> None:
        self._backend = backend
        self._profiles = profiles
        self._changes = changes

    def _scope(self) -> Scope:
        scope = self._backend.scope(self._profiles.url())
        if scope is None:
            raise DashboardError(
                ErrorCode.NOT_LINKED, "This dashboard is not linked to a family yet."
            )
        return scope

    def _child_categories(self, scope: Scope, child_id: str) -> dict[str, str]:
        """``{category id: title}`` of a known child."""
        cache = self._backend.cache
        if not any(
            u.data.get("id") == child_id
            and u.data.get("type") == "child"
            and u.on_server
            for u in cache.users(scope)
        ):
            raise DashboardError(ErrorCode.NOT_FOUND, "This child is not known.")
        return {
            str(c.data["categoryId"]): str(c.data.get("title", ""))
            for c in cache.categories(scope, child_id)
            if c.on_server
        }

    def overview(self, child_id: str) -> dict[str, Any]:
        """Every app of the child's devices with the category it is in, plus assigned apps no device lists."""
        scope = self._scope()
        cache = self._backend.cache
        categories = self._child_categories(scope, child_id)
        assigned: dict[str, str] = {}
        for category_id in categories:
            for raw in cache.category_apps(scope, category_id):
                assigned[raw.split(":", 1)[0]] = category_id
        apps: dict[str, dict[str, Any]] = {}
        devices = [
            d for d in cache.devices(scope) if d.data.get("currentUserId") == child_id
        ]
        for device in devices:
            for item in cache.installed_apps(scope, str(device.data["deviceId"])):
                package = str(item.get("packageName", ""))
                if not package:
                    continue
                known_app = apps.setdefault(
                    package,
                    {
                        "package": package,
                        "title": str(item.get("title") or package),
                        "launchable": bool(item.get("isLaunchable", True)),
                        "devices": [],
                    },
                )
                known_app["devices"].append(str(device.data.get("name", "")))
        known = bool(apps)
        for package in assigned:
            apps.setdefault(
                package,
                {
                    "package": package,
                    "title": package,
                    "launchable": True,
                    "devices": [],
                },
            )
        result = sorted(
            apps.values(), key=lambda a: (a["title"].casefold(), a["package"])
        )
        for found in result:
            owner = assigned.get(found["package"])
            found["category_id"] = owner
            found["category_title"] = categories.get(owner or "")
        return {"status": "ok", "known": known, "apps": result}

    @staticmethod
    def _packages(body: object) -> list[str]:
        packages = body.get("packages") if isinstance(body, dict) else None
        if not isinstance(packages, list) or not packages:
            raise _invalid("Choose at least one app.")
        for package in packages:
            if not isinstance(package, str) or not _PACKAGE.match(package):
                raise _invalid(
                    "A package name uses letters, digits, dots, underscores and dashes only."
                )
        if len(set(packages)) != len(packages):
            raise _invalid("An app is listed twice.")
        return list(packages)

    def assign(self, child_id: str, category_id: str, body: object) -> None:
        packages = self._packages(body)
        scope = self._scope()
        if category_id not in self._child_categories(scope, child_id):
            raise DashboardError(ErrorCode.NOT_FOUND, "This category is not known.")
        self._changes.push([actions.add_category_apps(category_id, packages)])

    def unassign(self, child_id: str, category_id: str, body: object) -> None:
        packages = self._packages(body)
        scope = self._scope()
        if category_id not in self._child_categories(scope, child_id):
            raise DashboardError(ErrorCode.NOT_FOUND, "This category is not known.")
        have = set(self._backend.cache.category_apps(scope, category_id))
        if any(p not in have for p in packages):
            raise _invalid("One of these apps is not in this category.")
        self._changes.push([actions.remove_category_apps(category_id, packages)])
