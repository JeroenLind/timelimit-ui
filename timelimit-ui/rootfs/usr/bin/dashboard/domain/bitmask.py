"""Pure encoders for the bit masks and strings of the TimeLimit protocol (TR-100).

Formats verified in the server source (``util/bitmask.ts``, ``action/*``):

* Day mask: bit 0 = Monday ... bit 6 = Sunday; 127 = every day.
* Blocked times (``UPDATE_CATEGORY_BLOCKED_TIMES.times``): comma separated pairs ``start,end``
  of minutes of the week (0..10080, Monday 00:00 = 0), the end is exclusive, the pairs are
  strictly increasing and must not touch or overlap; the empty string means "nothing blocked".
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from datetime import date, datetime, tzinfo

MINUTES_PER_DAY = 1440
MINUTES_PER_WEEK = 7 * MINUTES_PER_DAY
ALL_DAYS_MASK = 127

Interval = tuple[int, int]


class BitmaskError(ValueError):
    """Raised for values the server would reject."""


def day_mask(days: Iterable[int]) -> int:
    """Mask for weekdays given as 0 (Monday) .. 6 (Sunday)."""
    mask = 0
    for day in days:
        if isinstance(day, bool) or not isinstance(day, int) or not 0 <= day <= 6:
            raise BitmaskError(f"weekday must be 0..6, got {day!r}")
        mask |= 1 << day
    return mask


def days_from_mask(mask: int) -> list[int]:
    """Weekdays (0 = Monday) contained in a day mask."""
    if (
        isinstance(mask, bool)
        or not isinstance(mask, int)
        or not 0 <= mask <= ALL_DAYS_MASK
    ):
        raise BitmaskError(f"day mask must be 0..{ALL_DAYS_MASK}, got {mask!r}")
    return [day for day in range(7) if mask & (1 << day)]


def mask_has_day(mask: int, weekday: int) -> bool:
    return weekday in days_from_mask(mask)


def mask_without_day(mask: int, weekday: int) -> int:
    """The mask with one weekday removed (FR-307: rule off for today)."""
    days_from_mask(mask)
    day_mask([weekday])
    return mask & ~(1 << weekday) & ALL_DAYS_MASK


def mask_with_day(mask: int, weekday: int) -> int:
    days_from_mask(mask)
    return mask | day_mask([weekday])


def validate_intervals(intervals: Sequence[Interval]) -> list[Interval]:
    """Check a list of (start, end) pairs the way the server does and return them as a list."""
    result: list[Interval] = []
    previous_end = -1
    for pair in intervals:
        start, end = pair
        for value in (start, end):
            if isinstance(value, bool) or not isinstance(value, int):
                raise BitmaskError(f"minute must be an integer, got {value!r}")
        if start < 0 or end > MINUTES_PER_WEEK:
            raise BitmaskError(
                f"interval {start},{end} is outside 0..{MINUTES_PER_WEEK}"
            )
        if end <= start:
            raise BitmaskError(f"interval {start},{end} must end after it starts")
        if start <= previous_end:
            raise BitmaskError(
                f"interval {start},{end} overlaps or touches the previous one"
            )
        previous_end = end
        result.append((start, end))
    return result


def merge_intervals(intervals: Iterable[Interval]) -> list[Interval]:
    """Sort and merge overlapping or touching intervals so the result is valid for the server."""
    merged: list[Interval] = []
    for start, end in sorted(intervals):
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    return merged


def format_blocked_times(intervals: Sequence[Interval]) -> str:
    """Encode intervals as the ``times`` string. Raises ``BitmaskError`` when invalid."""
    return ",".join(f"{start},{end}" for start, end in validate_intervals(intervals))


def parse_blocked_times(text: str) -> list[Interval]:
    """Decode a ``times`` string; the inverse of :func:`format_blocked_times`."""
    if text == "":
        return []
    parts = text.split(",")
    if len(parts) % 2 != 0:
        raise BitmaskError("blocked times need an even number of values")
    numbers: list[int] = []
    for part in parts:
        if not part.isascii() or not part.isdigit():
            raise BitmaskError(f"not a number: {part!r}")
        numbers.append(int(part))
    return validate_intervals(list(zip(numbers[0::2], numbers[1::2], strict=True)))


def week_minute(weekday: int, minute_of_day: int) -> int:
    """Minute of the week for a weekday (0 = Monday) and a minute of the day (0..1440)."""
    day_mask([weekday])
    if isinstance(minute_of_day, bool) or not 0 <= minute_of_day <= MINUTES_PER_DAY:
        raise BitmaskError(
            f"minute of day must be 0..{MINUTES_PER_DAY}, got {minute_of_day!r}"
        )
    return weekday * MINUTES_PER_DAY + minute_of_day


def day_of_epoch(moment: datetime, zone: tzinfo) -> int:
    """Days since 1970-01-01 of ``moment`` in ``zone``; the ``day`` of extra time for "today only".

    The Android app sends ``dayOfEpoch`` of the child's date (``-1`` means every day). ``moment`` must be
    time-zone aware and comes from the injected clock.
    """
    if moment.tzinfo is None:
        raise BitmaskError("moment must be time-zone aware")
    return (moment.astimezone(zone).date() - date(1970, 1, 1)).days
