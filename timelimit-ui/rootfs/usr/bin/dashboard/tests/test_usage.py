"""Plan step E9: used time today and history (FR-600, FR-601, Q10, Q10b)."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pytest
from flask import Flask

from ..config import Settings
from ..domain.clock import FakeClock
from ..domain.secret import Secret
from ..factory import create_app
from .conftest import link_app, make_family, seed_children
from .fakeserver import FakeTimeLimitServer
from .fakeserver.state import version_id

NOW = datetime(2026, 11, 12, 12, 0, tzinfo=timezone.utc)  # a Thursday
MIN = 60000


def epoch_day(moment: datetime) -> int:
    return (moment.date() - date(1970, 1, 1)).days


@pytest.fixture
def make(
    data_dir: Path, fake_server: FakeTimeLimitServer
) -> Iterator[Callable[..., tuple[Flask, dict[str, str], FakeClock]]]:
    apps: list[Flask] = []

    def build(
        now: datetime = NOW, zone: str = "UTC"
    ) -> tuple[Flask, dict[str, str], FakeClock]:
        make_family(fake_server)
        ids = seed_children(fake_server, epoch_day(now))
        family(fake_server).users[ids["Anna"]].time_zone = zone
        clock = FakeClock(now)
        settings = Settings(
            data_dir=data_dir, server_url=fake_server.url, server_timeout=3.0
        )
        app = create_app(settings, Secret("s"), clock)
        apps.append(app)
        link_app(app, fake_server)
        return app, ids, clock

    yield build
    for app in apps:
        app.extensions["dashboard"]["backend"].close()


def family(fake: FakeTimeLimitServer) -> Any:
    return next(iter(fake.world.families.values()))


def pull(app: Flask, fake: FakeTimeLimitServer) -> None:
    backend = app.extensions["dashboard"]["backend"]
    link = backend.links.get(fake.url)
    backend.puller(fake.url).pull(fake.url, link.device_token, link.family_id)


def usage(app: Flask, ids: dict[str, str], child: str = "Anna") -> Any:
    res = app.test_client().get(f"/api/children/{ids[child]}/usage")
    assert res.status_code == 200
    return res.get_json()


def games(data: Any) -> dict[str, Any]:
    return next(c for c in data["categories"] if c["id"] == "cgames")


def test_today_against_the_limit(make: Any) -> None:
    app, ids, _ = make()
    data = usage(app, ids)
    assert data["today"] == "2026-11-12"
    g = games(data)
    assert g["used_today_ms"] == 65 * MIN
    assert g["limit_today_ms"] == 60 * MIN  # rule01: every day, 60 minutes
    assert g["extra_time_ms"] == 15 * MIN


def test_a_category_without_rules_has_no_limit_and_children_are_separate(
    make: Any,
) -> None:
    app, ids, _ = make()
    data = usage(app, ids)
    social = next(c for c in data["categories"] if c["id"] == "csocia")
    assert social["limit_today_ms"] is None
    assert {c["id"] for c in data["categories"]} == {"cgames", "csocia"}
    assert {c["id"] for c in usage(app, ids, "Ben")["categories"]} == {"cschol"}


def test_a_rule_for_another_weekday_is_no_limit_today(
    make: Any, fake_server: FakeTimeLimitServer
) -> None:
    app, ids, _ = make()
    rule = family(fake_server).categories["cgames"].rules["rule01"]
    rule.day_mask = 1 << 6  # Sunday only; the clock says Thursday
    family(fake_server).categories["cgames"].rules_version = version_id()
    pull(app, fake_server)
    assert games(usage(app, ids))["limit_today_ms"] is None


def test_the_strictest_applicable_rule_counts(
    make: Any, fake_server: FakeTimeLimitServer
) -> None:
    from .fakeserver.state import Rule

    app, ids, _ = make()
    cat = family(fake_server).categories["cgames"]
    cat.rules["rule02"] = Rule("rule02", False, 1 << 3, 30 * MIN, 0, 1439, 0, 0, False)
    cat.rules_version = version_id()
    pull(app, fake_server)
    assert games(usage(app, ids))["limit_today_ms"] == 30 * MIN


def test_history_has_30_days_ending_today_with_zeros_for_gaps(make: Any) -> None:
    app, ids, _ = make()
    history = games(usage(app, ids))["history"]
    assert len(history) == 30
    assert history[-1] == {"date": "2026-11-12", "used_ms": 65 * MIN}
    assert history[0]["date"] == "2026-10-14"
    assert all(h["used_ms"] == 0 for h in history[:-1])


def test_the_history_follows_the_childs_own_day(make: Any) -> None:
    late = datetime(2026, 11, 12, 23, 30, tzinfo=timezone.utc)
    app, ids, _ = make(now=late, zone="Pacific/Auckland")
    assert usage(app, ids)["today"] == "2026-11-13"


def test_server_days_are_summed_over_time_slots(
    make: Any, fake_server: FakeTimeLimitServer
) -> None:
    app, ids, _ = make()
    day = epoch_day(NOW) - 1
    cat = family(fake_server).categories["cgames"]
    cat.used_times[day] = {(0, 719): 10 * MIN, (720, 1439): 5 * MIN}
    cat.used_times_version = version_id()
    pull(app, fake_server)
    assert games(usage(app, ids))["history"][-2]["used_ms"] == 15 * MIN


def test_forty_days_of_pulls_leave_exactly_the_last_thirty(
    make: Any, fake_server: FakeTimeLimitServer
) -> None:
    app, ids, clock = make()
    cat = family(fake_server).categories["cgames"]
    first = epoch_day(NOW)
    for step in range(40):
        day = first + step
        clock.set(NOW + timedelta(days=step))
        cat.used_times = {
            day: {(0, 1439): (step + 1) * MIN}
        }  # the server keeps only the newest day
        cat.used_times_version = version_id()
        pull(app, fake_server)
    history = games(usage(app, ids))["history"]
    assert len(history) == 30
    assert [h["used_ms"] // MIN for h in history] == list(range(11, 41))
    cache = app.extensions["dashboard"]["backend"].cache
    scope = app.extensions["dashboard"]["backend"].scope(fake_server.url)
    assert min(cache.own_used_time(scope, "cgames")) == first + 10


def test_a_pull_updates_the_total_of_a_day(
    make: Any, fake_server: FakeTimeLimitServer
) -> None:
    app, ids, _ = make()
    cat = family(fake_server).categories["cgames"]
    cat.used_times = {epoch_day(NOW): {(0, 1439): 80 * MIN}}
    cat.used_times_version = version_id()
    pull(app, fake_server)
    assert games(usage(app, ids))["used_today_ms"] == 80 * MIN
    assert games(usage(app, ids))["history"][-1]["used_ms"] == 80 * MIN


def test_after_a_cache_reset_the_history_starts_again(
    make: Any, fake_server: FakeTimeLimitServer
) -> None:
    app, ids, clock = make()
    cat = family(fake_server).categories["cgames"]
    cat.used_times = {epoch_day(NOW): {(0, 1439): 10 * MIN}}
    cat.used_times_version = version_id()
    pull(app, fake_server)
    clock.set(NOW + timedelta(days=1))
    cat.used_times = {epoch_day(NOW) + 1: {(0, 1439): 20 * MIN}}
    cat.used_times_version = version_id()
    pull(app, fake_server)
    assert [h["used_ms"] // MIN for h in games(usage(app, ids))["history"][-2:]] == [
        10,
        20,
    ]
    backend = app.extensions["dashboard"]["backend"]
    backend.cache.clear_profile(fake_server.url)
    pull(app, fake_server)
    assert [h["used_ms"] // MIN for h in games(usage(app, ids))["history"][-2:]] == [
        0,
        20,
    ]


def test_an_unknown_child_is_404(make: Any) -> None:
    app, _, _ = make()
    assert app.test_client().get("/api/children/nobody/usage").status_code == 404
