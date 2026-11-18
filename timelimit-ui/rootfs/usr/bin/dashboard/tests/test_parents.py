"""Plan step E10: password actions and the "Dashboard" parent (FR-901, FR-902, Q13)."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest
from flask import Flask

from ..config import Settings
from ..domain import passwords
from ..domain.secret import Secret
from ..factory import create_app
from ..logs import configure_logging, shutdown_logging
from .conftest import PARENT_PASSWORD, link_app, make_family
from .fakeserver import FakeTimeLimitServer


@pytest.fixture
def make(
    data_dir: Path, fake_server: FakeTimeLimitServer
) -> Iterator[Callable[..., Flask]]:
    apps: list[Flask] = []

    def build(**overrides: Any) -> Flask:
        make_family(fake_server)
        settings = Settings(
            data_dir=data_dir,
            server_url=fake_server.url,
            server_timeout=3.0,
            **overrides,
        )
        app = create_app(settings, Secret("s"))
        apps.append(app)
        link_app(app, fake_server)
        return app

    yield build
    for app in apps:
        app.extensions["dashboard"]["backend"].close()
    shutdown_logging()


def family(fake: FakeTimeLimitServer) -> Any:
    return next(iter(fake.world.families.values()))


def user(fake: FakeTimeLimitServer, name: str) -> Any:
    return next(u for u in family(fake).users.values() if u.name == name)


def parents(app: Flask) -> Any:
    return app.test_client().get("/api/parents").get_json()


def starter_id(fake: FakeTimeLimitServer) -> str:
    found: str = next(
        u.user_id
        for u in family(fake).users.values()
        if u.type == "parent" and u.name != "Dashboard"
    )
    return found


def test_the_overview_lists_parents_and_the_dashboard_state(
    make: Any, fake_server: FakeTimeLimitServer
) -> None:
    data = parents(make())
    assert data["parents"][0]["name"] == "Dashboard"
    assert data["parents"][0]["is_dashboard"] is True
    assert len(data["parents"]) == 2
    assert data["dashboard"] == {
        "id": user(fake_server, "Dashboard").user_id,
        "signed_in": True,
        "keep_signed_in": True,
    }


def test_changing_a_password_is_accepted_by_the_server(
    make: Any, fake_server: FakeTimeLimitServer
) -> None:
    app = make()
    pid = starter_id(fake_server)
    before = len(fake_server.world.action_types)
    res = app.test_client().post(
        f"/api/parents/{pid}/password",
        json={"current_password": PARENT_PASSWORD, "new_password": "brand new 1"},
    )
    assert res.status_code == 200, res.get_json()
    assert fake_server.world.action_types[before:] == ["CHANGE_PARENT_PASSWORD"]
    stored = family(fake_server).users[pid]
    assert passwords.password_matches("brand new 1", stored.password_hash)
    assert stored.second_hash == passwords.second_hash_for(
        "brand new 1", stored.second_salt
    )
    # the cache follows: the old password no longer matches
    res = app.test_client().post(
        f"/api/parents/{pid}/password",
        json={"current_password": PARENT_PASSWORD, "new_password": "another 2"},
    )
    assert res.status_code == 403


def test_a_wrong_current_password_changes_nothing(
    make: Any, fake_server: FakeTimeLimitServer
) -> None:
    app = make()
    pid = starter_id(fake_server)
    old = family(fake_server).users[pid].password_hash
    before = len(fake_server.world.action_types)
    res = app.test_client().post(
        f"/api/parents/{pid}/password",
        json={"current_password": "wrong", "new_password": "brand new 1"},
    )
    assert res.status_code == 403
    body = res.get_json()
    assert (body["code"], body["field"]) == ("INVALID_PASSWORD", "current_password")
    assert len(fake_server.world.action_types) == before
    assert family(fake_server).users[pid].password_hash == old


@pytest.mark.parametrize(
    ("body", "field"),
    [
        ({"new_password": "long enough"}, "current_password"),
        ({"current_password": PARENT_PASSWORD, "new_password": "abc"}, "new_password"),
        ({"current_password": PARENT_PASSWORD}, "new_password"),
    ],
)
def test_bad_input_is_refused(
    make: Any, fake_server: FakeTimeLimitServer, body: dict[str, str], field: str
) -> None:
    app = make()
    res = app.test_client().post(
        f"/api/parents/{starter_id(fake_server)}/password", json=body
    )
    assert res.status_code == 400
    assert res.get_json()["field"] == field


def test_an_unknown_parent_or_a_child_is_404(
    make: Any, fake_server: FakeTimeLimitServer
) -> None:
    from .conftest import seed_children

    app = make()
    ids = seed_children(fake_server, 20000)
    backend = app.extensions["dashboard"]["backend"]
    link = backend.links.get(fake_server.url)
    backend.puller(fake_server.url).pull(
        fake_server.url, link.device_token, link.family_id
    )
    body = {"current_password": "x", "new_password": "long enough"}
    for target in ("nobody", ids["Anna"]):
        res = app.test_client().post(f"/api/parents/{target}/password", json=body)
        assert res.status_code == 404, target


def test_the_dashboard_parent_can_change_its_own_password(
    make: Any, fake_server: FakeTimeLimitServer
) -> None:
    app = make()
    did = user(fake_server, "Dashboard").user_id
    res = app.test_client().post(
        f"/api/parents/{did}/password",
        json={"current_password": PARENT_PASSWORD, "new_password": "dash new 9"},
    )
    assert res.status_code == 200, res.get_json()
    assert passwords.password_matches(
        "dash new 9", user(fake_server, "Dashboard").password_hash
    )
    assert parents(app)["dashboard"]["signed_in"] is True


def test_rules_and_categories_need_no_password(
    make: Any, fake_server: FakeTimeLimitServer
) -> None:
    app = make()
    from .conftest import seed_children

    ids = seed_children(fake_server, 20000)
    backend = app.extensions["dashboard"]["backend"]
    link = backend.links.get(fake_server.url)
    backend.puller(fake_server.url).pull(
        fake_server.url, link.device_token, link.family_id
    )
    res = app.test_client().post(
        f"/api/children/{ids['Anna']}/categories", json={"title": "Music"}
    )
    assert res.status_code == 201


def test_a_device_signed_in_as_someone_else_shows_up_and_can_sign_in_again(
    make: Any, fake_server: FakeTimeLimitServer
) -> None:
    app = make()
    backend = app.extensions["dashboard"]["backend"]
    link = backend.links.get(fake_server.url)
    device = family(fake_server).devices[link.own_device_id]
    device.current_user_id = starter_id(
        fake_server
    )  # SET_DEVICE_USER done in the official app
    device.keep_signed_in = False
    from .fakeserver.state import version_id

    family(fake_server).device_list_version = version_id()
    backend.puller(fake_server.url).pull(
        fake_server.url, link.device_token, link.family_id
    )
    state = app.test_client().get("/api/settings").get_json()["link"]["state"]
    assert state == "registered"
    assert parents(app)["dashboard"]["signed_in"] is False
    bad = app.test_client().post("/api/link/finish", json={"password": "nope"})
    assert bad.status_code == 403
    ok = app.test_client().post("/api/link/finish", json={"password": PARENT_PASSWORD})
    assert ok.status_code == 200, ok.get_json()
    assert app.test_client().get("/api/settings").get_json()["link"]["state"] == "ready"
    assert parents(app)["dashboard"]["keep_signed_in"] is True


def _everything_under(path: Path) -> bytes:
    return b"".join(p.read_bytes() for p in path.rglob("*") if p.is_file())


def test_a_typed_password_is_never_stored_and_not_in_the_info_log(
    make: Any, fake_server: FakeTimeLimitServer, data_dir: Path
) -> None:
    app = make()
    configure_logging(Settings(data_dir=data_dir, log_level="INFO"), console=False)
    pid = starter_id(fake_server)
    app.test_client().post(
        f"/api/parents/{pid}/password",
        json={"current_password": PARENT_PASSWORD, "new_password": "needle-pass-42"},
    )
    shutdown_logging()
    stored = _everything_under(data_dir)
    assert b"needle-pass-42" not in stored
    assert PARENT_PASSWORD.encode() not in stored


def test_at_debug_level_the_password_appears_in_the_log(
    make: Any, fake_server: FakeTimeLimitServer, data_dir: Path
) -> None:
    app = make()
    configure_logging(Settings(data_dir=data_dir, log_level="DEBUG"), console=False)
    app.test_client().post(
        f"/api/parents/{starter_id(fake_server)}/password",
        json={"current_password": PARENT_PASSWORD, "new_password": "needle-pass-43"},
    )
    shutdown_logging()
    log = Settings(data_dir=data_dir).log_file.read_bytes()
    assert b"needle-pass-43" in log
