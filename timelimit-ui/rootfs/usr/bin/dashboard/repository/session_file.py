"""The session file with backup (kept behaviour, TR-202): the link survives a lost or damaged database.

The file holds, per server profile, the device token, own ids and the sequence counter. It is written
atomically (temp file, then replace) and the previous good version is kept as ``.bak``. It never holds a
password. The token is on the local disk only (SEC-003).
"""

from __future__ import annotations

import json
import os
import shutil
import threading
from pathlib import Path
from typing import Any

from ..logs import fields, get_logger

log = get_logger("session_file")
FILE_VERSION = 1


class SessionFile:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.backup = path.with_name(path.name + ".bak")
        self._lock = threading.Lock()

    def _read_one(self, path: Path) -> dict[str, dict[str, Any]] | None:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            links = data["links"]
            if data.get("version") != FILE_VERSION or not isinstance(links, dict):
                return None
            return {str(key): dict(value) for key, value in links.items()}
        except (OSError, ValueError, KeyError, TypeError):
            return None

    def read(self) -> dict[str, dict[str, Any]]:
        """All saved links; falls back to the backup when the main file is missing or damaged."""
        for path in (self.path, self.backup):
            if path.exists():
                links = self._read_one(path)
                if links is not None:
                    return links
                log.warning("session file unreadable", extra=fields(file=path.name))
        return {}

    def save(self, profile_key: str, entry: dict[str, Any] | None) -> None:
        """Set (or, with ``None``, remove) one profile's entry."""
        with self._lock:
            links = self.read()
            if entry is None:
                links.pop(profile_key, None)
            else:
                links[profile_key] = entry
            payload = json.dumps({"version": FILE_VERSION, "links": links}, indent=2)
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temp = self.path.with_name(self.path.name + ".tmp")
            temp.write_text(payload, encoding="utf-8")
            if self.path.exists() and self._read_one(self.path) is not None:
                shutil.copyfile(self.path, self.backup)
            os.replace(temp, self.path)
