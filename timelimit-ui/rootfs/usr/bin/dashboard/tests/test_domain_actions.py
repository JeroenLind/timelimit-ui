"""Contract tests for every v1 action builder (B2, TR-100, TR-102, TR-501).

Every builder's output is validated against the server's own request schemas
(``tests/fakeserver/server_schemas.json``, generated from the server source) and invalid input must
raise ``ActionError`` before anything is sent. A coverage test fails when an action type or a builder
lacks a case.
"""

from __future__ import annotations

import inspect
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from dashboard.domain import actions as act
from dashboard.domain.actions import ActionError
from dashboard.domain.bitmask import ALL_DAYS_MASK

from .fakeserver import schemas
from .fakeserver.actions import _DEFS, schemas_valid

C1, C2, U1, D1 = "cat001", "cat002", "usr001", "dev001"
HASH = "$2a$12$" + "A" * 53
SALT = "$2a$12$" + "B" * 22
CONTAINER = "aXY=.cHVi.ab12"
ENCRYPTED = "0f" * 40
INTEGRITY = "ab" * 64

Case = tuple[Callable[..., dict[str, Any]], dict[str, Any]]

# one or more valid calls per wire type
VALID: dict[str, list[Case]] = {
    "CREATE_TIMELIMIT_RULE": [
        (
            act.create_timelimit_rule,
            {"rule_id": "rul001", "category_id": C1, "time_ms": 3_600_000},
        ),
        (
            act.create_timelimit_rule,
            {
                "rule_id": "rul001",
                "category_id": C1,
                "time_ms": 0,
                "days": 5,
                "extra_time": True,
                "start": 60,
                "end": 120,
                "dur": 1000,
                "pause": 500,
                "per_day": True,
            },
        ),
    ],
    "UPDATE_TIMELIMIT_RULE": [
        (act.update_timelimit_rule, {"rule_id": "rul001", "time_ms": 1000}),
        (
            act.update_timelimit_rule,
            {"rule_id": "rul001", "time_ms": 1000, "days": 0, "start": 0, "end": 1439},
        ),
    ],
    "DELETE_TIMELIMIT_RULE": [(act.delete_timelimit_rule, {"rule_id": "rul001"})],
    "CREATE_CATEGORY": [
        (act.create_category, {"child_id": U1, "category_id": C1, "title": "Games"})
    ],
    "DELETE_CATEGORY": [(act.delete_category, {"category_id": C1})],
    "UPDATE_CATEGORY_TITLE": [
        (act.update_category_title, {"category_id": C1, "new_title": "New"})
    ],
    "SET_PARENT_CATEGORY": [
        (act.set_parent_category, {"category_id": C1, "parent_category": C2}),
        (act.set_parent_category, {"category_id": C1, "parent_category": ""}),
    ],
    "UPDATE_CATEGORY_SORTING": [
        (act.update_category_sorting, {"category_ids": [C2, C1]})
    ],
    "UPDATE_CATEGORY_BLOCKED_TIMES": [
        (act.update_category_blocked_times, {"category_id": C1, "intervals": []}),
        (
            act.update_category_blocked_times,
            {"category_id": C1, "intervals": [(0, 60), (120, 10080)]},
        ),
    ],
    "UPDATE_CATEGORY_FLAGS": [
        (act.update_category_flags, {"category_id": C1, "modified": 1, "values": 1}),
        (act.update_category_flags, {"category_id": C1, "modified": 1, "values": 0}),
        (act.update_category_flags, {"category_id": C1, "modified": 0, "values": 0}),
    ],
    "UPDATE_CATEGORY_TIME_WARNINGS": [
        (
            act.update_category_time_warnings,
            {"category_id": C1, "enable": True, "flags": 31, "minutes": 10},
        ),
        (
            act.update_category_time_warnings,
            {"category_id": C1, "enable": False, "flags": 0},
        ),
    ],
    "UPDATE_CATEGORY_BLOCK_ALL_NOTIFICATIONS": [
        (
            act.update_category_block_all_notifications,
            {"category_id": C1, "blocked": True},
        ),
        (
            act.update_category_block_all_notifications,
            {"category_id": C1, "blocked": True, "block_delay_ms": 5000},
        ),
    ],
    "UPDATE_CATEGORY_BATTERY_LIMIT": [
        (act.update_category_battery_limit, {"category_id": C1}),
        (
            act.update_category_battery_limit,
            {"category_id": C1, "charge_limit": 20, "mobile_limit": 100},
        ),
    ],
    "ADD_CATEGORY_NETWORK_ID": [
        (
            act.add_category_network_id,
            {"category_id": C1, "item_id": "itm001", "hashed_network_id": "0a1B2c3D"},
        ),
    ],
    "RESET_CATEGORY_NETWORK_IDS": [
        (act.reset_category_network_ids, {"category_id": C1})
    ],
    "SET_CATEGORY_FOR_UNASSIGNED_APPS": [
        (act.set_category_for_unassigned_apps, {"child_id": U1, "category_id": C1}),
        (act.set_category_for_unassigned_apps, {"child_id": U1, "category_id": ""}),
    ],
    "UPDATE_CATEGORY_DISABLE_LIMITS": [
        (act.update_category_disable_limits, {"category_id": C1, "end_time_ms": 0})
    ],
    "SET_USER_DISABLE_LIMITS_UNTIL": [
        (
            act.set_user_disable_limits_until,
            {"child_id": U1, "time_ms": 1_700_000_000_000},
        )
    ],
    "INCREMENT_CATEGORY_EXTRATIME": [
        (act.increment_category_extra_time, {"category_id": C1, "added_ms": 60_000}),
        (
            act.increment_category_extra_time,
            {"category_id": C1, "added_ms": 60_000, "day": -1},
        ),
        (
            act.increment_category_extra_time,
            {"category_id": C1, "added_ms": 0, "day": 3},
        ),
    ],
    "SET_CATEGORY_EXTRA_TIME": [
        (act.set_category_extra_time, {"category_id": C1, "new_extra_ms": 0}),
        (
            act.set_category_extra_time,
            {"category_id": C1, "new_extra_ms": 1000, "day": 2},
        ),
    ],
    "UPDATE_CATEGORY_TEMPORARILY_BLOCKED": [
        (act.update_category_temporarily_blocked, {"category_id": C1, "blocked": True}),
        (
            act.update_category_temporarily_blocked,
            {"category_id": C1, "blocked": True, "end_time_ms": 1_800_000_000_000},
        ),
        (
            act.update_category_temporarily_blocked,
            {"category_id": C1, "blocked": False},
        ),
    ],
    "ADD_CATEGORY_APPS": [
        (act.add_category_apps, {"category_id": C1, "package_names": ["a.b", "c.d"]})
    ],
    "REMOVE_CATEGORY_APPS": [
        (act.remove_category_apps, {"category_id": C1, "package_names": ["a.b"]})
    ],
    "ADD_USER": [
        (
            act.add_child_user,
            {"user_id": U1, "name": "Kid", "time_zone": "Europe/Amsterdam"},
        ),
        (
            act.add_parent_user,
            {
                "user_id": U1,
                "name": "Dashboard",
                "time_zone": "Europe/Amsterdam",
                "password_hash": HASH,
                "second_salt": SALT,
                "second_hash_container": CONTAINER,
            },
        ),
    ],
    "REMOVE_USER": [
        (act.remove_user, {"user_id": U1}),
        (act.remove_user, {"user_id": U1, "authentication": "0123456789abcdef"}),
    ],
    "RENAME_CHILD": [(act.rename_child, {"child_id": U1, "new_name": "Kid"})],
    "SET_USER_TIMEZONE": [(act.set_user_timezone, {"user_id": U1, "time_zone": "UTC"})],
    "SET_KEEP_SIGNED_IN": [
        (act.set_keep_signed_in, {"device_id": D1, "keep_signed_in": True})
    ],
    "CHANGE_PARENT_PASSWORD": [
        (
            act.change_parent_password,
            {
                "user_id": U1,
                "new_hash": HASH,
                "new_second_salt": SALT,
                "second_hash_encrypted": ENCRYPTED,
                "integrity": INTEGRITY,
            },
        ),
    ],
}

