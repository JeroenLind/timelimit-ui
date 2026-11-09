"""Plan step B3: pull with version exchange against the fake server (FR-201, FR-202, TR-103)."""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from ..client.server import TimeLimitClient
from ..domain import actions as act
from ..domain.secret import Secret
from ..repository.cache import CacheRepository, Scope
from ..repository.db import Database
from ..sync.pull import (
    InconsistentServerAnswer,
    Puller,
    apply_server_status,
)
from .fakeserver import FakeTimeLimitServer
from .fakeserver.state import Family

PASSWORD = {
    "hash": "$2a$10$" + "a" * 53,
    "secondHash": "$2a$10$" + "b" * 53,
    "secondSalt": "$2a$10$" + "c" * 22,
}
PROFILE = "test"


class Harness:
    def __init__(self, fake: FakeTimeLimitServer, db_path: Path) -> None:
        self.fake = fake
        self.client = TimeLimitClient(fake.url, timeout=2.0)
        login = self.client.send_login_code("p@example.org", "en")
        auth = self.client.sign_in_by_code(login, fake.inbox[-1][1])
        answer = self.client.create_family(
            mail_auth_token=auth,
            parent_name="Parent",
            device_name="dash",
            device_model="test",
            time_zone="Europe/Amsterdam",
            password=PASSWORD,
        )
        self.token = Secret(answer["deviceAuthToken"])
        self.device_id: str = answer["ownDeviceId"]
        self.parent_id: str = answer["data"]["users"]["data"][0]["id"]
        self.family_id = next(iter(fake.world.families))
        self.sequence = 0
        self.db = Database(db_path)
        self.cache = CacheRepository(self.db)
        self.puller = Puller(self.client, self.cache, self.db)
        self.statuses: list[dict[str, Any]] = []
        self.answers: list[dict[str, Any]] = []
        original = self.client.pull_status

        def recording(token: Secret, status: dict[str, Any]) -> dict[str, Any]:
            self.statuses.append(json.loads(json.dumps(status)))
            answer = original(token, status)
            self.answers.append(answer)
            return answer

        self.client.pull_status = recording  # type: ignore[method-assign,assignment]

    @property
    def family(self) -> Family:
        return self.fake.world.families[self.family_id]

    def push(self, *actions: dict[str, Any]) -> bool:
        items = []
        for action in actions:
            items.append(act.parent_item(action, self.sequence, self.parent_id))
            self.sequence += 1
        return self.client.push_actions(self.token, items)

    def pull(self) -> Scope:
        return self.puller.pull(PROFILE, self.token, self.family_id).scope


@pytest.fixture
def h(fake_server: FakeTimeLimitServer, db_path: Path) -> Iterator[Harness]:
    yield Harness(fake_server, db_path)


def script_family(h: Harness) -> tuple[str, str, str]:
    """A child with two categories, rules, apps and used time. Returns child id and the two category ids."""
    child, cat1, cat2 = "chd001", "cat001", "cat002"
    assert not h.push(
        act.add_child_user(child, "Kid", "Europe/Amsterdam"),
        act.create_category(child, cat1, "Games"),
        act.create_category(child, cat2, "School"),
        act.create_timelimit_rule("rul001", cat1, 3_600_000, days=31),
        act.create_timelimit_rule(
            "rul002", cat1, 1_800_000, days=96, start=60, end=600
        ),
        act.create_timelimit_rule("rul003", cat2, 7_200_000),
        act.add_category_apps(cat1, ["com.game.a", "com.game.b"]),
        act.update_category_blocked_times(cat2, [(0, 480), (9000, 10080)]),
    )
    cat = h.family.categories[cat1]
    cat.used_times = {
        20000: {(0, 1439): 120_000},
        20001: {(0, 1439): 60_000, (0, 600): 5},
    }
    h.family.devices[h.device_id].installed_apps = [
        {
            "packageName": "com.game.a",
            "title": "Game A",
            "isLaunchable": True,
            "recommendation": "none",
        }
    ]
    return child, cat1, cat2


def snapshot(cache: CacheRepository, scope: Scope) -> dict[str, Any]:
    """Everything the cache holds for the scope, in a comparable form."""
    categories = cache.categories(scope)
    return {
        "versions": cache.client_status(scope),
        "devices": [(i.data, i.on_server) for i in cache.devices(scope)],
        "users": [(i.data, i.on_server) for i in cache.users(scope)],
        "categories": [(i.data, i.on_server) for i in categories],
        "apps": {
            c.data["categoryId"]: cache.category_apps(scope, c.data["categoryId"])
            for c in categories
        },
        "rules": {
            c.data["categoryId"]: [
                (r.data, r.on_server) for r in cache.rules(scope, c.data["categoryId"])
            ]
            for c in categories
        },
        "used": {
            c.data["categoryId"]: cache.used_time_by_day(scope, c.data["categoryId"])
            for c in categories
        },
    }


