"""Pure rules for "time limit rule off for today" (FR-307, plan E3a, decisions W1-W6).

Mechanism (W1): today's weekday bit is removed from the rule's day mask and put back at the dashboard's
midnight. "Today" and "midnight" are those of the machine running the dashboard (W2). Nothing here reads
the clock or the database; the callers pass the moment and the cached rule.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from dashboard.domain import actions
from dashboard.domain.bitmask import mask_with_day, mask_without_day

# The rule fields that make up its state, with the server's defaults for a field the cache does not have.
DEFAULTS: dict[str, Any] = {
    "dayMask": 0,
    "maxTime": 0,
    "extraTime": False,
    "start": 0,
    "end": 1439,
    "session": 0,
    "pause": 0,
    "perDay": False,
    "e": None,
}


def normalize(rule: dict[str, Any]) -> dict[str, Any]:
    found = {name: rule.get(name, default) for name, default in DEFAULTS.items()}
    found["extraTime"] = bool(found["extraTime"])
    found["perDay"] = bool(found["perDay"])
    return found


def snapshot(rule: dict[str, Any], day_mask: int) -> dict[str, Any]:
    """The rule as the dashboard sets it: the cached rule with the new day mask."""
    return {**normalize(rule), "dayMask": day_mask}


def same_rule(expected: dict[str, Any], current: dict[str, Any]) -> bool:
    """Is the rule on the server still exactly what the dashboard set? (W5)"""
    return normalize(current) == normalize(expected)


def applies_on(mask: int, moment: datetime) -> bool:
    return bool(mask & (1 << moment.weekday()))


def day_off(mask: int, moment: datetime) -> int:
    """The mask without the weekday of ``moment`` (may become 0 when it was the only day)."""
    return mask_without_day(mask, moment.weekday())


def day_back(mask: int, bit: int) -> int:
    return mask_with_day(mask, bit.bit_length() - 1)


def next_midnight(moment: datetime) -> datetime:
    """The next 00:00 in the time zone of ``moment``."""
    following = moment + timedelta(days=1)
    return following.replace(hour=0, minute=0, second=0, microsecond=0)


def rule_action(rule_id: str, rule: dict[str, Any], day_mask: int) -> actions.Action:
    """``UPDATE_TIMELIMIT_RULE`` carrying every field of ``rule`` with ``day_mask`` (the update is flat)."""
    fields = normalize(rule)
    has_window = (fields["start"], fields["end"]) != (0, 1439)
    return actions.update_timelimit_rule(
        rule_id,
        time_ms=int(fields["maxTime"]),
        days=day_mask,
        extra_time=fields["extraTime"],
        start=int(fields["start"]) if has_window else None,
        end=int(fields["end"]) if has_window else None,
        dur=int(fields["session"]) or None,
        pause=int(fields["pause"]) or None,
        per_day=fields["perDay"],
        expires_at=int(fields["e"]) if fields["e"] else None,
    )
