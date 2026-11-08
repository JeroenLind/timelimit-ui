"""Plan step A3: log files rotate; secrets are masked below debug level (TR-401, TR-402, Q13)."""

from __future__ import annotations

import json
import logging
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from dashboard.config import DATA_DIR_ENV, load_settings
from dashboard.domain.secret import Secret
from dashboard.logs import configure_logging, fields, get_logger, shutdown_logging

TOKEN = "tok-3f9a-very-secret-0001"
HASH = "second-hash-9d2c"
PASSWORD = "p4ssw0rd-typed"


@pytest.fixture(autouse=True)
def _close_logging() -> Iterator[None]:
    yield
    shutdown_logging()


def _settings(data_dir: Path, **overrides: str) -> Any:
    env = {DATA_DIR_ENV: str(data_dir)}
    env.update({f"DASHBOARD_{k.upper()}": v for k, v in overrides.items()})
    return load_settings(env)


def _lines(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line
    ]


def _log_secrets() -> None:
    log = get_logger("test")
    log.info("link %s and %r", Secret(TOKEN), Secret(TOKEN))
    log.info(
        "with fields",
        extra=fields(
            token=TOKEN,
            device_auth_token=Secret(TOKEN),
            parentPasswordSecondHash=HASH,
            nested={"password": PASSWORD, "list": [{"hash": HASH}], "ok": 1},
            family_id=7,
        ),
    )
    log.debug("debug line %s", Secret(TOKEN), extra=fields(password=PASSWORD))


@pytest.mark.parametrize("level", ["info", "warn", "error"])
def test_secrets_are_masked_below_debug_level(level: str, data_dir: Path) -> None:
    settings = _settings(data_dir, log_level=level)
    configure_logging(settings, console=False)
    _log_secrets()
    get_logger("test").error("boom", extra=fields(token=TOKEN))
    shutdown_logging()
    text = settings.log_file.read_text(encoding="utf-8")
    for secret in (TOKEN, HASH, PASSWORD):
        assert secret not in text
    assert "***" in text


def test_info_level_keeps_the_harmless_fields(data_dir: Path) -> None:
    settings = _settings(data_dir, log_level="info")
    configure_logging(settings, console=False)
    _log_secrets()
    shutdown_logging()
    entries = _lines(settings.log_file)
    assert [e["message"] for e in entries] == [
        "link *** and Secret(***)",
        "with fields",
    ]
    assert entries[1]["family_id"] == 7
    assert entries[1]["nested"]["ok"] == 1
    assert entries[1]["nested"]["password"] == "***"
    assert entries[1]["nested"]["list"] == [{"hash": "***"}]


def test_debug_level_writes_secrets_in_clear_text(data_dir: Path) -> None:
    settings = _settings(data_dir, log_level="debug")
    configure_logging(settings, console=False)
    _log_secrets()
    shutdown_logging()
    entries = _lines(settings.log_file)
    assert len(entries) == 3
    assert entries[0]["message"] == f"link {TOKEN} and {TOKEN!r}"
    assert entries[1]["token"] == TOKEN
    assert entries[1]["device_auth_token"] == TOKEN
    assert entries[1]["parentPasswordSecondHash"] == HASH
    assert entries[1]["nested"]["password"] == PASSWORD
    assert entries[2]["password"] == PASSWORD


def test_level_filters_lower_lines(data_dir: Path) -> None:
    settings = _settings(data_dir, log_level="warn")
    configure_logging(settings, console=False)
    log = get_logger("x")
    log.info("hidden")
    log.warning("shown")
    shutdown_logging()
    assert [e["message"] for e in _lines(settings.log_file)] == ["shown"]


def test_every_line_is_json_with_time_level_and_logger(data_dir: Path) -> None:
    settings = _settings(data_dir)
    configure_logging(settings, console=False)
    try:
        raise ValueError("bad")
    except ValueError:
        get_logger("sync").exception("failed", extra=fields(step="pull"))
    shutdown_logging()
    (entry,) = _lines(settings.log_file)
    assert entry["level"] == "error" and entry["logger"] == "dashboard.sync"
    assert entry["step"] == "pull" and "ValueError: bad" in entry["exception"]
    assert entry["timestamp"].endswith("+00:00")


def test_log_files_rotate_at_the_configured_size_and_count(data_dir: Path) -> None:
    settings = _settings(data_dir, log_max_bytes="2000", log_backup_count="2")
    configure_logging(settings, console=False)
    log = get_logger("rotate")
    for number in range(200):
        log.info("line %04d %s", number, "x" * 60)
    shutdown_logging()
    files = sorted(p.name for p in settings.log_dir.iterdir())
    assert files == ["dashboard.log", "dashboard.log.1", "dashboard.log.2"]
    for path in settings.log_dir.iterdir():
        assert path.stat().st_size <= 2000
    newest = _lines(settings.log_file)[-1]["message"]
    assert newest.startswith("line 0199")


def test_configuring_twice_does_not_duplicate_lines(data_dir: Path) -> None:
    settings = _settings(data_dir)
    configure_logging(settings, console=False)
    configure_logging(settings, console=False)
    get_logger("a").info("once")
    shutdown_logging()
    assert len(_lines(settings.log_file)) == 1


def test_shutdown_releases_the_file(data_dir: Path) -> None:
    settings = _settings(data_dir)
    configure_logging(settings, console=False)
    shutdown_logging()
    assert not [
        h
        for h in logging.getLogger("dashboard").handlers
        if hasattr(h, "_dashboard_handler")
    ]
    settings.log_file.unlink()  # would fail on Windows while the handler holds the file
