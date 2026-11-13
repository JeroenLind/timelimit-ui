"""Plan step E3a: time limit rule off for today (FR-307, decisions W1-W6, TR-512)."""

from __future__ import annotations

import json
import time
from collections.abc import Callable, Iterator
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pytest
from flask import Flask

from ..config import Settings
from ..domain import rule_today as pure
from ..domain.actions import ActionError
from ..domain.clock import FakeClock
from ..domain.secret import Secret
from ..factory import create_app
from .conftest import link_app, make_family, seed_children
from .fakeserver import FakeTimeLimitServer

WEDNESDAY = datetime(2026, 11, 11, 10, 0, tzinfo=timezone.utc)
MIDNIGHT = datetime(2026, 11, 12, 0, 0, tzinfo=timezone.utc)
ALL = 127
WED = 1 << 2


# -- pure rules ------------------------------------------------------------------------------------------------------------
@pytest.mark.parametrize("weekday", range(7))
def test_every_weekday_bit_can_be_removed_and_put_back(weekday: int) -> None:
    moment = datetime(
        2026, 11, 9 + weekday, 9, 0, tzinfo=timezone.utc
    )  # 2026-11-09 is a Monday
    assert moment.weekday() == weekday
    off = pure.day_off(ALL, moment)
    assert off == ALL & ~(1 << weekday)
    assert pure.day_back(off, 1 << weekday) == ALL
    pure.rule_action(
        "rule01", {"maxTime": 60000}, off
    )  # the schema of the action accepts it


def test_a_rule_with_only_today_gets_mask_zero_and_the_action_is_valid() -> None:
    off = pure.day_off(WED, WEDNESDAY)
    assert off == 0
    assert pure.rule_action("rule01", {"maxTime": 60000}, 0)["days"] == 0
    assert pure.day_back(0, WED) == WED


def test_applies_on_follows_the_weekday_of_the_given_moment() -> None:
    assert pure.applies_on(31, WEDNESDAY) and not pure.applies_on(
        31, WEDNESDAY + timedelta(days=3)
    )


@pytest.mark.parametrize(
    ("moment", "expected"),
    [
        (WEDNESDAY, MIDNIGHT),
        (
            datetime(2026, 11, 30, 23, 59, 59, tzinfo=timezone.utc),
            datetime(2026, 12, 1, tzinfo=timezone.utc),
        ),
        (
            datetime(2026, 12, 31, 12, 0, tzinfo=timezone.utc),
            datetime(2027, 1, 1, tzinfo=timezone.utc),
        ),
        (
            datetime(2026, 11, 11, 23, 30, tzinfo=timezone(timedelta(hours=1))),
            datetime(2026, 11, 12, 0, 0, tzinfo=timezone(timedelta(hours=1))),
        ),
    ],
)
def test_next_midnight_is_in_the_zone_of_the_moment(
    moment: datetime, expected: datetime
) -> None:
    assert pure.next_midnight(moment) == expected


def test_rule_action_keeps_every_field_and_same_rule_compares_all_of_them() -> None:
    rule = {"id": "rule01", "dayMask": 31, "maxTime": 5400000, "extraTime": True, "start": 480, "end": 1230,
            "session": 1800000, "pause": 300000, "perDay": True, "e": 1900000000000}  # fmt: skip
    action = pure.rule_action("rule01", rule, 27)
    assert action == {"type": "UPDATE_TIMELIMIT_RULE", "ruleId": "rule01", "time": 5400000, "days": 27,
                      "extraTime": True, "start": 480, "end": 1230, "dur": 1800000, "pause": 300000,
                      "perDay": True, "e": 1900000000000}  # fmt: skip
    snap = pure.snapshot(rule, 27)
    assert pure.same_rule(snap, {**rule, "dayMask": 27})
    for change in (
        {"dayMask": 31},
        {"maxTime": 1},
        {"extraTime": False},
        {"start": 0, "end": 1439},
        {"perDay": False},
    ):
        assert not pure.same_rule(snap, {**rule, "dayMask": 27, **change})
    with pytest.raises(ActionError):
        pure.rule_action("bad", rule, 27)  # rule ids are six characters


# -- with the app ------------------------------------------------------------------------------------------------------------
@pytest.fixture
def make(
    data_dir: Path, fake_server: FakeTimeLimitServer
) -> Iterator[Callable[..., tuple[Flask, dict[str, str], FakeClock]]]:
    apps: list[Flask] = []

    def build(start: datetime = WEDNESDAY) -> tuple[Flask, dict[str, str], FakeClock]:
        make_family(fake_server)
        ids = seed_children(fake_server)
        clock = FakeClock(start)
        settings = Settings(
            data_dir=data_dir, server_url=fake_server.url, server_timeout=3.0
        )
        app = create_app(settings, Secret("s"), clock)
        apps.append(app)
        link_app(app, fake_server)
        return app, ids, clock

    yield build
    for app in apps:
        app.extensions["dashboard"]["backend"].close()


