"""Persistent settings (key/value), e.g. the selected server (design 8.1). Survive cache resets."""

from __future__ import annotations

from .db import Database


class SettingsRepository:
    def __init__(self, db: Database) -> None:
        self._db = db

    def get(self, key: str, default: str | None = None) -> str | None:
        row = (
            self._db.connection()
            .execute("SELECT value FROM settings WHERE key=?", (key,))
            .fetchone()
        )
        return str(row["value"]) if row else default

    def set(self, key: str, value: str) -> None:
        with self._db.transaction() as conn:
            if (
                conn.execute(
                    "UPDATE settings SET value=? WHERE key=?", (value, key)
                ).rowcount
                == 0
            ):
                conn.execute(
                    "INSERT INTO settings (key, value) VALUES (?, ?)", (key, value)
                )

    def delete(self, key: str) -> None:
        with self._db.transaction() as conn:
            conn.execute("DELETE FROM settings WHERE key=?", (key,))

    def all(self) -> dict[str, str]:
        rows = (
            self._db.connection()
            .execute("SELECT key, value FROM settings ORDER BY key")
            .fetchall()
        )
        return {str(r["key"]): str(r["value"]) for r in rows}