# invalid calls: every one must raise ActionError
INVALID: list[tuple[Callable[..., dict[str, Any]], dict[str, Any]]] = [
    (act.create_timelimit_rule, {"rule_id": "short", "category_id": C1, "time_ms": 1}),
    (
        act.create_timelimit_rule,
        {"rule_id": "rul001", "category_id": "bad id!", "time_ms": 1},
    ),
    (
        act.create_timelimit_rule,
        {"rule_id": "rul001", "category_id": C1, "time_ms": -1},
    ),
    (
        act.create_timelimit_rule,
        {"rule_id": "rul001", "category_id": C1, "time_ms": True},
    ),
    (
        act.create_timelimit_rule,
        {"rule_id": "rul001", "category_id": C1, "time_ms": 1, "days": 128},
    ),
    (
        act.create_timelimit_rule,
        {"rule_id": "rul001", "category_id": C1, "time_ms": 1, "start": 5},
    ),
    (
        act.create_timelimit_rule,
        {"rule_id": "rul001", "category_id": C1, "time_ms": 1, "start": 10, "end": 5},
    ),
    (
        act.create_timelimit_rule,
        {"rule_id": "rul001", "category_id": C1, "time_ms": 1, "start": 0, "end": 1440},
    ),
    (
        act.create_timelimit_rule,
        {"rule_id": "rul001", "category_id": C1, "time_ms": 1, "dur": -1},
    ),
    (act.update_timelimit_rule, {"rule_id": "rul001", "time_ms": 1, "days": -1}),
    (
        act.update_timelimit_rule,
        {"rule_id": "rul001", "time_ms": 1, "extra_time": "yes"},
    ),
    (act.delete_timelimit_rule, {"rule_id": ""}),
    (act.create_category, {"child_id": U1, "category_id": C1, "title": "  "}),
    (act.create_category, {"child_id": "x", "category_id": C1, "title": "T"}),
    (act.delete_category, {"category_id": None}),
    (act.update_category_title, {"category_id": C1, "new_title": ""}),
    (act.set_parent_category, {"category_id": C1, "parent_category": "nope"}),
    (act.update_category_sorting, {"category_ids": []}),
    (act.update_category_sorting, {"category_ids": [C1, C1]}),
    (
        act.update_category_blocked_times,
        {"category_id": C1, "intervals": [(0, 10), (10, 20)]},
    ),
    (act.update_category_blocked_times, {"category_id": C1, "intervals": [(0, 10081)]}),
    (act.update_category_flags, {"category_id": C1, "modified": 2, "values": 2}),
    (act.update_category_flags, {"category_id": C1, "modified": 0, "values": 1}),
    (act.update_category_flags, {"category_id": C1, "modified": 1, "values": -1}),
    (
        act.update_category_time_warnings,
        {"category_id": C1, "enable": True, "flags": 32},
    ),
    (
        act.update_category_time_warnings,
        {"category_id": C1, "enable": True, "flags": 1, "minutes": 0},
    ),
    (
        act.update_category_time_warnings,
        {"category_id": C1, "enable": True, "flags": 1, "minutes": 10079},
    ),
    (act.update_category_time_warnings, {"category_id": C1, "enable": "x", "flags": 1}),
    (
        act.update_category_block_all_notifications,
        {"category_id": C1, "blocked": True, "block_delay_ms": -1},
    ),
    (act.update_category_battery_limit, {"category_id": C1, "charge_limit": 101}),
    (act.update_category_battery_limit, {"category_id": C1, "mobile_limit": -1}),
    (
        act.add_category_network_id,
        {"category_id": C1, "item_id": "itm001", "hashed_network_id": "xyz"},
    ),
    (
        act.add_category_network_id,
        {"category_id": C1, "item_id": "itm001", "hashed_network_id": "0a1B2c3Dff"},
    ),
    (act.set_category_for_unassigned_apps, {"child_id": U1, "category_id": "bad"}),
    (act.update_category_disable_limits, {"category_id": C1, "end_time_ms": -1}),
    (act.set_user_disable_limits_until, {"child_id": U1, "time_ms": -1}),
    (act.increment_category_extra_time, {"category_id": C1, "added_ms": -1}),
    (act.increment_category_extra_time, {"category_id": C1, "added_ms": 1, "day": -2}),
    (act.set_category_extra_time, {"category_id": C1, "new_extra_ms": -5}),
    (act.set_category_extra_time, {"category_id": C1, "new_extra_ms": 5, "day": -2}),
    (
        act.update_category_temporarily_blocked,
        {"category_id": C1, "blocked": False, "end_time_ms": 5},
    ),
    (act.add_category_apps, {"category_id": C1, "package_names": []}),
    (act.add_category_apps, {"category_id": C1, "package_names": ["a", "a"]}),
    (act.remove_category_apps, {"category_id": C1, "package_names": [""]}),
    (act.add_child_user, {"user_id": U1, "name": "", "time_zone": "UTC"}),
    (act.add_child_user, {"user_id": U1, "name": "Kid", "time_zone": ""}),
    (
        act.add_parent_user,
        {
            "user_id": U1,
            "name": "P",
            "time_zone": "UTC",
            "password_hash": "x",
            "second_salt": SALT,
            "second_hash_container": CONTAINER,
        },
    ),
    (
        act.add_parent_user,
        {
            "user_id": U1,
            "name": "P",
            "time_zone": "UTC",
            "password_hash": HASH,
            "second_salt": "x",
            "second_hash_container": CONTAINER,
        },
    ),
    (
        act.add_parent_user,
        {
            "user_id": U1,
            "name": "P",
            "time_zone": "UTC",
            "password_hash": HASH,
            "second_salt": SALT,
            "second_hash_container": HASH,
        },
    ),
    (act.remove_user, {"user_id": U1, "authentication": ""}),
    (act.rename_child, {"child_id": U1, "new_name": ""}),
    (act.set_user_timezone, {"user_id": U1, "time_zone": ""}),
    (act.set_keep_signed_in, {"device_id": D1, "keep_signed_in": "true"}),
    (
        act.change_parent_password,
        {
            "user_id": U1,
            "new_hash": HASH,
            "new_second_salt": SALT,
            "second_hash_encrypted": "ab",
            "integrity": INTEGRITY,
        },
    ),
    (
        act.change_parent_password,
        {
            "user_id": U1,
            "new_hash": HASH,
            "new_second_salt": SALT,
            "second_hash_encrypted": ENCRYPTED,
            "integrity": "ab",
        },
    ),
]

