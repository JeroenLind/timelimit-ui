"""Plan step E7: apps per category (FR-403..405)."""

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


def app_item(package: str, title: str, launchable: bool = True) -> dict[str, Any]:
    return {
        "packageName": package,
        "title": title,
        "isLaunchable": launchable,
        "recommendation": "none",
    }


@pytest.fixture
def make(
    data_dir: Path, fake_server: FakeTimeLimitServer
) -> Iterator[Callable[..., tuple[Flask, dict[str, str]]]]:
    apps: list[Flask] = []

    def build(with_apps: bool = True) -> tuple[Flask, dict[str, str]]:
        make_family(fake_server)
        ids = seed_children(fake_server, 20000)
        family = next(iter(fake_server.world.families.values()))
        if with_apps:
            tablet = family.devices["dtablet"]
            tablet.installed_apps = [
                app_item("com.game.one", "Alpha game"),
                app_item("com.chat.app", "Chat"),
                app_item("com.school.tool", "School tool"),
            ]
            tablet.apps_version = version_id()
            family.categories["cgames"].apps = ["com.game.one"]
            family.categories["cgames"].apps_version = version_id()
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


def base(ids: dict[str, str]) -> str:
    return f"/api/children/{ids['Anna']}"


def test_the_list_shows_labels_packages_and_current_categories(make: Any) -> None:
    app, ids = make()
    answer = app.test_client().get(f"{base(ids)}/apps").get_json()
    assert answer["known"] is True
    by_package = {a["package"]: a for a in answer["apps"]}
    assert [a["title"] for a in answer["apps"]] == ["Alpha game", "Chat", "School tool"]
    assert by_package["com.game.one"]["category_id"] == "cgames"
    assert by_package["com.game.one"]["category_title"] == "Games"
    assert by_package["com.chat.app"]["category_id"] is None
    assert by_package["com.chat.app"]["devices"] == ["Anna tablet"]


def test_an_empty_list_is_marked_unknown_and_assigned_apps_still_show(
    make: Any, fake_server: FakeTimeLimitServer
) -> None:
    app, ids = make(with_apps=False)
    family(fake_server).categories["cgames"].apps = ["com.hidden.app"]
    family(fake_server).categories["cgames"].apps_version = version_id()
    backend = app.extensions["dashboard"]["backend"]
    link = backend.links.get(fake_server.url)
    backend.puller(fake_server.url).pull(
        fake_server.url, link.device_token, link.family_id
    )
    answer = app.test_client().get(f"{base(ids)}/apps").get_json()
    assert answer["known"] is False
    assert [(a["package"], a["title"]) for a in answer["apps"]] == [
        ("com.hidden.app", "com.hidden.app")
    ]


def test_assigning_apps_moves_them_out_of_the_previous_category(
    make: Any, fake_server: FakeTimeLimitServer
) -> None:
    app, ids = make()
    answer = app.test_client().post(
        f"{base(ids)}/categories/csocia/apps",
        json={"packages": ["com.game.one", "com.chat.app"]},
    )
    assert answer.status_code == 200
    assert family(fake_server).categories["cgames"].apps == []
    assert sorted(family(fake_server).categories["csocia"].apps) == [
        "com.chat.app",
        "com.game.one",
    ]
    shown = {
        a["package"]: a["category_id"]
        for a in app.test_client().get(f"{base(ids)}/apps").get_json()["apps"]
    }
    assert shown["com.game.one"] == "csocia"


def test_a_manual_package_name_is_accepted(
    make: Any, fake_server: FakeTimeLimitServer
) -> None:
    app, ids = make()
    answer = app.test_client().post(
        f"{base(ids)}/categories/cgames/apps", json={"packages": ["org.example.manual"]}
    )
    assert answer.status_code == 200
    assert "org.example.manual" in family(fake_server).categories["cgames"].apps


@pytest.mark.parametrize(
    "packages",
    [
        None,
        [],
        "com.a",
        [""],
        [5],
        ["has space"],
        ["com.a", "com.a"],
        ["x" * 201],
        ["a;b"],
    ],
)
def test_invalid_or_duplicate_packages_are_refused_without_sending(
    packages: Any, make: Any, fake_server: FakeTimeLimitServer
) -> None:
    app, ids = make()
    pushes = fake_server.world.push_requests
    answer = app.test_client().post(
        f"{base(ids)}/categories/cgames/apps", json={"packages": packages}
    )
    assert (answer.status_code, answer.get_json()["field"]) == (400, "packages")
    assert fake_server.world.push_requests == pushes


def test_removing_apps(make: Any, fake_server: FakeTimeLimitServer) -> None:
    app, ids = make()
    answer = app.test_client().post(
        f"{base(ids)}/categories/cgames/apps/remove",
        json={"packages": ["com.game.one"]},
    )
    assert answer.status_code == 200
    assert family(fake_server).categories["cgames"].apps == []
    shown = {
        a["package"]: a["category_id"]
        for a in app.test_client().get(f"{base(ids)}/apps").get_json()["apps"]
    }
    assert shown["com.game.one"] is None


def test_removing_an_app_that_is_not_in_the_category_is_refused(
    make: Any, fake_server: FakeTimeLimitServer
) -> None:
    app, ids = make()
    pushes = fake_server.world.push_requests
    answer = app.test_client().post(
        f"{base(ids)}/categories/cgames/apps/remove",
        json={"packages": ["com.chat.app"]},
    )
    assert (answer.status_code, answer.get_json()["field"]) == (400, "packages")
    assert fake_server.world.push_requests == pushes


def test_a_category_of_another_child_or_an_unknown_one_is_not_found(make: Any) -> None:
    app, ids = make()
    client = app.test_client()
    assert (
        client.post(
            f"{base(ids)}/categories/cschol/apps", json={"packages": ["com.a"]}
        ).status_code
        == 404
    )
    assert (
        client.post(
            f"{base(ids)}/categories/nope/apps", json={"packages": ["com.a"]}
        ).status_code
        == 404
    )
    assert client.get("/api/children/nobody/apps").status_code == 404
