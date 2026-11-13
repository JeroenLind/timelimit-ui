"""Plan step E5: weekly blocked times per category (FR-304, Q4)."""

from __future__ import annotations

import random
from collections.abc import Callable, Iterator
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest
from flask import Flask

from ..config import Settings
from ..domain.bitmask import format_blocked_times, merge_intervals, parse_blocked_times
from ..domain.clock import FakeClock
from ..domain.secret import Secret
from ..factory import create_app
from .conftest import link_app, make_family, seed_children
from .fakeserver import FakeTimeLimitServer
from .fakeserver.state import version_id

NOW = datetime(2026, 11, 12, 12, 0, tzinfo=timezone.utc)
DAY = 1440
# Monday to Friday 22:00-24:00 and 00:00-07:00 the next morning, as the grid would send it
NIGHTS = [[d * DAY + 1320, (d + 1) * DAY + 420] for d in range(4)] + [
    [4 * DAY + 1320, 5 * DAY]
]
NIGHTS = [[0, 420], *NIGHTS]


@pytest.fixture
def make(
    data_dir: Path, fake_server: FakeTimeLimitServer
) -> Iterator[Callable[[], tuple[Flask, dict[str, str]]]]:
    apps: list[Flask] = []

    def build() -> tuple[Flask, dict[str, str]]:
        make_family(fake_server)
        ids = seed_children(fake_server, 20000)
        settings = Settings(
            data_dir=data_dir, server_url=fake_server.url, server_timeout=3.0
        )
        app = create_app(settings, Secret("s"), FakeClock(NOW))
        apps.append(app)
        link_app(app, fake_server)
        return app, ids

    yield build
    for app in apps:
        app.extensions["dashboard"]["backend"].close()


def games(fake: FakeTimeLimitServer) -> Any:
    return next(iter(fake.world.families.values())).categories["cgames"]


def category(app: Flask, ids: dict[str, str]) -> dict[str, Any]:
    detail = app.test_client().get(f"/api/children/{ids['Anna']}").get_json()
    return next(c for c in detail["categories"] if c["id"] == "cgames")


def put(app: Flask, ids: dict[str, str], body: Any) -> Any:
    return app.test_client().put(
        f"/api/children/{ids['Anna']}/categories/cgames/blocked-times", json=body
    )


def test_random_schedules_survive_the_encoding_round_trip() -> None:
    rng = random.Random(7)
    for _ in range(200):
        cuts = sorted(rng.sample(range(10081), rng.choice([0, 2, 4, 10, 40])))
        pairs = [
            (cuts[i], cuts[i + 1])
            for i in range(0, len(cuts) - 1, 2)
            if cuts[i] < cuts[i + 1]
        ]
        pairs = merge_intervals(pairs)
        assert parse_blocked_times(format_blocked_times(pairs)) == pairs


def test_a_category_starts_with_nothing_blocked(make: Any) -> None:
    app, ids = make()
    cat = category(app, ids)
    assert cat["blocked_times"] == [] and cat["blocked_version"]


def test_a_schedule_set_in_the_fake_is_shown_as_minutes_of_the_week(
    make: Any, fake_server: FakeTimeLimitServer
) -> None:
    app, ids = make()
    games(fake_server).blocked_times = "1320,1440,1500,1560"
    games(fake_server).base_version = version_id()
    backend = app.extensions["dashboard"]["backend"]
    link = backend.links.get(fake_server.url)
    backend.puller(fake_server.url).pull(
        fake_server.url, link.device_token, link.family_id
    )
    assert category(app, ids)["blocked_times"] == [[1320, 1440], [1500, 1560]]


def test_saving_blocks_monday_to_friday_nights_and_the_cache_equals_it(
    make: Any, fake_server: FakeTimeLimitServer
) -> None:
    app, ids = make()
    assert put(app, ids, {"intervals": NIGHTS}).status_code == 200
    assert parse_blocked_times(games(fake_server).blocked_times) == [
        tuple(i) for i in NIGHTS
    ]
    assert category(app, ids)["blocked_times"] == NIGHTS


def test_touching_and_unsorted_intervals_are_merged_before_sending(
    make: Any, fake_server: FakeTimeLimitServer
) -> None:
    app, ids = make()
    assert (
        put(app, ids, {"intervals": [[60, 120], [0, 60], [100, 200]]}).status_code
        == 200
    )
    assert games(fake_server).blocked_times == "0,200"


def test_clearing_everything_sends_the_empty_string(
    make: Any, fake_server: FakeTimeLimitServer
) -> None:
    app, ids = make()
    put(app, ids, {"intervals": [[0, 60]]})
    assert put(app, ids, {"intervals": []}).status_code == 200
    assert games(fake_server).blocked_times == ""


@pytest.mark.parametrize(
    "body",
    [
        None,
        {},
        {"intervals": "x"},
        {"intervals": [[1]]},
        {"intervals": [[0, "5"]]},
        {"intervals": [[-1, 5]]},
        {"intervals": [[0, 10081]]},
        {"intervals": [[5, 5]]},
    ],
)
def test_invalid_input_is_refused_before_sending(
    body: Any, make: Any, fake_server: FakeTimeLimitServer
) -> None:
    app, ids = make()
    pushes = fake_server.world.push_requests
    answer = put(app, ids, body)
    assert answer.status_code == 400
    assert fake_server.world.push_requests == pushes


def test_a_change_elsewhere_gives_a_conflict(
    make: Any, fake_server: FakeTimeLimitServer
) -> None:
    app, ids = make()
    version = category(app, ids)["blocked_version"]
    games(fake_server).blocked_times = "0,60"
    games(fake_server).base_version = version_id()
    backend = app.extensions["dashboard"]["backend"]
    link = backend.links.get(fake_server.url)
    backend.puller(fake_server.url).pull(
        fake_server.url, link.device_token, link.family_id
    )
    answer = put(app, ids, {"intervals": [[100, 200]], "version": version})
    assert (answer.status_code, answer.get_json()["code"]) == (409, "CONFLICT")
    assert games(fake_server).blocked_times == "0,60"
    assert put(app, ids, {"intervals": [[100, 200]]}).status_code == 200  # save anyway


def test_an_unknown_category_is_not_found(make: Any) -> None:
    app, ids = make()
    answer = app.test_client().put(
        f"/api/children/{ids['Anna']}/categories/nope/blocked-times",
        json={"intervals": []},
    )
    assert answer.status_code == 404
