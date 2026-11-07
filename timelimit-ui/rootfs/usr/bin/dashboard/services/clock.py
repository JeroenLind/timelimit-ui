"""The real clock (the only place that asks the system for the time, TR-512)."""

from __future__ import annotations

from datetime import datetime


class SystemClock:
    """Local time of the machine running the dashboard, with its time zone."""

    def now(self) -> datetime:
        return datetime.now().astimezone()
