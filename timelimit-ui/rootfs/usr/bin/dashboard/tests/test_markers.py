"""Plan step E4: conflict warning and clean-up (FR-206, FR-208, FR-209, TR-307)."""

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


def family(fake: FakeTimeLimitServer) -> Any:
    return next(iter(fake.world.families.values()))


def pull(app: Flask, fake: FakeTimeLimitServer) -> None:
    backend = app.extensions["dashboard"]["backend"]
    link = backend.links.get(fake.url)
    backend.puller(fake.url).pull(fake.url, link.device_token, link.family_id)


def shown(app: Flask, ids: dict[str, str]) -> dict[str, Any]:
    detail = app.test_client().get(f"/api/children/{ids['Anna']}").get_json()
    return next(c for c in detail["categories"] if c["id"] == "cgames")["rules"][0]  # type: ignore[no-any-return]


def change_elsewhere(app: Flask, fake: FakeTimeLimitServer, minutes: int) -> None:
    games = family(fake).categories["cgames"]
    games.rules["rule01"].max_time = minutes * 60000
    games.rules_version = version_id()
    pull(app, fake)


FORM = {"days": [0, 1, 2], "minutes": 45}


def test_the_rule_view_carries_a_version_that_follows_the_data(
    make: Any, fake_server: FakeTimeLimitServer
) -> None:
    app, ids = make()
    before = shown(app, ids)["version"]
    assert shown(app, ids)["version"] == before
    change_elsewhere(app, fake_server, 30)
    assert shown(app, ids)["version"] != before


def test_saving_with_the_version_it_started_with_works(
    make: Any, fake_server: FakeTimeLimitServer
) -> None:
    app, ids = make()
    version = shown(app, ids)["version"]
    answer = app.test_client().put(
        f"/api/children/{ids['Anna']}/rules/rule01", json={**FORM, "version": version}
    )
    assert answer.status_code == 200
    assert (
        family(fake_server).categories["cgames"].rules["rule01"].max_time == 45 * 60000
    )


def test_a_change_elsewhere_gives_a_conflict_and_sends_nothing(
    make: Any, fake_server: FakeTimeLimitServer
) -> None:
    app, ids = make()
    version = shown(app, ids)["version"]
    change_elsewhere(app, fake_server, 30)
    pushes = fake_server.world.push_requests
    answer = app.test_client().put(
        f"/api/children/{ids['Anna']}/rules/rule01", json={**FORM, "version": version}
    )
    body = answer.get_json()
    assert (answer.status_code, body["code"], body["field"]) == (
        409,
        "CONFLICT",
        "version",
    )
    assert fake_server.world.push_requests == pushes
    # the parent confirms: no version means last writer wins
    again = app.test_client().put(
        f"/api/children/{ids['Anna']}/rules/rule01", json=FORM
    )
    assert again.status_code == 200
    assert (
        family(fake_server).categories["cgames"].rules["rule01"].max_time == 45 * 60000
    )


def test_delete_checks_the_version_too(
    make: Any, fake_server: FakeTimeLimitServer
) -> None:
    app, ids = make()
    version = shown(app, ids)["version"]
    change_elsewhere(app, fake_server, 30)
    url = f"/api/children/{ids['Anna']}/rules/rule01"
    assert app.test_client().delete(f"{url}?version={version}").status_code == 409
    assert "rule01" in family(fake_server).categories["cgames"].rules
    assert app.test_client().delete(url).status_code == 200


def test_clean_up_removes_what_the_server_no_longer_reports(
    make: Any, fake_server: FakeTimeLimitServer
) -> None:
    app, ids = make()
    client = app.test_client()
    assert [n["code"] for n in client.get("/api/notices").get_json()["notices"]] == []
    fam = family(fake_server)
    del fam.users[ids["Ben"]]
    fam.user_list_version = version_id()
    pull(app, fake_server)
    notices = client.get("/api/notices").get_json()["notices"]
    assert [
        (n["code"], n["count"]) for n in notices if n["code"] == "ITEMS_MISSING"
    ] == [("ITEMS_MISSING", 1)]
    assert (
        len(client.get("/api/children").get_json()["children"]) == 2
    )  # kept and flagged (FR-206)
    answer = client.post("/api/cleanup")
    assert answer.get_json()["removed"] >= 1
    assert [c["name"] for c in client.get("/api/children").get_json()["children"]] == [
        "Anna"
    ]
    assert all(
        n["code"] != "ITEMS_MISSING"
        for n in client.get("/api/notices").get_json()["notices"]
    )
    assert client.post("/api/cleanup").get_json()["removed"] == 0
    entries = app.extensions["dashboard"]["backend"].audit.entries(fake_server.url)
    assert "cleanup" in [e.action for e in entries]


def test_after_a_full_resync_no_flag_remains_for_what_the_server_reports(
    make: Any, fake_server: FakeTimeLimitServer
) -> None:
    app, ids = make()
    fam = family(fake_server)
    removed = fam.users.pop(ids["Ben"])
    fam.user_list_version = version_id()
    pull(app, fake_server)
    assert (
        app.extensions["dashboard"]["backend"].cache.count_missing(
            app.extensions["dashboard"]["backend"].scope(fake_server.url)
        )
        >= 1
    )
    fam.users[ids["Ben"]] = removed  # it comes back
    fam.user_list_version = version_id()
    app.extensions["dashboard"]["backend"].db.reset_cache()
    pull(app, fake_server)
    children = app.test_client().get("/api/children").get_json()["children"]
    assert all(c["on_server"] for c in children) and len(children) == 2