HELPERS = {
    "encode_action",
    "new_id",
    "is_valid_id",
    "parent_item",
    "app_logic_item",
}


def _cases() -> list[tuple[str, Callable[..., dict[str, Any]], dict[str, Any]]]:
    return [
        (wire, fn, kwargs) for wire, entries in VALID.items() for fn, kwargs in entries
    ]


@pytest.mark.parametrize(("wire", "builder", "kwargs"), _cases())
def test_valid_output_matches_the_server_schema(
    wire: str, builder: Callable[..., dict[str, Any]], kwargs: dict[str, Any]
) -> None:
    action = builder(**kwargs)
    assert action["type"] == wire
    assert schemas_valid(action), schemas.definitions()[_DEFS[wire]]


@pytest.mark.parametrize(("wire", "builder", "kwargs"), _cases())
def test_valid_output_survives_the_wire_unchanged(
    wire: str, builder: Callable[..., dict[str, Any]], kwargs: dict[str, Any]
) -> None:
    action = builder(**kwargs)
    assert json.loads(act.encode_action(action)) == action


@pytest.mark.parametrize(
    ("builder", "kwargs"), INVALID, ids=lambda v: v.__name__ if callable(v) else ""
)
def test_invalid_input_raises_before_anything_is_sent(
    builder: Callable[..., dict[str, Any]], kwargs: dict[str, Any]
) -> None:
    with pytest.raises(ActionError):
        builder(**kwargs)


