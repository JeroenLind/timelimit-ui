"""The cache of server data, keyed by server profile and family id (plan B1, TR-200, design 4).

Entities keep the server's full record as JSON plus the columns we query by. Each ``set_*`` method
replaces one part exactly like the server sends it (the sync engine in step B3 decides what to call);
combine several calls in ``db.transaction()`` to make them atomic. Items the server no longer reports
stay, flagged ``on_server=False`` (FR-206), until :meth:`CacheRepository.purge_missing`.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from .db import Database


@dataclass(frozen=True)
class Scope:
    """Whose data this is: one server profile and the family id the server reported."""

    profile_key: str
    family_id: str

    @property
    def args(self) -> tuple[str, str]:
        return (self.profile_key, self.family_id)


@dataclass(frozen=True)
class CachedItem:
    data: dict[str, Any]
    on_server: bool


class CacheRepository:
    def __init__(self, db: Database) -> None:
        self._db = db

    # -- scope ---------------------------------------------------------------------------------------
    def activate(self, profile_key: str, family_id: str) -> Scope:
        """Select the family of a profile. A different family id (the server was reset or the link moved to
        another family) drops everything cached for the profile (FR-103)."""
        with self._db.transaction() as conn:
            row = conn.execute(
                "SELECT family_id FROM cache_scope WHERE profile_key=?", (profile_key,)
            ).fetchone()
            if row is None:
                conn.execute(
                    "INSERT INTO cache_scope (profile_key, family_id) VALUES (?, ?)",
                    (profile_key, family_id),
                )
            elif row["family_id"] != family_id:
                self._clear_profile(profile_key)
                conn.execute(
                    "UPDATE cache_scope SET family_id=? WHERE profile_key=?",
                    (family_id, profile_key),
                )
        return Scope(profile_key, family_id)

    def clear_profile(self, profile_key: str) -> None:
        """Forget everything cached for one profile (not its link, settings or pending restores)."""
        with self._db.transaction():
            self._clear_profile(profile_key)

    def _clear_profile(self, profile_key: str) -> None:
        conn = self._db.connection()
        for table in (
            "versions",
            "devices",
            "users",
            "categories",
            "category_apps",
            "rules",
            "used_time",
            "own_used_time",
            "installed_apps",
        ):
            conn.execute(f"DELETE FROM {table} WHERE profile_key=?", (profile_key,))

    # -- versions --------------------------------------------------------------------------------------
    def _set_version(self, scope: Scope, name: str, value: str) -> None:
        # One atomic statement: update-then-insert let two threads both insert (found in B3).
        self._db.connection().execute(
            "INSERT INTO versions (profile_key, family_id, name, value) VALUES (?, ?, ?, ?)"
            " ON CONFLICT (profile_key, family_id, name) DO UPDATE SET value=excluded.value",
            (*scope.args, name, value),
        )

    def version(self, scope: Scope, name: str) -> str:
        row = (
            self._db.connection()
            .execute(
                "SELECT value FROM versions WHERE profile_key=? AND family_id=? AND name=?",
                (*scope.args, name),
            )
            .fetchone()
        )
        return str(row["value"]) if row else ""

    # -- bookkeeping that is not a version of server data ---------------------------------------------
    def set_meta(self, scope: Scope, name: str, value: str) -> None:
        """Small facts about the cache (server info, the "full resync" notice). Not sent to the server."""
        self._set_version(scope, f"meta:{name}", value)

    def meta(self, scope: Scope, name: str) -> str:
        return self.version(scope, f"meta:{name}")

    def forget_versions(self, scope: Scope) -> None:
        """After ``shouldDoFullSync`` (FR-202): the next pull asks for everything. The data stays in place
        until the answer replaces it, so a failed pull leaves the cache usable."""
        with self._db.transaction() as conn:
            conn.execute(
                "DELETE FROM versions WHERE profile_key=? AND family_id=? AND name NOT LIKE 'meta:%'",
                scope.args,
            )
            conn.execute(
                "UPDATE categories SET base_version='', apps_version='', rules_version='',"
                " used_time_version='' WHERE profile_key=? AND family_id=?",
                scope.args,
            )

    # -- devices and users ---------------------------------------------------------------------------------
    def set_devices(
        self, scope: Scope, devices: Iterable[dict[str, Any]], version: str
    ) -> None:
        with self._db.transaction():
            self._replace_entities(
                scope,
                "devices",
                "device_id",
                {d["deviceId"]: d for d in devices},
                mark_missing=True,
            )
            self._set_version(scope, "devices", version)

    def set_users(
        self, scope: Scope, users: Iterable[dict[str, Any]], version: str
    ) -> None:
        with self._db.transaction():
            self._replace_entities(
                scope,
                "users",
                "user_id",
                {u["id"]: u for u in users},
                mark_missing=True,
            )
            self._set_version(scope, "users", version)

    def devices(self, scope: Scope) -> list[CachedItem]:
        return self._items(scope, "devices", "device_id")

    def users(self, scope: Scope) -> list[CachedItem]:
        return self._items(scope, "users", "user_id")

    def _replace_entities(
        self,
        scope: Scope,
        table: str,
        key: str,
        entities: dict[str, dict[str, Any]],
        *,
        mark_missing: bool,
    ) -> None:
        with self._db.transaction() as conn:
            for entity_id, data in entities.items():
                payload = json.dumps(data, sort_keys=True)
                if (
                    conn.execute(
                        f"UPDATE {table} SET data=?, on_server=1 WHERE profile_key=? AND family_id=? AND {key}=?",
                        (payload, *scope.args, entity_id),
                    ).rowcount
                    == 0
                ):
                    conn.execute(
                        f"INSERT INTO {table} (profile_key, family_id, {key}, data) VALUES (?, ?, ?, ?)",
                        (*scope.args, entity_id, payload),
                    )
            if mark_missing:
                present = list(entities)
                marks = ",".join("?" * len(present))
                conn.execute(
                    f"UPDATE {table} SET on_server=0 WHERE profile_key=? AND family_id=?"
                    + (f" AND {key} NOT IN ({marks})" if present else ""),
                    (*scope.args, *present),
                )

    def _items(self, scope: Scope, table: str, key: str) -> list[CachedItem]:
        rows = self._db.connection().execute(
            f"SELECT data, on_server FROM {table} WHERE profile_key=? AND family_id=? ORDER BY {key}",
            scope.args,
        )
        return [CachedItem(json.loads(r["data"]), bool(r["on_server"])) for r in rows]

    # -- categories ----------------------------------------------------------------------------------------------
    def set_category_base(
        self, scope: Scope, entries: Iterable[dict[str, Any]]
    ) -> None:
        """``ServerUpdatedCategoryBaseData`` entries: insert or update, keep the other parts' versions."""
        with self._db.transaction() as conn:
            for entry in entries:
                payload = json.dumps(entry, sort_keys=True)
                values = (entry["childId"], payload, entry["version"])
                if (
                    conn.execute(
                        "UPDATE categories SET child_id=?, data=?, base_version=?, on_server=1"
                        " WHERE profile_key=? AND family_id=? AND category_id=?",
                        (*values, *scope.args, entry["categoryId"]),
                    ).rowcount
                    == 0
                ):
                    conn.execute(
                        "INSERT INTO categories (child_id, data, base_version, profile_key, family_id, category_id)"
                        " VALUES (?, ?, ?, ?, ?, ?)",
                        (*values, *scope.args, entry["categoryId"]),
                    )

    def remove_categories(self, scope: Scope, category_ids: Iterable[str]) -> None:
        """The server removed these: they stay, flagged (FR-206)."""
        with self._db.transaction() as conn:
            for category_id in category_ids:
                conn.execute(
                    "UPDATE categories SET on_server=0 WHERE profile_key=? AND family_id=? AND category_id=?",
                    (*scope.args, category_id),
                )

    def categories(self, scope: Scope, child_id: str | None = None) -> list[CachedItem]:
        sql = (
            "SELECT data, on_server FROM categories WHERE profile_key=? AND family_id=?"
        )
        args: list[Any] = [*scope.args]
        if child_id is not None:
            sql += " AND child_id=?"
            args.append(child_id)
        rows = self._db.connection().execute(sql + " ORDER BY category_id", args)
        return [CachedItem(json.loads(r["data"]), bool(r["on_server"])) for r in rows]

    def _category_exists(self, scope: Scope, category_id: str) -> None:
        row = (
            self._db.connection()
            .execute(
                "SELECT 1 FROM categories WHERE profile_key=? AND family_id=? AND category_id=?",
                (*scope.args, category_id),
            )
            .fetchone()
        )
        if row is None:
            raise LookupError(
                f"category {category_id} is not cached (its base data must arrive first)"
            )

    def _set_category_version(
        self, scope: Scope, category_id: str, column: str, version: str
    ) -> None:
        self._db.connection().execute(
            f"UPDATE categories SET {column}=? WHERE profile_key=? AND family_id=? AND category_id=?",
            (version, *scope.args, category_id),
        )

    def set_category_apps(
        self, scope: Scope, category_id: str, packages: Iterable[str], version: str
    ) -> None:
        with self._db.transaction() as conn:
            self._category_exists(scope, category_id)
            conn.execute(
                "DELETE FROM category_apps WHERE profile_key=? AND family_id=? AND category_id=?",
                (*scope.args, category_id),
            )
            conn.executemany(
                "INSERT OR IGNORE INTO category_apps (profile_key, family_id, category_id, package_name) VALUES (?, ?, ?, ?)",
                [(*scope.args, category_id, p) for p in packages],
            )
            self._set_category_version(scope, category_id, "apps_version", version)

    def category_apps(self, scope: Scope, category_id: str) -> list[str]:
        rows = self._db.connection().execute(
            "SELECT package_name FROM category_apps WHERE profile_key=? AND family_id=? AND category_id=?"
            " ORDER BY package_name",
            (*scope.args, category_id),
        )
        return [str(r["package_name"]) for r in rows]

    def set_category_rules(
        self,
        scope: Scope,
        category_id: str,
        rules: Iterable[dict[str, Any]],
        version: str,
    ) -> None:
        with self._db.transaction() as conn:
            self._category_exists(scope, category_id)
            incoming = {r["id"]: r for r in rules}
            for rule_id, data in incoming.items():
                payload = json.dumps(data, sort_keys=True)
                if (
                    conn.execute(
                        "UPDATE rules SET category_id=?, data=?, on_server=1 WHERE profile_key=? AND family_id=? AND rule_id=?",
                        (category_id, payload, *scope.args, rule_id),
                    ).rowcount
                    == 0
                ):
                    conn.execute(
                        "INSERT INTO rules (profile_key, family_id, rule_id, category_id, data) VALUES (?, ?, ?, ?, ?)",
                        (*scope.args, rule_id, category_id, payload),
                    )
            present = list(incoming)
            conn.execute(
                "UPDATE rules SET on_server=0 WHERE profile_key=? AND family_id=? AND category_id=?"
                + (
                    f" AND rule_id NOT IN ({','.join('?' * len(present))})"
                    if present
                    else ""
                ),
                (*scope.args, category_id, *present),
            )
            self._set_category_version(scope, category_id, "rules_version", version)

    def rules(self, scope: Scope, category_id: str) -> list[CachedItem]:
        rows = self._db.connection().execute(
            "SELECT data, on_server FROM rules WHERE profile_key=? AND family_id=? AND category_id=? ORDER BY rule_id",
            (*scope.args, category_id),
        )
        return [CachedItem(json.loads(r["data"]), bool(r["on_server"])) for r in rows]

    def forget_rule(self, scope: Scope, rule_id: str) -> None:
        """Remove one rule that is already flagged "no longer on server" (the parent deleted it herself)."""
        self._db.connection().execute(
            "DELETE FROM rules WHERE profile_key=? AND family_id=? AND rule_id=? AND on_server=0",
            (*scope.args, rule_id),
        )

    # -- used time ---------------------------------------------------------------------------------------------------
    def set_category_used_times(
        self,
        scope: Scope,
        category_id: str,
        times: Iterable[dict[str, Any]],
        version: str,
    ) -> None:
        """Server-reported used time per day and time slot (``times`` of ``ServerUpdatedCategoryUsedTimes``)."""
        with self._db.transaction() as conn:
            self._category_exists(scope, category_id)
            conn.execute(
                "DELETE FROM used_time WHERE profile_key=? AND family_id=? AND category_id=?",
                (*scope.args, category_id),
            )
            conn.executemany(
                "INSERT OR REPLACE INTO used_time (profile_key, family_id, category_id, day, start_minute, end_minute,"
                " time_ms) VALUES (?, ?, ?, ?, ?, ?, ?)",
                [
                    (
                        *scope.args,
                        category_id,
                        t["day"],
                        t["start"],
                        t["end"],
                        t["time"],
                    )
                    for t in times
                ],
            )
            self._set_category_version(scope, category_id, "used_time_version", version)

    def used_time_by_day(self, scope: Scope, category_id: str) -> dict[int, int]:
        """Total used milliseconds per day (days counted since the epoch, as the server does)."""
        rows = self._db.connection().execute(
            "SELECT day, SUM(time_ms) AS total FROM used_time WHERE profile_key=? AND family_id=? AND category_id=?"
            " GROUP BY day ORDER BY day",
            (*scope.args, category_id),
        )
        return {int(r["day"]): int(r["total"]) for r in rows}

    def add_own_used_time(
        self, scope: Scope, category_id: str, day: int, time_ms: int
    ) -> None:
        """The dashboard's own daily totals, so history grows past what the server sends (Q10, lost on reset)."""
        with self._db.transaction() as conn:
            if (
                conn.execute(
                    "UPDATE own_used_time SET time_ms=? WHERE profile_key=? AND family_id=? AND category_id=? AND day=?",
                    (time_ms, *scope.args, category_id, day),
                ).rowcount
                == 0
            ):
                conn.execute(
                    "INSERT INTO own_used_time (profile_key, family_id, category_id, day, time_ms) VALUES (?, ?, ?, ?, ?)",
                    (*scope.args, category_id, day, time_ms),
                )

    def own_used_time(self, scope: Scope, category_id: str) -> dict[int, int]:
        rows = self._db.connection().execute(
            "SELECT day, time_ms FROM own_used_time WHERE profile_key=? AND family_id=? AND category_id=? ORDER BY day",
            (*scope.args, category_id),
        )
        return {int(r["day"]): int(r["time_ms"]) for r in rows}

    # -- installed apps (no tasks are stored: decision R2) -------------------------------------------------------------
    def set_installed_apps(
        self, scope: Scope, device_id: str, apps: Iterable[dict[str, Any]], version: str
    ) -> None:
        with self._db.transaction() as conn:
            conn.execute(
                "DELETE FROM installed_apps WHERE profile_key=? AND family_id=? AND device_id=?",
                (*scope.args, device_id),
            )
            conn.executemany(
                "INSERT OR REPLACE INTO installed_apps (profile_key, family_id, device_id, package_name, data)"
                " VALUES (?, ?, ?, ?, ?)",
                [
                    (
                        *scope.args,
                        device_id,
                        a["packageName"],
                        json.dumps(a, sort_keys=True),
                    )
                    for a in apps
                ],
            )
            self._set_version(scope, f"apps:{device_id}", version)

    def installed_apps(self, scope: Scope, device_id: str) -> list[dict[str, Any]]:
        rows = self._db.connection().execute(
            "SELECT data FROM installed_apps WHERE profile_key=? AND family_id=? AND device_id=? ORDER BY package_name",
            (*scope.args, device_id),
        )
        return [json.loads(r["data"]) for r in rows]

    # -- what we tell the server we have -----------------------------------------------------------------------------------
    def client_status(self, scope: Scope) -> dict[str, Any]:
        """``ClientDataStatus`` without ``clientLevel``: all versions we hold (TR-103)."""
        conn = self._db.connection()
        apps = {
            str(r["name"])[len("apps:") :]: str(r["value"])
            for r in conn.execute(
                "SELECT name, value FROM versions WHERE profile_key=? AND family_id=? AND name LIKE 'apps:%'",
                scope.args,
            )
        }
        categories = {
            str(r["category_id"]): {
                "base": r["base_version"],
                "apps": r["apps_version"],
                "rules": r["rules_version"],
                "usedTime": r["used_time_version"],
                "tasks": "",
            }
            for r in conn.execute(
                "SELECT * FROM categories WHERE profile_key=? AND family_id=? AND on_server=1",
                scope.args,
            )
        }
        status: dict[str, Any] = {
            "devices": self.version(scope, "devices"),
            "users": self.version(scope, "users"),
            "apps": apps,
            "categories": categories,
        }
        dh_version = self.version(scope, "dh")
        if dh_version:
            status["dh"] = dh_version
        return status

    # -- the server's DH key (for the encrypted password of a new parent) ---------------------------------------
    def set_dh_key(self, scope: Scope, public_key: str, key_id: str) -> None:
        self.set_meta(scope, "dh_public_key", public_key)
        self._set_version(scope, "dh", key_id)

    def dh_key(self, scope: Scope) -> tuple[str, str] | None:
        """``(public key, key id)`` the server sent, or None when it never did."""
        key, key_id = self.meta(scope, "dh_public_key"), self.version(scope, "dh")
        return (key, key_id) if key and key_id else None

    # -- cleanup ---------------------------------------------------------------------------------------------------------------
    def count_missing(self, scope: Scope) -> int:
        """How many rows are flagged "no longer on server" (what :meth:`purge_missing` would remove)."""
        total = 0
        with self._db.transaction() as conn:
            for table in ("devices", "users", "rules", "categories"):
                row = conn.execute(
                    f"SELECT COUNT(*) AS n FROM {table} WHERE profile_key=? AND family_id=? AND on_server=0",
                    scope.args,
                ).fetchone()
                total += int(row["n"])
        return total

    def purge_missing(self, scope: Scope) -> int:
        """The parent's cleanup of everything flagged "no longer on server". Returns the number of rows removed."""
        removed = 0
        with self._db.transaction() as conn:
            for table in ("devices", "users", "rules"):
                removed += conn.execute(
                    f"DELETE FROM {table} WHERE profile_key=? AND family_id=? AND on_server=0",
                    scope.args,
                ).rowcount
            gone = [
                r["category_id"]
                for r in conn.execute(
                    "SELECT category_id FROM categories WHERE profile_key=? AND family_id=? AND on_server=0",
                    scope.args,
                )
            ]
            for category_id in gone:
                for table in ("category_apps", "rules", "used_time", "own_used_time"):
                    conn.execute(
                        f"DELETE FROM {table} WHERE profile_key=? AND family_id=? AND category_id=?",
                        (*scope.args, category_id),
                    )
                conn.execute(
                    "DELETE FROM categories WHERE profile_key=? AND family_id=? AND category_id=?",
                    (*scope.args, category_id),
                )
                removed += 1
        return removed
