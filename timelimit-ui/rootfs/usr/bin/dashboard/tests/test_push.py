"""Plan step B4: push, confirmation and rollback against the fake (FR-200, 203, 204, 209, TR-304)."""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from ..domain import actions as act
from ..domain.errors import DashboardError, ErrorCode
from ..repository.links import LinkRepository
from ..sync.push import Pusher
from .fakeserver import FakeTimeLimitServer
from .test_pull import PROFILE, Harness, assert_cache_equals_server


class PushHarness(Harness):
    def __init__(self, fake: FakeTimeLimitServer, db_path: Path) -> None:
        super().__init__(fake, db_path)
        self.links = LinkRepository(self.db)
        self.links.set(
            PROFILE,
            device_token=self.token,
            own_device_id=self.device_id,
            family_id=self.family_id,
            now_ms=1,
        )
        self.pusher = Pusher(self.client, self.links, self.puller)
        self.sent: list[list[int]] = []
        original = self.client.push_actions

        def recording(token: Any, items: list[dict[str, Any]]) -> bool:
            self.sent.append([i["sequenceNumber"] for i in items])
            return original(token, items)

        self.client.push_actions = recording  # type: ignore[method-assign,assignment]

    def send(self, *actions: dict[str, Any]) -> Any:
        return self.pusher.push(PROFILE, self.parent_id, list(actions))


@pytest.fixture
def h(fake_server: FakeTimeLimitServer, db_path: Path) -> Iterator[PushHarness]:
    yield PushHarness(fake_server, db_path)


def child_with_category(h: PushHarness) -> None:
    h.send(
        act.add_child_user("chd001", "Kid", "Europe/Amsterdam"),
        act.create_category("chd001", "cat001", "Games"),
    )


def test_an_accepted_action_is_confirmed_and_visible_in_the_cache(
    h: PushHarness,
) -> None:
    result = h.send(
        act.add_child_user("chd001", "Kid", "Europe/Amsterdam"),
        act.create_category("chd001", "cat001", "Games"),
        act.create_timelimit_rule("rul001", "cat001", 3_600_000),
    )
    assert (result.sent, result.batches) == (3, 1)
    scope = result.pull.scope
    assert {i.data["categoryId"] for i in h.cache.categories(scope)} == {"cat001"}
    assert [r.data["id"] for r in h.cache.rules(scope, "cat001")] == ["rul001"]
    assert_cache_equals_server(h, scope)


def test_an_action_the_server_drops_is_not_confirmed_and_the_cache_equals_the_server(
    h: PushHarness,
) -> None:
    child_with_category(h)
    # valid for the schema, but the category does not exist: the server drops it silently (HTTP 200)
    with pytest.raises(DashboardError) as raised:
        h.send(
            act.update_category_title("nocat1", "Ghost"), act.delete_category("nocat1")
        )
    assert raised.value.code is ErrorCode.ACTION_NOT_CONFIRMED
    scope = h.cache.activate(PROFILE, h.family_id)
    assert_cache_equals_server(h, scope)
    assert h.puller.take_resync_notice(scope) is True


def test_sixty_actions_go_in_three_requests_with_consecutive_numbers(
    h: PushHarness,
) -> None:
    h.send(act.add_child_user("chd001", "Kid", "Europe/Amsterdam"))
    h.sent.clear()
    ids = [f"c{n:05d}" for n in range(60)]
    result = h.send(
        *[act.create_category("chd001", cid, f"Cat {n}") for n, cid in enumerate(ids)]
    )
    assert result.batches == 3
    assert [len(batch) for batch in h.sent] == [25, 25, 10]
    flat = [number for batch in h.sent for number in batch]
    assert flat == list(range(1, 61))
    assert len(h.cache.categories(result.pull.scope)) == 60


def test_numbers_keep_counting_after_an_unconfirmed_action(h: PushHarness) -> None:
    with pytest.raises(DashboardError):
        h.send(act.delete_category("nocat1"))
    h.send(act.add_child_user("chd001", "Kid", "Europe/Amsterdam"))
    assert h.sent == [[0], [1]]
    assert h.family.users.keys() >= {"chd001"}, (
        "the second action was not ignored as a reused number"
    )


