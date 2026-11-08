"""Fixtures of the new suite: every test gets its own temporary data folder (plan A2, TR-500).

Nothing in the repository tree is used or written by a test; everything lives under ``tmp_path``.
"""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture
def data_dir(tmp_path: Path) -> Path:
    """The data folder of one test (own database, secret key, logs, session files)."""
    folder = tmp_path / "data"
    folder.mkdir()
    return folder


@pytest.fixture
def db_path(data_dir: Path) -> Path:
    """Path of the test's own SQLite file. The file is not created; the code under test does that."""
    return data_dir / "dashboard.db"


@pytest.fixture
def log_dir(data_dir: Path) -> Path:
    """The test's own log folder."""
    folder = data_dir / "logs"
    folder.mkdir()
    return folder


@pytest.fixture
def fake_server():  # type: ignore[no-untyped-def]
    """A fake TimeLimit server on an ephemeral port (plan A5); asserts no unsimulated action was used."""
    from .fakeserver import FakeTimeLimitServer

    server = FakeTimeLimitServer()
    server.start()
    try:
        yield server
    finally:
        server.stop()
    assert server.unsimulated == [], (
        f"actions the fake does not simulate: {server.unsimulated}"
    )


class LiveApp:
    """The dashboard on an ephemeral port in a background thread, for browser tests."""

    def __init__(self, settings, secret_key) -> None:  # type: ignore[no-untyped-def]
        import threading

        from werkzeug.serving import make_server

        from dashboard.factory import create_app

        self.app = create_app(settings, secret_key)
        self._server = make_server("127.0.0.1", 0, self.app, threaded=True)
        self.url = f"http://127.0.0.1:{self._server.server_port}"
        self._thread = threading.Thread(
            target=lambda: self._server.serve_forever(poll_interval=0.02),
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        self._server.shutdown()
        self._server.server_close()
        self._thread.join(timeout=5)


@pytest.fixture
def live_app_factory(data_dir: Path, fake_server):  # type: ignore[no-untyped-def]
    """Start the dashboard against the fake server; keyword arguments override Settings fields."""
    import dataclasses

    from dashboard.config import Settings
    from dashboard.domain.secret import Secret

    started: list[LiveApp] = []

    def start(**overrides):  # type: ignore[no-untyped-def]
        base = Settings(
            data_dir=data_dir,
            server_url=fake_server.url,
            health_timeout=1.0,
            health_interval=0.3,
            backoff_initial=0.3,
            backoff_max=0.6,
            browser_timeout=2.0,
        )
        live = LiveApp(dataclasses.replace(base, **overrides), Secret("test-secret"))
        started.append(live)
        return live

    yield start
    for live in started:
        live.stop()


@pytest.fixture
def browser():  # type: ignore[no-untyped-def]
    from playwright.sync_api import sync_playwright

    with sync_playwright() as playwright:
        chromium = playwright.chromium.launch()
        yield chromium
        chromium.close()
