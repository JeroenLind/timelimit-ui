"""Plan step E6b: category settings (FR-402 groups 2 and 3, Q5a)."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from datetime import datetime, timezone
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

NOW = datetime(2026, 11, 12, 12, 0, tzinfo=timezone.utc)


@pytest.fixture
def make(
    data_dir: Path, fake_server: FakeTimeLimitServer
) -> Iterator[Callable[[], tuple[Flask, dict[str, str]]]]:
    apps: list[Flask] = []

    def build() -> tuple[Flask, dict[str, str]]:
        make_family(fake_server)
        ids = seed_children(fake_server, 20000)
        settings = Settings(
            data_dir=data_dir, server_url=fake_server.url, server_timeout=3.0
        )
        app = create_app(settings, Secret("s"), FakeClock(NOW))
        apps.append(app)
        link_app(app, fake_server)
        return app, ids

    yield build
    for app in apps:
        app.extensions["dashboard"]["backend"].close()


def games(fake: FakeTimeLimitServer) -> Any:
    return next(iter(fake.world.families.values())).categories["cgames"]


def shown(app: Flask, ids: dict[str, str]) -> dict[str, Any]:
    detail = app.test_client().get(f"/api/children/{ids['Anna']}").get_json()
    return next(c for c in detail["categories"] if c["id"] == "cgames")


def url(ids: dict[str, str], part: str) -> str:
    return f"/api/children/{ids['Anna']}/categories/cgames/{part}"


def test_defaults_are_shown(make: Any) -> None:
    app, ids = make()
    cat = shown(app, ids)
    assert cat["block_notifications"] is False
    assert (cat["notification_delay_minutes"], cat["time_warning_minutes"]) == (0, [])
    assert (cat["battery_charging"], cat["battery_mobile"]) == (0, 0)
    assert (cat["network_count"], cat["network_list_enabled"]) == (0, False)


def test_block_all_notifications_with_a_delay(
    make: Any, fake_server: FakeTimeLimitServer
) -> None:
    app, ids = make()
    answer = app.test_client().put(
        url(ids, "notifications"), json={"blocked": True, "delay_minutes": 5}
    )
    assert answer.status_code == 200
    assert (
        games(fake_server).block_all_notifications,
        games(fake_server).block_notification_delay,
    ) == (True, 300000)
    cat = shown(app, ids)
    assert cat["block_notifications"] and cat["notification_delay_minutes"] == 5
    assert (
        app.test_client()
        .put(url(ids, "notifications"), json={"blocked": False})
        .status_code
        == 200
    )
    assert games(fake_server).block_all_notifications is False
    assert (
        games(fake_server).block_notification_delay == 300000
    )  # untouched without a delay


@pytest.mark.parametrize(
    "body",
    [
        None,
        {},
        {"blocked": 1},
        {"blocked": True, "delay_minutes": -1},
        {"blocked": True, "delay_minutes": "5"},
        {"blocked": True, "delay_minutes": 99999},
    ],
)
def test_invalid_notification_input_is_refused_without_sending(
    body: Any, make: Any, fake_server: FakeTimeLimitServer
) -> None:
    app, ids = make()
    pushes = fake_server.world.push_requests
    assert (
        app.test_client().put(url(ids, "notifications"), json=body).status_code == 400
    )
    assert fake_server.world.push_requests == pushes


def test_time_warnings_send_only_the_difference(
    make: Any, fake_server: FakeTimeLimitServer
) -> None:
    app, ids = make()
    client = app.test_client()
    before = len(fake_server.world.action_types)
    assert (
        client.put(url(ids, "time-warnings"), json={"minutes": [1, 10]}).status_code
        == 200
    )
    assert fake_server.world.action_types[before:] == ["UPDATE_CATEGORY_TIME_WARNINGS"]
    assert games(fake_server).time_warnings == 0b01001
    assert shown(app, ids)["time_warning_minutes"] == [1, 10]
    before = len(fake_server.world.action_types)
    assert (
        client.put(url(ids, "time-warnings"), json={"minutes": [10, 15]}).status_code
        == 200
    )
    assert (
        fake_server.world.action_types[before:] == ["UPDATE_CATEGORY_TIME_WARNINGS"] * 2
    )
    assert games(fake_server).time_warnings == 0b11000
    pushes = fake_server.world.push_requests
    assert (
        client.put(url(ids, "time-warnings"), json={"minutes": [15, 10]}).status_code
        == 200
    )
    assert fake_server.world.push_requests == pushes  # unchanged: nothing sent
    assert (
        client.put(url(ids, "time-warnings"), json={"minutes": []}).status_code == 200
    )
    assert games(fake_server).time_warnings == 0


@pytest.mark.parametrize("minutes", [None, "5", [2], [True], [1, "3"], [0]])
def test_invalid_time_warnings_are_refused(minutes: Any, make: Any) -> None:
    app, ids = make()
    answer = app.test_client().put(url(ids, "time-warnings"), json={"minutes": minutes})
    assert (answer.status_code, answer.get_json()["field"]) == (400, "minutes")


def test_battery_limits(make: Any, fake_server: FakeTimeLimitServer) -> None:
    app, ids = make()
    assert (
        app.test_client()
        .put(url(ids, "battery"), json={"charging": 15, "mobile": 40})
        .status_code
        == 200
    )
    assert (
        games(fake_server).min_battery_charging,
        games(fake_server).min_battery_mobile,
    ) == (15, 40)
    cat = shown(app, ids)
    assert (cat["battery_charging"], cat["battery_mobile"]) == (15, 40)
    assert (
        app.test_client()
        .put(url(ids, "battery"), json={"charging": 0, "mobile": 0})
        .status_code
        == 200
    )
    assert (
        games(fake_server).min_battery_charging,
        games(fake_server).min_battery_mobile,
    ) == (0, 0)


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"charging": 5},
        {"charging": 101, "mobile": 0},
        {"charging": 0, "mobile": -1},
        {"charging": "5", "mobile": 5},
    ],
)
def test_invalid_battery_input_is_refused(body: Any, make: Any) -> None:
    app, ids = make()
    assert app.test_client().put(url(ids, "battery"), json=body).status_code == 400


def test_the_network_list_flag_and_the_reset(
    make: Any, fake_server: FakeTimeLimitServer
) -> None:
    app, ids = make()
    client = app.test_client()
    games(fake_server).networks = [{"itemId": "net001", "hashedNetworkId": "a" * 40}]
    games(fake_server).base_version = version_id()
    backend = app.extensions["dashboard"]["backend"]
    link = backend.links.get(fake_server.url)
    backend.puller(fake_server.url).pull(
        fake_server.url, link.device_token, link.family_id
    )
    assert shown(app, ids)["network_count"] == 1
    assert (
        client.put(url(ids, "network-list"), json={"enabled": True}).status_code == 200
    )
    assert games(fake_server).flags == 1 and shown(app, ids)["network_list_enabled"]
    pushes = fake_server.world.push_requests
    assert (
        client.put(url(ids, "network-list"), json={"enabled": True}).status_code == 200
    )
    assert fake_server.world.push_requests == pushes  # already on
    assert client.delete(url(ids, "networks")).status_code == 200
    assert games(fake_server).networks == [] and shown(app, ids)["network_count"] == 0
    assert (
        client.put(url(ids, "network-list"), json={"enabled": False}).status_code == 200
    )
    assert games(fake_server).flags == 0


def test_unknown_category_and_non_boolean_flag(make: Any) -> None:
    app, ids = make()
    base = f"/api/children/{ids['Anna']}/categories/nope"
    assert (
        app.test_client()
        .put(f"{base}/battery", json={"charging": 1, "mobile": 1})
        .status_code
        == 404
    )
    assert app.test_client().delete(f"{base}/networks").status_code == 404
    assert (
        app.test_client()
        .put(url(ids, "network-list"), json={"enabled": "yes"})
        .status_code
        == 400
    )