def games(fake: FakeTimeLimitServer) -> Any:
    return next(iter(fake.world.families.values())).categories["cgames"]


def pull(app: Flask, fake: FakeTimeLimitServer) -> None:
    backend = app.extensions["dashboard"]["backend"]
    link = backend.links.get(fake.url)
    backend.puller(fake.url).pull(fake.url, link.device_token, link.family_id)


def today(app: Flask) -> Any:
    return app.extensions["dashboard"]["rule_today"]


def off(app: Flask, ids: dict[str, str], rule: str = "rule01") -> Any:
    return app.test_client().put(f"/api/children/{ids['Anna']}/rules/{rule}/off-today")


def on_again(app: Flask, ids: dict[str, str], rule: str = "rule01") -> Any:
    return app.test_client().delete(
        f"/api/children/{ids['Anna']}/rules/{rule}/off-today"
    )


def view(app: Flask, ids: dict[str, str]) -> dict[str, Any]:
    detail = app.test_client().get(f"/api/children/{ids['Anna']}").get_json()
    return next(c for c in detail["categories"] if c["id"] == "cgames")["rules"][0]  # type: ignore[no-any-return]


def audit(app: Flask, fake: FakeTimeLimitServer) -> list[str]:
    entries = app.extensions["dashboard"]["backend"].audit.entries(fake.url)
    return [e.action for e in reversed(entries)]


def notices(app: Flask) -> list[dict[str, Any]]:
    found = app.test_client().get("/api/notices").get_json()["notices"]
    # ITEMS_MISSING (FR-206, E4) is about something else: a rule that vanished elsewhere is flagged
    return [n for n in found if n["code"] != "ITEMS_MISSING"]


def wait_for(check: Callable[[], bool], seconds: float = 8.0) -> None:
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        if check():
            return
        time.sleep(0.05)
    raise AssertionError("condition not reached in time")


def test_switching_off_on_a_wednesday_removes_only_the_wednesday_bit(
    make: Any, fake_server: FakeTimeLimitServer
) -> None:
    app, ids, _ = make()
    before = len(fake_server.world.action_types)
    assert off(app, ids).status_code == 200
    rule = games(fake_server).rules["rule01"]
    assert rule.day_mask == ALL & ~WED
    assert (rule.max_time, rule.start, rule.end, rule.session, rule.pause) == (
        3600000,
        0,
        1439,
        0,
        0,
    )
    assert (rule.extra_time, rule.per_day) == (False, False)
    # the server never sees anything but UPDATE_TIMELIMIT_RULE for this feature
    assert fake_server.world.action_types[before:] == ["UPDATE_TIMELIMIT_RULE"]
    backend = app.extensions["dashboard"]["backend"]
    pending = backend.restores.get(fake_server.url, "rule01")
    assert pending is not None and pending.restore_at == int(
        MIDNIGHT.timestamp() * 1000
    )
    shown = view(app, ids)
    assert shown["days"] == list(
        range(7)
    )  # the real days, not the server's temporary mask
    assert shown["off_today"] == {"restore_at": pending.restore_at}
    assert audit(app, fake_server)[-1] == "rule_off_today"


def test_at_midnight_the_bit_is_back_and_the_pending_restore_is_gone(
    make: Any, fake_server: FakeTimeLimitServer
) -> None:
    app, ids, clock = make()
    off(app, ids)
    clock.set(MIDNIGHT + timedelta(seconds=20))
    before = len(fake_server.world.action_types)
    done = today(app).tick()
    assert [(d.rule_id, d.outcome) for d in done] == [("rule01", "restored")]
    assert games(fake_server).rules["rule01"].day_mask == ALL
    assert fake_server.world.action_types[before:] == ["UPDATE_TIMELIMIT_RULE"]
    assert (
        app.extensions["dashboard"]["backend"].restores.get(fake_server.url, "rule01")
        is None
    )
    assert audit(app, fake_server)[-2:] == ["rule_off_today", "rule_restored"]
    assert notices(app) == []  # on time: no notice
    assert view(app, ids)["off_today"] is None
    assert today(app).tick() == []  # nothing left to do


