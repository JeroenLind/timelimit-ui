"""Plan step A2: per-test isolation, a clean tree after a run, the timeout (TR-500)."""

from __future__ import annotations

import os
import subprocess
import sys
import textwrap
import time
from pathlib import Path

import pytest

APP = Path(__file__).resolve().parents[5]
CACHE_DIRS = {".git", "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache"}


@pytest.mark.parametrize("round_", [1, 2])
def test_each_test_gets_its_own_empty_data_folder(
    round_: int, data_dir: Path, db_path: Path, log_dir: Path
) -> None:
    # Both rounds find an empty folder: what round 1 writes is not seen by round 2.
    assert list(data_dir.iterdir()) == [log_dir]
    assert not db_path.exists()
    db_path.write_bytes(b"x")
    (log_dir / "dashboard.log").write_text("x", encoding="utf-8")


def test_the_data_folder_is_outside_the_repository(data_dir: Path) -> None:
    assert APP not in data_dir.parents


def _snapshot(root: Path) -> dict[str, tuple[int, int]]:
    result = {}
    for folder, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in CACHE_DIRS]
        for name in files:
            path = Path(folder) / name
            stat = path.stat()
            result[str(path.relative_to(root))] = (stat.st_size, stat.st_mtime_ns)
    return result


def _run_pytest(*args: str, cwd: Path = APP) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", *args],
        cwd=cwd,
        check=False,
        capture_output=True,
        text=True,
    )


def test_a_run_leaves_no_file_in_the_repository_tree() -> None:
    before = _snapshot(APP)
    result = _run_pytest("rootfs/usr/bin/dashboard/tests/test_secret_clock.py")
    assert result.returncode == 0, result.stdout[-500:]
    assert _snapshot(APP) == before


def test_the_timeout_is_30_seconds(pytestconfig: pytest.Config) -> None:
    assert pytestconfig.getini("timeout") == "30"


def test_a_hanging_test_is_killed_by_the_timeout(tmp_path: Path) -> None:
    hanging = tmp_path / "test_hang.py"
    hanging.write_text(
        textwrap.dedent(
            """
            import time

            def test_hang():
                time.sleep(60)
            """
        ),
        encoding="utf-8",
    )
    started = time.monotonic()
    result = _run_pytest(
        str(hanging), "-o", "timeout=2", "--rootdir", str(tmp_path), cwd=tmp_path
    )
    assert result.returncode != 0
    assert "Timeout" in result.stdout
    assert time.monotonic() - started < 30
