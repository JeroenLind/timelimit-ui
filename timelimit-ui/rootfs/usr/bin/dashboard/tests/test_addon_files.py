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


def test_the_run_script_starts_the_addon_module_of_the_new_dashboard() -> None:
    script = (S6 / "dashboard-v2" / "run").read_text()
    folder = re.search(r"^cd (\S+)", script, re.MULTILINE)
    module = re.search(r"^exec python3 (?:-u )?-m (\S+)", script, re.MULTILINE)
    assert folder and module, "run script must `cd` and `exec python3 -m <module>`"
    path = (
        REPO
        / "rootfs"
        / folder.group(1).lstrip("/")
        / (module.group(1).replace(".", "/") + ".py")
    )
    assert path.is_file()
    assert module.group(1) == "dashboard.addon"


def test_the_dockerfile_references_no_legacy_file() -> None:
    text = (REPO / "Dockerfile").read_text()
    assert [name for name in LEGACY if name in text] == []


def test_the_dockerfile_makes_the_enabled_service_executable() -> None:
    text = (REPO / "Dockerfile").read_text()
    for name in enabled_services():
        assert f"/etc/s6-overlay/s6-rc.d/{name}/run" in text


def test_the_image_installs_from_the_requirements_and_the_constraints_file() -> None:
    text = (REPO / "Dockerfile").read_text()
    assert "-r /tmp/requirements.txt" in text
    assert "-c /tmp/constraints.txt" in text
    assert "COPY requirements.txt constraints.txt" in text


def test_every_requirement_is_pinned_in_the_constraints_file() -> None:
    pinned = {
        re.split(r"[=<>\[]", line, maxsplit=1)[0].lower().replace("_", "-")
        for line in (REPO / "constraints.txt").read_text().splitlines()
        if line and not line.startswith("#")
    }
    for line in (REPO / "requirements.txt").read_text().splitlines():
        line = line.split("#")[0].strip()
        if line:
            name = re.split(r"[=<>\[]", line, maxsplit=1)[0].lower().replace("_", "-")
            assert name in pinned, name


def test_the_image_does_not_depend_on_the_legacy_libraries() -> None:
    text = (REPO / "Dockerfile").read_text().lower()
    for package in ("structlog", "apscheduler"):
        assert package not in text
