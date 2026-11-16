"""Plan step E8: extra time and temporary blocking (FR-500..504)."""

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

NOW = datetime(2026, 11, 12, 12, 0, tzinfo=timezone.utc)
MIN = 60000


def epoch_day(moment: datetime) -> int:
    return (moment.date() - date(1970, 1, 1)).days


@pytest.fixture
def make(
    data_dir: Path, fake_server: FakeTimeLimitServer
) -> Iterator[Callable[..., tuple[Flask, dict[str, str], FakeClock]]]:
    apps: list[Flask] = []

    def build(
        now: datetime = NOW, zone: str = "UTC", extra_minutes: int = 15
    ) -> tuple[Flask, dict[str, str], FakeClock]:
        make_family(fake_server)
        ids = seed_children(fake_server, epoch_day(now))
        family = next(iter(fake_server.world.families.values()))
        family.users[ids["Anna"]].time_zone = zone
        games = family.categories["cgames"]
        games.extra_time = extra_minutes * MIN
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


def path(ids: dict[str, str], category: str, part: str) -> str:
    return f"/api/children/{ids['Anna']}/categories/{category}/{part}"


def games(app: Flask, ids: dict[str, str]) -> dict[str, Any]:
    detail = app.test_client().get(f"/api/children/{ids['Anna']}").get_json()
    return next(c for c in detail["categories"] if c["id"] == "cgames")


def put(app: Flask, url: str, body: Any) -> Any:
    return app.test_client().put(url, json=body)


def test_add_then_subtract_shows_the_difference(
    make: Any, fake_server: FakeTimeLimitServer
) -> None:
    app, ids, _ = make()
    assert (
        put(
            app, path(ids, "cgames", "extra-time"), {"mode": "add", "minutes": 30}
        ).status_code
        == 200
    )
    assert games(app, ids)["extra_time_ms"] == 45 * MIN
    assert (
        put(
            app, path(ids, "cgames", "extra-time"), {"mode": "subtract", "minutes": 30}
        ).status_code
        == 200
    )
    assert games(app, ids)["extra_time_ms"] == 15 * MIN
    cat = family(fake_server).categories["cgames"]
    assert (cat.extra_time, cat.extra_time_day) == (15 * MIN, epoch_day(NOW))


def test_subtracting_more_than_available_stops_at_zero(make: Any) -> None:
    app, ids, _ = make()
    assert (
        put(
            app, path(ids, "cgames", "extra-time"), {"mode": "subtract", "minutes": 60}
        ).status_code
        == 200
    )
    assert games(app, ids)["extra_time_ms"] == 0


def test_subtracting_when_there_is_none_pushes_nothing(
    make: Any, fake_server: FakeTimeLimitServer
) -> None:
    app, ids, _ = make(extra_minutes=0)
    before = len(fake_server.world.action_types)
    assert (
        put(
            app, path(ids, "cgames", "extra-time"), {"mode": "subtract", "minutes": 5}
        ).status_code
        == 200
    )
    assert len(fake_server.world.action_types) == before


def test_set_replaces_the_amount_and_zero_resets(make: Any) -> None:
    app, ids, _ = make()
    put(app, path(ids, "cgames", "extra-time"), {"mode": "set", "minutes": 40})
    assert games(app, ids)["extra_time_ms"] == 40 * MIN
    put(app, path(ids, "cgames", "extra-time"), {"mode": "set", "minutes": 0})
    assert games(app, ids)["extra_time_ms"] == 0


def test_extra_time_uses_the_childs_own_day(
    make: Any, fake_server: FakeTimeLimitServer
) -> None:
    # 23:30 UTC on 12 Nov is already 13 Nov in Auckland
    late = datetime(2026, 11, 12, 23, 30, tzinfo=timezone.utc)
    app, ids, _ = make(now=late, zone="Pacific/Auckland")
    put(app, path(ids, "cgames", "extra-time"), {"mode": "add", "minutes": 10})
    assert (
        family(fake_server).categories["cgames"].extra_time_day == epoch_day(late) + 1
    )


