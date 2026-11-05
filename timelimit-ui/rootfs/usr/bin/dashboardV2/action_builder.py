"""Wire-correct TimeLimit sync actions.

Everything here follows docs/ServerAPI.md (sections 4, 5 and 7) and the generated
docs/protocol/actions-reference.md. In short:

* The wire ``type`` of an action is SCREAMING_SNAKE (``CREATE_TIMELIMIT_RULE``), never a
  class name.
* Parent actions are pushed with outer type ``parent``, ``userId`` = the parent's id and
  ``integrity`` = ``"device"`` (the dashboard device is signed in as that parent) or
  ``"password:<base64 hmac>"``.
* ``encodedAction`` is a *string* holding the JSON; the integrity covers exactly that string.
* Ids inside a family are exactly 6 characters ``[0-9a-zA-Z]``.

The builders validate their input the way the server does, so a mistake fails here with a
clear message instead of being silently dropped by the server.
"""

import json
import re
import secrets
import string
from typing import Any, Dict, Iterable, List, Optional

ID_PATTERN = re.compile(r"^[0-9a-zA-Z]{6}$")
_ID_ALPHABET = string.ascii_letters + string.digits

MAX_MINUTE_OF_DAY = 1439
ALL_DAYS_MASK = 127

# Server limit is 50 actions per request, the Android app uses 25.
MAX_ACTIONS_PER_REQUEST = 25


class ActionError(ValueError):
    """Raised when an action cannot be built because its input is invalid."""


def new_id() -> str:
    """Return a random id that is valid inside a family (6 alphanumeric characters)."""
    return "".join(secrets.choice(_ID_ALPHABET) for _ in range(6))


def is_valid_id(value: Any) -> bool:
    return isinstance(value, str) and ID_PATTERN.match(value) is not None


def _require_id(name: str, value: Any) -> str:
    if not is_valid_id(value):
        raise ActionError(f"{name} must be exactly 6 characters [0-9a-zA-Z], got {value!r}")
    return value


def _require_int(name: str, value: Any, minimum: int, maximum: Optional[int] = None) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ActionError(f"{name} must be an integer, got {value!r}")
    if value < minimum or (maximum is not None and value > maximum):
        limit = f">= {minimum}" if maximum is None else f"between {minimum} and {maximum}"
        raise ActionError(f"{name} must be {limit}, got {value}")
    return value


def encode_action(action: Dict[str, Any]) -> str:
    """Serialize an action to the string that goes into ``encodedAction``.

    Compact separators, no re-ordering. The integrity is computed over this exact string,
    so it must be sent unchanged.
    """
    return json.dumps(action, separators=(",", ":"), ensure_ascii=False)


# ---------------------------------------------------------------------------
# Time limit rules
# ---------------------------------------------------------------------------

def _rule_fields(
    time_ms: int,
    days: int,
    extra_time: bool,
    start: Optional[int],
    end: Optional[int],
    dur: Optional[int],
    pause: Optional[int],
    per_day: Optional[bool],
    expires_at: Optional[int],
) -> Dict[str, Any]:
    fields: Dict[str, Any] = {
        "time": _require_int("time", time_ms, 0),
        "days": _require_int("days", days, 0, ALL_DAYS_MASK),
        "extraTime": bool(extra_time),
    }
    if (start is None) != (end is None):
        raise ActionError("start and end must be given together")
    if start is not None:
        _require_int("start", start, 0, MAX_MINUTE_OF_DAY)
        _require_int("end", end, 0, MAX_MINUTE_OF_DAY)
        if start > end:
            raise ActionError(f"start ({start}) must not be after end ({end})")
        fields["start"] = start
        fields["end"] = end
    if dur is not None:
        fields["dur"] = _require_int("dur", dur, 0)
    if pause is not None:
        fields["pause"] = _require_int("pause", pause, 0)
    if per_day is not None:
        fields["perDay"] = bool(per_day)
    if expires_at is not None:
        fields["e"] = _require_int("e", expires_at, 1)
    return fields


def create_timelimit_rule(
    rule_id: str,
    category_id: str,
    time_ms: int,
    days: int = ALL_DAYS_MASK,
    extra_time: bool = False,
    start: Optional[int] = None,
    end: Optional[int] = None,
    dur: Optional[int] = None,
    pause: Optional[int] = None,
    per_day: Optional[bool] = None,
    expires_at: Optional[int] = None,
) -> Dict[str, Any]:
    """``CREATE_TIMELIMIT_RULE``. The rule fields are nested in ``rule``.

    time_ms: allowed time in milliseconds. days: bit mask (127 = every day).
    start/end: minutes of the day (0..1439), start <= end.
    dur/pause: maximum session length and pause between sessions, in milliseconds.
    """
    rule = {
        "ruleId": _require_id("ruleId", rule_id),
        "categoryId": _require_id("categoryId", category_id),
    }
    rule.update(_rule_fields(time_ms, days, extra_time, start, end, dur, pause, per_day, expires_at))
    return {"type": "CREATE_TIMELIMIT_RULE", "rule": rule}


