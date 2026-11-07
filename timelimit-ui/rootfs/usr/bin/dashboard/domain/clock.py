"""The clock the domain gets from outside (TR-512).

The domain never asks the system for the time; it receives a ``Clock``. All times are
time-zone aware. ``SystemClock`` lives in ``services/``, ``FakeClock`` here so tests of every layer
can use it.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone, tzinfo
from typing import Protocol


class NaiveTimeError(ValueError):
    """A time without a time zone was used where an aware time is required."""


def require_aware(moment: datetime) -> datetime:
    """Return ``moment`` when it has a time zone, else raise ``NaiveTimeError``."""
    if moment.tzinfo is None or moment.utcoffset() is None:
        raise NaiveTimeError("time without a time zone is not allowed")
    return moment


class Clock(Protocol):
    """Anything that can say what time it is, with a time zone."""

    def now(self) -> datetime: ...


class FakeClock:
    """A clock for tests that only moves when told to."""

    def __init__(self, start: datetime | None = None) -> None:
        self._now = require_aware(
            start or datetime(2026, 1, 7, 12, 0, tzinfo=timezone.utc)
        )

    def now(self) -> datetime:
        return self._now

    def set(self, moment: datetime) -> None:
        self._now = require_aware(moment)

    def advance(self, delta: timedelta) -> None:
        self._now = self._now + delta

    def convert(self, zone: tzinfo) -> datetime:
        """The current fake time in another time zone."""
        return self._now.astimezone(zone)
