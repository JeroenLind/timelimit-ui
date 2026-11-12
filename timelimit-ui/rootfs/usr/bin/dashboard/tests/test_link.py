"""Plan step E1: linking, server profiles, version warning, debug export (FR-100..104, TR-402)."""

from __future__ import annotations

import dataclasses
import time
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest
from flask import Flask

from ..config import Settings
from ..domain.secret import Secret
from ..factory import create_app
from .conftest import PARENT_MAIL, PARENT_PASSWORD, link_app, make_family
from .fakeserver import FakeTimeLimitServer


@pytest.fixture
def make_app(
    data_dir: Path, fake_server: FakeTimeLimitServer
) -> Iterator[Callable[..., Flask]]:
    apps: list[Flask] = []

    def build(**overrides: Any) -> Flask:
        settings = Settings(
            data_dir=data_dir,
            server_url=overrides.pop("server_url", fake_server.url),
            server_timeout=3.0,
            poll_interval=0.2,
            **overrides,
        )
        app = create_app(settings, Secret("test-secret"))
        apps.append(app)
        return app

    yield build
    for app in apps:
        app.extensions["dashboard"]["backend"].close()


def backend(app: Flask) -> Any:
    return app.extensions["dashboard"]["backend"]


def view(app: Flask) -> dict[str, Any]:
    return app.test_client().get("/api/settings").get_json()  # type: ignore[no-any-return]


def wait_for(check: Callable[[], bool], seconds: float = 5.0) -> None:
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        if check():
            return
        time.sleep(0.05)
    raise AssertionError("condition not reached in time")


def mail_login(app: Flask, fake: FakeTimeLimitServer, mail: str = PARENT_MAIL) -> Any:
    http = app.test_client()
    assert (
        http.post(
            "/api/link/mail-code", json={"mail": mail, "locale": "en"}
        ).status_code
        == 200
    )
    answer = http.post("/api/link/confirm-code", json={"code": fake.inbox[-1][1]})
    assert answer.status_code == 200
    return http


def the_family(fake: FakeTimeLimitServer) -> Any:
    return next(iter(fake.world.families.values()))


# -- first start and joining an existing family ---------------------------------------------------------------------
def test_first_start_shows_only_the_settings_screen(make_app: Any) -> None:
    app = make_app()
    http = app.test_client()
    answer = http.get("/")
    assert answer.status_code == 302 and answer.headers["Location"].endswith(
        "/settings"
    )
    assert http.get("/settings").status_code == 200
    assert view(app)["link"]["state"] == "not_linked"


def test_no_server_chosen_gives_state_no_server(make_app: Any) -> None:
    app = make_app(server_url="")
    assert view(app)["link"]["state"] == "no_server"
    assert app.test_client().get("/").status_code == 302


def test_joining_creates_the_dashboard_parent_and_signs_in(
    make_app: Any, fake_server: FakeTimeLimitServer, data_dir: Path
) -> None:
    make_family(fake_server)
    app = make_app()
    link_app(app, fake_server)
    family = the_family(fake_server)
    dashboards = [u for u in family.users.values() if u.name == "Dashboard"]
    assert len(dashboards) == 1 and dashboards[0].type == "parent"
    own = next(d for d in family.devices.values() if d.name == "Dashboard")
    assert own.current_user_id == dashboards[0].user_id and own.keep_signed_in
    assert app.test_client().get("/").status_code == 200
    # the typed password is in no file of the data folder (SEC-003)
    for path in data_dir.rglob("*"):
        if path.is_file():
            assert PARENT_PASSWORD.encode() not in path.read_bytes(), path.name


def test_a_wrong_password_is_refused_and_the_step_can_be_repeated(
    make_app: Any, fake_server: FakeTimeLimitServer
) -> None:
    make_family(fake_server)
    app = make_app()
    http = mail_login(app, fake_server)
    bad = http.post("/api/link/join", json={"password": "nope", "time_zone": "UTC"})
    assert bad.status_code == 403 and bad.get_json()["code"] == "INVALID_PASSWORD"
    assert (
        view(app)["link"]["state"] == "registered"
    )  # the device is registered, "Dashboard" is not
    assert not [
        u for u in the_family(fake_server).users.values() if u.name == "Dashboard"
    ]
    good = http.post("/api/link/finish", json={"password": PARENT_PASSWORD})
    assert good.status_code == 200 and good.get_json()["state"] == "ready"
    assert (
        len(
            [u for u in the_family(fake_server).users.values() if u.name == "Dashboard"]
        )
        == 1
    )


