"""Start-up inside the Home Assistant add-on: add-on options -> dashboard settings (plan F2).

The s6 service runs ``python3 -m dashboard.addon``. Home Assistant writes the options the user chose to
``/data/options.json``; this module turns them into the ``DASHBOARD_*`` settings and starts the dashboard.
Only the log level is an option: the listen address and port belong to the add-on (ingress) and the TimeLimit
server is chosen in the settings screen (design 8.1).
"""

from __future__ import annotations

import json
import os
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any

OPTIONS_FILE = Path("/data/options.json")
DATA_DIR = "/data"
INGRESS_PORT = 8099
LOG_LEVELS = ("debug", "info", "warning", "error")
DEFAULT_LOG_LEVEL = "info"


class OptionsError(ValueError):
    """The add-on options are not usable."""


def read_options(path: Path = OPTIONS_FILE) -> dict[str, Any]:
    """The options file; a missing file means the defaults (a start outside Home Assistant)."""
    if not path.exists():
        return {}
    try:
        content = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise OptionsError(f"{path}: cannot be read as JSON ({error})") from error
    if not isinstance(content, dict):
        raise OptionsError(f"{path}: must contain a JSON object")
    return content


def environment_from_options(options: Mapping[str, Any]) -> dict[str, str]:
    """The ``DASHBOARD_*`` variables for these options. Raises :class:`OptionsError` for a bad value."""
    unknown = sorted(set(options) - {"log_level"})
    if unknown:
        raise OptionsError(f"unknown add-on option(s): {', '.join(unknown)}")
    level = str(options.get("log_level", DEFAULT_LOG_LEVEL)).strip().lower()
    if level not in LOG_LEVELS:
        raise OptionsError(
            f"log_level must be one of {', '.join(LOG_LEVELS)} (got {level!r})"
        )
    return {
        "DASHBOARD_HOST": "0.0.0.0",
        "DASHBOARD_PORT": str(INGRESS_PORT),
        "DASHBOARD_DATA_DIR": DATA_DIR,
        "DASHBOARD_LOG_LEVEL": level,
    }


def main(options_file: Path = OPTIONS_FILE) -> int:
    try:
        environment = environment_from_options(read_options(options_file))
    except OptionsError as error:
        print(f"Invalid add-on options: {error}", file=sys.stderr)
        return 2
    os.environ.update(environment)
    from dashboard.main import main as run

    return run()


if __name__ == "__main__":
    raise SystemExit(main())
