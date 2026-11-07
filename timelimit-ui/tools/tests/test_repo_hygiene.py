"""Repository hygiene checks for plan step A0 (TR-510, 511, 516, 519)."""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

APP = Path(__file__).resolve().parents[2]
BINARY_SUFFIXES = {
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".ico",
    ".db",
    ".pyc",
    ".woff",
    ".woff2",
    ".zip",
}


def _git_root() -> Path | None:
    if shutil.which("git") is None:
        return None
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        check=False,
        cwd=APP,
        capture_output=True,
        text=True,
    )
    return Path(result.stdout.strip()) if result.returncode == 0 else None


def _tracked_files(root: Path) -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files", "-z"], cwd=root, capture_output=True, check=True
    )
    names = [n for n in result.stdout.decode("utf-8").split("\0") if n]
    return [root / n for n in names if (root / n).is_file()]


def test_no_tracked_text_file_has_crlf() -> None:
    root = _git_root()
    if root is None:
        pytest.skip("not inside a git checkout")
    offenders = [
        str(path.relative_to(root))
        for path in _tracked_files(root)
        if path.suffix.lower() not in BINARY_SUFFIXES and b"\r\n" in path.read_bytes()
    ]
    assert offenders == [], f"CRLF found in: {offenders}"


def test_gitattributes_and_editorconfig_force_lf() -> None:
    root = _git_root()
    if root is None:
        pytest.skip("not inside a git checkout")
    assert "eol=lf" in (root / ".gitattributes").read_text(encoding="utf-8")
    assert "end_of_line = lf" in (root / ".editorconfig").read_text(encoding="utf-8")


def _requirement_names(path: Path) -> set[str]:
    names = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith(("#", "-")):
            continue
        names.add(
            re.split(r"[<>=!~;\[ ]", line, maxsplit=1)[0].lower().replace("_", "-")
        )
    return names


def test_constraints_pin_every_requirement() -> None:
    constraints = (APP / "constraints.txt").read_text(encoding="utf-8")
    pinned = {
        line.split("==")[0].lower().replace("_", "-")
        for line in constraints.splitlines()
        if "==" in line
    }
    missing = _requirement_names(APP / "requirements.txt") - pinned
    assert missing == set(), f"not pinned in constraints.txt: {missing}"
    assert all(
        "==" in line
        for line in constraints.splitlines()
        if line and not line.startswith(("#", " "))
    )
    assert "/home/" not in constraints and "C:\\" not in constraints


def test_every_plan_decision_has_a_record() -> None:
    plan = (APP / "docs/plan/implementation-plan.md").read_text(encoding="utf-8")
    section = plan.split("## 3. Decisions taken")[1].split("\n## 4.")[0]
    ids = re.findall(r"^\|\s*([A-Z]\d+[a-z]?)\s*\|", section, flags=re.MULTILINE)
    assert len(ids) >= 30
    records = {p.name.split("-")[0] for p in (APP / "docs/decisions").glob("*.md")}
    missing = [i for i in ids if i not in records]
    assert missing == [], f"no decision record for: {missing}"


def test_check_command_fails_on_a_style_error(tmp_path: Path) -> None:
    bad = tmp_path / "bad.py"
    bad.write_text(
        "import os\n", encoding="utf-8", newline="\n"
    )  # unused import (F401)
    result = subprocess.run(
        [sys.executable, "-m", "ruff", "check", str(bad)],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
