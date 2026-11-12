"""Plan step E3: time limit rules (FR-300..303, FR-305)."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest
from flask import Flask

from ..config import Settings
from ..domain.secret import Secret
from ..factory import create_app
from ..services.rules import parse_rule
from .conftest import link_app, make_family, seed_children
from .fakeserver import FakeTimeLimitServer
from .fakeserver.state import Rule

GOOD: dict[str, Any] = {"days": [0, 1, 2, 3, 4], "minutes": 90}


@pytest.fixture
def linked(
    data_dir: Path, fake_server: FakeTimeLimitServer
) -> Iterator[Callable[..., tuple[Flask, dict[str, str]]]]:
    apps: list[Flask] = []

    def build(fake: FakeTimeLimitServer | None = None) -> tuple[Flask, dict[str, str]]:
        fake = fake or fake_server
        make_family(fake)
        ids = seed_children(fake)
        settings = Settings(data_dir=data_dir, server_url=fake.url, server_timeout=3.0)
        app = create_app(settings, Secret("s"))
        apps.append(app)
        link_app(app, fake)
        return app, ids

    yield build
    for app in apps:
        app.extensions["dashboard"]["backend"].close()


def family(fake: FakeTimeLimitServer) -> Any:
    return next(iter(fake.world.families.values()))


def rules_of(app: Flask, child: str, category: str) -> list[dict[str, Any]]:
    detail = app.test_client().get(f"/api/children/{child}").get_json()
    return next(c for c in detail["categories"] if c["id"] == category)["rules"]  # type: ignore[no-any-return]


# -- validation (nothing is sent for an invalid form) ---------------------------------------------------------------
@pytest.mark.parametrize(
    ("change", "field"),
    [
        ({"days": []}, "days"),
        ({"days": [7]}, "days"),
        ({"days": ["mon"]}, "days"),
        ({"days": None}, "days"),
        ({"minutes": -1}, "minutes"),
        ({"minutes": 1441}, "minutes"),
        ({"minutes": "90"}, "minutes"),
        ({"minutes": None}, "minutes"),
        ({"start": "09:00"}, "end"),
        ({"end": "09:00"}, "start"),
        ({"start": "18:00", "end": "09:00"}, "end"),
        ({"start": "24:00", "end": "24:30"}, "start"),
        ({"start": "9:75", "end": "10:00"}, "start"),
        ({"session_minutes": 30}, "pause_minutes"),
        ({"pause_minutes": 5}, "session_minutes"),
        ({"session_minutes": -5, "pause_minutes": 5}, "session_minutes"),
    ],
)
def test_parse_rule_refuses_bad_input_naming_the_field(
    change: dict[str, Any], field: str
) -> None:
    from ..domain.errors import DashboardError

    with pytest.raises(DashboardError) as raised:
        parse_rule({**GOOD, **change})
    assert raised.value.field == field


def test_parse_rule_builds_the_wire_values() -> None:
    fields = parse_rule(
        {
            **GOOD,
            "start": "08:30",
            "end": "20:00",
            "session_minutes": 45,
            "pause_minutes": 10,
            "per_day": True,
            "extra_time": True,
        }
    )
    assert fields == {
        "time_ms": 90 * 60000,
        "days": 0b0011111,
        "extra_time": True,
        "start": 510,
        "end": 1200,
        "dur": 45 * 60000,
        "pause": 10 * 60000,
        "per_day": True,
    }


def test_parse_rule_without_window_or_session_sends_neither() -> None:
    fields = parse_rule(GOOD)
    assert (fields["start"], fields["end"], fields["dur"], fields["pause"]) == (
        None,
    ) * 4
    assert parse_rule({**GOOD, "minutes": 0})["time_ms"] == 0
    assert parse_rule({**GOOD, "minutes": 1440})["time_ms"] == 1440 * 60000


# -- create, update, delete against the fake server ----------------------------------------------------------------------
def test_create_shows_the_rule_with_the_same_values_after_the_pull(
    linked: Any, fake_server: FakeTimeLimitServer
) -> None:
    app, ids = linked()
    body = {
        **GOOD,
        "start": "08:00",
        "end": "20:30",
        "session_minutes": 30,
        "pause_minutes": 5,
        "per_day": True,
    }
    answer = app.test_client().post(
        f"/api/children/{ids['Anna']}/categories/{ids['Games']}/rules", json=body
    )
    assert answer.status_code == 201
    rule_id = answer.get_json()["rule_id"]
    on_server = family(fake_server).categories[ids["Games"]].rules[rule_id]
    assert (on_server.day_mask, on_server.max_time, on_server.start, on_server.end) == (
        31,
        90 * 60000,
        480,
        1230,
    )
    assert (on_server.session, on_server.pause, on_server.per_day) == (
        30 * 60000,
        5 * 60000,
        True,
    )
    shown = next(
        r for r in rules_of(app, ids["Anna"], ids["Games"]) if r["id"] == rule_id
    )
    assert shown == {
        "id": rule_id,
        "days": [0, 1, 2, 3, 4],
        "minutes": 90,
        "extra_time": False,
        "start": 480,
        "end": 1230,
        "session_minutes": 30,
        "pause_minutes": 5,
        "per_day": True,
        "expires_at": None,
        "on_server": True,
    }
    assert (
        len(rules_of(app, ids["Anna"], ids["Games"])) == 2
    )  # the seeded rule is still there


def test_a_rule_pulled_from_the_server_with_an_expiry_is_shown(linked: Any) -> None:
    with FakeTimeLimitServer(rule_expiry=True) as fake:
        app, ids = linked(fake)
        family(fake).categories[ids["Games"]].rules["rexp"] = Rule(
            "rexp", False, 3, 600000, 0, 1439, 0, 0, False, expires=1893456000000
        )
        backend = app.extensions["dashboard"]["backend"]
        link = backend.links.get(fake.url)
        backend.puller(fake.url).full_resync(
            fake.url, link.device_token, link.family_id
        )
        shown = next(
            r for r in rules_of(app, ids["Anna"], ids["Games"]) if r["id"] == "rexp"
        )
        assert shown["expires_at"] == 1893456000000
        assert (shown["days"], shown["minutes"]) == ([0, 1], 10)


def test_update_changes_the_rule_on_the_server(
    linked: Any, fake_server: FakeTimeLimitServer
) -> None:
    app, ids = linked()
    body = {"days": [5, 6], "minutes": 45, "start": "10:00", "end": "12:00"}
    answer = app.test_client().put(
        f"/api/children/{ids['Anna']}/rules/rule01", json=body
    )
    assert answer.status_code == 200
    rule = family(fake_server).categories[ids["Games"]].rules["rule01"]
    assert (rule.day_mask, rule.max_time, rule.start, rule.end) == (
        96,
        45 * 60000,
        600,
        720,
    )
    shown = next(
        r for r in rules_of(app, ids["Anna"], ids["Games"]) if r["id"] == "rule01"
    )
    assert (shown["days"], shown["minutes"], shown["start"], shown["end"]) == (
        [5, 6],
        45,
        600,
        720,
    )


def test_delete_removes_the_rule(linked: Any, fake_server: FakeTimeLimitServer) -> None:
    app, ids = linked()
    assert (
        app.test_client()
        .delete(f"/api/children/{ids['Anna']}/rules/rule01")
        .status_code
        == 200
    )
    assert "rule01" not in family(fake_server).categories[ids["Games"]].rules
    assert rules_of(app, ids["Anna"], ids["Games"]) == []


def test_an_invalid_form_sends_nothing(
    linked: Any, fake_server: FakeTimeLimitServer
) -> None:
    app, ids = linked()
    before = fake_server.world.push_requests
    http = app.test_client()
    path = f"/api/children/{ids['Anna']}/categories/{ids['Games']}/rules"
    bad = http.post(path, json={**GOOD, "start": "18:00", "end": "09:00"})
    assert bad.status_code == 400
    body = bad.get_json()
    assert (body["code"], body["field"]) == ("INVALID_INPUT", "end")
    assert (
        http.put(
            f"/api/children/{ids['Anna']}/rules/rule01", json={"days": [], "minutes": 5}
        ).status_code
        == 400
    )
    assert (
        http.post(path, data="not json", content_type="application/json").status_code
        == 400
    )
    assert fake_server.world.push_requests == before


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("post", "/api/children/{anna}/categories/nope/rules"),
        ("post", "/api/children/{anna}/categories/{school}/rules"),  # Ben's category
        ("post", "/api/children/nobody/categories/{games}/rules"),
        ("put", "/api/children/{anna}/rules/nope"),
        ("delete", "/api/children/{ben}/rules/rule01"),  # rule01 belongs to Anna
    ],
)
def test_unknown_children_categories_and_rules_are_not_found(
    method: str, path: str, linked: Any, fake_server: FakeTimeLimitServer
) -> None:
    app, ids = linked()
    before = fake_server.world.push_requests
    path = path.format(
        anna=ids["Anna"], ben=ids["Ben"], games=ids["Games"], school=ids["School"]
    )
    answer = getattr(app.test_client(), method)(path, json=GOOD)
    assert answer.status_code == 404 and answer.get_json()["code"] == "NOT_FOUND"
    assert fake_server.world.push_requests == before


# -- failures ------------------------------------------------------------------------------------------------------------------
def test_a_rejected_change_is_rolled_back_and_reported(
    linked: Any, fake_server: FakeTimeLimitServer
) -> None:
    app, ids = linked()
    # someone else deleted the rule; the dashboard has not heard yet, so the update is dropped by the server
    del family(fake_server).categories[ids["Games"]].rules["rule01"]
    answer = app.test_client().put(
        f"/api/children/{ids['Anna']}/rules/rule01", json=GOOD
    )
    assert answer.status_code == 502
    assert answer.get_json()["code"] == "ACTION_NOT_CONFIRMED"
    shown = rules_of(app, ids["Anna"], ids["Games"])
    # the cache now shows what the server has: the rule is flagged as gone, not silently kept as valid
    assert [r["on_server"] for r in shown] == [False]


def test_changes_are_refused_while_the_server_is_down(
    linked: Any, fake_server: FakeTimeLimitServer
) -> None:
    app, ids = linked()
    fake_server.stop()
    before = fake_server.world.push_requests
    answer = app.test_client().delete(f"/api/children/{ids['Anna']}/rules/rule01")
    assert (
        answer.status_code == 503 and answer.get_json()["code"] == "READ_ONLY_OFFLINE"
    )
    assert fake_server.world.push_requests == before
    assert (
        len(rules_of(app, ids["Anna"], ids["Games"])) == 1
    )  # still readable from the cache


def test_a_change_tells_the_browsers_to_read_again(linked: Any) -> None:
    app, ids = linked()
    hub = app.extensions["dashboard"]["hub"]
    subscription = hub.subscribe()
    app.test_client().delete(f"/api/children/{ids['Anna']}/rules/rule01")
    events: list[Any] = []
    while not subscription.events.empty():
        events.append(subscription.events.get_nowait())
    assert any(e.get("type") == "changed" for e in events)
    hub.unsubscribe(subscription)
