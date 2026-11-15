"""Read-only look into every table, for the test section's database page (plan E11)."""

from __future__ import annotations

import re
from typing import Any

from dashboard.repository.db import Database

_SECRET_COLUMN = re.compile(r"token|secret|password|hash", re.IGNORECASE)
_TABLE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class DatabaseInspector:
    def __init__(self, db: Database) -> None:
        self._db = db

    def tables(self, max_rows: int) -> list[dict[str, Any]]:
        """Every table with up to ``max_rows`` rows; values of columns that look like secrets are masked."""
        conn = self._db.connection()
        names = [
            r[0]
            for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
            )
        ]
        tables: list[dict[str, Any]] = []
        for name in names:
            if not _TABLE.match(name):
                continue
            cursor = conn.execute(f'SELECT * FROM "{name}" LIMIT {int(max_rows)}')
            columns = [c[0] for c in cursor.description]
            rows = [
                [
                    "***" if _SECRET_COLUMN.search(col) and value else value
                    for col, value in zip(columns, row, strict=True)
                ]
                for row in cursor.fetchall()
            ]
            total = conn.execute(f'SELECT COUNT(*) FROM "{name}"').fetchone()[0]
            tables.append(
                {"name": name, "columns": columns, "rows": rows, "total": total}
            )
        return tables
