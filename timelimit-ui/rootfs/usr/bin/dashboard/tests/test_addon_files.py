"""Plan step C1: the Home Assistant add-on starts the dashboard (TR-312, TR-302 in part)."""

from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[5]
S6 = REPO / "rootfs" / "etc" / "s6-overlay" / "s6-rc.d"
LEGACY = (
    "web_server.py",
    "web-server",
    "api_client.py",
    "frontend.py",
    "check_server.py",
)


def enabled_services() -> set[str]:
    return {p.name for p in (S6 / "user" / "contents.d").iterdir()}


def test_the_dashboard_service_is_enabled_and_the_legacy_one_is_not() -> None:
    assert "dashboard-v2" in enabled_services()
    assert "web-server" not in enabled_services()
    assert not (S6 / "web-server").exists()


def test_every_enabled_service_is_a_complete_longrun_service() -> None:
    for name in enabled_services():
        assert (S6 / name / "type").read_text().strip() == "longrun", name
        assert (S6 / name / "run").is_file(), name


def test_the_run_script_starts_a_file_that_exists() -> None:
    script = (S6 / "dashboard-v2" / "run").read_text()
    folder = re.search(r"^cd (\S+)", script, re.MULTILINE)
    target = re.search(r"^exec python3 (?:-u )?(\S+\.py)", script, re.MULTILINE)
    assert folder and target, (
        "run script must `cd` into the app folder and `exec python3 <file>.py`"
    )
    assert (REPO / "rootfs" / folder.group(1).lstrip("/") / target.group(1)).is_file()


def test_the_dockerfile_references_no_legacy_file() -> None:
    text = (REPO / "Dockerfile").read_text()
    assert [name for name in LEGACY if name in text] == []


def test_the_dockerfile_makes_the_enabled_service_executable() -> None:
    text = (REPO / "Dockerfile").read_text()
    for name in enabled_services():
        assert f"/etc/s6-overlay/s6-rc.d/{name}/run" in text


def test_the_image_installs_what_the_started_app_imports() -> None:
    """The started app needs these third-party packages; the Dockerfile must provide them."""
    text = (REPO / "Dockerfile").read_text().lower()
    for package in (
        "flask",
        "werkzeug",
        "requests",
        "bcrypt",
        "cryptography",
        "structlog",
        "apscheduler",
    ):
        assert package in text, package
