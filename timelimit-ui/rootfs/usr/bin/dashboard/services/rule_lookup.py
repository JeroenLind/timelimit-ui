"""Find a rule of a child in the cache (shared by the rule and the rule-off-today services)."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from dashboard.domain.errors import DashboardError, ErrorCode
from dashboard.repository.cache import Scope
from dashboard.sync.backend import Backend


def find_rule(
    backend: Backend, scope: Scope, child_id: str, rule_id: str
) -> tuple[str, dict[str, Any]]:
    """``(category_id, rule record)`` of a rule that belongs to ``child_id`` and is on the server."""
    cache = backend.cache
    for category in cache.categories(scope, child_id):
        if not category.on_server:
            continue
        category_id = str(category.data["categoryId"])
        for rule in cache.rules(scope, category_id):
            if rule.data.get("id") == rule_id and rule.on_server:
                return category_id, rule.data
    raise DashboardError(ErrorCode.NOT_FOUND, "This rule is not known.")


def rule_version(rule: dict[str, Any]) -> str:
    """A short fingerprint of a rule as cached; the browser sends it back to detect a change by someone else (FR-208)."""
    text = json.dumps(rule, sort_keys=True, default=str)
    return hashlib.sha1(text.encode(), usedforsecurity=False).hexdigest()[:12]


def check_version(rule: dict[str, Any], expected: object) -> None:
    """Refuse when the rule changed since the browser read it; ``None`` means "save anyway" (last writer wins)."""
    if expected is None:
        return
    if not isinstance(expected, str) or expected != rule_version(rule):
        raise DashboardError(
            ErrorCode.CONFLICT,
            "This rule was changed on the server after you opened it.",
            "version",
        )
