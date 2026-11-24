"""Plan step F3: one version everywhere, and the release workflow builds only what we ship."""

from __future__ import annotations

import re
from pathlib import Path

from .. import __version__
from .test_addon import simple_yaml

APP = Path(__file__).resolve().parents[5]
WORKFLOW = APP.parent / ".github" / "workflows" / "builder.yaml"


def test_the_version_is_the_same_in_the_app_and_in_config_yaml() -> None:
    assert re.fullmatch(r"\d+\.\d+\.\d+(-beta\.\d+)?", __version__)
    assert simple_yaml(APP / "config.yaml")["version"] == __version__


def test_health_reports_the_version(tmp_path: Path) -> None:
    from ..config import Settings
    from ..domain.secret import Secret
    from ..factory import create_app

    app = create_app(Settings(data_dir=tmp_path), Secret("s"))
    try:
        body = app.test_client().get("/api/health").get_json()
    finally:
        app.extensions["dashboard"]["backend"].close()
    assert body["version"] == __version__


def test_the_workflow_builds_aarch64_only_and_only_after_checks_and_smoke_test() -> (
    None
):
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "--aarch64" in text
    assert "--amd64" not in text
    assert "needs: checks" in text
    assert "needs: smoke" in text
    assert "/api/health" in text
    assert "ghcr.io/jeroenlind" in text


def test_the_workflow_runs_on_a_version_change_or_by_hand() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "timelimit-ui/config.yaml" in text
    assert "workflow_dispatch" in text


def test_the_smoke_test_uses_the_same_entry_point_as_the_s6_service() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    run = (APP / "rootfs/etc/s6-overlay/s6-rc.d/dashboard-v2/run").read_text()
    module = re.search(r"python3 -u -m (\S+)", run)
    assert module and f"-m {module.group(1)}" in text
