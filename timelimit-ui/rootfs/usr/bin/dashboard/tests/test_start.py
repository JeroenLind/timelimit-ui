"""Plan step A3: the app starts on 127.0.0.1:8100 by default and refuses other interfaces."""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import threading
import time
import urllib.request
from collections.abc import Iterator
from pathlib import Path

import pytest

from dashboard.config import Settings, load_settings
from dashboard.domain.clock import FakeClock
from dashboard.domain.secret import Secret
from dashboard.factory import create_app
from dashboard.main import build_server

BIN = Path(__file__).resolve().parents[2]
PACKAGE = BIN / "dashboard"


def _free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


def _other_interface_address() -> str | None:
    """An address of this machine that is not loopback (None when there is none)."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
            probe.connect(("192.0.2.1", 9))  # no packet is sent
            address = str(probe.getsockname()[0])
    except OSError:
        return None
    return None if address.startswith("127.") else address


def test_health_route_and_app_wiring(data_dir: Path) -> None:
    settings = load_settings({"DASHBOARD_DATA_DIR": str(data_dir)})
    clock = FakeClock()
    app = create_app(settings, Secret("k" * 40), clock)
    assert app.config["SECRET_KEY"] == "k" * 40
    assert app.extensions["dashboard"]["clock"] is clock
    response = app.test_client().get("/api/health")
    assert response.status_code == 200
    assert response.get_json() == {"status": "ok"}


@pytest.fixture
def server(data_dir: Path) -> Iterator[tuple[str, int]]:
    settings = Settings(port=0, data_dir=data_dir)  # default host: 127.0.0.1
    app = create_app(settings, Secret("k" * 40))
    httpd = build_server(settings, app)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield settings.host, httpd.server_port
    httpd.shutdown()
    httpd.server_close()
    thread.join(5)


def test_server_answers_on_127_0_0_1(server: tuple[str, int]) -> None:
    host, port = server
    assert host == "127.0.0.1"
    with urllib.request.urlopen(f"http://{host}:{port}/api/health", timeout=5) as reply:
        assert json.load(reply) == {"status": "ok"}


def test_a_connection_from_another_interface_is_refused(
    server: tuple[str, int],
) -> None:
    other = _other_interface_address()
    if other is None:
        pytest.skip("this machine has no non-loopback address")
    _host, port = server
    with (
        pytest.raises(ConnectionRefusedError),
        socket.create_connection((other, port), timeout=3),
    ):
        pass


def _run(
    args: list[str], cwd: Path, env_extra: dict[str, str]
) -> subprocess.Popen[str]:
    env = {**os.environ, "PYTHONPATH": str(BIN), **env_extra}
    return subprocess.Popen(
        [sys.executable, *args],
        cwd=cwd,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )


def _wait_for_health(port: int, process: subprocess.Popen[str]) -> None:
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        if process.poll() is not None:
            pytest.fail(
                f"process ended early: {process.stdout.read() if process.stdout else ''}"
            )
        try:
            with urllib.request.urlopen(
                f"http://127.0.0.1:{port}/api/health", timeout=1
            ):
                return
        except OSError:
            time.sleep(0.2)
    pytest.fail("the dashboard did not start in time")


@pytest.mark.parametrize(
    ("args", "cwd"),
    [(["app.py"], PACKAGE), (["-m", "dashboard"], BIN)],
    ids=["app.py", "-m dashboard"],
)
def test_start_creates_the_data_folder_and_listens(
    args: list[str], cwd: Path, tmp_path: Path
) -> None:
    port = _free_port()
    data = tmp_path / "data"
    process = _run(
        args, cwd, {"DASHBOARD_DATA_DIR": str(data), "DASHBOARD_PORT": str(port)}
    )
    try:
        _wait_for_health(port, process)
        assert (data / "logs" / "dashboard.log").is_file()
        assert (data / "secret_key").is_file()
        lines = (
            (data / "logs" / "dashboard.log").read_text(encoding="utf-8").splitlines()
        )
        assert json.loads(lines[0])["message"] == "started"
    finally:
        process.terminate()
        process.communicate(timeout=10)


def test_invalid_settings_stop_the_start_with_a_clear_message(tmp_path: Path) -> None:
    process = _run(
        ["-m", "dashboard"],
        BIN,
        {"DASHBOARD_DATA_DIR": str(tmp_path), "DASHBOARD_PORT": "eighty"},
    )
    output, _ = process.communicate(timeout=20)
    assert process.returncode == 2
    assert "DASHBOARD_PORT" in output and "'eighty'" in output


def test_port_in_use_stops_the_start_with_a_clear_message(tmp_path: Path) -> None:
    with socket.socket() as blocker:
        blocker.bind(("127.0.0.1", 0))
        blocker.listen()
        port = blocker.getsockname()[1]
        process = _run(
            ["-m", "dashboard"],
            BIN,
            {"DASHBOARD_DATA_DIR": str(tmp_path), "DASHBOARD_PORT": str(port)},
        )
        output, _ = process.communicate(timeout=20)
    assert process.returncode == 1
    assert f"Cannot listen on 127.0.0.1:{port}" in output