def test_every_v1_type_has_a_builder_and_is_a_known_server_action() -> None:
    v1 = set(VALID)
    assert v1 <= set(_DEFS), "builders for types the server schema does not know"
    # the 50 parent action types of the server minus the ones the dashboard never sends in v1
    not_in_v1 = {
        "ADD_PARENT_U2F",
        "REMOVE_PARENT_U2F",
        "REPORT_U2F_LOGIN",
        "DELETE_CHILD_TASK",
        "REVIEW_CHILD_TASK",
        "UPDATE_CHILD_TASK",
        "IGNORE_MANIPULATION",
        "SET_CHILD_PASSWORD",
        "SET_CONSIDER_REBOOT_MANIPULATION",
        "SET_DEVICE_DEFAULT_USER",
        "SET_DEVICE_DEFAULT_USER_TIMEOUT",
        "SET_DEVICE_USER",
        "SET_RELAX_PRIMARY_DEVICE",
        "SET_SEND_DEVICE_CONNECTED",
        "UPDATE_DEVICE_NAME",
        "UPDATE_ENABLE_ACTIVITY_LEVEL_BLOCKING",
        "UPDATE_NETWORK_TIME_VERIFICATION",
        "UPDATE_PARENT_NOTIFICATION_FLAGS",
        "UPDATE_USER_FLAGS",
        "UPDATE_USER_LIMIT_LOGIN_CATEGORY",
        "UPDATE_USER_LIMIT_LOGIN_PRE_BLOCK_DURATION",
    }
    parent_types = _parent_types()
    assert len(parent_types) == 50
    assert parent_types - v1 == not_in_v1, (
        "an action is neither built nor explicitly out of scope"
    )


