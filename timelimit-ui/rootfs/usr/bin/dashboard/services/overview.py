"""Placeholder for the overview list (plan A7).

There is no cache yet (repository comes in step B); this stands in for "one read-only list from the
cache" so the offline behaviour can be built and tested. It is replaced by the children overview.
"""

from __future__ import annotations

PLACEHOLDER_ITEMS = ("Sample child A", "Sample child B")


def overview_items() -> list[dict[str, str]]:
    return [{"name": name} for name in PLACEHOLDER_ITEMS]