def update_timelimit_rule(
    rule_id: str,
    time_ms: int,
    days: int = ALL_DAYS_MASK,
    extra_time: bool = False,
    start: Optional[int] = None,
    end: Optional[int] = None,
    dur: Optional[int] = None,
    pause: Optional[int] = None,
    per_day: Optional[bool] = None,
    expires_at: Optional[int] = None,
) -> Dict[str, Any]:
    """``UPDATE_TIMELIMIT_RULE``. Unlike create, the fields are flat and there is no categoryId."""
    action: Dict[str, Any] = {"type": "UPDATE_TIMELIMIT_RULE", "ruleId": _require_id("ruleId", rule_id)}
    action.update(_rule_fields(time_ms, days, extra_time, start, end, dur, pause, per_day, expires_at))
    return action


def delete_timelimit_rule(rule_id: str) -> Dict[str, Any]:
    """``DELETE_TIMELIMIT_RULE``."""
    return {"type": "DELETE_TIMELIMIT_RULE", "ruleId": _require_id("ruleId", rule_id)}


# ---------------------------------------------------------------------------
# Apps per category
# ---------------------------------------------------------------------------

def _package_names(package_names: Iterable[str]) -> List[str]:
    names = list(package_names)
    if not names:
        raise ActionError("packageNames must not be empty")
    if any(not isinstance(n, str) or not n for n in names):
        raise ActionError("packageNames must be non-empty strings")
    if len(set(names)) != len(names):
        raise ActionError("packageNames must not contain duplicates")
    return names


def add_category_apps(category_id: str, package_names: Iterable[str]) -> Dict[str, Any]:
    """``ADD_CATEGORY_APPS``: assign apps to a category (moves them out of their old category)."""
    return {
        "type": "ADD_CATEGORY_APPS",
        "categoryId": _require_id("categoryId", category_id),
        "packageNames": _package_names(package_names),
    }


def remove_category_apps(category_id: str, package_names: Iterable[str]) -> Dict[str, Any]:
    """``REMOVE_CATEGORY_APPS``."""
    return {
        "type": "REMOVE_CATEGORY_APPS",
        "categoryId": _require_id("categoryId", category_id),
        "packageNames": _package_names(package_names),
    }


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------

def add_child_user(user_id: str, name: str, time_zone: str) -> Dict[str, Any]:
    """``ADD_USER`` for a child (no password).

    A parent user needs an encrypted password container and is not supported here.
    """
    if not isinstance(name, str) or not name.strip():
        raise ActionError("name must not be empty")
    if not isinstance(time_zone, str) or not time_zone:
        raise ActionError("timeZone must not be empty")
    return {
        "type": "ADD_USER",
        "name": name,
        "userType": "child",
        "userId": _require_id("userId", user_id),
        "timeZone": time_zone,
    }


# ---------------------------------------------------------------------------
# Push items (the objects inside ``actions`` of POST /sync/push-actions)
# ---------------------------------------------------------------------------

def parent_item(
    action: Dict[str, Any],
    sequence_number: int,
    parent_user_id: str,
    own_device_id: Optional[str] = None,
    second_hash: Optional[str] = None,
) -> Dict[str, Any]:
    """Build the push item for a parent action.

    Without ``second_hash`` the device method is used (``integrity: "device"``). With a
    ``second_hash`` the password method is used and ``own_device_id`` (the id of the device
    that pushes, NOT a user id) is required for the HMAC.
    """
    _require_int("sequenceNumber", sequence_number, 0)
    _require_id("userId", parent_user_id)
    encoded = encode_action(action)
    if second_hash:
        if not is_valid_id(own_device_id):
            raise ActionError("own_device_id is required for password integrity")
        import os
        import sys

        # crypto_utils lives in the parent directory (rootfs/usr/bin)
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from crypto_utils import calculate_hmac_sha256_binary

        integrity = calculate_hmac_sha256_binary(second_hash, sequence_number, own_device_id, encoded)
    else:
        integrity = "device"
    return {
        "encodedAction": encoded,
        "sequenceNumber": sequence_number,
        "integrity": integrity,
        "type": "parent",
        "userId": parent_user_id,
    }


def app_logic_item(action: Dict[str, Any], sequence_number: int) -> Dict[str, Any]:
    """Build the push item for an appLogic action (sent by a device about itself; no integrity)."""
    _require_int("sequenceNumber", sequence_number, 0)
    return {
        "encodedAction": encode_action(action),
        "sequenceNumber": sequence_number,
        "integrity": "",
        "type": "appLogic",
        "userId": "",
    }
