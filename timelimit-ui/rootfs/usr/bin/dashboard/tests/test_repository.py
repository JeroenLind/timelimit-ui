"""Plan step B1: repository and cache schema (TR-200, 201, 202, 310, FR-103, FR-206, SEC-003)."""

from __future__ import annotations

import json
import sqlite3
import threading
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from dashboard.domain.secret import Secret
from dashboard.repository.audit import AuditRepository
from dashboard.repository.cache import CacheRepository, Scope
from dashboard.repository.db import KEPT_TABLES, SCHEMA_VERSION, Database
from dashboard.repository.links import RECOVERY_MARGIN, LinkRepository
from dashboard.repository.restores import PendingRestore, PendingRestoreRepository
from dashboard.repository.session_file import SessionFile
from dashboard.repository.settings_store import SettingsRepository

PROFILE = "http://localhost:8080"
TYPED_PASSWORD = "correct-horse-battery-staple"

DEVICE = {
    "deviceId": "dev001",
    "name": "Phone",
    "model": "X",
    "currentUserId": "kid001",
}
PARENT = {"id": "par001", "name": "Parent", "type": "parent", "password": "$2a$10$hash"}
CHILD = {"id": "kid001", "name": "Kid", "type": "child", "password": ""}
CATEGORY = {
    "categoryId": "cat001",
    "childId": "kid001",
    "title": "Games",
    "blockedTimes": "0,60",
    "version": "b1",
}
RULE = {
    "id": "rul001",
    "maxTime": 3600000,
    "dayMask": 127,
    "start": 0,
    "end": 1439,
    "extraTime": False,
}


@pytest.fixture
def db(data_dir: Path) -> Iterator[Database]:
    database = Database(data_dir / "dashboard.db")
    yield database
    database.close()


@pytest.fixture
def cache(db: Database) -> CacheRepository:
    return CacheRepository(db)


@pytest.fixture
def scope(cache: CacheRepository) -> Scope:
    return cache.activate(PROFILE, "fam001")


def fill(cache: CacheRepository, scope: Scope) -> None:
    with cache._db.transaction():
        cache.set_devices(scope, [DEVICE], "dv1")
        cache.set_users(scope, [PARENT, CHILD], "uv1")
        cache.set_category_base(scope, [CATEGORY])
        cache.set_category_apps(scope, "cat001", ["com.b", "com.a"], "av1")
        cache.set_category_rules(scope, "cat001", [RULE], "rv1")
        cache.set_category_used_times(
            scope,
            "cat001",
            [
                {"day": 20000, "start": 0, "end": 1439, "time": 60000},
                {"day": 20000, "start": 0, "end": 59, "time": 1000},
                {"day": 20001, "start": 0, "end": 1439, "time": 5},
            ],
            "tv1",
        )
        cache.add_own_used_time(scope, "cat001", 20000, 61000)
        cache.set_installed_apps(
            scope, "dev001", [{"packageName": "com.a", "title": "A"}], "iv1"
        )


# -- round trip -----------------------------------------------------------------------------------------------


def test_every_entity_makes_a_round_trip(cache: CacheRepository, scope: Scope) -> None:
    fill(cache, scope)
    assert [i.data for i in cache.devices(scope)] == [DEVICE]
    assert [i.data for i in cache.users(scope)] == [CHILD, PARENT]  # ordered by id
    assert [i.data for i in cache.categories(scope)] == [CATEGORY]
    assert [i.data for i in cache.categories(scope, "nobody")] == []
    assert cache.category_apps(scope, "cat001") == ["com.a", "com.b"]
    assert [i.data for i in cache.rules(scope, "cat001")] == [RULE]
    assert cache.used_time_by_day(scope, "cat001") == {20000: 61000, 20001: 5}
    assert cache.own_used_time(scope, "cat001") == {20000: 61000}
    assert cache.installed_apps(scope, "dev001") == [
        {"packageName": "com.a", "title": "A"}
    ]
    assert all(i.on_server for i in cache.users(scope))