def test_extra_time_from_an_earlier_day_does_not_count_and_is_replaced(
    make: Any, fake_server: FakeTimeLimitServer
) -> None:
    app, ids, clock = make()
    clock.set(NOW + timedelta(days=1))
    assert games(app, ids)["extra_time_ms"] == 0
    put(app, path(ids, "cgames", "extra-time"), {"mode": "add", "minutes": 20})
    cat = family(fake_server).categories["cgames"]
    assert (cat.extra_time, cat.extra_time_day) == (20 * MIN, epoch_day(NOW) + 1)


@pytest.mark.parametrize(
    "body",
    [
        {"mode": "add", "minutes": 0},
        {"mode": "add", "minutes": -5},
        {"mode": "add", "minutes": 1441},
        {"mode": "add", "minutes": "5"},
        {"mode": "add", "minutes": True},
        {"mode": "double", "minutes": 5},
        {"minutes": 5},
    ],
)
def test_bad_extra_time_input_is_refused(
    make: Any, fake_server: FakeTimeLimitServer, body: dict[str, Any]
) -> None:
    app, ids, _ = make()
    before = len(fake_server.world.action_types)
    res = put(app, path(ids, "cgames", "extra-time"), body)
    assert res.status_code == 400
    assert len(fake_server.world.action_types) == before


def test_extra_time_for_an_unknown_category_is_404(make: Any) -> None:
    app, ids, _ = make()
    res = put(app, path(ids, "nothing", "extra-time"), {"mode": "add", "minutes": 5})
    assert res.status_code == 404


def test_block_for_an_hour_shows_the_end_time_and_ends_with_the_clock(
    make: Any, fake_server: FakeTimeLimitServer
) -> None:
    app, ids, clock = make()
    assert (
        put(app, path(ids, "cgames", "temp-block"), {"minutes": 60}).status_code == 200
    )
    end = int(NOW.timestamp() * 1000) + 60 * MIN
    view = games(app, ids)
    assert view["temp_blocked"] is True
    assert view["temp_blocked_until"] == end
    cat = family(fake_server).categories["cgames"]
    assert (cat.temp_blocked, cat.temp_block_end) == (True, end)
    clock.set(NOW + timedelta(minutes=61))
    assert games(app, ids)["temp_blocked"] is False


def test_block_until_an_absolute_time(make: Any) -> None:
    app, ids, _ = make()
    until = int(NOW.timestamp() * 1000) + 5 * 3600000
    assert (
        put(app, path(ids, "cgames", "temp-block"), {"until": until}).status_code == 200
    )
    assert games(app, ids)["temp_blocked_until"] == until


@pytest.mark.parametrize(
    "body",
    [
        {"minutes": 0},
        {"minutes": 10081},
        {"minutes": 1.5},
        {},
        {"until": 1},
        {"until": "tomorrow"},
        {"until": int(NOW.timestamp() * 1000) + 8 * 86400000},
    ],
)
def test_bad_block_input_is_refused(make: Any, body: dict[str, Any]) -> None:
    app, ids, _ = make()
    assert put(app, path(ids, "cgames", "temp-block"), body).status_code == 400


def test_unblock_removes_the_block(make: Any, fake_server: FakeTimeLimitServer) -> None:
    app, ids, _ = make()
    put(app, path(ids, "cgames", "temp-block"), {"minutes": 60})
    res = app.test_client().delete(path(ids, "cgames", "temp-block"))
    assert res.status_code == 200
    assert games(app, ids)["temp_blocked"] is False
    assert family(fake_server).categories["cgames"].temp_blocked is False


def test_the_server_without_premium_refuses_and_the_error_comes_back(
    make: Any, fake_server: FakeTimeLimitServer
) -> None:
    app, ids, _ = make()
    family(fake_server).has_full_version = False
    res = put(app, path(ids, "cgames", "temp-block"), {"minutes": 60})
    assert res.status_code == 502
    assert res.get_json()["code"] == "ACTION_NOT_CONFIRMED"
