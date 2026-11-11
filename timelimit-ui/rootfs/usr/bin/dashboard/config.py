"""Settings of the dashboard: environment > config file > default (TR-301, 305, 306, 400, 401).

* Environment variables are ``DASHBOARD_<SETTING>`` (for example ``DASHBOARD_PORT``).
* The optional config file is ``config.json`` in the data folder.
* The data folder is ``data/`` next to ``app.py`` unless ``DASHBOARD_DATA_DIR`` says otherwise
  (the Home Assistant add-on sets ``/data``). It is the one setting that cannot be in the file.
* The secret key (Flask sessions) is generated on first start and kept in the data folder;
  ``DASHBOARD_SECRET_KEY`` overrides it.

Server-related UI settings (which server, test-server switch per server, timings changed in the
settings screen) are stored in the database (plan B1/E1); the values here are the defaults.
"""

from __future__ import annotations

import json
import math
import os
import secrets
from collections.abc import Callable, Mapping
from dataclasses import dataclass, fields
from pathlib import Path
from typing import Any

from dashboard.client.server import OFFICIAL_SERVER_URL as OFFICIAL_SERVER_URL
from dashboard.client.server import validate_server_url
from dashboard.domain.errors import DashboardError
from dashboard.domain.secret import Secret

ENV_PREFIX = "DASHBOARD_"
APP_DIR = Path(__file__).resolve().parent
CONFIG_FILE_NAME = "config.json"
SECRET_KEY_FILE_NAME = "secret_key"
SECRET_KEY_ENV = "DASHBOARD_SECRET_KEY"
DATA_DIR_ENV = "DASHBOARD_DATA_DIR"
LOG_LEVELS = {
    "debug": "DEBUG",
    "info": "INFO",
    "warn": "WARNING",
    "warning": "WARNING",
    "error": "ERROR",
}


class ConfigError(ValueError):
    """One or more settings are invalid. The message names every problem and where it came from."""


def _parse_bool(raw: Any) -> bool:
    if isinstance(raw, bool):
        return raw
    text = str(raw).strip().lower()
    if text in {"1", "true", "yes", "on"}:
        return True
    if text in {"0", "false", "no", "off"}:
        return False
    raise ValueError("expected true or false")


def _parse_int(minimum: int, maximum: int | None = None) -> Callable[[Any], int]:
    def parse(raw: Any) -> int:
        if isinstance(raw, bool):
            raise ValueError("expected a whole number")  # noqa: TRY004 (callers catch ValueError)
        try:
            value = int(str(raw).strip())
        except ValueError:
            raise ValueError("expected a whole number") from None
        if value < minimum or (maximum is not None and value > maximum):
            limit = (
                f"at least {minimum}" if maximum is None else f"{minimum} to {maximum}"
            )
            raise ValueError(f"must be {limit}")
        return value

    return parse


def _parse_seconds(raw: Any) -> float:
    if isinstance(raw, bool):
        raise ValueError("expected a number of seconds")  # noqa: TRY004 (callers catch ValueError)
    try:
        value = float(str(raw).strip())
    except ValueError:
        raise ValueError("expected a number of seconds") from None
    if not (value > 0 and math.isfinite(value)):
        raise ValueError("must be greater than 0")
    return value


def _parse_server_url(raw: Any) -> str:
    """Empty = no server chosen yet; otherwise the SEC-002 rules decide."""
    text = str(raw).strip()
    if not text:
        return ""
    try:
        return validate_server_url(text)
    except DashboardError as error:
        raise ValueError(error.message) from None


def normalize_server_url(raw: str) -> str:
    """The SEC-002 check for a server address chosen in the settings screen (raises ``ValueError``)."""
    return _parse_server_url(raw)


def _parse_host(raw: Any) -> str:
    text = str(raw).strip()
    if not text:
        raise ValueError("must not be empty")
    return text


def _parse_log_level(raw: Any) -> str:
    key = str(raw).strip().lower()
    if key not in LOG_LEVELS:
        raise ValueError("expected debug, info, warn or error")
    return LOG_LEVELS[key]