def test_client_status_lists_all_versions_we_hold(
    cache: CacheRepository, scope: Scope
) -> None:
    assert cache.client_status(scope) == {
        "devices": "",
        "users": "",
        "apps": {},
        "categories": {},
    }
    fill(cache, scope)
    assert cache.client_status(scope) == {
        "devices": "dv1",
        "users": "uv1",
        "apps": {"dev001": "iv1"},
        "categories": {
            "cat001": {
                "base": "b1",
                "apps": "av1",
                "rules": "rv1",
                "usedTime": "tv1",
                "tasks": "",
            }
        },
    }


def test_a_part_replaces_the_previous_one_like_the_server_sends_it(
    cache: CacheRepository, scope: Scope
) -> None:
    fill(cache, scope)
    cache.set_category_apps(scope, "cat001", ["com.c"], "av2")
    cache.set_category_used_times(scope, "cat001", [], "tv2")
    assert cache.category_apps(scope, "cat001") == ["com.c"]
    assert cache.used_time_by_day(scope, "cat001") == {}
    assert cache.client_status(scope)["categories"]["cat001"]["apps"] == "av2"


def test_a_part_of_an_unknown_category_is_refused(
    cache: CacheRepository, scope: Scope
) -> None:
    with pytest.raises(LookupError):
        cache.set_category_apps(scope, "nocat1", ["com.a"], "v")


# -- flags, scopes ------------------------------------------------------------------------------------------------


def test_things_the_server_stops_reporting_are_kept_and_flagged_until_purged(
    cache: CacheRepository, scope: Scope
) -> None:
    fill(cache, scope)
    cache.set_users(scope, [PARENT], "uv2")
    cache.remove_categories(scope, ["cat001"])
    cache.set_category_rules(scope, "cat001", [], "rv2")
    flags = {i.data["id"]: i.on_server for i in cache.users(scope)}
    assert flags == {"par001": True, "kid001": False}
    assert [i.on_server for i in cache.categories(scope)] == [False]
    assert [i.on_server for i in cache.rules(scope, "cat001")] == [False]
    assert "cat001" not in cache.client_status(scope)["categories"]
    assert (
        cache.purge_missing(scope) == 3
    )  # user, rule, category (the removed category's data goes with it)
    assert [i.data["id"] for i in cache.users(scope)] == ["par001"]
    assert cache.categories(scope) == []
    assert cache.category_apps(scope, "cat001") == []


def test_profiles_do_not_mix_and_a_new_family_drops_only_its_profile(
    cache: CacheRepository,
) -> None:
    one = cache.activate("https://one.example.org", "fam001")
    two = cache.activate("https://two.example.org", "fam001")
    cache.set_users(one, [PARENT], "u")
    cache.set_users(two, [CHILD], "u")
    assert [i.data["id"] for i in cache.users(one)] == ["par001"]
    assert [i.data["id"] for i in cache.users(two)] == ["kid001"]
    moved = cache.activate("https://one.example.org", "fam999")  # the server was reset
    assert cache.users(moved) == []
    assert [i.data["id"] for i in cache.users(two)] == ["kid001"]
    assert cache.activate("https://one.example.org", "fam999") == moved


# -- transactions, reset, schema -------------------------------------------------------------------------------------


def test_a_failure_in_the_middle_leaves_nothing_half_written(
    db: Database, cache: CacheRepository, scope: Scope
) -> None:
    with pytest.raises(LookupError), db.transaction():
        cache.set_users(scope, [PARENT], "uv1")
        cache.set_category_base(scope, [CATEGORY])
        cache.set_category_apps(
            scope, "missing", ["com.a"], "av1"
        )  # fails after two tables were written
    assert cache.users(scope) == []
    assert cache.categories(scope) == []
    assert cache.version(scope, "users") == ""


def test_an_unserialisable_entity_rolls_the_whole_part_back(
    cache: CacheRepository, scope: Scope
) -> None:
    with pytest.raises(TypeError):
        cache.set_users(scope, [PARENT, {"id": "bad001", "x": object()}], "uv1")
    assert cache.users(scope) == []


