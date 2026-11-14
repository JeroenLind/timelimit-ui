"""Builders for every parent action the dashboard sends in v1 (TR-100, TR-101, TR-102).

Pure and strictly typed. Wire format: docs/ServerAPI.md sections 4, 5, 7 and
docs/protocol/actions-reference.md. Each builder checks its input the way the server does, so a
mistake raises :class:`ActionError` here, before a sequence number is used, instead of being dropped
silently by the server (HTTP 200 with ``shouldDoFullSync``).

Facts worth knowing:

* The wire ``type`` is SCREAMING_SNAKE (``CREATE_TIMELIMIT_RULE``).
* Ids inside a family are exactly 6 characters ``[0-9a-zA-Z]``.
* ``encodedAction`` is a *string* holding the JSON; the integrity covers exactly that string.
* Time values are milliseconds unless the name says minutes.
"""

from __future__ import annotations

import json
import re
import secrets
import string
from collections.abc import Iterable
from typing import Any

from dashboard.domain.bitmask import (
    ALL_DAYS_MASK,
    BitmaskError,
    Interval,
    format_blocked_times,
)
from dashboard.domain.integrity import password_integrity

Action = dict[str, Any]
PushItem = dict[str, Any]

ID_PATTERN = re.compile(r"^[0-9a-zA-Z]{6}$")
_ID_ALPHABET = string.ascii_letters + string.digits

MAX_MINUTE_OF_DAY = 1439
MAX_ACTIONS_PER_REQUEST = 25  # the server accepts 50, the Android app sends 25
MIN_WARNING_MINUTES = 1
MAX_WARNING_MINUTES = 60 * 24 * 7 - 2
ALLOWED_TIME_WARNING_FLAGS = 1 | 2 | 4 | 8 | 16
CATEGORY_FLAG_BLOCKED_NETWORK_LIST = 1  # the only category flag the server knows
MAX_CATEGORY_FLAGS = CATEGORY_FLAG_BLOCKED_NETWORK_LIST
NETWORK_ID_HEX_LENGTH = 8
SECOND_HASH_PATTERN = re.compile(r"^\$2a\$[123][0-9]\$[./A-Za-z0-9]{53}$")
SECOND_SALT_PATTERN = re.compile(r"^\$2a\$[123][0-9]\$[./A-Za-z0-9]{22}$")
_HEX = re.compile(r"^[0-9a-fA-F]+$")


class ActionError(ValueError):
    """Raised when an action cannot be built because its input is invalid."""


def new_id() -> str:
    """A random id that is valid inside a family (6 alphanumeric characters)."""
    return "".join(secrets.choice(_ID_ALPHABET) for _ in range(6))


def is_valid_id(value: object) -> bool:
    return isinstance(value, str) and ID_PATTERN.match(value) is not None


def encode_action(action: Action) -> str:
    """The string for ``encodedAction``: compact separators, no re-ordering."""
    return json.dumps(action, separators=(",", ":"), ensure_ascii=False)


# --- validation helpers -----------------------------------------------------------------------


def _id(name: str, value: object) -> str:
    if not isinstance(value, str) or ID_PATTERN.match(value) is None:
        raise ActionError(
            f"{name} must be exactly 6 characters [0-9a-zA-Z], got {value!r}"
        )
    return value


def _optional_id(name: str, value: str) -> str:
    """An id that may also be empty (meaning 'none')."""
    return value if value == "" else _id(name, value)


def _int(name: str, value: object, minimum: int, maximum: int | None = None) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ActionError(f"{name} must be an integer, got {value!r}")
    if value < minimum or (maximum is not None and value > maximum):
        limit = (
            f">= {minimum}" if maximum is None else f"between {minimum} and {maximum}"
        )
        raise ActionError(f"{name} must be {limit}, got {value}")
    return value


def _bool(name: str, value: object) -> bool:
    if not isinstance(value, bool):
        raise ActionError(f"{name} must be true or false, got {value!r}")
    return value


