"""Plan step A7, backend half: the server state the offline banner is built on (FR-1000..1003)."""

from __future__ import annotations

import dataclasses
from pathlib import Path
from typing import Any

import pytest
from flask.testing import FlaskClient

from dashboard.config import Settings
from dashboard.domain.errors import DashboardError, ErrorCode
from dashboard.domain.secret import Secret
from dashboard.factory import create_app
from dashboard.services.connection import ConnectionService

from .fakeserver import FakeTimeLimitServer


def settings_for(data_dir: Path, url: str, **extra: Any) -> Settings:
    return dataclasses.replace(
        Settings(data_dir=data_dir, health_timeout=0.5, server_url=url), **extra
    )


@pytest.fixture
def web(data_dir: Path, fake_server: FakeTimeLimitServer) -> FlaskClient:
    app = create_app(settings_for(data_dir, fake_server.url), Secret("k"))
    return app.test_client()


def test_status_is_up_while_the_server_answers(web: FlaskClient) -> None:
    assert web.get("/api/server/status").get_json() == {"state": "up", "code": None}


def test_status_is_down_when_the_server_is_stopped(
    web: FlaskClient, fake_server: FakeTimeLimitServer
) -> None:
    fake_server.stop()
    assert web.get("/api/server/status").get_json() == {
        "state": "down",
        "code": "SERVER_UNREACHABLE",
    }


def test_a_slow_server_is_down_with_server_timeout(
    web: FlaskClient, fake_server: FakeTimeLimitServer
) -> None:
    fake_server.faults.delay_seconds = 1.0
    assert web.get("/api/server/status").get_json()["code"] == "SERVER_TIMEOUT"


def test_without_a_server_the_state_is_not_configured(data_dir: Path) -> None:
    app = create_app(settings_for(data_dir, ""), Secret("k"))
    assert app.test_client().get("/api/server/status").get_json() == {
        "state": "not_configured",
        "code": None,
    }


def test_changes_are_refused_while_the_server_is_down(
    data_dir: Path, fake_server: FakeTimeLimitServer
) -> None:
    service = ConnectionService(settings_for(data_dir, fake_server.url))
    service.require_online()  # up: fine
    fake_server.stop()
    with pytest.raises(DashboardError) as info:
        service.require_online()
    assert info.value.code is ErrorCode.READ_ONLY_OFFLINE


def test_state_changes_are_logged_once(
    data_dir: Path,
    fake_server: FakeTimeLimitServer,
    caplog: pytest.LogCaptureFixture,
) -> None:
    service = ConnectionService(settings_for(data_dir, fake_server.url))
    with caplog.at_level("INFO"):
        service.status()
        service.status()
        fake_server.stop()
        service.status()
        service.status()
    assert [r.getMessage() for r in caplog.records].count("server state changed") == 2


def test_the_server_url_setting_follows_the_https_rule(tmp_path: Path) -> None:
    from dashboard.config import ConfigError, load_settings

    with pytest.raises(ConfigError, match="https://"):
        load_settings(
            env={"DASHBOARD_SERVER_URL": "http://example.org"}, app_dir=tmp_path
        )
    ok = load_settings(
        env={"DASHBOARD_SERVER_URL": "http://localhost:8080/"}, app_dir=tmp_path
    )
    assert ok.server_url == "http://localhost:8080"