def test_an_inner_failure_that_is_caught_undoes_only_the_inner_part(
    db: Database, cache: CacheRepository, scope: Scope
) -> None:
    with db.transaction():
        cache.set_users(scope, [PARENT], "uv1")
        with pytest.raises(LookupError):
            cache.set_category_apps(scope, "missing", [], "v")
    assert [i.data["id"] for i in cache.users(scope)] == ["par001"]


def keep_everything_but_the_cache(db: Database) -> dict[str, Any]:
    links = LinkRepository(db)
    links.set(
        PROFILE,
        device_token=Secret("tok"),
        own_device_id="own001",
        family_id="fam001",
        now_ms=1,
    )
    for _ in range(7):
        links.reserve_sequence(PROFILE)
    SettingsRepository(db).set("selected_server", PROFILE)
    PendingRestoreRepository(db).add(
        PendingRestore(PROFILE, "fam001", "cat001", "rul001", 4, 123, 99999, 5)
    )
    AuditRepository(db).append(PROFILE, at=10, action="rule.create", child_id="kid001")
    return snapshot_kept(db)


def snapshot_kept(db: Database) -> dict[str, Any]:
    conn = db.connection()
    return {
        t: [tuple(r) for r in conn.execute(f"SELECT * FROM {t} ORDER BY 1")]
        for t in KEPT_TABLES
    }


def test_reset_cache_keeps_link_settings_counter_restores_and_audit(
    db: Database, cache: CacheRepository
) -> None:
    scope = cache.activate(PROFILE, "fam001")
    fill(cache, scope)
    before = keep_everything_but_the_cache(db)
    db.reset_cache()
    assert snapshot_kept(db) == before
    assert LinkRepository(db).get(PROFILE).next_sequence == 7  # type: ignore[union-attr]
    scope = cache.activate(PROFILE, "fam001")
    assert (
        cache.users(scope) == []
        and cache.devices(scope) == []
        and cache.categories(scope) == []
    )


def test_a_schema_version_change_at_start_resets_the_cache_and_keeps_the_counter(
    data_dir: Path,
) -> None:
    path = data_dir / "dashboard.db"
    db = Database(path)
    cache = CacheRepository(db)
    fill(cache, cache.activate(PROFILE, "fam001"))
    before = keep_everything_but_the_cache(db)
    db.close()
    raw = sqlite3.connect(path)
    raw.execute(
        "UPDATE meta SET value=? WHERE key='schema_version'", (str(SCHEMA_VERSION - 1),)
    )
    raw.commit()
    raw.close()
    reopened = Database(path)
    try:
        assert reopened.cache_was_reset is True
        assert snapshot_kept(reopened)["link"] == before["link"]
        assert snapshot_kept(reopened)["pending_restore"] == before["pending_restore"]
        assert LinkRepository(reopened).get(PROFILE).next_sequence == 7  # type: ignore[union-attr]
        assert CacheRepository(reopened).users(Scope(PROFILE, "fam001")) == []
    finally:
        reopened.close()
    again = Database(path)
    assert (
        again.cache_was_reset is False
    )  # only the first start after the change resets
    again.close()


# -- link and sequence counter --------------------------------------------------------------------------------------------


def test_the_sequence_counter_counts_up_per_profile(db: Database) -> None:
    links = LinkRepository(db)
    for profile in ("https://a.example.org", "https://b.example.org"):
        links.set(
            profile,
            device_token=Secret("t"),
            own_device_id="own001",
            family_id="f",
            now_ms=1,
        )
    assert [links.reserve_sequence("https://a.example.org") for _ in range(3)] == [
        0,
        1,
        2,
    ]
    assert links.reserve_sequence("https://b.example.org") == 0
    with pytest.raises(LookupError):
        links.reserve_sequence("https://none.example.org")


