"""Logging: JSON lines in a rotating file, secrets masked below debug level (TR-400, 401, 402, Q13).

Use it like this::

    log = get_logger("sync")
    log.info("pulled", extra=fields(family_id=3, devices=2))

* Level and rotation (size, file count) come from the settings.
* ``Secret`` values and fields with a sensitive name (token, password, hash, ...) are masked.
  Only when the log level is **debug** are they written in clear text, in the log and in the debug
  export. The UI warns before such a log is shared.
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from typing import Any

from dashboard.config import Settings
from dashboard.domain.secret import Secret, is_sensitive_field, mask

ROOT_NAME = "dashboard"
HANDLER_MARK = "_dashboard_handler"
MAX_DEPTH = 6


def get_logger(name: str) -> logging.Logger:
    """The logger of one part of the dashboard (``dashboard.<name>``)."""
    return logging.getLogger(f"{ROOT_NAME}.{name}" if name else ROOT_NAME)


def fields(**values: Any) -> dict[str, Any]:
    """Structured fields for a log call: ``log.info("event", extra=fields(user_id=1))``."""
    return {"fields": values}


def _clean(value: Any, reveal: bool, key: str | None = None, depth: int = 0) -> Any:
    """A JSON-safe copy of ``value`` with secrets masked (or revealed at debug level)."""
    if isinstance(value, Secret):
        return value.reveal() if reveal else mask(value)
    if (
        key is not None
        and is_sensitive_field(key)
        and not isinstance(value, (dict, list, tuple))
    ):
        return value if reveal else mask(value)
    if depth >= MAX_DEPTH:
        return "<too deep>"
    if isinstance(value, dict):
        return {str(k): _clean(v, reveal, str(k), depth + 1) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_clean(v, reveal, None, depth + 1) for v in value]
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    return str(value)


class JsonFormatter(logging.Formatter):
    """One JSON object per line. ``reveal_secrets`` is true only at debug level."""

    def __init__(self, reveal_secrets: bool) -> None:
        super().__init__()
        self.reveal_secrets = reveal_secrets

    def _message(self, record: logging.LogRecord) -> str:
        args = record.args
        if self.reveal_secrets and args:
            if isinstance(args, dict):
                shown: Any = {
                    k: v.reveal() if isinstance(v, Secret) else v
                    for k, v in args.items()
                }
            else:
                shown = tuple(v.reveal() if isinstance(v, Secret) else v for v in args)
            return str(str(record.msg) % shown)
        return record.getMessage()

    def format(self, record: logging.LogRecord) -> str:
        entry: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, timezone.utc).isoformat(
                timespec="milliseconds"
            ),
            "level": record.levelname.lower(),
            "logger": record.name,
            "message": self._message(record),
        }
        extra = getattr(record, "fields", None)
        if isinstance(extra, dict):
            entry.update(_clean(extra, self.reveal_secrets))
        if record.exc_info:
            entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(entry, ensure_ascii=False)


def _remove_our_handlers(logger: logging.Logger) -> None:
    for handler in list(logger.handlers):
        if getattr(handler, HANDLER_MARK, False):
            logger.removeHandler(handler)
            handler.close()


def configure_logging(settings: Settings, console: bool = True) -> logging.Logger:
    """Install the file handler (rotating) and optionally a console handler. Safe to call twice."""
    settings.log_dir.mkdir(parents=True, exist_ok=True)
    root = logging.getLogger(ROOT_NAME)
    _remove_our_handlers(root)
    level = getattr(logging, settings.log_level)
    formatter = JsonFormatter(reveal_secrets=settings.log_level == "DEBUG")

    handlers: list[logging.Handler] = [
        RotatingFileHandler(
            settings.log_file,
            maxBytes=settings.log_max_bytes,
            backupCount=settings.log_backup_count,
            encoding="utf-8",
        )
    ]
    if console:
        handlers.append(logging.StreamHandler(sys.stderr))
    for handler in handlers:
        handler.setFormatter(formatter)
        handler.setLevel(level)
        setattr(handler, HANDLER_MARK, True)
        root.addHandler(handler)
    root.setLevel(level)
    root.propagate = False
    return root


def shutdown_logging() -> None:
    """Close and remove the dashboard handlers (releases the log file, important on Windows)."""
    _remove_our_handlers(logging.getLogger(ROOT_NAME))