def assert_cache_equals_server(h: Harness, scope: Scope) -> None:
    family = h.family
    cache = h.cache
    assert {i.data["deviceId"] for i in cache.devices(scope)} == set(family.devices)
    assert {i.data["id"] for i in cache.users(scope)} == set(family.users)
    cached = {i.data["categoryId"]: i for i in cache.categories(scope)}
    assert set(cached) == set(family.categories)
    for cid, cat in family.categories.items():
        data = cached[cid].data
        assert cached[cid].on_server
        assert (data["title"], data["childId"], data["blockedTimes"]) == (
            cat.title,
            cat.child_id,
            cat.blocked_times,
        )
        assert data["version"] == cat.base_version
        assert cache.category_apps(scope, cid) == sorted(cat.apps)
        rules = {r.data["id"]: r.data for r in cache.rules(scope, cid)}
        assert set(rules) == set(cat.rules)
        for rule_id, rule in cat.rules.items():
            assert (rules[rule_id]["maxTime"], rules[rule_id]["dayMask"]) == (
                rule.max_time,
                rule.day_mask,
            )
        expected = {day: sum(per.values()) for day, per in cat.used_times.items()}
        assert cache.used_time_by_day(scope, cid) == expected
    for device in family.devices.values():
        assert [
            a["packageName"] for a in cache.installed_apps(scope, device.device_id)
        ] == [
            a["packageName"]
            for a in sorted(device.installed_apps, key=lambda a: a["packageName"])
        ]


# -- FR-201 ------------------------------------------------------------------------------------------------------------


def test_first_pull_makes_the_cache_equal_to_the_server(h: Harness) -> None:
    script_family(h)
    scope = h.pull()
    assert_cache_equals_server(h, scope)
    assert h.cache.meta(scope, "api_level") == str(h.fake.world.api_level)


def test_second_pull_sends_the_stored_versions_and_gets_no_data(h: Harness) -> None:
    _, cat1, _ = script_family(h)
    scope = h.pull()
    h.pull()
    first, second = h.statuses
    assert first["devices"] == "" and first["categories"] == {}
    assert second == h.cache.client_status(scope)
    assert second["devices"] == h.family.device_list_version
    assert second["users"] == h.family.user_list_version
    assert (
        second["categories"][cat1]["rules"] == h.family.categories[cat1].rules_version
    )
    assert second["apps"] == {h.device_id: h.family.devices[h.device_id].apps_version}
    # nothing but the always-present parts: tasks are sent without a stored version (finding, decision R2)
    assert set(h.answers[1]) <= {"fullVersion", "apiLevel", "tasks"}


def test_server_changes_of_every_kind_arrive_with_the_next_pull(h: Harness) -> None:
    _child, cat1, cat2 = script_family(h)
    scope = h.pull()

    assert not h.push(act.update_timelimit_rule("rul001", 999_000, days=1))
    result = h.puller.pull(PROFILE, h.token, h.family_id)
    assert result.changed == {"rules"}
    assert {r.data["id"]: r.data["maxTime"] for r in h.cache.rules(scope, cat1)}[
        "rul001"
    ] == 999_000

    assert not h.push(act.add_category_apps(cat1, ["com.game.c"]))
    assert h.puller.pull(PROFILE, h.token, h.family_id).changed == {"category_apps"}
    assert "com.game.c" in h.cache.category_apps(scope, cat1)

    device = h.family.devices[h.device_id]
    device.installed_apps.append(
        {
            "packageName": "com.new",
            "title": "New",
            "isLaunchable": True,
            "recommendation": "none",
        }
    )
    from .fakeserver.state import version_id

    device.apps_version = version_id()
    assert h.puller.pull(PROFILE, h.token, h.family_id).changed == {"installed_apps"}
    assert {a["packageName"] for a in h.cache.installed_apps(scope, h.device_id)} == {
        "com.game.a",
        "com.new",
    }

    category = h.family.categories[cat1]
    category.used_times[20002] = {(0, 1439): 777}
    category.used_times_version = version_id()
    assert h.puller.pull(PROFILE, h.token, h.family_id).changed == {"used_time"}
    assert h.cache.used_time_by_day(scope, cat1)[20002] == 777

    assert not h.push(act.delete_category(cat2))
    assert h.puller.pull(PROFILE, h.token, h.family_id).changed == {"categories"}
    gone = {i.data["categoryId"]: i.on_server for i in h.cache.categories(scope)}
    assert gone == {
        cat1: True,
        cat2: False,
    }  # kept, flagged "no longer on server" (FR-206)
    assert_cache_equals_server_except_removed(h, scope, cat2)


def assert_cache_equals_server_except_removed(
    h: Harness, scope: Scope, removed: str
) -> None:
    live = {i.data["categoryId"] for i in h.cache.categories(scope) if i.on_server}
    assert live == set(h.family.categories) and removed not in live


