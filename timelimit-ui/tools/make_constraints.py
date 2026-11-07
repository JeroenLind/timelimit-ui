"""Generate constraints.txt (pinned versions) from requirements.txt with pip-tools.

Usage:  py -3 tools/make_constraints.py
The HA image installs with ``pip install -r requirements.txt -c constraints.txt`` (plan F2).
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

APP = Path(__file__).resolve().parent.parent


def main() -> int:
    cmd = [
        sys.executable,
        "-m",
        "piptools",
        "compile",
        "--quiet",
        "--strip-extras",
        "--no-annotate",
        "--no-header",
        "--output-file",
        str(APP / "constraints.txt"),
        str(APP / "requirements.txt"),
    ]
    return subprocess.call(cmd, cwd=APP)


if __name__ == "__main__":
    raise SystemExit(main())
