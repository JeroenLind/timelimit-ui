"""Plan step E12: the audit log of changes (FR-1100, FR-1101, Q12)."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pytest
from flask import Flask

from ..config import Settings
from ..domain.clock import FakeClock
from ..domain.secret import Secret
from ..factory import create_app
from .conftest import PARENT_PASSWORD, link_app, make_family, seed_children
from .fakeserver import FakeTimeLimitServer

NOW = datetime(2026, 11, 12, 12, 0, tzinfo=timezone.utc)
DAY_MS = 86_400_000


@pytest.fixture
def make(
    data_dir: Path, fake_server: FakeTimeLimitServer
) -> Iterator[Callable[..., tuple[Flask, dict[str, str], FakeClock]]]:
    apps: list[Flask] = []

    def build() -> tuple[Flask, dict[str, str], FakeClock]:
        make_family(fake_server)
        ids = seed_children(fake_server, 20000)
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


def log(app: Flask, child: str | None = None) -> list[dict[str, Any]]:
    path = f"/api/children/{child}/audit" if child else "/api/audit"
    res = app.test_client().get(path)
    assert res.status_code == 200
    return res.get_json()["entries"]  # type: ignore[no-any-return]


def actions_of(entries: list[dict[str, Any]]) -> list[str]:
    return [e["action"] for e in entries]


def test_each_feature_writes_one_confirmed_entry_for_the_right_child(make: Any) -> None:
    app, ids, _ = make()
    c = app.test_client()
    anna = ids["Anna"]
    base = f"/api/children/{anna}/categories/cgames"
    assert (
        c.post(f"{base}/rules", json={"days": [0, 1], "minutes": 30}).status_code == 201
    )
    assert (
        c.put(f"{base}/extra-time", json={"mode": "add", "minutes": 10}).status_code
        == 200
    )
    assert c.put(f"{base}/temp-block", json={"minutes": 30}).status_code == 200
    assert c.post(f"{base}/apps", json={"packages": ["com.a.b"]}).status_code == 200
    entries = log(app, anna)
    assert actions_of(entries) == [
        "ADD_CATEGORY_APPS",
        "UPDATE_CATEGORY_TEMPORARILY_BLOCKED",
        "INCREMENT_CATEGORY_EXTRATIME",
        "CREATE_TIMELIMIT_RULE",
    ]
    assert {e["result"] for e in entries} == {"confirmed"}
    assert {e["category_id"] for e in entries} == {"cgames"}
    assert {e["category_title"] for e in entries} == {"Games"}


def test_other_children_and_the_general_list_stay_separate(make: Any) -> None:
    app, ids, _ = make()
    c = app.test_client()
    c.put(
        f"/api/children/{ids['Anna']}/categories/cgames/extra-time",
        json={"mode": "add", "minutes": 5},
    )
    assert log(app, ids["Ben"]) == []
    assert log(app) == []


def test_a_rejected_change_is_logged_as_not_confirmed(
    make: Any, fake_server: FakeTimeLimitServer
) -> None:
    app, ids, _ = make()
    next(iter(fake_server.world.families.values())).has_full_version = False
    res = app.test_client().put(
        f"/api/children/{ids['Anna']}/categories/cgames/temp-block",
        json={"minutes": 30},
    )
    assert res.status_code == 502
    [entry] = log(app, ids["Anna"])
    assert (entry["action"], entry["result"]) == (
        "UPDATE_CATEGORY_TEMPORARILY_BLOCKED",
        "not_confirmed",
    )


def test_entries_without_a_child_go_to_the_general_list_without_secrets(
    make: Any, fake_server: FakeTimeLimitServer
) -> None:
    app, _, _ = make()
    pid = next(
        u.user_id
        for u in next(iter(fake_server.world.families.values())).users.values()
        if u.type == "parent" and u.name != "Dashboard"
    )
    res = app.test_client().post(
        f"/api/parents/{pid}/password",
        json={"current_password": PARENT_PASSWORD, "new_password": "needle-audit-7"},
    )
    assert res.status_code == 200
    [entry] = log(app)
    assert entry["action"] == "CHANGE_PARENT_PASSWORD"
    text = app.test_client().get("/api/audit").get_data(as_text=True)
    assert "needle-audit-7" not in text
    assert PARENT_PASSWORD not in text
    assert "integrity" not in text


def test_adding_a_child_belongs_to_that_child(make: Any) -> None:
    app, _, _ = make()
    app.test_client().put("/api/settings/test-server", json={"enabled": True})
    res = app.test_client().post(
        "/api/test/users", json={"type": "child", "name": "Mia"}
    )
    new_id = res.get_json()["user_id"]
    assert actions_of(log(app, new_id)) == ["ADD_USER"]


def test_the_newest_entry_comes_first(make: Any) -> None:
    app, ids, clock = make()
    base = f"/api/children/{ids['Anna']}/categories/cgames"
    app.test_client().put(f"{base}/extra-time", json={"mode": "add", "minutes": 5})
    clock.set(NOW + timedelta(minutes=5))
    app.test_client().put(f"{base}/temp-block", json={"minutes": 5})
    entries = log(app, ids["Anna"])
    assert actions_of(entries) == [
        "UPDATE_CATEGORY_TEMPORARILY_BLOCKED",
        "INCREMENT_CATEGORY_EXTRATIME",
    ]
    assert entries[0]["at"] > entries[1]["at"]


def test_entries_older_than_30_days_are_purged_and_the_boundary_is_kept(
    make: Any,
) -> None:
    app, ids, clock = make()
    backend = app.extensions["dashboard"]["backend"]
    profile = app.extensions["dashboard"]["profiles"].url()
    now_ms = int(NOW.timestamp() * 1000)
    anna = ids["Anna"]
    for name, age in (
        ("too_old", 30 * DAY_MS + 1),
        ("boundary", 30 * DAY_MS),
        ("recent", DAY_MS),
    ):
        backend.audit.append(profile, at=now_ms - age, action=name, child_id=anna)
    assert actions_of(log(app, anna)) == ["recent", "boundary"]
    clock.set(NOW + timedelta(days=1))
    assert actions_of(log(app, anna)) == ["recent"]