def test_nothing_happens_before_midnight(
    make: Any, fake_server: FakeTimeLimitServer
) -> None:
    app, ids, clock = make()
    off(app, ids)
    clock.set(MIDNIGHT - timedelta(seconds=1))
    assert today(app).tick() == []
    assert games(fake_server).rules["rule01"].day_mask == ALL & ~WED


def test_a_restore_overdue_at_start_runs_at_once_with_a_notice(
    make: Any, fake_server: FakeTimeLimitServer, data_dir: Path
) -> None:
    app, ids, _clock = make()
    off(app, ids)
    app.extensions["dashboard"][
        "backend"
    ].close()  # the dashboard is stopped before midnight ...
    afternoon = MIDNIGHT + timedelta(hours=15)  # ... and started the next afternoon
    settings = Settings(
        data_dir=data_dir, server_url=fake_server.url, server_timeout=3.0
    )
    again = create_app(settings, Secret("s"), FakeClock(afternoon))
    try:
        wait_for(lambda: games(fake_server).rules["rule01"].day_mask == ALL)
        wait_for(lambda: [n["code"] for n in notices(again)] == ["RULE_RESTORED_LATE"])
        notice = notices(again)[0]
        assert (notice["child"], notice["category"]) == ("Anna", "Games")
        assert (
            again.extensions["dashboard"]["backend"].restores.get(
                fake_server.url, "rule01"
            )
            is None
        )
    finally:
        again.extensions["dashboard"]["backend"].close()


@pytest.mark.parametrize("how", ["changed", "deleted"])
def test_a_rule_changed_or_deleted_elsewhere_is_not_touched_at_restore(
    how: str, make: Any, fake_server: FakeTimeLimitServer
) -> None:
    app, ids, clock = make()
    off(app, ids)
    category = games(fake_server)
    if how == "changed":
        category.rules["rule01"].max_time = 30 * 60000
    else:
        del category.rules["rule01"]
    category.rules_version = (
        "changed-elsewhere"  # as the server does after any rule change
    )
    clock.set(MIDNIGHT + timedelta(minutes=1))
    before = len(fake_server.world.action_types)
    done = today(app).tick()
    assert [d.outcome for d in done] == ["skipped"]
    assert len(fake_server.world.action_types) == before  # nothing sent
    if how == "changed":
        assert (
            category.rules["rule01"].day_mask == ALL & ~WED
        )  # left as the other parent has it
    assert [n["code"] for n in notices(app)] == ["RULE_RESTORE_SKIPPED"]
    assert (
        app.extensions["dashboard"]["backend"].restores.get(fake_server.url, "rule01")
        is None
    )
    assert "rule_restore_skipped" in audit(app, fake_server)
    notice_id = notices(app)[0]["id"]
    assert app.test_client().delete(f"/api/notices/{notice_id}").status_code == 200
    assert notices(app) == []


def test_editing_an_off_rule_restores_it_first_in_the_same_push(
    make: Any, fake_server: FakeTimeLimitServer
) -> None:
    app, ids, _ = make()
    off(app, ids)
    before = len(fake_server.world.action_types)
    answer = app.test_client().put(
        f"/api/children/{ids['Anna']}/rules/rule01",
        json={"days": [0, 1, 2], "minutes": 45},
    )
    assert answer.status_code == 200
    assert fake_server.world.action_types[before:] == [
        "UPDATE_TIMELIMIT_RULE",
        "UPDATE_TIMELIMIT_RULE",
    ]
    rule = games(fake_server).rules["rule01"]
    assert (rule.day_mask, rule.max_time) == (7, 45 * 60000)
    assert (
        app.extensions["dashboard"]["backend"].restores.get(fake_server.url, "rule01")
        is None
    )
    assert [n["code"] for n in notices(app)] == ["RULE_OFF_ENDED"]
    assert audit(app, fake_server)[-2:] == ["rule_off_today", "rule_off_ended"]


def test_deleting_an_off_rule_restores_it_first_then_deletes(
    make: Any, fake_server: FakeTimeLimitServer
) -> None:
    app, ids, _ = make()
    off(app, ids)
    before = len(fake_server.world.action_types)
    assert (
        app.test_client()
        .delete(f"/api/children/{ids['Anna']}/rules/rule01")
        .status_code
        == 200
    )
    assert fake_server.world.action_types[before:] == [
        "UPDATE_TIMELIMIT_RULE",
        "DELETE_TIMELIMIT_RULE",
    ]
    assert games(fake_server).rules == {}
    assert [n["code"] for n in notices(app)] == ["RULE_OFF_ENDED"]