def test_rule_expiry_field_is_kept_when_the_server_sends_it(
    db_path: Path,
) -> None:
    fake = FakeTimeLimitServer(rule_expiry=True)
    fake.start()
    try:
        h = Harness(fake, db_path)
        _, cat1, _ = script_family(h)
        h.family.categories[cat1].rules["rul001"].expires = 1_900_000_000_000
        scope = h.pull()
        rule = {r.data["id"]: r.data for r in h.cache.rules(scope, cat1)}["rul001"]
        assert rule["e"] == 1_900_000_000_000
    finally:
        fake.stop()


# -- idempotence ----------------------------------------------------------------------------------------------------------------


def test_applying_the_same_answer_twice_changes_nothing(h: Harness) -> None:
    script_family(h)
    scope = h.pull()
    answer = h.client.pull_status(
        h.token, {"apps": {}, "categories": {}, "devices": "", "users": ""}
    )
    with h.db.transaction():
        apply_server_status(h.cache, scope, answer)
    once = snapshot(h.cache, scope)
    with h.db.transaction():
        apply_server_status(h.cache, scope, answer)
    assert snapshot(h.cache, scope) == once
    assert_cache_equals_server(h, scope)


# -- FR-202 ----------------------------------------------------------------------------------------------------------------------


def test_should_do_full_sync_forgets_versions_repulls_once_and_sets_a_notice(
    h: Harness,
) -> None:
    _, _cat1, cat2 = script_family(h)
    scope = h.pull()
    assert not h.puller.take_resync_notice(scope)
    # a schema-invalid action is dropped silently and the server says: do a full sync
    broken = act.delete_category(cat2)
    broken["extra"] = "field"
    item = act.parent_item(broken, h.sequence, h.parent_id)
    h.sequence += 1
    assert h.client.push_actions(h.token, [item]) is True

    h.statuses.clear()
    result = h.puller.full_resync(PROFILE, h.token, h.family_id)
    assert result.full_resync
    assert len(h.statuses) == 1, "exactly one re-pull"
    status = h.statuses[0]
    assert status["devices"] == "" and status["users"] == "" and status["apps"] == {}
    assert all(
        v == {"base": "", "apps": "", "rules": "", "usedTime": "", "tasks": ""}
        for v in status["categories"].values()
    )
    assert_cache_equals_server(h, scope)
    assert h.puller.take_resync_notice(scope) is True
    assert h.puller.take_resync_notice(scope) is False


def test_full_resync_finds_what_was_removed_on_the_server_meanwhile(h: Harness) -> None:
    _, cat1, cat2 = script_family(h)
    scope = h.pull()
    assert not h.push(act.delete_category(cat2))
    h.puller.full_resync(PROFILE, h.token, h.family_id)
    assert {i.data["categoryId"]: i.on_server for i in h.cache.categories(scope)} == {
        cat1: True,
        cat2: False,
    }


def test_a_failed_pull_leaves_the_cache_usable(h: Harness) -> None:
    script_family(h)
    scope = h.pull()
    before = snapshot(h.cache, scope)
    h.fake.faults.fail_next.append(500)
    from ..domain.errors import DashboardError

    with pytest.raises(DashboardError):
        h.puller.full_resync(PROFILE, h.token, h.family_id)
    assert snapshot(h.cache, scope)["devices"] == before["devices"]
    assert h.cache.categories(scope)  # data still there


# -- inconsistent answers --------------------------------------------------------------------------------------------------------


def test_rules_for_an_unknown_category_are_reported_not_stored(h: Harness) -> None:
    scope = h.cache.activate(PROFILE, "fam")
    answer = {
        "apiLevel": 9,
        "fullVersion": 0,
        "rules": [{"categoryId": "nocat1", "rules": [], "version": "abcd"}],
    }
    with pytest.raises(InconsistentServerAnswer), h.db.transaction():
        apply_server_status(h.cache, scope, answer)
    assert h.cache.categories(scope) == []


def test_pull_repairs_an_inconsistent_answer_with_a_full_resync(h: Harness) -> None:
    script_family(h)
    real = h.client.pull_status
    calls = {"n": 0}

    def flaky(token: Secret, status: dict[str, Any]) -> dict[str, Any]:
        calls["n"] += 1
        answer = real(token, status)
        if calls["n"] == 1:
            answer = {
                **answer,
                "rules": [{"categoryId": "nocat1", "rules": [], "version": "abcd"}],
            }
        return answer

    h.client.pull_status = flaky  # type: ignore[method-assign,assignment]
    result = h.puller.pull(PROFILE, h.token, h.family_id)
    assert result.full_resync and calls["n"] == 2
    assert_cache_equals_server(h, result.scope)
    assert h.puller.take_resync_notice(result.scope)


def test_a_new_family_id_drops_the_old_cache(h: Harness) -> None:
    script_family(h)
    scope = h.pull()
    assert h.cache.categories(scope)
    other = h.cache.activate(PROFILE, "otherfamily")
    assert h.cache.categories(other) == [] and h.cache.users(other) == []
