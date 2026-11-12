"""Plan step E2: children overview and child detail from the cache (FR-700..702)."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from datetime import date, datetime, timezone
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
TODAY = (NOW.date() - date(1970, 1, 1)).days


@pytest.fixture
def linked(
    data_dir: Path, fake_server: FakeTimeLimitServer
) -> Iterator[Callable[..., tuple[Flask, dict[str, str]]]]:
    apps: list[Flask] = []

    def build(clock: FakeClock | None = None) -> tuple[Flask, dict[str, str]]:
        make_family(fake_server)
        ids = seed_children(fake_server)
        settings = Settings(
            data_dir=data_dir, server_url=fake_server.url, server_timeout=3.0
        )
        app = create_app(settings, Secret("s"), clock or FakeClock(NOW))
        apps.append(app)
        link_app(app, fake_server)
        return app, ids

    yield build
    for app in apps:
        app.extensions["dashboard"]["backend"].close()


def pull(app: Flask, fake: FakeTimeLimitServer) -> None:
    backend = app.extensions["dashboard"]["backend"]
    url = fake.url
    link = backend.links.get(url)
    backend.puller(url).pull(url, link.device_token, link.family_id)


def family(fake: FakeTimeLimitServer) -> Any:
    return next(iter(fake.world.families.values()))


def minutes(value: int) -> int:
    return value * 60000


def test_overview_lists_children_with_used_time_counts_and_status(linked: Any) -> None:
    app, ids = linked()
    answer = app.test_client().get("/api/children")
    assert answer.status_code == 200
    children = {c["name"]: c for c in answer.get_json()["children"]}
    assert list(children) == ["Anna", "Ben"]
    anna, ben = children["Anna"], children["Ben"]
    assert anna["id"] == ids["Anna"]
    # Games 65 min; Social (a sub-category) is already part of its parent: not counted twice
    assert anna["used_today_ms"] == minutes(65)
    assert (anna["category_count"], anna["device_count"]) == (2, 1)
    assert (ben["used_today_ms"], ben["category_count"], ben["device_count"]) == (
        0,
        1,
        1,
    )
    assert anna["status"] == ben["status"] == "ok"
    assert anna["on_server"] and ben["on_server"]


def test_detail_shows_categories_in_tree_order_and_devices(linked: Any) -> None:
    app, ids = linked()
    detail = app.test_client().get(f"/api/children/{ids['Anna']}").get_json()
    assert detail["child"]["name"] == "Anna" and detail["today"] == TODAY
    games, social = detail["categories"]
    assert (games["title"], games["depth"]) == ("Games", 0)
    assert (social["title"], social["depth"], social["parent_id"]) == (
        "Social",
        1,
        "cgames",
    )
    assert games["used_today_ms"] == minutes(65) and social["used_today_ms"] == minutes(
        20
    )
    assert games["extra_time_ms"] == minutes(15) and social["extra_time_ms"] == 0
    assert (games["app_count"], games["rule_count"]) == (2, 1)
    assert [(d["name"], d["model"]) for d in detail["devices"]] == [
        ("Anna tablet", "Pixel Tablet")
    ]


def test_unknown_child_and_parents_are_not_found(linked: Any) -> None:
    app, _ = linked()
    http = app.test_client()
    assert http.get("/api/children/nobody").status_code == 404
    parent_id = next(
        u.data["id"] for u in app.extensions["dashboard"]["backend"].cache.users(
            app.extensions["dashboard"]["backend"].scope(app.extensions["dashboard"]["profiles"].url())
        ) if u.data["type"] == "parent"
    )  # fmt: skip
    assert http.get(f"/api/children/{parent_id}").get_json()["code"] == "NOT_FOUND"


def test_temporary_block_and_disabled_limits_change_the_status(
    linked: Any, fake_server: FakeTimeLimitServer
) -> None:
    app, ids = linked()
    fam = family(fake_server)
    fam.categories["csocial"].temp_blocked = True
    fam.categories["csocial"].temp_block_end = int(NOW.timestamp() * 1000) + 600000
    fam.categories["csocial"].base_version = version_id()
    fam.users[ids["Ben"]].disable_limits_until = int(NOW.timestamp() * 1000) + 3600000
    fam.user_list_version = version_id()
    pull(app, fake_server)
    children = {
        c["name"]: c
        for c in app.test_client().get("/api/children").get_json()["children"]
    }
    assert children["Anna"]["status"] == "temp_blocked"
    assert children["Ben"]["status"] == "limits_disabled"
    social = (
        app.test_client()
        .get(f"/api/children/{ids['Anna']}")
        .get_json()["categories"][1]
    )
    assert social["temp_blocked"] and social["temp_blocked_until"] is not None


def test_an_expired_temporary_block_is_not_shown(
    linked: Any, fake_server: FakeTimeLimitServer
) -> None:
    app, _ = linked()
    cat = family(fake_server).categories["csocial"]
    cat.temp_blocked, cat.temp_block_end, cat.base_version = (
        True,
        int(NOW.timestamp() * 1000) - 1000,
        version_id(),
    )
    pull(app, fake_server)
    assert (
        app.test_client().get("/api/children").get_json()["children"][0]["status"]
        == "ok"
    )


def test_today_is_the_date_in_the_childs_time_zone(
    linked: Any, fake_server: FakeTimeLimitServer
) -> None:
    clock = FakeClock(datetime(2026, 11, 12, 23, 30, tzinfo=timezone.utc))
    app, ids = linked(clock)
    fam = family(fake_server)
    utc_day = (clock.now().date() - date(1970, 1, 1)).days
    games = fam.categories["cgames"]
    games.used_times = {
        utc_day: {(0, 1439): minutes(10)},
        utc_day + 1: {(0, 1439): minutes(40)},
    }
    games.extra_time_day = -1
    games.used_times_version = games.base_version = version_id()
    fam.users[ids["Anna"]].time_zone = "Pacific/Auckland"  # already 13 November there
    fam.user_list_version = version_id()
    pull(app, fake_server)
    anna = app.test_client().get(f"/api/children/{ids['Anna']}").get_json()
    assert anna["today"] == utc_day + 1
    assert anna["child"]["used_today_ms"] == minutes(40)
    fam.users[ids["Anna"]].time_zone = "UTC"
    fam.user_list_version = version_id()
    pull(app, fake_server)
    assert app.test_client().get(f"/api/children/{ids['Anna']}").get_json()["child"][
        "used_today_ms"
    ] == minutes(10)


def test_extra_time_of_another_day_is_not_counted(
    linked: Any, fake_server: FakeTimeLimitServer
) -> None:
    app, ids = linked()
    cat = family(fake_server).categories["cgames"]
    cat.extra_time_day, cat.base_version = TODAY - 1, version_id()
    pull(app, fake_server)
    games = (
        app.test_client()
        .get(f"/api/children/{ids['Anna']}")
        .get_json()["categories"][0]
    )
    assert games["extra_time_ms"] == 0


def test_a_removed_child_stays_visible_flagged_not_on_server(
    linked: Any, fake_server: FakeTimeLimitServer
) -> None:
    app, ids = linked()
    fam = family(fake_server)
    del fam.users[ids["Ben"]]
    fam.user_list_version = version_id()
    pull(app, fake_server)
    http = app.test_client()
    children = {c["name"]: c for c in http.get("/api/children").get_json()["children"]}
    assert (
        children["Ben"]["on_server"] is False and children["Anna"]["on_server"] is True
    )
    detail = http.get(f"/api/children/{ids['Ben']}")
    assert (
        detail.status_code == 200 and detail.get_json()["child"]["on_server"] is False
    )


def test_an_unknown_time_zone_falls_back_to_utc(
    linked: Any, fake_server: FakeTimeLimitServer
) -> None:
    app, ids = linked()
    family(fake_server).users[ids["Anna"]].time_zone = "Not/AZone"
    family(fake_server).user_list_version = version_id()
    pull(app, fake_server)
    assert (
        app.test_client().get(f"/api/children/{ids['Anna']}").get_json()["today"]
        == TODAY
    )


def test_the_pages_are_served_and_redirect_without_a_link(
    linked: Any, data_dir: Path
) -> None:
    app, ids = linked()
    http = app.test_client()
    assert http.get(f"/children/{ids['Anna']}").status_code == 200
    other = create_app(
        Settings(data_dir=data_dir / "other", server_url="http://127.0.0.1:9"),
        Secret("s"),
    )
    try:
        assert other.test_client().get("/children/x").status_code == 302
    finally:
        other.extensions["dashboard"]["backend"].close()
