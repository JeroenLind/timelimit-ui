"""Pending restores of "rule off for today" (FR-307, decision W4): they survive restarts and cache resets."""

from __future__ import annotations

from dataclasses import dataclass

from .db import Database


@dataclass(frozen=True)
class PendingRestore:
    profile_key: str
    family_id: str
    category_id: str
    rule_id: str
    day_bit: int  # the weekday bit that was removed from the rule's day mask
    mask_set: int  # the mask the dashboard put on the server (to detect later changes by others, W5)
    restore_at: int  # ms since epoch
    created_at: int
    rule_set: str = (
        "{}"  # JSON of the rule as the dashboard set it (the state to compare with, W5)
    )


class PendingRestoreRepository:
    def __init__(self, db: Database) -> None:
        self._db = db

    def add(self, item: PendingRestore) -> None:
        values = (
            item.family_id,
            item.category_id,
            item.day_bit,
            item.mask_set,
            item.restore_at,
            item.created_at,
            item.rule_set,
        )
        with self._db.transaction() as conn:
            updated = conn.execute(
                "UPDATE pending_restore SET family_id=?, category_id=?, day_bit=?, mask_set=?, restore_at=?, created_at=?, rule_set=?"
                " WHERE profile_key=? AND rule_id=?",
                (*values, item.profile_key, item.rule_id),
            ).rowcount
            if updated == 0:
                conn.execute(
                    "INSERT INTO pending_restore (family_id, category_id, day_bit, mask_set, restore_at, created_at,"
                    " rule_set, profile_key, rule_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (*values, item.profile_key, item.rule_id),
                )

    def for_profile(self, profile_key: str) -> list[PendingRestore]:
        rows = self._db.connection().execute(
            "SELECT * FROM pending_restore WHERE profile_key=? ORDER BY restore_at, rule_id",
            (profile_key,),
        )
        return [_restore(r) for r in rows]

    def get(self, profile_key: str, rule_id: str) -> PendingRestore | None:
        return next(
            (r for r in self.for_profile(profile_key) if r.rule_id == rule_id), None
        )

    def due(self, profile_key: str, now_ms: int) -> list[PendingRestore]:
        return [r for r in self.for_profile(profile_key) if r.restore_at <= now_ms]

    def remove(self, profile_key: str, rule_id: str) -> bool:
        with self._db.transaction() as conn:
            return (
                conn.execute(
                    "DELETE FROM pending_restore WHERE profile_key=? AND rule_id=?",
                    (profile_key, rule_id),
                ).rowcount
                > 0
            )


def _restore(row: object) -> PendingRestore:
    r = row
    return PendingRestore(
        profile_key=r["profile_key"],  # type: ignore[index]
        family_id=r["family_id"],  # type: ignore[index]
        category_id=r["category_id"],  # type: ignore[index]
        rule_id=r["rule_id"],  # type: ignore[index]
        day_bit=int(r["day_bit"]),  # type: ignore[index]
        mask_set=int(r["mask_set"]),  # type: ignore[index]
        restore_at=int(r["restore_at"]),  # type: ignore[index]
        created_at=int(r["created_at"]),  # type: ignore[index]
        rule_set=str(r["rule_set"]),  # type: ignore[index]
    )
