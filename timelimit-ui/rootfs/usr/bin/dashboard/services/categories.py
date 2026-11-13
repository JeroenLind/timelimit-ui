"""Categories of a child: create, rename, delete, order, parent, unassigned apps, disable limits (plan E6a, FR-400..401)."""

from __future__ import annotations

from typing import Any

from dashboard.domain import actions
from dashboard.domain.clock import Clock
from dashboard.domain.errors import DashboardError, ErrorCode
from dashboard.repository.cache import CachedItem, Scope
from dashboard.services.changes import ChangeService
from dashboard.services.profiles import ServerProfiles
from dashboard.sync.backend import Backend

MAX_DISABLE_MINUTES = 7 * 24 * 60


def _invalid(field: str, message: str) -> DashboardError:
    return DashboardError(ErrorCode.INVALID_INPUT, message, field)


def _body(body: object) -> dict[str, Any]:
    if not isinstance(body, dict):
        raise _invalid("body", "Send a JSON object.")
    return body


class CategoriesService:
    def __init__(
        self,
        backend: Backend,
        profiles: ServerProfiles,
        changes: ChangeService,
        clock: Clock,
    ) -> None:
        self._backend = backend
        self._profiles = profiles
        self._changes = changes
        self._clock = clock

    # -- lookups ---------------------------------------------------------------------------------------------------------------
    def _scope(self) -> Scope:
        scope = self._backend.scope(self._profiles.url())
        if scope is None:
            raise DashboardError(
                ErrorCode.NOT_LINKED, "This dashboard is not linked to a family yet."
            )
        return scope

    def _child(self, scope: Scope, child_id: str) -> CachedItem:
        for user in self._backend.cache.users(scope):
            if (
                user.data.get("id") == child_id
                and user.data.get("type") == "child"
                and user.on_server
            ):
                return user
        raise DashboardError(ErrorCode.NOT_FOUND, "This child is not known.")

    def _categories(self, scope: Scope, child_id: str) -> list[dict[str, Any]]:
        self._child(scope, child_id)
        return [
            c.data
            for c in self._backend.cache.categories(scope, child_id)
            if c.on_server
        ]

    @staticmethod
    def _find(categories: list[dict[str, Any]], category_id: str) -> dict[str, Any]:
        for data in categories:
            if data.get("categoryId") == category_id:
                return data
        raise DashboardError(ErrorCode.NOT_FOUND, "This category is not known.")

    @staticmethod
    def _below(categories: list[dict[str, Any]], category_id: str) -> set[str]:
        """Ids of all sub-categories, at any depth."""
        found: set[str] = set()
        pending = [category_id]
        while pending:
            current = pending.pop()
            for data in categories:
                child = str(data.get("categoryId"))
                if data.get("parentCategoryId") == current and child not in found:
                    found.add(child)
                    pending.append(child)
        return found

    def _check_parent(
        self, categories: list[dict[str, Any]], category_id: str | None, parent: object
    ) -> str:
        if parent is None or parent == "":
            return ""
        if not isinstance(parent, str):
            raise _invalid("parent_id", "Choose a category as parent.")
        self._find(categories, parent)  # must be a category of the same child
        if category_id is not None and (
            parent == category_id or parent in self._below(categories, category_id)
        ):
            raise _invalid(
                "parent_id",
                "A category can not be placed below one of its own sub-categories.",
            )
        return parent

    def _push(self, built: list[Any]) -> None:
        try:
            actions_list = [make() for make in built]
        except actions.ActionError as error:
            raise _invalid("title", str(error)) from error
        self._changes.push(actions_list)

    # -- changes ---------------------------------------------------------------------------------------------------------------
    def create(self, child_id: str, body: object) -> str:
        data = _body(body)
        scope = self._scope()
        categories = self._categories(scope, child_id)
        parent = self._check_parent(categories, None, data.get("parent_id"))
        title = data.get("title")
        if not isinstance(title, str) or not title.strip():
            raise _invalid("title", "Give the category a name.")
        category_id = actions.new_id()
        built = [lambda: actions.create_category(child_id, category_id, title)]
        if parent:
            built.append(lambda: actions.set_parent_category(category_id, parent))
        self._push(built)
        return category_id

    def update(self, child_id: str, category_id: str, body: object) -> None:
        data = _body(body)
        scope = self._scope()
        categories = self._categories(scope, child_id)
        current = self._find(categories, category_id)
        built = []
        if "title" in data:
            title = data["title"]
            if not isinstance(title, str) or not title.strip():
                raise _invalid("title", "Give the category a name.")
            if title != current.get("title"):
                built.append(lambda: actions.update_category_title(category_id, title))
        if "parent_id" in data:
            parent = self._check_parent(categories, category_id, data["parent_id"])
            if parent != (current.get("parentCategoryId") or ""):
                built.append(lambda: actions.set_parent_category(category_id, parent))
        if built:
            self._push(built)

    def delete(self, child_id: str, category_id: str) -> None:
        scope = self._scope()
        categories = self._categories(scope, child_id)
        self._find(categories, category_id)
        if self._below(categories, category_id):
            raise _invalid(
                "category",
                "This category has sub-categories. Move or delete them first.",
            )
        self._push([lambda: actions.delete_category(category_id)])
        # deleted by the parent herself: forget it at once instead of flagging it "no longer on server"
        self._backend.cache.forget_category(scope, category_id)

    def move(self, child_id: str, category_id: str, body: object) -> None:
        """Swap a category with its neighbour among the categories with the same parent."""
        direction = _body(body).get("direction")
        if direction not in ("up", "down"):
            raise _invalid("direction", "Choose up or down.")
        scope = self._scope()
        categories = self._categories(scope, child_id)
        current = self._find(categories, category_id)
        order = sorted(
            categories, key=lambda c: (int(c.get("sort", 0)), str(c.get("title", "")))
        )
        parent = current.get("parentCategoryId") or ""
        siblings = [c for c in order if (c.get("parentCategoryId") or "") == parent]
        at = siblings.index(current)
        other_at = at - 1 if direction == "up" else at + 1
        if not 0 <= other_at < len(siblings):
            return  # already first or last
        one, two = order.index(siblings[at]), order.index(siblings[other_at])
        order[one], order[two] = order[two], order[one]
        ids = [str(c["categoryId"]) for c in order]
        self._push([lambda: actions.update_category_sorting(ids)])

    def set_unassigned(self, child_id: str, body: object) -> None:
        value = _body(body).get("category_id", "")
        scope = self._scope()
        categories = self._categories(scope, child_id)
        if value in (None, ""):
            value = ""
        else:
            if not isinstance(value, str):
                raise _invalid("category_id", "Choose a category.")
            self._find(categories, value)
        category_id = str(value)
        self._push(
            [lambda: actions.set_category_for_unassigned_apps(child_id, category_id)]
        )

    def disable_limits(self, child_id: str, category_id: str, body: object) -> None:
        minutes = _body(body).get("minutes")
        if (
            isinstance(minutes, bool)
            or not isinstance(minutes, int)
            or not 0 <= minutes <= MAX_DISABLE_MINUTES
        ):
            raise _invalid(
                "minutes",
                f"Enter whole minutes from 0 to {MAX_DISABLE_MINUTES} (0 switches it off).",
            )
        scope = self._scope()
        self._find(self._categories(scope, child_id), category_id)
        end = (
            0
            if minutes == 0
            else int(self._clock.now().timestamp() * 1000) + minutes * 60000
        )
        self._push([lambda: actions.update_category_disable_limits(category_id, end)])