def _parent_types() -> set[str]:
    reference = (
        Path(__file__).resolve().parents[5]
        / "docs"
        / "protocol"
        / "actions-reference.md"
    )
    text = reference.read_text(encoding="utf-8")
    parent_block = text.split("## Outer type `parent`")[1].split(
        "## Outer type `child`"
    )[0]
    return {
        line[5:-1] for line in parent_block.splitlines() if line.startswith("### `")
    }


def test_every_public_builder_has_a_valid_case() -> None:
    covered = {fn for entries in VALID.values() for fn, _ in entries}
    public = {
        obj
        for name, obj in inspect.getmembers(act, inspect.isfunction)
        if obj.__module__ == act.__name__
        and not name.startswith("_")
        and name not in HELPERS
    }
    assert public - covered == set(), "builder without a contract test"


def test_ids_have_the_family_format() -> None:
    for _ in range(50):
        assert act.is_valid_id(act.new_id())


def test_the_server_does_not_require_a_block_delay_key_when_omitted() -> None:
    action = act.update_category_block_all_notifications(C1, True)
    assert "blockDelay" not in action
    assert schemas_valid(action)


def test_push_item_with_device_integrity() -> None:
    item = act.parent_item(act.delete_category(C1), 5, U1)
    assert (
        item["integrity"] == "device"
        and item["type"] == "parent"
        and item["userId"] == U1
    )
    assert json.loads(item["encodedAction"])["type"] == "DELETE_CATEGORY"
    assert schemas.is_valid(
        "isClientPushChangesRequest", {"deviceAuthToken": "t" * 32, "actions": [item]}
    )


def test_push_item_with_password_integrity_uses_the_device_id() -> None:
    item = act.parent_item(
        act.delete_category(C1), 9, U1, own_device_id=D1, second_hash=HASH
    )
    assert item["integrity"].startswith("password:")
    with pytest.raises(ActionError):
        act.parent_item(
            act.delete_category(C1), 9, U1, own_device_id="x", second_hash=HASH
        )


def test_push_item_rejects_bad_numbers_and_users() -> None:
    with pytest.raises(ActionError):
        act.parent_item(act.delete_category(C1), -1, U1)
    with pytest.raises(ActionError):
        act.parent_item(act.delete_category(C1), 0, "bad")


def test_app_logic_item_has_no_integrity() -> None:
    item = act.app_logic_item({"type": "FORCE_SYNC"}, 3)
    assert item["integrity"] == "" and item["type"] == "appLogic"


def test_day_mask_default_is_every_day() -> None:
    assert act.create_timelimit_rule("rul001", C1, 1)["rule"]["days"] == ALL_DAYS_MASK
