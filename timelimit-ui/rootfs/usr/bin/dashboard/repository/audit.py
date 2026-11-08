"""Audit log of changes made through the dashboard (retention 30 days, shown per child; plan E12)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from .db import Database

RETENTION_DAYS = 30


@dataclass(frozen=True)
class AuditEntry:
    id: int
    at: int
    child_id: str | None
    category_id: str | None
    action: str
    detail: dict[str, Any]


class AuditRepository:
    def __init__(self, db: Database) -> None:
        self._db = db

    def append(
        self,
        profile_key: str,
        *,
        at: int,
        action: str,
        child_id: str | None = None,
        category_id: str | None = None,
        detail: dict[str, Any] | None = None,
    ) -> None:
        with self._db.transaction() as conn:
            conn.execute(
                "INSERT INTO audit_log (profile_key, at, child_id, category_id, action, detail) VALUES (?, ?, ?, ?, ?, ?)",
                (
                    profile_key,
                    at,
                    child_id,
                    category_id,
                    action,
                    json.dumps(detail or {}, sort_keys=True),
                ),
            )

    def list(
        self, profile_key: str, *, child_id: str | None = None, limit: int = 200
    ) -> list[AuditEntry]:
        sql = "SELECT * FROM audit_log WHERE profile_key=?"
        args: list[Any] = [profile_key]
        if child_id is not None:
            sql += " AND child_id=?"
            args.append(child_id)
        sql += " ORDER BY at DESC, id DESC LIMIT ?"
        args.append(limit)
        return [
            AuditEntry(
                id=int(r["id"]),
                at=int(r["at"]),
                child_id=r["child_id"],
                category_id=r["category_id"],
                action=r["action"],
                detail=json.loads(r["detail"]),
            )
            for r in self._db.connection().execute(sql, args)
        ]

    def purge_older_than(self, cutoff_ms: int) -> int:
        with self._db.transaction() as conn:
            return conn.execute(
                "DELETE FROM audit_log WHERE at < ?", (cutoff_ms,)
            ).rowcount
