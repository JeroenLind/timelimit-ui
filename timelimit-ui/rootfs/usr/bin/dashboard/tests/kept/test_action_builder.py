"""Contract tests for action_builder.py.

Every action the builder produces is checked against docs/protocol/actions-reference.md, which
is generated from the timelimit-server sources (docs/protocol/gen_actions.py). A builder that
drifts from the server's wire format fails here, instead of being silently dropped by the real
server (it answers shouldDoFullSync=true and skips the action).
"""

import json
import os
import re
from pathlib import Path

import action_builder as ab
import pytest
from action_builder import ActionError

REFERENCE = str(
    Path(__file__).resolve().parents[6] / "docs" / "protocol" / "actions-reference.md"
)


def load_reference():
    """Return {action type: (outer type, allowed fields, required fields)}."""
    assert os.path.exists(REFERENCE), "docs/protocol/actions-reference.md not found"
    result, outer, current = {}, None, None
    with open(REFERENCE, encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\n")
            m = re.match(r"## Outer type `(\w+)`", line)
            if m:
                outer, current = m.group(1), None
                continue
            m = re.match(r"### `([A-Z0-9_]+)`$", line)
            if m and outer:
                current = m.group(1)
                result[current] = (outer, set(), set())
                continue
            if line.startswith("## "):
                current = None
            m = re.match(r"\| `(\w+)` \| .* \| (yes|no) \|", line)
            if m and current:
                result[current][1].add(m.group(1))
                if m.group(2) == "yes":
                    result[current][2].add(m.group(1))
    return result


@pytest.fixture(scope="module")
def ref():
    return load_reference()


def assert_matches_server(action, ref, expected_outer):
    assert action["type"] in ref, f"{action['type']} is not a server action type"
    outer, allowed, required = ref[action["type"]]
    assert outer == expected_outer
    fields = set(action) - {"type"}
    assert fields <= allowed, (
        f"fields the server does not know: {sorted(fields - allowed)}"
    )
    assert required <= fields, f"required fields missing: {sorted(required - fields)}"


RULE_ID, CAT_ID, USER_ID, DEVICE_ID = "rule01", "cat001", "usr001", "dev001"


class TestWireFormat:
    def test_create_rule(self, ref):
        action = ab.create_timelimit_rule(
            RULE_ID,
            CAT_ID,
            3600000,
            days=31,
            extra_time=True,
            start=480,
            end=1080,
            dur=900000,
            pause=300000,
            per_day=True,
            expires_at=1,
        )
        assert_matches_server(action, ref, "parent")
        # create nests the fields in "rule"
        rule = action["rule"]
        assert rule == {
            "ruleId": RULE_ID,
            "categoryId": CAT_ID,
            "time": 3600000,
            "days": 31,
            "extraTime": True,
            "start": 480,
            "end": 1080,
            "dur": 900000,
            "pause": 300000,
            "perDay": True,
            "e": 1,
        }
        rule_fields = ref["CREATE_TIMELIMIT_RULE"][1]
        assert rule_fields == {"rule"}

    def test_create_rule_minimal(self, ref):
        action = ab.create_timelimit_rule(RULE_ID, CAT_ID, 60000)
        assert_matches_server(action, ref, "parent")
        assert action["rule"] == {
            "ruleId": RULE_ID,
            "categoryId": CAT_ID,
            "time": 60000,
            "days": 127,
            "extraTime": False,
        }

    def test_update_rule_is_flat_without_category(self, ref):
        action = ab.update_timelimit_rule(RULE_ID, 120000, days=3, start=0, end=60)
        assert_matches_server(action, ref, "parent")
        assert "categoryId" not in action and "rule" not in action
        assert action["ruleId"] == RULE_ID

    def test_delete_rule(self, ref):
        action = ab.delete_timelimit_rule(RULE_ID)
        assert_matches_server(action, ref, "parent")
        assert action == {"type": "DELETE_TIMELIMIT_RULE", "ruleId": RULE_ID}

    def test_category_apps(self, ref):
        add = ab.add_category_apps(CAT_ID, ["com.a", "com.b"])
        remove = ab.remove_category_apps(CAT_ID, ["com.a"])
        assert_matches_server(add, ref, "parent")
        assert_matches_server(remove, ref, "parent")
        assert add["packageNames"] == ["com.a", "com.b"]

    def test_add_child_user(self, ref):
        action = ab.add_child_user(USER_ID, "Kid", "Europe/Amsterdam")
        assert_matches_server(action, ref, "parent")
        assert action["userType"] == "child" and "password" not in action

    def test_no_class_style_type_names(self):
        for action in (
            ab.create_timelimit_rule(RULE_ID, CAT_ID, 1),
            ab.delete_timelimit_rule(RULE_ID),
            ab.add_category_apps(CAT_ID, ["a"]),
        ):
            assert re.fullmatch(r"[A-Z0-9_]+", action["type"]), action["type"]


class TestValidation:
    @pytest.mark.parametrize(
        "bad_id", ["", "abc", "abcdefg", "ab cde", "rule_123", "äbcdef", None, 123456]
    )
    def test_ids_must_be_six_alphanumerics(self, bad_id):
        with pytest.raises(ActionError):
            ab.delete_timelimit_rule(bad_id)
        with pytest.raises(ActionError):
            ab.create_timelimit_rule(RULE_ID, bad_id, 1)

    def test_new_id_is_valid_and_random(self):
        ids = {ab.new_id() for _ in range(50)}
        assert len(ids) > 40
        assert all(ab.is_valid_id(i) for i in ids)

    @pytest.mark.parametrize(
        "kwargs",
        [
            {"start": 600, "end": 500},  # start after end
            {"start": 0, "end": 1440},  # minute out of range
            {"start": -1, "end": 10},
            {"start": 10},  # start without end
            {"end": 10},
            {"days": 128},
            {"days": -1},
            {"dur": -1},
            {"pause": -1},
            {"expires_at": 0},
        ],
    )
    def test_rule_field_limits_like_the_server(self, kwargs):
        with pytest.raises(ActionError):
            ab.create_timelimit_rule(RULE_ID, CAT_ID, 1000, **kwargs)

    def test_time_must_be_a_non_negative_integer(self):
        for bad in (-1, 1.5, "60", None, True):
            with pytest.raises(ActionError):
                ab.create_timelimit_rule(RULE_ID, CAT_ID, bad)

    def test_package_names(self):
        for bad in ([], [""], ["a", "a"], [None]):
            with pytest.raises(ActionError):
                ab.add_category_apps(CAT_ID, bad)

    def test_child_user_needs_name_and_time_zone(self):
        with pytest.raises(ActionError):
            ab.add_child_user(USER_ID, "  ", "Europe/Amsterdam")
        with pytest.raises(ActionError):
            ab.add_child_user(USER_ID, "Kid", None)


class TestPushItems:
    def test_device_integrity_item(self):
        action = ab.delete_timelimit_rule(RULE_ID)
        item = ab.parent_item(action, 0, USER_ID)
        assert set(item) == {
            "encodedAction",
            "sequenceNumber",
            "integrity",
            "type",
            "userId",
        }
        assert item["type"] == "parent"
        assert item["integrity"] == "device"
        assert item["userId"] == USER_ID
        assert item["sequenceNumber"] == 0
        # encodedAction is a string that contains the JSON of the action
        assert isinstance(item["encodedAction"], str)
        assert json.loads(item["encodedAction"]) == action

    def test_encoding_is_compact_and_keeps_unicode(self):
        assert ab.encode_action({"a": "é", "b": [1, 2]}) == '{"a":"é","b":[1,2]}'

    def test_password_integrity_uses_own_device_id_and_exact_string(self):
        # key is a secondHash-like string; the HMAC covers the exact encodedAction string
        key = "$2a$12$abcdefghijklmnopqrstuuABCDEFGHIJKLMNOPQRSTUVWXYZ01234"
        action = ab.delete_timelimit_rule(RULE_ID)
        item = ab.parent_item(
            action, 7, USER_ID, own_device_id=DEVICE_ID, second_hash=key
        )
        from crypto_utils import calculate_hmac_sha256_binary

        assert item["integrity"] == calculate_hmac_sha256_binary(
            key, 7, DEVICE_ID, item["encodedAction"]
        )
        assert item["integrity"].startswith("password:")
        # a different device id gives a different value (the id is part of the message)
        other = ab.parent_item(
            action, 7, USER_ID, own_device_id="dev002", second_hash=key
        )
        assert other["integrity"] != item["integrity"]

    def test_password_integrity_needs_device_id(self):
        with pytest.raises(ActionError):
            ab.parent_item(
                ab.delete_timelimit_rule(RULE_ID), 0, USER_ID, second_hash="x"
            )

    def test_item_validation(self):
        with pytest.raises(ActionError):
            ab.parent_item(ab.delete_timelimit_rule(RULE_ID), -1, USER_ID)
        with pytest.raises(ActionError):
            ab.parent_item(ab.delete_timelimit_rule(RULE_ID), 0, "user_parent_123")

    def test_app_logic_item_has_no_integrity_and_no_user(self):
        item = ab.app_logic_item({"type": "UPDATE_DEVICE_STATUS", "appVersion": 227}, 3)
        assert (
            item["type"] == "appLogic"
            and item["integrity"] == ""
            and item["userId"] == ""
        )


class TestHmacTestVectors:
    """The two vectors of docs/ServerAPI.md 5.4 (computed with the server algorithm)."""

    def test_vector_1(self):
        from crypto_utils import calculate_hmac_sha256_binary

        key = "$2a$12$abcdefghijklmnopqrstuuABCDEFGHIJKLMNOPQRSTUVWXYZ01234"
        got = calculate_hmac_sha256_binary(
            key, 7, "dev123", '{"type":"CREATE_TIMELIMIT_RULE","rule":{"ruleId":"r1"}}'
        )
        assert got == "password:n10GZyWfMKiUKda4gXQEWgvlFYpTnKC3OG6zM6Jl6ms="

    def test_vector_2_non_ascii(self):
        from crypto_utils import calculate_hmac_sha256_binary

        key = "$2a$12$abcdefghijklmnopqrstuuABCDEFGHIJKLMNOPQRSTUVWXYZ01234"
        assert (
            calculate_hmac_sha256_binary(key, 0, "äöü", '{"a":"é"}')
            == "password:eC7BY0YnRSRFX8stS6q4iG32JSNSb1p6KU4X92BFsz0="
        )
