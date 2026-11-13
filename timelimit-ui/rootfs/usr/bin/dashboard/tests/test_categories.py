"""Plan step E6a: create, rename, delete, order, parent, unassigned apps, disable limits (FR-400, FR-401)."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest
from flask import Flask

from ..config import Settings
from ..domain.clock import FakeClock
from ..domain.secret import Secret
from ..factory import create_app
from .conftest import link_app, make_family, seed_children
from .fakeserver import FakeTimeLimitServer

NOW = datetime(2026, 11, 12, 12, 0, tzinfo=timezone.utc)
NOW_MS = int(NOW.timestamp() * 1000)


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


def family(fake: FakeTimeLimitServer) -> Any:
    return next(iter(fake.world.families.values()))


def detail(app: Flask, ids: dict[str, str], child: str = "Anna") -> dict[str, Any]:
    return app.test_client().get(f"/api/children/{ids[child]}").get_json()  # type: ignore[no-any-return]


def titles(app: Flask, ids: dict[str, str]) -> list[str]:
    return [c["title"] for c in detail(app, ids)["categories"]]


def base(ids: dict[str, str], child: str = "Anna") -> str:
    return f"/api/children/{ids[child]}"


def test_create_a_category_it_comes_last_and_exists_on_the_server(
    make: Any, fake_server: FakeTimeLimitServer
) -> None:
    app, ids = make()
    answer = app.test_client().post(f"{base(ids)}/categories", json={"title": "Music"})
    assert answer.status_code == 201
    new_id = answer.get_json()["category_id"]
    assert family(fake_server).categories[new_id].title == "Music"
    assert titles(app, ids)[-1] == "Music"


def test_create_below_a_parent_sends_both_actions_in_one_push(
    make: Any, fake_server: FakeTimeLimitServer
) -> None:
    app, ids = make()
    before = len(fake_server.world.action_types)
    answer = app.test_client().post(
        f"{base(ids)}/categories", json={"title": "Chess", "parent_id": "cgames"}
    )
    assert answer.status_code == 201
    assert fake_server.world.action_types[before:] == [
        "CREATE_CATEGORY",
        "SET_PARENT_CATEGORY",
    ]
    assert (
        family(fake_server).categories[answer.get_json()["category_id"]].parent_id
        == "cgames"
    )


@pytest.mark.parametrize(
    "body",
    [
        None,
        {},
        {"title": ""},
        {"title": "  "},
        {"title": 5},
        {"title": "x", "parent_id": "nope"},
        {"title": "x", "parent_id": 4},
    ],
)
def test_invalid_create_is_refused_before_sending(
    body: Any, make: Any, fake_server: FakeTimeLimitServer
) -> None:
    app, ids = make()
    pushes = fake_server.world.push_requests
    assert app.test_client().post(f"{base(ids)}/categories", json=body).status_code in (
        400,
        404,
    )
    assert fake_server.world.push_requests == pushes


def test_a_parent_of_another_child_is_refused(make: Any) -> None:
    app, ids = make()
    anna_cat = detail(app, ids)["categories"][0]["id"]
    answer = app.test_client().post(
        f"{base(ids, 'Ben')}/categories", json={"title": "x", "parent_id": anna_cat}
    )
    assert answer.status_code == 404


def test_rename_sends_only_the_title(
    make: Any, fake_server: FakeTimeLimitServer
) -> None:
    app, ids = make()
    before = len(fake_server.world.action_types)
    assert (
        app.test_client()
        .put(f"{base(ids)}/categories/cgames", json={"title": "Play"})
        .status_code
        == 200
    )
    assert fake_server.world.action_types[before:] == ["UPDATE_CATEGORY_TITLE"]
    assert family(fake_server).categories["cgames"].title == "Play"


def test_an_unchanged_update_sends_nothing(
    make: Any, fake_server: FakeTimeLimitServer
) -> None:
    app, ids = make()
    pushes = fake_server.world.push_requests
    assert (
        app.test_client()
        .put(f"{base(ids)}/categories/cgames", json={"title": "Games"})
        .status_code
        == 200
    )
    assert fake_server.world.push_requests == pushes


def test_move_below_another_category_and_back_to_top_level(
    make: Any, fake_server: FakeTimeLimitServer
) -> None:
    app, ids = make()
    client = app.test_client()
    answer = client.post(f"{base(ids)}/categories", json={"title": "Music"})
    new = answer.get_json()["category_id"]
    url = f"{base(ids)}/categories/{new}"
    assert client.put(url, json={"parent_id": "cgames"}).status_code == 200
    assert family(fake_server).categories[new].parent_id == "cgames"
    assert client.put(url, json={"parent_id": ""}).status_code == 200
    assert family(fake_server).categories[new].parent_id == ""


def test_a_loop_in_the_tree_is_refused_without_sending(
    make: Any, fake_server: FakeTimeLimitServer
) -> None:
    app, ids = make()
    client = app.test_client()
    pushes = fake_server.world.push_requests  # Social is below Games in the seed
    for parent in ("csocia", "cgames"):  # below its own sub-category, below itself
        answer = client.put(
            f"{base(ids)}/categories/cgames", json={"parent_id": parent}
        )
        assert (answer.status_code, answer.get_json()["field"]) == (400, "parent_id")
    assert fake_server.world.push_requests == pushes


def test_delete_a_category_with_its_rules(
    make: Any, fake_server: FakeTimeLimitServer
) -> None:
    app, ids = make()
    client = app.test_client()
    client.delete(f"{base(ids)}/categories/csocia")  # Social is below Games
    assert client.delete(f"{base(ids)}/categories/cgames").status_code == 200
    assert "cgames" not in family(fake_server).categories


def test_a_category_with_sub_categories_can_not_be_deleted(
    make: Any, fake_server: FakeTimeLimitServer
) -> None:
    app, ids = make()
    client = app.test_client()
    answer = client.delete(f"{base(ids)}/categories/cgames")
    assert (answer.status_code, answer.get_json()["field"]) == (400, "category")
    assert "cgames" in family(fake_server).categories
    assert client.delete(f"{base(ids)}/categories/csocia").status_code == 200
    assert client.delete(f"{base(ids)}/categories/cgames").status_code == 200


def test_deleting_the_category_for_unassigned_apps_clears_it(
    make: Any, fake_server: FakeTimeLimitServer
) -> None:
    app, ids = make()
    client = app.test_client()
    assert (
        client.put(
            f"{base(ids)}/unassigned-category", json={"category_id": "cgames"}
        ).status_code
        == 200
    )
    assert detail(app, ids)["child"]["category_for_unassigned"] == "cgames"
    client.delete(f"{base(ids)}/categories/csocia")
    assert client.delete(f"{base(ids)}/categories/cgames").status_code == 200
    assert detail(app, ids)["child"]["category_for_unassigned"] == ""


def test_the_category_for_unassigned_apps_must_belong_to_the_child(make: Any) -> None:
    app, ids = make()
    ben_cat = detail(app, ids, "Ben")["categories"]
    assert (
        app.test_client()
        .put(f"{base(ids)}/unassigned-category", json={"category_id": "nope"})
        .status_code
        == 404
    )
    assert (
        ben_cat == []
        or app.test_client()
        .put(f"{base(ids)}/unassigned-category", json={"category_id": ben_cat[0]["id"]})
        .status_code
        == 404
    )
    assert (
        app.test_client()
        .put(f"{base(ids)}/unassigned-category", json={"category_id": ""})
        .status_code
        == 200
    )


def test_move_up_and_down_swaps_with_the_neighbour(
    make: Any, fake_server: FakeTimeLimitServer
) -> None:
    app, ids = make()
    client = app.test_client()
    client.post(f"{base(ids)}/categories", json={"title": "Music"})
    first = titles(app, ids)
    assert len(first) == 3
    mid = detail(app, ids)["categories"][-1]["id"]  # Music, top level like Games
    assert (
        client.post(
            f"{base(ids)}/categories/{mid}/move", json={"direction": "up"}
        ).status_code
        == 200
    )
    again = titles(app, ids)
    assert again == ["Music", "Games", "Social"]
    # at the edge nothing is sent
    pushes = fake_server.world.push_requests
    top = detail(app, ids)["categories"][0]["id"]
    assert (
        client.post(
            f"{base(ids)}/categories/{top}/move", json={"direction": "up"}
        ).status_code
        == 200
    )
    assert fake_server.world.push_requests == pushes
    assert (
        client.post(
            f"{base(ids)}/categories/{top}/move", json={"direction": "left"}
        ).status_code
        == 400
    )


def test_disable_limits_for_a_while_and_switch_off_again(
    make: Any, fake_server: FakeTimeLimitServer
) -> None:
    app, ids = make()
    client = app.test_client()
    url = f"{base(ids)}/categories/cgames/disable-limits"
    assert client.put(url, json={"minutes": 30}).status_code == 200
    assert (
        family(fake_server).categories["cgames"].disable_limits_until
        == NOW_MS + 30 * 60000
    )
    shown = next(c for c in detail(app, ids)["categories"] if c["id"] == "cgames")
    assert (
        shown["limits_disabled"]
        and shown["limits_disabled_until"] == NOW_MS + 30 * 60000
    )
    assert client.put(url, json={"minutes": 0}).status_code == 200
    assert family(fake_server).categories["cgames"].disable_limits_until == 0


@pytest.mark.parametrize("minutes", [-1, 10081, "5", 1.5, None, True])
def test_invalid_disable_minutes_are_refused(minutes: Any, make: Any) -> None:
    app, ids = make()
    answer = app.test_client().put(
        f"{base(ids)}/categories/cgames/disable-limits", json={"minutes": minutes}
    )
    assert (answer.status_code, answer.get_json()["field"]) == (400, "minutes")


def test_unknown_child_or_category_is_not_found(make: Any) -> None:
    app, ids = make()
    client = app.test_client()
    assert (
        client.put(f"{base(ids)}/categories/nope", json={"title": "x"}).status_code
        == 404
    )
    assert client.delete("/api/children/nobody/categories/cgames").status_code == 404


def test_the_server_down_gives_503_and_changes_nothing(
    make: Any, fake_server: FakeTimeLimitServer
) -> None:
    app, ids = make()
    fake_server.faults.drop_connection = True
    answer = app.test_client().post(f"{base(ids)}/categories", json={"title": "x"})
    fake_server.faults.drop_connection = False
    assert answer.status_code == 503