@dataclass(frozen=True)
class Settings:
    """All settings with their defaults. Timings are in seconds."""

    host: str = "127.0.0.1"
    port: int = 8100
    data_dir: Path = APP_DIR / "data"
    log_level: str = "INFO"
    log_max_bytes: int = 10 * 1024 * 1024
    log_backup_count: int = 5
    health_timeout: float = 3.0
    health_interval: float = 5.0
    backoff_initial: float = 10.0
    backoff_max: float = 30.0
    sync_target: float = 5.0
    poll_interval: float = 30.0
    retry_delay: float = 0.25
    retry_count: int = 2
    browser_timeout: float = 10.0
    server_timeout: float = 10.0
    test_server: bool = False
    # Temporary until the settings screen with the server dropdown exists (design 8.1).
    server_url: str = ""

    @property
    def log_dir(self) -> Path:
        return self.data_dir / "logs"

    @property
    def log_file(self) -> Path:
        return self.log_dir / "dashboard.log"


# name -> parser; the order is the order of the settings screen / error messages.
PARSERS: dict[str, Callable[[Any], Any]] = {
    "host": _parse_host,
    "port": _parse_int(0, 65535),
    "log_level": _parse_log_level,
    "log_max_bytes": _parse_int(1),
    "log_backup_count": _parse_int(1),
    "health_timeout": _parse_seconds,
    "health_interval": _parse_seconds,
    "backoff_initial": _parse_seconds,
    "backoff_max": _parse_seconds,
    "sync_target": _parse_seconds,
    "poll_interval": _parse_seconds,
    "retry_delay": _parse_seconds,
    "retry_count": _parse_int(0, 10),
    "browser_timeout": _parse_seconds,
    "server_timeout": _parse_seconds,
    "test_server": _parse_bool,
    "server_url": _parse_server_url,
}


def env_name(setting: str) -> str:
    return ENV_PREFIX + setting.upper()


def _read_config_file(path: Path, problems: list[str]) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        content = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        problems.append(f"{path}: cannot be read as JSON ({error})")
        return {}
    if not isinstance(content, dict):
        problems.append(f"{path}: must contain a JSON object")
        return {}
    for key in content:
        if key == "data_dir":
            problems.append(
                f"{path}: 'data_dir' cannot be set in the file, use {DATA_DIR_ENV}"
            )
        elif key not in PARSERS:
            problems.append(f"{path}: unknown setting '{key}'")
    return content


def load_settings(
    env: Mapping[str, str] | None = None, app_dir: Path | None = None
) -> Settings:
    """Build the settings. Raises :class:`ConfigError` listing every invalid value."""
    env = os.environ if env is None else env
    problems: list[str] = []

    raw_dir = env.get(DATA_DIR_ENV, "").strip()
    data_dir = Path(raw_dir) if raw_dir else (app_dir or APP_DIR) / "data"
    values: dict[str, Any] = {"data_dir": data_dir}

    file_values = _read_config_file(data_dir / CONFIG_FILE_NAME, problems)
    for name, parse in PARSERS.items():
        if env_name(name) in env:
            source, raw = f"environment variable {env_name(name)}", env[env_name(name)]
        elif name in file_values:
            source, raw = f"{CONFIG_FILE_NAME} setting '{name}'", file_values[name]
        else:
            continue
        try:
            values[name] = parse(raw)
        except ValueError as error:
            problems.append(f"{source}: {error} (got {raw!r})")

    settings = Settings(**values)
    if settings.backoff_max < settings.backoff_initial:
        problems.append(
            f"backoff_max ({settings.backoff_max}) must not be smaller than backoff_initial "
            f"({settings.backoff_initial})"
        )
    if problems:
        raise ConfigError("Invalid settings:\n  - " + "\n  - ".join(problems))
    return settings


def setting_names() -> list[str]:
    return [field.name for field in fields(Settings)]


def ensure_data_dir(settings: Settings) -> Path:
    """Create the data folder (and its log folder) when they do not exist yet."""
    settings.log_dir.mkdir(parents=True, exist_ok=True)
    return settings.data_dir


def load_secret_key(settings: Settings, env: Mapping[str, str] | None = None) -> Secret:
    """The Flask secret key: environment variable, else the kept file, else a new random key.

    A file that is empty or too short (an interrupted first start) is replaced by a new key.
    """
    env = os.environ if env is None else env
    from_env = env.get(SECRET_KEY_ENV, "").strip()
    if from_env:
        return Secret(from_env)

    path = settings.data_dir / SECRET_KEY_FILE_NAME
    if path.exists():
        existing = path.read_text(encoding="utf-8").strip()
        if len(existing) >= 32:
            return Secret(existing)

    key = secrets.token_hex(32)
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        handle.write(key)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)
    return Secret(key)