# -- a family on a fresh test server (Q6c) -----------------------------------------------------------------------
def test_create_family_only_with_the_test_server_switch(
    make_app: Any, fake_server: FakeTimeLimitServer
) -> None:
    app = make_app()
    http = mail_login(app, fake_server, "new@example.org")
    assert view(app)["link"]["can_create_family"] is False
    refused = http.post(
        "/api/link/create-family", json={"password": "pw", "time_zone": "UTC"}
    )
    assert refused.status_code == 400 and not fake_server.world.families

    assert (
        http.put("/api/settings/test-server", json={"enabled": True}).status_code == 200
    )
    assert view(app)["link"]["can_create_family"] is True
    done = http.post(
        "/api/link/create-family", json={"password": "pw", "time_zone": "UTC"}
    )
    assert done.status_code == 200 and done.get_json()["state"] == "ready"
    users = list(the_family(fake_server).users.values())
    assert [(u.name, u.type) for u in users] == [("Dashboard", "parent")]


# -- persistence ---------------------------------------------------------------------------------------------------------
def test_the_link_survives_a_restart_and_a_cache_reset(
    make_app: Any, fake_server: FakeTimeLimitServer
) -> None:
    make_family(fake_server)
    first = make_app()
    link_app(first, fake_server)
    device_id = view(first)["link"]["device_id"]
    backend(first).close()

    second = make_app()
    assert view(second)["link"]["state"] == "ready"
    backend(second).db.reset_cache()
    assert view(second)["link"]["device_id"] == device_id
    assert view(second)["link"]["state"] == "ready"


def test_the_alternative_server_choice_survives_a_restart(
    make_app: Any, fake_server: FakeTimeLimitServer
) -> None:
    app = make_app(server_url="")
    http = app.test_client()
    chosen = http.put(
        "/api/settings/server",
        json={
            "mode": "alternative",
            "protocol": "http",
            "address": "127.0.0.1",
            "port": fake_server.port,
        },
    )
    assert chosen.status_code == 200
    expected = f"http://127.0.0.1:{fake_server.port}"
    assert chosen.get_json()["server"]["url"] == expected
    backend(app).close()
    again = make_app(server_url="")
    server = view(again)["server"]
    assert (server["mode"], server["protocol"], server["address"], server["port"]) == (
        "alternative",
        "http",
        "127.0.0.1",
        fake_server.port,
    )


@pytest.mark.parametrize(
    "body",
    [
        {"mode": "alternative", "protocol": "ftp", "address": "127.0.0.1"},
        {"mode": "alternative", "protocol": "http", "address": "http://x"},
        {"mode": "alternative", "protocol": "http", "address": ""},
        {
            "mode": "alternative",
            "protocol": "http",
            "address": "127.0.0.1",
            "port": 70000,
        },
        {
            "mode": "alternative",
            "protocol": "http",
            "address": "example.org",
        },  # plain http, public
        {"mode": "other"},
    ],
)
def test_a_bad_server_choice_is_refused(make_app: Any, body: dict[str, Any]) -> None:
    app = make_app(server_url="")
    answer = app.test_client().put("/api/settings/server", json=body)
    assert answer.status_code == 400 and answer.get_json()["code"] == "INVALID_INPUT"
    assert view(app)["server"]["mode"] == "none"


def test_the_official_server_can_be_chosen(make_app: Any) -> None:
    app = make_app(server_url="")
    chosen = app.test_client().put("/api/settings/server", json={"mode": "official"})
    assert chosen.get_json()["server"]["url"] == "https://api.timelimit.io"