def test_relinking_the_same_device_keeps_the_counter_a_new_device_restarts_it(
    db: Database,
) -> None:
    links = LinkRepository(db)
    links.set(
        PROFILE,
        device_token=Secret("t1"),
        own_device_id="own001",
        family_id="f",
        now_ms=1,
    )
    links.reserve_sequence(PROFILE)
    links.set(
        PROFILE,
        device_token=Secret("t2"),
        own_device_id="own001",
        family_id="f",
        now_ms=2,
    )
    link = links.get(PROFILE)
    assert (
        link is not None
        and link.next_sequence == 1
        and link.device_token == Secret("t2")
    )
    links.set(
        PROFILE,
        device_token=Secret("t3"),
        own_device_id="own002",
        family_id="f",
        now_ms=3,
    )
    link = links.get(PROFILE)
    assert link is not None and link.next_sequence == 0
    links.clear(PROFILE)
    assert links.get(PROFILE) is None


def test_the_token_is_a_secret_in_logs_and_repr(db: Database) -> None:
    link = LinkRepository(db).set(
        PROFILE,
        device_token=Secret("tok-123"),
        own_device_id="o",
        family_id="f",
        now_ms=1,
    )
    assert "tok-123" not in repr(link) and "tok-123" not in str(link)


# -- session file with backup -------------------------------------------------------------------------------------------------


def test_the_link_comes_back_from_the_session_file_when_the_database_is_lost(
    data_dir: Path,
) -> None:
    session = SessionFile(data_dir / "session.json")
    first = Database(data_dir / "dashboard.db")
    links = LinkRepository(first, session)
    links.set(
        PROFILE,
        device_token=Secret("tok"),
        own_device_id="own001",
        family_id="fam001",
        now_ms=5,
        mail="p@example.org",
    )
    for _ in range(4):
        links.reserve_sequence(PROFILE)
    first.close()
    (data_dir / "dashboard.db").unlink()
    for extra in data_dir.glob("dashboard.db-*"):
        extra.unlink()
    second = Database(data_dir / "dashboard.db")
    try:
        link = LinkRepository(second, session).get(PROFILE)
        assert link is not None
        assert (
            link.device_token.reveal(),
            link.own_device_id,
            link.family_id,
            link.mail,
        ) == ("tok", "own001", "fam001", "p@example.org")
        assert (
            link.next_sequence == 4 + RECOVERY_MARGIN
        )  # skips ahead; the server accepts jumps forward
    finally:
        second.close()


def test_a_damaged_session_file_falls_back_to_the_backup(data_dir: Path) -> None:
    session = SessionFile(data_dir / "session.json")
    session.save(PROFILE, {"device_token": "one"})
    session.save(PROFILE, {"device_token": "two"})
    (data_dir / "session.json").write_text("{ not json", encoding="utf-8")
    assert (
        session.read()[PROFILE]["device_token"] == "one"
    )  # the backup holds the previous good version
    (data_dir / "session.json.bak").unlink()
    assert session.read() == {}


def test_unlinking_removes_the_session_entry(data_dir: Path) -> None:
    session = SessionFile(data_dir / "session.json")
    db = Database(data_dir / "dashboard.db")
    links = LinkRepository(db, session)
    links.set(
        PROFILE, device_token=Secret("tok"), own_device_id="o", family_id="f", now_ms=1
    )
    links.clear(PROFILE)
    assert session.read() == {}
    db.close()


# -- settings, restores, audit ---------------------------------------------------------------------------------------------------


def test_settings_round_trip(db: Database) -> None:
    settings = SettingsRepository(db)
    assert settings.get("selected_server") is None and settings.get("x", "d") == "d"
    settings.set("selected_server", "https://api.timelimit.io")
    settings.set("selected_server", PROFILE)
    assert settings.get("selected_server") == PROFILE
    assert settings.all() == {"selected_server": PROFILE}
    settings.delete("selected_server")
    assert settings.all() == {}


