"""Time limit rules: create, change and delete (plan E3, FR-300..303, FR-305).

Input arrives as the browser form sends it (minutes, weekdays 0..6 with Monday = 0, "HH:MM" times) and is
validated here, before anything is sent: an invalid form never reaches the server. The wire format
(milliseconds, day mask) is built by :mod:`dashboard.domain.actions` and :mod:`dashboard.domain.bitmask`.
"""

from __future__ import annotations

import re
from typing import Any

from dashboard.domain import actions
from dashboard.domain.bitmask import day_mask
from dashboard.domain.errors import DashboardError, ErrorCode
from dashboard.repository.cache import Scope
from dashboard.services.changes import ChangeService
from dashboard.services.profiles import ServerProfiles
from dashboard.services.rule_lookup import find_rule
from dashboard.services.rule_today import RuleTodayService
from dashboard.sync.backend import Backend

_TIME = re.compile(r"^([01]?\d|2[0-3]):([0-5]\d)$")
MAX_MINUTES = 24 * 60


def _invalid(field: str, message: str) -> DashboardError:
    return DashboardError(ErrorCode.INVALID_INPUT, message, field)


def _whole(body: dict[str, Any], field: str, low: int, high: int | None = None) -> int:
    value = body.get(field)
    if isinstance(value, bool) or not isinstance(value, int):
        raise _invalid(field, "Enter a whole number.")
    if value < low or (high is not None and value > high):
        raise _invalid(
            field,
            f"Enter a number from {low} to {high}."
            if high is not None
            else f"Enter {low} or more.",
        )
    return value


def _optional_minutes(body: dict[str, Any], field: str) -> int | None:
    if body.get(field) in (None, ""):
        return None
    return _whole(body, field, 0, MAX_MINUTES)


def _clock(body: dict[str, Any], field: str) -> int | None:
    value = body.get(field)
    if value in (None, ""):
        return None
    match = _TIME.match(value) if isinstance(value, str) else None
    if match is None:
        raise _invalid(field, "Enter a time as HH:MM (00:00 to 23:59).")
    return int(match.group(1)) * 60 + int(match.group(2))


def parse_rule(body: object) -> dict[str, Any]:
    """Validate the form and return the keyword arguments of the rule action builders."""
    if not isinstance(body, dict):
        raise DashboardError(
            ErrorCode.INVALID_INPUT, "The request body must be an object."
        )
    days = body.get("days")
    if (
        not isinstance(days, list)
        or not days
        or any(
            isinstance(d, bool) or not isinstance(d, int) or not 0 <= d <= 6
            for d in days
        )
    ):
        raise _invalid("days", "Choose at least one day.")
    start, end = _clock(body, "start"), _clock(body, "end")
    if (start is None) != (end is None):
        raise _invalid(
            "end" if end is None else "start",
            "Enter both a start and an end time, or neither.",
        )
    if start is not None and end is not None and start > end:
        raise _invalid("end", "The end time must not be before the start time.")
    session, pause = (
        _optional_minutes(body, "session_minutes"),
        _optional_minutes(body, "pause_minutes"),
    )
    if (session is None) != (pause is None):
        raise _invalid(
            "pause_minutes" if pause is None else "session_minutes",
            "Enter both a session length and a break, or neither.",
        )
    return {
        "time_ms": _whole(body, "minutes", 0, MAX_MINUTES) * 60000,
        "days": day_mask(days),
        "extra_time": bool(body.get("extra_time")),
        "start": start,
        "end": end,
        "dur": None if session is None else session * 60000,
        "pause": None if pause is None else pause * 60000,
        "per_day": bool(body.get("per_day")),
    }


class RulesService:
    def __init__(
        self,
        backend: Backend,
        profiles: ServerProfiles,
        changes: ChangeService,
        rule_today: RuleTodayService,
    ) -> None:
        self._backend = backend
        self._profiles = profiles
        self._changes = changes
        self._rule_today = rule_today

    def _scope(self) -> Scope:
        scope = self._backend.scope(self._profiles.url())
        if scope is None:
            raise DashboardError(
                ErrorCode.NOT_LINKED, "This dashboard is not linked to a family yet."
            )
        return scope

    def _check_category(self, scope: Scope, child_id: str, category_id: str) -> None:
        categories = self._backend.cache.categories(scope, child_id)
        if not any(
            c.data.get("categoryId") == category_id and c.on_server for c in categories
        ):
            raise DashboardError(ErrorCode.NOT_FOUND, "This category is not known.")

    def create(self, child_id: str, category_id: str, body: object) -> str:
        fields = parse_rule(body)
        scope = self._scope()
        self._check_category(scope, child_id, category_id)
        rule_id = actions.new_id()
        self._changes.push(
            [actions.create_timelimit_rule(rule_id, category_id, **fields)]
        )
        return rule_id

    def update(self, child_id: str, rule_id: str, body: object) -> None:
        fields = parse_rule(body)
        _, rule = find_rule(self._backend, self._scope(), child_id, rule_id)
        # a rule that is off for today is put back first, in the same push (W6)
        before, pending = self._rule_today.actions_before_change(rule_id, rule)
        self._changes.push([*before, actions.update_timelimit_rule(rule_id, **fields)])
        if pending is not None:
            self._rule_today.ended_by_change(pending)

    def delete(self, child_id: str, rule_id: str) -> None:
        scope = self._scope()
        _, rule = find_rule(self._backend, scope, child_id, rule_id)
        before, pending = self._rule_today.actions_before_change(rule_id, rule)
        self._changes.push([*before, actions.delete_timelimit_rule(rule_id)])
        if pending is not None:
            self._rule_today.ended_by_change(pending)
        # confirmed by the pull: the server no longer lists it, so it is flagged; she asked for this, so
        # it is not kept as "no longer on server" (that is for changes made elsewhere, FR-206)
        self._backend.cache.forget_rule(scope, rule_id)
        self._backend.hub.publish({"type": "changed", "parts": ["rules"]})