def test_the_counter_survives_a_restart(
    fake_server: FakeTimeLimitServer, db_path: Path
) -> None:
    first = PushHarness(fake_server, db_path)
    first.send(act.add_child_user("chd001", "Kid", "Europe/Amsterdam"))
    first.send(act.create_category("chd001", "cat001", "Games"))
    first.db.close()
    # a new process: new database object on the same file, new client
    second = PushHarness.__new__(PushHarness)
    second.fake = fake_server
    from ..client.server import TimeLimitClient
    from ..repository.cache import CacheRepository
    from ..repository.db import Database
    from ..sync.pull import Puller

    second.db = Database(db_path)
    second.client = TimeLimitClient(fake_server.url, timeout=2.0)
    second.cache = CacheRepository(second.db)
    second.puller = Puller(second.client, second.cache, second.db)
    second.links = LinkRepository(second.db)
    second.pusher = Pusher(second.client, second.links, second.puller)
    second.parent_id = first.parent_id
    second.sent = []
    original = second.client.push_actions

    def recording(token: Any, items: list[dict[str, Any]]) -> bool:
        second.sent.append([x["sequenceNumber"] for x in items])
        return original(token, items)

    second.client.push_actions = recording  # type: ignore[method-assign,assignment]
    second.send(act.update_category_title("cat001", "Renamed"))
    assert second.sent == [[2]]
    assert (
        fake_server.world.families[first.family_id].categories["cat001"].title
        == "Renamed"
    )


def test_a_network_failure_is_reported_and_its_number_is_consumed(
    h: PushHarness,
) -> None:
    child_with_category(h)
    h.sent.clear()
    h.fake.faults.drop_connection = True
    with pytest.raises(DashboardError) as raised:
        h.send(act.update_category_title("cat001", "Lost"))
    assert raised.value.code is ErrorCode.SERVER_UNREACHABLE
    h.fake.faults.drop_connection = False
    h.send(act.update_category_title("cat001", "Found"))
    # the failed number (2) is gone for good; the next push uses 3 and is accepted
    assert [b[0] for b in h.sent] == [2, 3]
    assert h.family.categories["cat001"].title == "Found"


def test_a_failure_in_a_later_batch_burns_no_numbers_for_unsent_actions(
    h: PushHarness,
) -> None:
    h.send(act.add_child_user("chd001", "Kid", "Europe/Amsterdam"))
    h.sent.clear()
    original = h.client.push_actions
    calls = {"n": 0}

    def flaky(token: Any, items: list[dict[str, Any]]) -> bool:
        calls["n"] += 1
        if calls["n"] == 2:
            raise DashboardError(ErrorCode.SERVER_UNREACHABLE, "down")
        return original(token, items)

    h.client.push_actions = flaky  # type: ignore[method-assign,assignment]
    actions = [
        act.create_category("chd001", f"c{n:05d}", f"Cat {n}") for n in range(60)
    ]
    with pytest.raises(DashboardError):
        h.send(*actions)
    link = h.links.get(PROFILE)
    # 1 (the child) + batch 1 (25) + the failed batch 2 (25, consumed); batch 3 was never sent
    assert link is not None and link.next_sequence == 1 + 25 + 25


def test_every_pushed_item_uses_the_device_method_and_the_own_parent(
    h: PushHarness,
) -> None:
    seen: list[dict[str, Any]] = []
    original = h.client.push_actions

    def spy(token: Any, items: list[dict[str, Any]]) -> bool:
        seen.extend(items)
        return original(token, items)

    h.client.push_actions = spy  # type: ignore[method-assign,assignment]
    child_with_category(h)
    assert {i["integrity"] for i in seen} == {"device"}
    assert {i["userId"] for i in seen} == {h.parent_id}
    assert json.loads(seen[0]["encodedAction"])["type"] == "ADD_USER"


def test_not_linked_and_empty_pushes_are_refused(h: PushHarness) -> None:
    with pytest.raises(ValueError):
        h.pusher.push(PROFILE, h.parent_id, [])
    with pytest.raises(DashboardError) as raised:
        h.pusher.push("unknown", h.parent_id, [act.delete_category("cat001")])
    assert raised.value.code is ErrorCode.NOT_LINKED
