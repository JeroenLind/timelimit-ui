"""Plan step E11: the test section (FR-800, FR-801)."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest
from flask import Flask

from ..config import Settings
from ..domain import actions
from ..domain.clock import FakeClock
from ..domain.secret import Secret
from ..factory import create_app
from .conftest import link_app, make_family
from .fakeserver import FakeTimeLimitServer

NOW = datetime(2026, 11, 15, 12, 0, tzinfo=timezone.utc)


@pytest.fixture
def make(
    data_dir: Path, fake_server: FakeTimeLimitServer
) -> Iterator[Callable[..., Flask]]:
    apps: list[Flask] = []

    def build(test_server: bool = True) -> Flask:
        make_family(fake_server)
        settings = Settings(
            data_dir=data_dir, server_url=fake_server.url, server_timeout=3.0
        )
        app = create_app(settings, Secret("s"), FakeClock(NOW))
        apps.append(app)
        link_app(app, fake_server)
        if test_server:
            res = app.test_client().put(
                "/api/settings/test-server", json={"enabled": True}
            )
            assert res.status_code == 200
        return app

    yield build
    for app in apps:
        app.extensions["dashboard"]["backend"].close()


def family(fake: FakeTimeLimitServer) -> Any:
    return next(iter(fake.world.families.values()))


def test_everything_answers_404_while_the_switch_is_off(make: Any) -> None:
    client = make(test_server=False).test_client()
    for path in ("/test", "/test/database", "/api/test/users", "/api/test/database"):
        assert client.get(path).status_code == 404, path
    res = client.post("/api/test/users", json={"type": "child", "name": "X"})
    assert res.status_code == 404
    assert b'id="nav-test"' not in client.get("/").data


def test_the_menu_item_shows_while_the_switch_is_on(make: Any) -> None:
    client = make().test_client()
    assert b'id="nav-test"' in client.get("/").data
    assert client.get("/test").status_code == 200
    assert client.get("/test/database").status_code == 200


def test_adding_a_child_pushes_add_user_first(
    make: Any, fake_server: FakeTimeLimitServer
) -> None:
    client = make().test_client()
    before = len(fake_server.world.action_types)
    res = client.post(
        "/api/test/users",
        json={"type": "child", "name": "Mia", "time_zone": "Europe/Amsterdam"},
    )
    assert res.status_code == 201
    assert fake_server.world.action_types[before] == "ADD_USER"
    kids = [u for u in family(fake_server).users.values() if u.name == "Mia"]
    assert [(u.type, u.time_zone) for u in kids] == [("child", "Europe/Amsterdam")]
    listed = client.get("/api/test/users").get_json()["users"]
    assert ("Mia", "child") in [(u["name"], u["type"]) for u in listed]


def test_adding_a_parent_sends_a_container_the_fake_decrypts(
    make: Any, fake_server: FakeTimeLimitServer
) -> None:
    client = make().test_client()
    res = client.post(
        "/api/test/users", json={"type": "parent", "name": "Pa", "password": "secret1"}
    )
    assert res.status_code == 201, res.get_json()
    parent = next(u for u in family(fake_server).users.values() if u.name == "Pa")
    assert parent.type == "parent"
    assert parent.second_hash.startswith("$2a$")
    assert parent.password_hash.startswith("$2a$")


@pytest.mark.parametrize(
    ("body", "field"),
    [
        ({"type": "pet", "name": "X"}, "type"),
        ({"type": "child", "name": "  "}, "name"),
        ({"type": "child", "name": "X" * 51}, "name"),
        ({"type": "child", "name": "X", "time_zone": "Mars/Base"}, "time_zone"),
        ({"type": "parent", "name": "X", "password": "ab"}, "password"),
    ],
)
def test_invalid_input_is_refused_before_anything_is_pushed(
    make: Any, fake_server: FakeTimeLimitServer, body: dict[str, str], field: str
) -> None:
    client = make().test_client()
    before = len(fake_server.world.action_types)
    res = client.post("/api/test/users", json=body)
    assert res.status_code == 400
    assert res.get_json()["field"] == field
    assert len(fake_server.world.action_types) == before


def test_a_server_that_does_not_confirm_gives_502(
    make: Any, fake_server: FakeTimeLimitServer, monkeypatch: pytest.MonkeyPatch
) -> None:
    client = make().test_client()
    existing = next(iter(family(fake_server).users.values()))
    # reuse an id: the fake refuses the action and asks for a full sync
    monkeypatch.setattr(actions, "new_id", lambda: existing.user_id)
    res = client.post("/api/test/users", json={"type": "child", "name": "Dup"})
    assert res.status_code == 502
    assert res.get_json()["code"] == "ACTION_NOT_CONFIRMED"


def test_the_database_page_lists_tables_and_hides_secrets(make: Any) -> None:
    client = make().test_client()
    data = client.get("/api/test/database").get_json()
    names = {t["name"] for t in data["tables"]}
    assert {"link", "users", "settings"} <= names
    link = next(t for t in data["tables"] if t["name"] == "link")
    column = link["columns"].index("device_token")
    assert all(row[column] == "***" for row in link["rows"])
    assert link["rows"]