def _text(name: str, value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ActionError(f"{name} must not be empty")
    return value


# --- time limit rules ---------------------------------------------------------------------------


def _rule_fields(
    time_ms: int,
    days: int,
    extra_time: bool,
    start: int | None,
    end: int | None,
    dur: int | None,
    pause: int | None,
    per_day: bool | None,
    expires_at: int | None,
) -> Action:
    fields: Action = {
        "time": _int("time", time_ms, 0),
        "days": _int("days", days, 0, ALL_DAYS_MASK),
        "extraTime": _bool("extraTime", extra_time),
    }
    if (start is None) != (end is None):
        raise ActionError("start and end must be given together")
    if start is not None and end is not None:
        _int("start", start, 0, MAX_MINUTE_OF_DAY)
        _int("end", end, 0, MAX_MINUTE_OF_DAY)
        if start > end:
            raise ActionError(f"start ({start}) must not be after end ({end})")
        fields["start"] = start
        fields["end"] = end
    if dur is not None:
        fields["dur"] = _int("dur", dur, 0)
    if pause is not None:
        fields["pause"] = _int("pause", pause, 0)
    if per_day is not None:
        fields["perDay"] = _bool("perDay", per_day)
    if expires_at is not None:
        fields["e"] = _int("e", expires_at, 1)
    return fields


def create_timelimit_rule(
    rule_id: str,
    category_id: str,
    time_ms: int,
    days: int = ALL_DAYS_MASK,
    extra_time: bool = False,
    start: int | None = None,
    end: int | None = None,
    dur: int | None = None,
    pause: int | None = None,
    per_day: bool | None = None,
    expires_at: int | None = None,
) -> Action:
    """``CREATE_TIMELIMIT_RULE``; the rule fields are nested in ``rule``.

    ``expires_at`` (field ``e``) exists on only one server variant; the fake server and the
    real server schema decide whether it is accepted.
    """
    rule: Action = {
        "ruleId": _id("ruleId", rule_id),
        "categoryId": _id("categoryId", category_id),
    }
    rule.update(
        _rule_fields(
            time_ms, days, extra_time, start, end, dur, pause, per_day, expires_at
        )
    )
    return {"type": "CREATE_TIMELIMIT_RULE", "rule": rule}


def update_timelimit_rule(
    rule_id: str,
    time_ms: int,
    days: int = ALL_DAYS_MASK,
    extra_time: bool = False,
    start: int | None = None,
    end: int | None = None,
    dur: int | None = None,
    pause: int | None = None,
    per_day: bool | None = None,
    expires_at: int | None = None,
) -> Action:
    """``UPDATE_TIMELIMIT_RULE``: flat fields and no categoryId."""
    action: Action = {"type": "UPDATE_TIMELIMIT_RULE", "ruleId": _id("ruleId", rule_id)}
    action.update(
        _rule_fields(
            time_ms, days, extra_time, start, end, dur, pause, per_day, expires_at
        )
    )
    return action


def delete_timelimit_rule(rule_id: str) -> Action:
    return {"type": "DELETE_TIMELIMIT_RULE", "ruleId": _id("ruleId", rule_id)}


# --- categories ---------------------------------------------------------------------------------


def create_category(child_id: str, category_id: str, title: str) -> Action:
    return {
        "type": "CREATE_CATEGORY",
        "childId": _id("childId", child_id),
        "categoryId": _id("categoryId", category_id),
        "title": _text("title", title),
    }


def delete_category(category_id: str) -> Action:
    return {"type": "DELETE_CATEGORY", "categoryId": _id("categoryId", category_id)}


def update_category_title(category_id: str, new_title: str) -> Action:
    return {
        "type": "UPDATE_CATEGORY_TITLE",
        "categoryId": _id("categoryId", category_id),
        "newTitle": _text("newTitle", new_title),
    }


def set_parent_category(category_id: str, parent_category: str) -> Action:
    """``parent_category`` may be empty to make the category top-level."""
    return {
        "type": "SET_PARENT_CATEGORY",
        "categoryId": _id("categoryId", category_id),
        "parentCategory": _optional_id("parentCategory", parent_category),
    }


def update_category_sorting(category_ids: Iterable[str]) -> Action:
    ids = [_id("categoryIds", item) for item in category_ids]
    if not ids:
        raise ActionError("categoryIds must not be empty")
    if len(set(ids)) != len(ids):
        raise ActionError("categoryIds must not contain duplicates")
    return {"type": "UPDATE_CATEGORY_SORTING", "categoryIds": ids}


def update_category_blocked_times(
    category_id: str, intervals: list[Interval]
) -> Action:
    """``intervals``: (start, end) minutes of the week; see :mod:`dashboard.domain.bitmask`."""
    try:
        times = format_blocked_times(intervals)
    except BitmaskError as error:
        raise ActionError(str(error)) from error
    return {
        "type": "UPDATE_CATEGORY_BLOCKED_TIMES",
        "categoryId": _id("categoryId", category_id),
        "times": times,
    }


# --- category settings (Q5, FR-402): flags, notifications and warnings, battery and networks ----


def update_category_flags(category_id: str, modified: int, values: int) -> Action:
    """``modified`` = bits that change, ``values`` = their new values (subset of ``modified``)."""
    _int("modified", modified, 0)
    _int("values", values, 0)
    if (
        modified | MAX_CATEGORY_FLAGS != MAX_CATEGORY_FLAGS
        or modified | values != modified
    ):
        raise ActionError("flags are out of the valid range")
    return {
        "type": "UPDATE_CATEGORY_FLAGS",
        "categoryId": _id("categoryId", category_id),
        "modified": modified,
        "values": values,
    }


def update_category_time_warnings(
    category_id: str, enable: bool, flags: int, minutes: int | None = None
) -> Action:
    if (_int("flags", flags, 0) & ALLOWED_TIME_WARNING_FLAGS) != flags:
        raise ActionError(
            f"flags must only use bits of {ALLOWED_TIME_WARNING_FLAGS}, got {flags}"
        )
    action: Action = {
        "type": "UPDATE_CATEGORY_TIME_WARNINGS",
        "categoryId": _id("categoryId", category_id),
        "enable": _bool("enable", enable),
        "flags": flags,
    }
    if minutes is not None:
        action["minutes"] = _int(
            "minutes", minutes, MIN_WARNING_MINUTES, MAX_WARNING_MINUTES
        )
    return action


def update_category_block_all_notifications(
    category_id: str, blocked: bool, block_delay_ms: int | None = None
) -> Action:
    """The server requires the ``blockDelay`` key; ``None`` is sent as an absent value (omitted)."""
    action: Action = {
        "type": "UPDATE_CATEGORY_BLOCK_ALL_NOTIFICATIONS",
        "categoryId": _id("categoryId", category_id),
        "blocked": _bool("blocked", blocked),
    }
    if block_delay_ms is not None:
        action["blockDelay"] = _int("blockDelay", block_delay_ms, 0)
    return action


def update_category_battery_limit(
    category_id: str, charge_limit: int | None = None, mobile_limit: int | None = None
) -> Action:
    """Battery levels in percent (0..100); 0 means no limit. An omitted limit stays as it is (server code)."""
    action: Action = {
        "type": "UPDATE_CATEGORY_BATTERY_LIMIT",
        "categoryId": _id("categoryId", category_id),
    }
    if charge_limit is not None:
        action["chargeLimit"] = _int("chargeLimit", charge_limit, 0, 100)
    if mobile_limit is not None:
        action["mobileLimit"] = _int("mobileLimit", mobile_limit, 0, 100)
    return action


def add_category_network_id(
    category_id: str, item_id: str, hashed_network_id: str
) -> Action:
    if (
        not isinstance(hashed_network_id, str)
        or len(hashed_network_id) != NETWORK_ID_HEX_LENGTH
        or _HEX.match(hashed_network_id) is None
    ):
        raise ActionError(
            f"hashedNetworkId must be {NETWORK_ID_HEX_LENGTH} hex characters"
        )
    return {
        "type": "ADD_CATEGORY_NETWORK_ID",
        "categoryId": _id("categoryId", category_id),
        "itemId": _id("itemId", item_id),
        "hashedNetworkId": hashed_network_id,
    }


def reset_category_network_ids(category_id: str) -> Action:
    return {
        "type": "RESET_CATEGORY_NETWORK_IDS",
        "categoryId": _id("categoryId", category_id),
    }


def set_category_for_unassigned_apps(child_id: str, category_id: str) -> Action:
    """``category_id`` may be empty: unassigned apps then fall back to the default handling."""
    return {
        "type": "SET_CATEGORY_FOR_UNASSIGNED_APPS",
        "childId": _id("childId", child_id),
        "categoryId": _optional_id("categoryId", category_id),
    }


def update_category_disable_limits(category_id: str, end_time_ms: int) -> Action:
    """Limits of this category are ignored until ``end_time_ms`` (epoch ms); 0 switches it off."""
    return {
        "type": "UPDATE_CATEGORY_DISABLE_LIMITS",
        "categoryId": _id("categoryId", category_id),
        "endTime": _int("endTime", end_time_ms, 0),
    }


def set_user_disable_limits_until(child_id: str, time_ms: int) -> Action:
    """Limits of the whole child are ignored until ``time_ms`` (epoch ms); 0 switches it off."""
    return {
        "type": "SET_USER_DISABLE_LIMITS_UNTIL",
        "childId": _id("childId", child_id),
        "time": _int("time", time_ms, 0),
    }


# --- extra time and temporary block ---------------------------------------------------------------


def increment_category_extra_time(
    category_id: str, added_ms: int, day: int | None = None
) -> Action:
    """Add extra time. ``day``: -1 = every day (default), 0.. = a specific day. Needs premium."""
    action: Action = {
        "type": "INCREMENT_CATEGORY_EXTRATIME",
        "categoryId": _id("categoryId", category_id),
        "addedExtraTime": _int("addedExtraTime", added_ms, 0),
    }
    if day is not None:
        action["day"] = _int("day", day, -1)
    return action


def set_category_extra_time(
    category_id: str, new_extra_ms: int, day: int | None = None
) -> Action:
    action: Action = {
        "type": "SET_CATEGORY_EXTRA_TIME",
        "categoryId": _id("categoryId", category_id),
        "newExtraTime": _int("newExtraTime", new_extra_ms, 0),
    }
    if day is not None:
        action["day"] = _int("day", day, -1)
    return action


def update_category_temporarily_blocked(
    category_id: str, blocked: bool, end_time_ms: int | None = None
) -> Action:
    """Block (optionally until ``end_time_ms``) or unblock. An end time with ``blocked=False`` is rejected."""
    action: Action = {
        "type": "UPDATE_CATEGORY_TEMPORARILY_BLOCKED",
        "categoryId": _id("categoryId", category_id),
        "blocked": _bool("blocked", blocked),
    }
    if end_time_ms is not None:
        if not blocked:
            raise ActionError("an end time cannot be set when unblocking")
        action["endTime"] = _int("endTime", end_time_ms, 0)
    return action


# --- apps per category ------------------------------------------------------------------------


def _package_names(package_names: Iterable[str]) -> list[str]:
    names = list(package_names)
    if not names:
        raise ActionError("packageNames must not be empty")
    if any(not isinstance(name, str) or not name for name in names):
        raise ActionError("packageNames must be non-empty strings")
    if len(set(names)) != len(names):
        raise ActionError("packageNames must not contain duplicates")
    return names


def add_category_apps(category_id: str, package_names: Iterable[str]) -> Action:
    """Assign apps to a category (moves them out of their old category)."""
    return {
        "type": "ADD_CATEGORY_APPS",
        "categoryId": _id("categoryId", category_id),
        "packageNames": _package_names(package_names),
    }


def remove_category_apps(category_id: str, package_names: Iterable[str]) -> Action:
    return {
        "type": "REMOVE_CATEGORY_APPS",
        "categoryId": _id("categoryId", category_id),
        "packageNames": _package_names(package_names),
    }


# --- users, devices and passwords --------------------------------------------------------------


def add_child_user(user_id: str, name: str, time_zone: str) -> Action:
    """``ADD_USER`` for a child (no password)."""
    return {
        "type": "ADD_USER",
        "name": _text("name", name),
        "userType": "child",
        "userId": _id("userId", user_id),
        "timeZone": _text("timeZone", time_zone),
    }


def add_parent_user(
    user_id: str,
    name: str,
    time_zone: str,
    password_hash: str,
    second_salt: str,
    second_hash_container: str,
) -> Action:
    """``ADD_USER`` for a parent with an encrypted password.

    ``second_hash_container`` is the output of :func:`dashboard.domain.integrity.encrypt_parent_password`.
    """
    if (
        not isinstance(password_hash, str)
        or len(password_hash) != 60
        or not password_hash.startswith("$2a$")
    ):
        raise ActionError("password hash must be a 60 character $2a$ bcrypt string")
    if SECOND_SALT_PATTERN.match(second_salt) is None:
        raise ActionError("second salt must be a 29 character $2a$ bcrypt salt")
    if not second_hash_container or second_hash_container.count(".") != 2:
        raise ActionError("second hash must be an encrypted container (three parts)")
    return {
        "type": "ADD_USER",
        "name": _text("name", name),
        "userType": "parent",
        "userId": _id("userId", user_id),
        "password": {
            "hash": password_hash,
            "secondHash": second_hash_container,
            "secondSalt": second_salt,
            "encrypted": True,
        },
        "timeZone": _text("timeZone", time_zone),
    }


def remove_user(user_id: str, authentication: str | None = None) -> Action:
    """``REMOVE_USER``; a parent user needs ``authentication`` (see ``remove_user_authentication``)."""
    action: Action = {"type": "REMOVE_USER", "userId": _id("userId", user_id)}
    if authentication is not None:
        action["authentication"] = _text("authentication", authentication)
    return action


def rename_child(child_id: str, new_name: str) -> Action:
    return {
        "type": "RENAME_CHILD",
        "childId": _id("childId", child_id),
        "newName": _text("newName", new_name),
    }


def set_user_timezone(user_id: str, time_zone: str) -> Action:
    return {
        "type": "SET_USER_TIMEZONE",
        "userId": _id("userId", user_id),
        "timezone": _text("timezone", time_zone),
    }


def set_device_user(device_id: str, user_id: str) -> Action:
    """``SET_DEVICE_USER``: sign a device in as another user. The server also clears keep-signed-in."""
    return {
        "type": "SET_DEVICE_USER",
        "deviceId": _id("deviceId", device_id),
        "userId": _id("userId", user_id),
    }


def set_keep_signed_in(device_id: str, keep_signed_in: bool) -> Action:
    return {
        "type": "SET_KEEP_SIGNED_IN",
        "deviceId": _id("deviceId", device_id),
        "keepSignedIn": _bool("keepSignedIn", keep_signed_in),
    }


def change_parent_password(
    user_id: str,
    new_hash: str,
    new_second_salt: str,
    second_hash_encrypted: str,
    integrity: str,
) -> Action:
    """``CHANGE_PARENT_PASSWORD``; build the two crypto values with ``dashboard.domain.integrity``."""
    if (
        not isinstance(new_hash, str)
        or len(new_hash) != 60
        or not new_hash.startswith("$2a$")
    ):
        raise ActionError("hash must be a 60 character $2a$ bcrypt string")
    if SECOND_SALT_PATTERN.match(new_second_salt) is None:
        raise ActionError("second salt must be a 29 character $2a$ bcrypt salt")
    if len(second_hash_encrypted) <= 70 or _HEX.match(second_hash_encrypted) is None:
        raise ActionError(
            "encrypted second hash must be hex and longer than 70 characters"
        )
    if len(integrity) != 128 or _HEX.match(integrity) is None:
        raise ActionError("integrity must be 128 hex characters")
    return {
        "type": "CHANGE_PARENT_PASSWORD",
        "userId": _id("userId", user_id),
        "hash": new_hash,
        "secondSalt": new_second_salt,
        "secondHashEncrypted": second_hash_encrypted,
        "integrity": integrity,
    }


# --- push items (the objects inside ``actions`` of POST /sync/push-actions) -------------------------


def parent_item(
    action: Action,
    sequence_number: int,
    parent_user_id: str,
    own_device_id: str | None = None,
    second_hash: str | None = None,
) -> PushItem:
    """Push item for a parent action.

    Without ``second_hash`` the device method is used (``integrity: "device"``). With it the password
    method is used and ``own_device_id`` (the pushing device, NOT a user id) is required.
    """
    _int("sequenceNumber", sequence_number, 0)
    _id("userId", parent_user_id)
    encoded = encode_action(action)
    if second_hash:
        integrity = password_integrity(
            sequence_number=sequence_number,
            device_id=_id("own_device_id", own_device_id),
            encoded_action=encoded,
            second_hash=second_hash,
        )
    else:
        integrity = "device"
    return {
        "encodedAction": encoded,
        "sequenceNumber": sequence_number,
        "integrity": integrity,
        "type": "parent",
        "userId": parent_user_id,
    }


def app_logic_item(action: Action, sequence_number: int) -> PushItem:
    """Push item for an appLogic action (no integrity)."""
    _int("sequenceNumber", sequence_number, 0)
    return {
        "encodedAction": encode_action(action),
        "sequenceNumber": sequence_number,
        "integrity": "",
        "type": "appLogic",
        "userId": "",
    }
