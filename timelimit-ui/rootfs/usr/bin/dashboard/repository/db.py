"""SQLite access: one file, thread-safe connections, transactions, schema and cache reset (plan B1).

Only the ``repository`` package contains SQL (TR-201). Rules of this module:

* one connection per thread (``sqlite3`` objects must not cross threads), WAL, foreign keys, busy timeout;
* every write that touches several tables runs inside :meth:`Database.transaction`, which nests with
  savepoints, so a failure in the middle leaves nothing half-written;
* there is no ``INSERT OR REPLACE`` on state that must not be replaced blindly (the link and the
  sequence counter are only changed with explicit ``UPDATE``);
* a schema version change drops the **cache** tables only. The link, the settings, the sequence counter,
  the pending "rule off for today" restores and the audit log are kept (TR-310). These kept tables only
  ever change by adding columns, never by a rewrite.
"""

from __future__ import annotations

import sqlite3
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

SCHEMA_VERSION = 1
BUSY_TIMEOUT_MS = 5000

# Tables that survive a cache reset. Everything else in the database is cache.
KEPT_TABLES = ("meta", "settings", "link", "pending_restore", "audit_log")

KEPT_SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS link (
    profile_key TEXT PRIMARY KEY,
    device_token TEXT NOT NULL,
    own_device_id TEXT NOT NULL,
    family_id TEXT NOT NULL,
    mail TEXT NOT NULL DEFAULT '',
    next_sequence INTEGER NOT NULL DEFAULT 0,
    linked_at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS pending_restore (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    profile_key TEXT NOT NULL,
    family_id TEXT NOT NULL,
    category_id TEXT NOT NULL,
    rule_id TEXT NOT NULL,
    day_bit INTEGER NOT NULL,
    mask_set INTEGER NOT NULL,
    restore_at INTEGER NOT NULL,
    created_at INTEGER NOT NULL,
    rule_set TEXT NOT NULL DEFAULT '{}',
    UNIQUE (profile_key, rule_id)
);
CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    profile_key TEXT NOT NULL,
    at INTEGER NOT NULL,
    child_id TEXT,
    category_id TEXT,
    action TEXT NOT NULL,
    detail TEXT NOT NULL DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS audit_log_at ON audit_log (profile_key, at);
"""

# Server data. Entities keep the server's full record in ``data`` (JSON) next to the columns we query by.
# ``on_server`` = 0 means "no longer on server" (FR-206): kept until the parent cleans it up.
CACHE_TABLES = (
    "cache_scope",
    "versions",
    "devices",
    "users",
    "categories",
    "category_apps",
    "rules",
    "used_time",
    "own_used_time",
    "installed_apps",
)

CACHE_SCHEMA = """
CREATE TABLE cache_scope (
    profile_key TEXT PRIMARY KEY,
    family_id TEXT NOT NULL
);
CREATE TABLE versions (
    profile_key TEXT NOT NULL,
    family_id TEXT NOT NULL,
    name TEXT NOT NULL,
    value TEXT NOT NULL,
    PRIMARY KEY (profile_key, family_id, name)
);
CREATE TABLE devices (
    profile_key TEXT NOT NULL,
    family_id TEXT NOT NULL,
    device_id TEXT NOT NULL,
    data TEXT NOT NULL,
    on_server INTEGER NOT NULL DEFAULT 1,
    PRIMARY KEY (profile_key, family_id, device_id)
);
CREATE TABLE users (
    profile_key TEXT NOT NULL,
    family_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    data TEXT NOT NULL,
    on_server INTEGER NOT NULL DEFAULT 1,
    PRIMARY KEY (profile_key, family_id, user_id)
);
CREATE TABLE categories (
    profile_key TEXT NOT NULL,
    family_id TEXT NOT NULL,
    category_id TEXT NOT NULL,
    child_id TEXT NOT NULL,
    data TEXT NOT NULL,
    base_version TEXT NOT NULL DEFAULT '',
    apps_version TEXT NOT NULL DEFAULT '',
    rules_version TEXT NOT NULL DEFAULT '',
    used_time_version TEXT NOT NULL DEFAULT '',
    on_server INTEGER NOT NULL DEFAULT 1,
    PRIMARY KEY (profile_key, family_id, category_id)
);
CREATE INDEX categories_child ON categories (profile_key, family_id, child_id);
CREATE TABLE category_apps (
    profile_key TEXT NOT NULL,
    family_id TEXT NOT NULL,
    category_id TEXT NOT NULL,
    package_name TEXT NOT NULL,
    PRIMARY KEY (profile_key, family_id, category_id, package_name)
);
CREATE TABLE rules (
    profile_key TEXT NOT NULL,
    family_id TEXT NOT NULL,
    rule_id TEXT NOT NULL,
    category_id TEXT NOT NULL,
    data TEXT NOT NULL,
    on_server INTEGER NOT NULL DEFAULT 1,
    PRIMARY KEY (profile_key, family_id, rule_id)
);
CREATE INDEX rules_category ON rules (profile_key, family_id, category_id);
CREATE TABLE used_time (
    profile_key TEXT NOT NULL,
    family_id TEXT NOT NULL,
    category_id TEXT NOT NULL,
    day INTEGER NOT NULL,
    start_minute INTEGER NOT NULL,
    end_minute INTEGER NOT NULL,
    time_ms INTEGER NOT NULL,
    PRIMARY KEY (profile_key, family_id, category_id, day, start_minute, end_minute)
);
CREATE TABLE own_used_time (
    profile_key TEXT NOT NULL,
    family_id TEXT NOT NULL,
    category_id TEXT NOT NULL,
    day INTEGER NOT NULL,
    time_ms INTEGER NOT NULL,
    PRIMARY KEY (profile_key, family_id, category_id, day)
);
CREATE TABLE installed_apps (
    profile_key TEXT NOT NULL,
    family_id TEXT NOT NULL,
    device_id TEXT NOT NULL,
    package_name TEXT NOT NULL,
    data TEXT NOT NULL,
    PRIMARY KEY (profile_key, family_id, device_id, package_name)
);
"""


class Database:
    """The SQLite file of one installation. Create once, share between threads."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._local = threading.local()
        self._write_lock = threading.RLock()
        self.cache_was_reset = False
        path.parent.mkdir(parents=True, exist_ok=True)
        self._prepare()

    # -- connections ---------------------------------------------------------------------------------
    def connection(self) -> sqlite3.Connection:
        conn: sqlite3.Connection | None = getattr(self._local, "conn", None)
        if conn is None:
            conn = sqlite3.connect(
                self.path, timeout=BUSY_TIMEOUT_MS / 1000, isolation_level=None
            )
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA foreign_keys=ON")
            conn.execute(f"PRAGMA busy_timeout={BUSY_TIMEOUT_MS}")
            self._local.conn = conn
            self._local.depth = 0
        return conn

    def close(self) -> None:
        """Close the calling thread's connection (tests and shutdown)."""
        conn: sqlite3.Connection | None = getattr(self._local, "conn", None)
        if conn is not None:
            conn.close()
            self._local.conn = None

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        """All-or-nothing block. Nested blocks become savepoints, so an inner failure undoes only itself
        unless it is not caught, in which case the outer block rolls back as well."""
        conn = self.connection()
        depth: int = self._local.depth
        with self._write_lock:
            if depth == 0:
                conn.execute("BEGIN IMMEDIATE")
            else:
                conn.execute(f"SAVEPOINT sp{depth}")
            self._local.depth = depth + 1
            try:
                yield conn
            except BaseException:
                self._local.depth = depth
                conn.execute("ROLLBACK" if depth == 0 else f"ROLLBACK TO sp{depth}")
                if depth:
                    conn.execute(f"RELEASE sp{depth}")
                raise
            else:
                self._local.depth = depth
                conn.execute("COMMIT" if depth == 0 else f"RELEASE sp{depth}")

    # -- schema --------------------------------------------------------------------------------------
    def _prepare(self) -> None:
        conn = self.connection()
        with self.transaction():
            # executescript() would commit; run the statements one by one inside the transaction
            for statement in _statements(KEPT_SCHEMA):
                conn.execute(statement)
            self._add_missing_columns(conn)
            row = conn.execute(
                "SELECT value FROM meta WHERE key='schema_version'"
            ).fetchone()
            found = int(row["value"]) if row else None
            if found != SCHEMA_VERSION:
                self._drop_cache(conn)
                self._create_cache(conn)
                self.cache_was_reset = found is not None
                if row:
                    conn.execute(
                        "UPDATE meta SET value=? WHERE key='schema_version'",
                        (str(SCHEMA_VERSION),),
                    )
                else:
                    conn.execute(
                        "INSERT INTO meta (key, value) VALUES ('schema_version', ?)",
                        (str(SCHEMA_VERSION),),
                    )

    @staticmethod
    def _add_missing_columns(conn: sqlite3.Connection) -> None:
        """Kept tables only ever get new columns: an older file gets them here, nothing is dropped."""
        columns = {
            r["name"] for r in conn.execute("PRAGMA table_info(pending_restore)")
        }
        if "rule_set" not in columns:
            conn.execute(
                "ALTER TABLE pending_restore ADD COLUMN rule_set TEXT NOT NULL DEFAULT '{}'"
            )

    @staticmethod
    def _drop_cache(conn: sqlite3.Connection) -> None:
        for table in CACHE_TABLES:
            conn.execute(f"DROP TABLE IF EXISTS {table}")

    @staticmethod
    def _create_cache(conn: sqlite3.Connection) -> None:
        for statement in _statements(CACHE_SCHEMA):
            conn.execute(statement)

    def reset_cache(self) -> None:
        """Drop and recreate the cache tables. Link, settings, sequence counter, pending restores and
        audit log are untouched; the next sync fetches everything again."""
        with self.transaction() as conn:
            self._drop_cache(conn)
            self._create_cache(conn)


def _statements(script: str) -> list[str]:
    return [part.strip() for part in script.split(";") if part.strip()]