def test_a_cache_reset_keeps_the_pending_restore(
    make: Any, fake_server: FakeTimeLimitServer
) -> None:
    app, ids, clock = make()
    off(app, ids)
    backend = app.extensions["dashboard"]["backend"]
    backend.db.reset_cache()
    assert backend.restores.get(fake_server.url, "rule01") is not None
    clock.set(MIDNIGHT + timedelta(seconds=5))
    assert [d.outcome for d in today(app).tick()] == ["restored"]
    assert games(fake_server).rules["rule01"].day_mask == ALL


def test_a_rule_that_does_not_apply_today_is_refused_before_sending(
    make: Any, fake_server: FakeTimeLimitServer
) -> None:
    saturday = datetime(2026, 11, 14, 10, 0, tzinfo=timezone.utc)
    app, ids, _ = make(saturday)
    games(fake_server).rules["rule01"].day_mask = 31  # Monday to Friday
    games(fake_server).rules_version = "mon-fri"
    pull(app, fake_server)
    assert view(app, ids)["applies_today"] is False
    pushes = fake_server.world.push_requests
    answer = off(app, ids)
    assert answer.status_code == 400
    assert (answer.get_json()["code"], answer.get_json()["field"]) == (
        "INVALID_INPUT",
        "rule",
    )
    assert fake_server.world.push_requests == pushes
    assert (
        app.extensions["dashboard"]["backend"].restores.get(fake_server.url, "rule01")
        is None
    )


def test_a_rule_with_only_today_goes_to_mask_zero_and_comes_back(
    make: Any, fake_server: FakeTimeLimitServer
) -> None:
    app, ids, clock = make()
    games(fake_server).rules["rule01"].day_mask = WED
    games(fake_server).rules_version = "only-wed"
    pull(app, fake_server)
    assert off(app, ids).status_code == 200
    assert games(fake_server).rules["rule01"].day_mask == 0
    clock.set(MIDNIGHT + timedelta(seconds=1))
    today(app).tick()
    assert games(fake_server).rules["rule01"].day_mask == WED


def test_switching_on_again_the_same_day_restores_at_once(
    make: Any, fake_server: FakeTimeLimitServer
) -> None:
    app, ids, _ = make()
    off(app, ids)
    answer = on_again(app, ids)
    assert answer.status_code == 200 and answer.get_json()["outcome"] == "restored"
    assert games(fake_server).rules["rule01"].day_mask == ALL
    assert on_again(app, ids).status_code == 404  # not off any more
    assert audit(app, fake_server)[-2:] == ["rule_off_today", "rule_restored"]


def test_switching_off_twice_is_refused(make: Any) -> None:
    app, ids, _ = make()
    assert off(app, ids).status_code == 200
    assert off(app, ids).status_code == 409


def test_a_failed_switch_off_leaves_no_pending_restore(
    make: Any, fake_server: FakeTimeLimitServer
) -> None:
    app, ids, _ = make()
    fake_server.faults.drop_connection = True
    answer = off(app, ids)
    assert (
        answer.status_code == 503
    )  # the server is down: changes are disabled (FR-1001)
    fake_server.faults.drop_connection = False
    assert (
        app.extensions["dashboard"]["backend"].restores.get(fake_server.url, "rule01")
        is None
    )


def test_the_warning_names_both_time_zones_when_they_differ(
    make: Any, fake_server: FakeTimeLimitServer
) -> None:
    app, ids, _ = make()
    detail = app.test_client().get(f"/api/children/{ids['Anna']}").get_json()
    assert detail["child"]["time_zone_warning"] is None  # both UTC
    family = next(iter(fake_server.world.families.values()))
    family.users[ids["Anna"]].time_zone = "Pacific/Auckland"
    family.user_list_version = "zone-changed"
    pull(app, fake_server)
    warning = (
        app.test_client()
        .get(f"/api/children/{ids['Anna']}")
        .get_json()["child"]["time_zone_warning"]
    )
    assert "UTC+13:00" in warning["child"] and "UTC+00:00" in warning["dashboard"]
    assert off(app, ids).status_code == 200  # the function still works (W3)


def test_an_unknown_rule_is_not_found(make: Any) -> None:
    app, ids, _ = make()
    assert off(app, ids, "nope00").status_code == 404
    assert on_again(app, ids, "nope00").status_code == 404


def test_the_snapshot_survives_json(
    make: Any, fake_server: FakeTimeLimitServer
) -> None:
    app, ids, _ = make()
    off(app, ids)
    pending = app.extensions["dashboard"]["backend"].restores.get(
        fake_server.url, "rule01"
    )
    assert pending is not None and json.loads(pending.rule_set)["dayMask"] == ALL & ~WED