def test_pending_restores_add_replace_due_remove(db: Database) -> None:
    repo = PendingRestoreRepository(db)
    repo.add(PendingRestore(PROFILE, "f", "cat001", "rul001", 4, 123, 1000, 1))
    repo.add(
        PendingRestore(PROFILE, "f", "cat001", "rul001", 4, 123, 2000, 2)
    )  # same rule: replaced
    repo.add(PendingRestore(PROFILE, "f", "cat001", "rul002", 2, 5, 500, 2))
    repo.add(
        PendingRestore(
            "https://other.example.org", "f", "cat001", "rul001", 4, 123, 1, 1
        )
    )
    assert [r.rule_id for r in repo.for_profile(PROFILE)] == ["rul002", "rul001"]
    assert [r.rule_id for r in repo.due(PROFILE, 1500)] == ["rul002"]
    assert (
        repo.remove(PROFILE, "rul002") is True
        and repo.remove(PROFILE, "rul002") is False
    )


def test_audit_log_lists_newest_first_filters_by_child_and_purges(db: Database) -> None:
    audit = AuditRepository(db)
    audit.append(PROFILE, at=1, action="a", child_id="kid001", detail={"x": 1})
    audit.append(PROFILE, at=2, action="b", child_id="kid002")
    audit.append(PROFILE, at=3, action="c")
    assert [e.action for e in audit.entries(PROFILE)] == ["c", "b", "a"]
    assert [e.detail for e in audit.entries(PROFILE, child_id="kid001")] == [{"x": 1}]
    assert audit.purge_older_than(3) == 2
    assert [e.action for e in audit.entries(PROFILE)] == ["c"]


# -- threads, secrets, layering --------------------------------------------------------------------------------------------------


def test_concurrent_writers_do_not_clash(db: Database, cache: CacheRepository) -> None:
    links = LinkRepository(db)
    links.set(
        PROFILE, device_token=Secret("t"), own_device_id="o", family_id="f", now_ms=1
    )
    scope = cache.activate(PROFILE, "fam001")
    numbers: list[int] = []
    errors: list[BaseException] = []

    def worker(index: int) -> None:
        try:
            for step in range(25):
                numbers.append(links.reserve_sequence(PROFILE))
                cache.set_users(
                    scope,
                    [{"id": f"u{index}{step:03d}", "name": "n"}],
                    f"v{index}-{step}",
                )
                cache.users(scope)
        except BaseException as exc:  # noqa: BLE001 - the test reports whatever a thread hit
            errors.append(exc)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=20)
    assert errors == []
    assert sorted(numbers) == list(range(200))  # every number handed out exactly once
    assert LinkRepository(db).get(PROFILE).next_sequence == 200  # type: ignore[union-attr]


def test_no_typed_password_is_ever_written(
    data_dir: Path, db: Database, cache: CacheRepository
) -> None:
    session = SessionFile(data_dir / "session.json")
    links = LinkRepository(db, session)
    links.set(
        PROFILE, device_token=Secret("tok"), own_device_id="o", family_id="f", now_ms=1
    )
    fill(cache, cache.activate(PROFILE, "fam001"))
    keep_everything_but_the_cache(db)
    # nothing in the repository API takes a password; read the raw files to be sure
    for path in data_dir.iterdir():
        assert TYPED_PASSWORD.encode() not in path.read_bytes(), path.name
    assert "password" not in json.dumps(session.read()).lower()


def test_sql_lives_only_in_the_repository_package() -> None:
    package = Path(__file__).resolve().parents[1]
    offenders = []
    for path in package.rglob("*.py"):
        if "tests" in path.parts or "repository" in path.parts:
            continue
        text = path.read_text(encoding="utf-8")
        if "sqlite3" in text or ".execute(" in text:
            offenders.append(str(path.relative_to(package)))
    assert offenders == []


def test_insert_or_replace_is_not_used_on_state_that_must_not_be_replaced() -> None:
    package = Path(__file__).resolve().parents[1] / "repository"
    for name in ("links.py", "settings_store.py", "restores.py", "audit.py"):
        assert (
            "INSERT OR REPLACE"
            not in (package / name).read_text(encoding="utf-8").upper()
        ), name