def test_two_servers_keep_separate_profiles(
    make_app: Any, fake_server: FakeTimeLimitServer
) -> None:
    other = FakeTimeLimitServer()
    other.start()
    try:
        make_family(fake_server)
        make_family(other, "other@example.org", "other password")
        app = make_app()
        http = app.test_client()
        link_app(app, fake_server)
        url_a = fake_server.url
        link_a = backend(app).links.get(url_a)
        seq_a = backend(app).links.reserve_sequence(url_a)

        http.put(
            "/api/settings/server",
            json={
                "mode": "alternative",
                "protocol": "http",
                "address": "127.0.0.1",
                "port": other.port,
            },
        )
        assert view(app)["link"]["state"] == "not_linked"  # server B has no link yet
        link_app(app, other, "other@example.org", "other password")
        link_b = backend(app).links.get(other.url)
        assert link_b.own_device_id != link_a.own_device_id
        assert backend(app).links.get(url_a).own_device_id == link_a.own_device_id
        assert (
            backend(app).links.reserve_sequence(url_a) > seq_a
        )  # counter of A kept going on its own

        http.put(
            "/api/settings/server",
            json={
                "mode": "alternative",
                "protocol": "http",
                "address": "127.0.0.1",
                "port": fake_server.port,
            },
        )
        assert view(app)["link"]["state"] == "ready"
        assert view(app)["link"]["device_id"] == link_a.own_device_id
        users_a = {
            u.data["name"] for u in backend(app).cache.users(backend(app).scope(url_a))
        }
        users_b = {
            u.data["name"]
            for u in backend(app).cache.users(backend(app).scope(other.url))
        }
        assert users_a == users_b == {"Parent", "Dashboard"}
    finally:
        other.stop()


# -- version warning (Q7) ----------------------------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("level", "warns"), [(7, False), (9, False), (8, True), (10, True), (3, True)]
)
def test_untested_api_level_warns_but_stays_usable(
    level: int, warns: bool, make_app: Any, data_dir: Path
) -> None:
    with FakeTimeLimitServer(api_level=level) as fake:
        make_family(fake)
        app = make_app(server_url=fake.url)
        link_app(app, fake)
        http = app.test_client()
        assert view(app)["version_warning"] is warns
        codes = [n["code"] for n in http.get("/api/notices").get_json()["notices"]]
        assert ("VERSION_UNTESTED" in codes) is warns
        assert http.get("/").status_code == 200


# -- session ended by the server ---------------------------------------------------------------------------------------------
def test_a_signed_out_device_shows_link_again(
    make_app: Any, fake_server: FakeTimeLimitServer
) -> None:
    make_family(fake_server)
    app = make_app()
    link_app(app, fake_server)
    token = backend(app).links.get(fake_server.url).device_token.reveal()
    wait_for(lambda: fake_server.socket_clients >= 1)  # the listener is connected
    fake_server.sign_out(token)
    wait_for(lambda: view(app)["link"]["state"] == "session_invalid")
    codes = [
        n["code"] for n in app.test_client().get("/api/notices").get_json()["notices"]
    ]
    assert "SESSION_INVALID" in codes
    assert (
        app.test_client().get("/").status_code == 200
    )  # still usable (read-only), not a dead end


# -- the token never leaves the backend (TR-402) -----------------------------------------------------------------------
def test_the_token_is_in_no_page_script_or_api_answer(
    make_app: Any, fake_server: FakeTimeLimitServer
) -> None:
    make_family(fake_server)
    app = make_app()
    link_app(app, fake_server)
    token = backend(app).links.get(fake_server.url).device_token.reveal()
    http = app.test_client()
    paths = [
        "/",
        "/settings",
        "/api/settings",
        "/api/notices",
        "/api/children",
        "/api/server/status",
        "/api/health",
        "/api/settings/debug-export",
    ]
    static = Path(app.static_folder or "")
    paths += [
        f"/static/{p.relative_to(static).as_posix()}"
        for p in static.rglob("*")
        if p.is_file()
    ]
    assert len(paths) > 20
    for path in paths:
        answer = http.get(path)
        assert token.encode() not in answer.data, path
        assert PARENT_PASSWORD.encode() not in answer.data, path


# -- debug export (FR-104) -----------------------------------------------------------------------------------------------
def test_debug_export_is_a_text_download_without_the_token(
    make_app: Any, fake_server: FakeTimeLimitServer
) -> None:
    make_family(fake_server)
    app = make_app()
    link_app(app, fake_server)
    answer = app.test_client().get("/api/settings/debug-export")
    assert answer.status_code == 200
    assert answer.mimetype == "text/plain"
    assert "attachment" in answer.headers["Content-Disposition"]
    text = answer.get_data(as_text=True)
    assert '"log_level"' in text and "device_id" in text
    assert backend(app).links.get(fake_server.url).device_token.reveal() not in text
    assert PARENT_PASSWORD not in text


def test_settings_view_has_no_secret_fields(
    make_app: Any, fake_server: FakeTimeLimitServer
) -> None:
    make_family(fake_server)
    app = make_app()
    link_app(app, fake_server)
    flat = repr(view(app)).lower()
    assert "token" not in flat and "password" not in flat
    assert dataclasses.is_dataclass(app.extensions["dashboard"]["settings"])
