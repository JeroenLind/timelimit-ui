"""One command for lint, format check, type check and tests (TR-517).

    py -3 tools/check.py          # everything (the definition of done)
    py -3 tools/check.py --fast   # pre-commit: ruff + mypy + unit tests, no browser tests

Stops at the first failing step and exits with its exit code.
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

APP = Path(__file__).resolve().parent.parent
TARGETS = ["rootfs/usr/bin/dashboard", "tools"]


def steps(fast: bool) -> list[tuple[str, list[str]]]:
    py = sys.executable
    pytest = [py, "-m", "pytest", "-q"]
    if importlib.util.find_spec("xdist") is not None:
        pytest += ["-n", "auto"]
    if fast:
        pytest += ["-m", "not ui and not legacy"]
    return [
        ("ruff check", [py, "-m", "ruff", "check", *TARGETS]),
        ("ruff format", [py, "-m", "ruff", "format", "--check", *TARGETS]),
        ("mypy", [py, "-m", "mypy"]),
        ("pytest", pytest),
    ]


def main(argv: list[str]) -> int:
    fast = "--fast" in argv
    for name, cmd in steps(fast):
        print(f"==> {name}", flush=True)
        code = subprocess.call(cmd, cwd=APP)
        if code != 0:
            print(f"FAILED: {name} (exit {code})", flush=True)
            return code
    print("check OK", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
