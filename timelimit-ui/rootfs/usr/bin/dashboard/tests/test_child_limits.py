"""Plan step E13: all limits of a child off until a time (FR-505)."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import pytest
from flask import Flask

from ..config import Settings
from ..domain import actions
from ..domain.clock import FakeClock
from ..domain.secret import Secret
from ..factory import create_app
from .conftest import link_app, make_family, seed_children
from .fakeserver import FakeTimeLimitServer

NOW = datetime(2026, 11, 12, 12, 0, tzinfo=timezone.utc)
NOW_MS = int(NOW.timestamp() * 1000)
MIN = 60000


@pytest.fixture
def make(
    data_dir: Path, fake_server: FakeTimeLimitServer
) -> Iterator[Callable[[], tuple[Flask, dict[str, str], FakeClock]]]:
    apps: list[Flask] = []

    def build() -> tuple[Flask, dict[str, str], FakeClock]:
        make_family(fake_server)
        day = (NOW.date() - date(1970, 1, 1)).days
        ids = seed_children(fake_server, day)
        clock = FakeClock(NOW)
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


def put(app: Flask, ids: dict[str, str], body: Any) -> Any:
    return app.test_client().put(
        f"/api/children/{ids['Anna']}/disable-limits", json=body
    )


def child(app: Flask, ids: dict[str, str]) -> dict[str, Any]:
    detail: dict[str, Any] = (
        app.test_client().get(f"/api/children/{ids['Anna']}").get_json()
    )
    result: dict[str, Any] = detail["child"]
    return result


def test_builder_matches_the_contract() -> None:
    assert actions.set_user_disable_limits_until("uanna0", 5) == {
        "type": "SET_USER_DISABLE_LIMITS_UNTIL",
        "childId": "uanna0",
        "time": 5,
    }


def test_switch_off_for_an_hour_then_on_again(
    make: Any, fake_server: FakeTimeLimitServer
) -> None:
    app, ids, _ = make()
    assert child(app, ids)["limits_disabled_until"] is None
    assert put(app, ids, {"minutes": 60}).status_code == 200
    assert (
        family(fake_server).users[ids["Anna"]].disable_limits_until == NOW_MS + 60 * MIN
    )
    view = child(app, ids)
    assert view["limits_disabled_until"] == NOW_MS + 60 * MIN
    assert view["status"] == "limits_disabled"
    assert put(app, ids, {"minutes": 0}).status_code == 200
    assert family(fake_server).users[ids["Anna"]].disable_limits_until == 0
    assert child(app, ids)["limits_disabled_until"] is None


def test_an_ended_period_counts_as_none(make: Any) -> None:
    app, ids, clock = make()
    put(app, ids, {"minutes": 30})
    clock.set(datetime(2026, 11, 12, 13, 0, tzinfo=timezone.utc))
    assert child(app, ids)["limits_disabled_until"] is None


@pytest.mark.parametrize("minutes", [-1, 10081, 1.5, "60", None, True])
def test_invalid_minutes_are_refused_and_nothing_is_sent(
    make: Any, fake_server: FakeTimeLimitServer, minutes: Any
) -> None:
    app, ids, _ = make()
    before = len(fake_server.world.action_types)
    res = put(app, ids, {"minutes": minutes})
    assert res.status_code == 400
    assert res.get_json()["field"] == "minutes"
    assert len(fake_server.world.action_types) == before


def test_unknown_child_is_not_found(make: Any) -> None:
    app, _, _ = make()
    res = app.test_client().put(
        "/api/children/nobody/disable-limits", json={"minutes": 5}
    )
    assert res.status_code == 404


def test_without_premium_the_server_refuses(
    make: Any, fake_server: FakeTimeLimitServer
) -> None:
    app, ids, _ = make()
    family(fake_server).has_full_version = False
    res = put(app, ids, {"minutes": 60})
    assert res.status_code == 502
    assert res.get_json()["code"] == "ACTION_NOT_CONFIRMED"
    assert child(app, ids)["limits_disabled_until"] is None


def test_the_change_is_in_the_audit_log(make: Any) -> None:
    app, ids, _ = make()
    put(app, ids, {"minutes": 60})
    entries = app.test_client().get(f"/api/children/{ids['Anna']}/audit").get_json()
    assert any("SET_USER_DISABLE_LIMITS_UNTIL" in str(e) for e in entries["entries"])
