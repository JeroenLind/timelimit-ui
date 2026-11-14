"""Parent/app-logic actions as the real server applies them (``apply-actions``), plan A5.

Only the actions the dashboard sends are simulated. A schema-valid action that is not simulated is
recorded in ``World.unsimulated`` and fails silently, so a test notices when the dashboard starts using
one that the fake does not know yet.
"""

from __future__ import annotations

import copy
import itertools
import json
import re
from dataclasses import dataclass
from typing import Any

from . import schemas
from .integrity import check_parent_integrity, remove_user_authentication
from .state import (
    Category,
    Family,
    Rule,
    User,
    World,
    version_id,
)

DAY_MINUTES = 24 * 60
BLOCKED_TIMES_LENGTH = DAY_MINUTES * 7
_ID = re.compile(r"[a-zA-Z0-9]{6}")
_BITMASK = re.compile(r"(\d+(,\d+)*)?")
_MAX_DAY = 1 | 2 | 4 | 8 | 16 | 32 | 64


class ActionFailed(Exception):
    """Any reason the real server fails an action silently (rolled back, full sync requested)."""


@dataclass
class Outcome:
    full_sync: bool = False
    triggered_level: int = 0


def _type_to_definition() -> dict[str, str]:
    mapping: dict[str, str] = {}
    for name, schema in schemas.definitions().items():
        enum = (schema.get("properties", {}).get("type") or {}).get("enum")
        if enum and len(enum) == 1:
            mapping[enum[0]] = name
    return mapping


_DEFS = _type_to_definition()


def _id(value: Any) -> str:
    if not isinstance(value, str) or not _ID.fullmatch(value):
        raise ActionFailed("invalid id within family")
    return value


def _int(value: Any) -> int:
    if (
        isinstance(value, bool)
        or not isinstance(value, int | float)
        or value != int(value)
    ):
        raise ActionFailed("not a safe integer")
    return int(value)


def _bitmask(value: str) -> None:
    if not _BITMASK.fullmatch(value):
        raise ActionFailed("bitmask does not match regex")
    if value == "":
        return
    points = [int(p) for p in value.split(",")]
    if len(points) % 2 or any(p > BLOCKED_TIMES_LENGTH for p in points):
        raise ActionFailed("bitmask invalid")
    if any(b <= a for a, b in itertools.pairwise(points)):
        raise ActionFailed("bitmask not strictly sorted")


def _category(family: Family, category_id: str) -> Category:
    cat = family.categories.get(category_id)
    if cat is None:
        raise ActionFailed("missing category")
    return cat


def _bump_base(cat: Category) -> None:
    cat.base_version = version_id()


def _rule_from(
    rule_id: str, a: dict[str, Any], *, time_key: str = "time", days_key: str = "days"
) -> Rule:
    max_time = _int(a[time_key])
    day_mask = _int(a[days_key])
    start = _int(a.get("start", 0))
    end = _int(a.get("end", DAY_MINUTES - 1))
    dur = _int(a.get("dur", 0))
    pause = _int(a.get("pause", 0))
    expires = _int(a["e"]) if "e" in a else None
    if max_time < 0 or not 0 <= day_mask <= _MAX_DAY:
        raise ActionFailed("invalid rule")
    if start < 0 or end > DAY_MINUTES - 1 or start > end or dur < 0 or pause < 0:
        raise ActionFailed("invalid rule range")
    if expires is not None and expires <= 0:
        raise ActionFailed("invalid expiry")
    return Rule(
        rule_id=rule_id,
        extra_time=bool(a["extraTime"]),
        day_mask=day_mask,
        max_time=max_time,
        start=start,
        end=end,
        session=dur,
        pause=pause,
        per_day=bool(a.get("perDay", False)),
        expires=expires,
    )


def _find_rule(family: Family, rule_id: str) -> tuple[Category, Rule]:
    for cat in family.categories.values():
        if rule_id in cat.rules:
            return cat, cat.rules[rule_id]
    raise ActionFailed("missing rule")


def _apply(
    world: World,
    family: Family,
    parent: User | None,
    a: dict[str, Any],
    out: Outcome,
    integrity_kind: str = "",
) -> None:
    kind = a["type"]
    if kind == "ADD_USER":
        user_id = _id(a["userId"])
        if user_id in family.users:
            raise ActionFailed("user exists")
        pw = a.get("password") or {}
        second_hash = pw.get("secondHash", "")
        if pw.get("encrypted"):
            second_hash = world.decrypt_second_hash(
                second_hash, pw.get("hash", ""), pw.get("secondSalt", "")
            )
        family.users[user_id] = User(
            user_id=user_id,
            name=a["name"],
            type=a["userType"],
            password_hash=pw.get("hash", ""),
            second_hash=second_hash,
            second_salt=pw.get("secondSalt", ""),
            time_zone=a["timeZone"],
        )
        family.user_list_version = version_id()
        out.triggered_level = max(out.triggered_level, 1)
    elif kind == "SET_DEVICE_USER":
        device = family.devices.get(a["deviceId"])
        if device is None:
            raise ActionFailed("missing device")
        if a["userId"] and a["userId"] not in family.users:
            raise ActionFailed("missing user")
        device.current_user_id = a["userId"]
        device.keep_signed_in = False
        family.device_list_version = version_id()
        out.triggered_level = max(out.triggered_level, 1)
    elif kind == "SET_KEEP_SIGNED_IN":
        device = family.devices.get(a["deviceId"])
        if device is None:
            raise ActionFailed("missing device")
        if integrity_kind != "password":
            raise ActionFailed("keep-signed-in needs the password")
        if device.current_user_id != (parent.user_id if parent else ""):
            raise ActionFailed("device is not signed in as this parent")
        device.keep_signed_in = bool(a["keepSignedIn"])
        family.device_list_version = version_id()
        out.triggered_level = max(out.triggered_level, 1)
    elif kind == "REMOVE_USER":
        user = family.users.get(_id(a["userId"]))
        if user is None:
            raise ActionFailed("missing user")
        if user.type == "parent":
            if parent is None or parent.user_id == user.user_id:
                raise ActionFailed("users can not delete themself")
            if a.get("authentication") != remove_user_authentication(
                user.user_id, user.second_hash
            ):
                raise ActionFailed("invalid authentication value for removing a user")
            parents = [u for u in family.users.values() if u.type == "parent"]
            if user.mail and sum(1 for u in parents if u.mail) <= 1:
                raise ActionFailed("last user with a linked mail address")
        else:
            for cid in [
                c.category_id
                for c in family.categories.values()
                if c.child_id == user.user_id
            ]:
                del family.categories[cid]
        for device in family.devices.values():
            if device.current_user_id == user.user_id:
                device.current_user_id = ""
                device.keep_signed_in = False
                family.device_list_version = version_id()
        del family.users[user.user_id]
        family.user_list_version = version_id()
        out.triggered_level = max(out.triggered_level, 2)
    elif kind == "RENAME_CHILD":
        user = family.users.get(_id(a["childId"]))
        if user is None or user.type != "child":
            raise ActionFailed("missing user")
        user.name = a["newName"]
        family.user_list_version = version_id()
        out.triggered_level = max(out.triggered_level, 1)
    elif kind == "CREATE_CATEGORY":
        category_id, child_id = _id(a["categoryId"]), _id(a["childId"])
        child = family.users.get(child_id)
        if child is None or child.type != "child":
            raise ActionFailed("missing user")
        if category_id in family.categories:
            raise ActionFailed("category exists")
        sorts = [c.sort for c in family.categories.values() if c.child_id == child_id]
        family.categories[category_id] = Category(
            category_id=category_id,
            child_id=child_id,
            title=a["title"],
            sort=max(sorts) + 1 if sorts else 0,
        )
        out.triggered_level = max(out.triggered_level, 1)
    elif kind == "DELETE_CATEGORY":
        cat = _category(family, _id(a["categoryId"]))
        for user in family.users.values():
            if user.category_for_unassigned == cat.category_id:
                user.category_for_unassigned = ""
                family.user_list_version = version_id()
        del family.categories[cat.category_id]
        out.triggered_level = max(out.triggered_level, 2)
    elif kind == "UPDATE_CATEGORY_TITLE":
        cat = _category(family, _id(a["categoryId"]))
        cat.title = a["newTitle"]
        _bump_base(cat)
        out.triggered_level = max(out.triggered_level, 2)
    elif kind in ("ADD_CATEGORY_APPS", "REMOVE_CATEGORY_APPS"):
        cat = _category(family, _id(a["categoryId"]))
        names = a["packageNames"]
        if not names or len(set(names)) != len(names):
            raise ActionFailed("empty list or duplicates")
        if kind == "ADD_CATEGORY_APPS":
            for other in family.categories.values():
                if other.child_id == cat.child_id:
                    other.apps = [p for p in other.apps if p not in names]
                    other.apps_version = version_id()
            cat.apps.extend(names)
        else:
            if any(p not in cat.apps for p in names):
                raise ActionFailed("could not remove all requested category app items")
            cat.apps = [p for p in cat.apps if p not in names]
        cat.apps_version = version_id()
        out.triggered_level = max(out.triggered_level, 2)
    elif kind == "CREATE_TIMELIMIT_RULE":
        raw = a["rule"]
        cat = _category(family, _id(raw["categoryId"]))
        rule_id = _id(raw["ruleId"])
        if any(rule_id in c.rules for c in family.categories.values()):
            raise ActionFailed("rule exists")
        cat.rules[rule_id] = _rule_from(rule_id, raw)
        cat.rules_version = version_id()
        out.triggered_level = max(out.triggered_level, 2)
    elif kind == "UPDATE_TIMELIMIT_RULE":
        cat, old = _find_rule(family, _id(a["ruleId"]))
        cat.rules[old.rule_id] = _rule_from(old.rule_id, a)
        cat.rules_version = version_id()
        out.triggered_level = max(out.triggered_level, 2)
    elif kind == "DELETE_TIMELIMIT_RULE":
        cat, old = _find_rule(family, _id(a["ruleId"]))
        del cat.rules[old.rule_id]
        cat.rules_version = version_id()
        out.triggered_level = max(out.triggered_level, 2)
    elif kind == "UPDATE_CATEGORY_BLOCKED_TIMES":
        cat = _category(family, _id(a["categoryId"]))
        _bitmask(a["times"])
        cat.blocked_times = a["times"]
        _bump_base(cat)
        out.triggered_level = max(out.triggered_level, 2)
    elif kind in ("INCREMENT_CATEGORY_EXTRATIME", "SET_CATEGORY_EXTRA_TIME"):
        if not family.has_full_version:
            raise ActionFailed("premium version missing")
        cat = _category(family, _id(a["categoryId"]))
        day = _int(a.get("day", -1))
        if kind == "SET_CATEGORY_EXTRA_TIME":
            cat.extra_time, cat.extra_time_day = _int(a["newExtraTime"]), day
            _bump_base(cat)
        else:
            added = _int(a["addedExtraTime"])
            if added < 0:
                raise ActionFailed("negative extra time")
            targets = [cat]
            if cat.parent_id and cat.parent_id in family.categories:
                targets.append(family.categories[cat.parent_id])
            for target in targets:
                if day == target.extra_time_day or target.extra_time_day == -1:
                    target.extra_time += added
                else:
                    target.extra_time = added
                target.extra_time_day = day
                _bump_base(target)
        out.triggered_level = max(out.triggered_level, 2)
    elif kind == "SET_PARENT_CATEGORY":
        cat = _category(family, _id(a["categoryId"]))
        wanted_parent = a["parentCategory"]
        if wanted_parent != "":
            parent_cat = family.categories.get(wanted_parent)
            if parent_cat is None or parent_cat.child_id != cat.child_id:
                raise ActionFailed("missing category")
            below: set[str] = set()
            pending = [cat.category_id]
            while pending:
                current = pending.pop()
                for member in family.categories.values():
                    if member.parent_id == current and member.category_id not in below:
                        below.add(member.category_id)
                        pending.append(member.category_id)
            if wanted_parent in below or wanted_parent == cat.category_id:
                raise ActionFailed("a category can not be the parent of its own parent")
        cat.parent_id = wanted_parent
        _bump_base(cat)
        out.triggered_level = max(out.triggered_level, 2)
    elif kind == "UPDATE_CATEGORY_SORTING":
        for position, category_id in enumerate(a["categoryIds"]):
            ordered = family.categories.get(category_id)
            if ordered is not None:
                ordered.sort = position
                _bump_base(ordered)
        out.triggered_level = max(out.triggered_level, 1)
    elif kind == "SET_CATEGORY_FOR_UNASSIGNED_APPS":
        owner = family.users.get(_id(a["childId"]))
        if owner is None or owner.type != "child":
            raise ActionFailed("missing user")
        if a["categoryId"] != "":
            chosen = family.categories.get(a["categoryId"])
            if chosen is None or chosen.child_id != owner.user_id:
                raise ActionFailed("category of another child or missing")
        owner.category_for_unassigned = a["categoryId"]
        family.user_list_version = version_id()
        out.triggered_level = max(out.triggered_level, 2)
    elif kind == "UPDATE_CATEGORY_DISABLE_LIMITS":
        if a["endTime"] != 0 and not family.has_full_version:
            raise ActionFailed("premium version missing")
        cat = _category(family, _id(a["categoryId"]))
        cat.disable_limits_until = _int(a["endTime"])
        _bump_base(cat)
        out.triggered_level = max(out.triggered_level, 2)
    elif kind == "UPDATE_CATEGORY_FLAGS":
        flag_cat = _category(family, _id(a["categoryId"]))
        flag_cat.flags = (flag_cat.flags & ~a["modified"]) | a["values"]
        _bump_base(flag_cat)
        out.triggered_level = max(out.triggered_level, 2)
    elif kind == "UPDATE_CATEGORY_TIME_WARNINGS":
        warn_cat = _category(family, _id(a["categoryId"]))
        if a["enable"]:
            warn_cat.time_warnings |= a["flags"]
        else:
            warn_cat.time_warnings &= ~a["flags"]
        _bump_base(warn_cat)
        out.triggered_level = max(out.triggered_level, 2)
    elif kind == "UPDATE_CATEGORY_BLOCK_ALL_NOTIFICATIONS":
        note_cat = _category(family, _id(a["categoryId"]))
        note_cat.block_all_notifications = bool(a["blocked"])
        if "blockDelay" in a:
            note_cat.block_notification_delay = _int(a["blockDelay"])
        _bump_base(note_cat)
        out.triggered_level = max(out.triggered_level, 2)
    elif kind == "UPDATE_CATEGORY_BATTERY_LIMIT":
        battery_cat = _category(family, _id(a["categoryId"]))
        if "chargeLimit" in a:
            battery_cat.min_battery_charging = _int(a["chargeLimit"])
        if "mobileLimit" in a:  # an omitted limit stays as it is (server code)
            battery_cat.min_battery_mobile = _int(a["mobileLimit"])
        _bump_base(battery_cat)
        out.triggered_level = max(out.triggered_level, 2)
    elif kind == "RESET_CATEGORY_NETWORK_IDS":
        network_cat = _category(family, _id(a["categoryId"]))
        network_cat.networks = []
        _bump_base(network_cat)
        out.triggered_level = max(out.triggered_level, 2)
    elif kind == "UPDATE_CATEGORY_TEMPORARILY_BLOCKED":
        if a["blocked"] and not family.has_full_version:
            raise ActionFailed("premium version missing")
        cat = _category(family, _id(a["categoryId"]))
        cat.temp_blocked = bool(a["blocked"])
        cat.temp_block_end = _int(a.get("endTime", 0)) if a["blocked"] else 0
        _bump_base(cat)
        out.triggered_level = max(out.triggered_level, 2)
    else:
        world.unsimulated.append(kind)
        raise ActionFailed("action not simulated by the fake")


def _apply_used_time(family: Family, a: dict[str, Any], out: Outcome) -> None:
    day = _int(a["d"])
    for item in a["i"]:
        cat = family.categories.get(item["categoryId"])
        if cat is None:
            out.full_sync = True
            continue
        slot = cat.used_times.setdefault(day, {})
        key = (0, DAY_MINUTES - 1)
        slot[key] = max(
            0, min(slot.get(key, 0) + _int(item["tta"]), DAY_MINUTES * 60_000)
        )
        cat.used_times_version = version_id()
        subtract = _int(item["etts"])
        if subtract:
            cat.extra_time = max(0, cat.extra_time - subtract)
            _bump_base(cat)
        out.triggered_level = max(out.triggered_level, 2)


def apply_action(
    world: World,
    family: Family,
    device_id: str,
    request: dict[str, Any],
) -> Outcome:
    """Apply one ``ClientPushChangesRequestAction``; mirrors the sequence/rollback rules of the server."""
    out = Outcome()
    device = family.devices[device_id]
    seq = request["sequenceNumber"]
    if seq < device.next_sequence_number:
        return out  # already received: ignored, nothing changes
    device.next_sequence_number = seq + 1  # consumed even when the action fails
    snapshot = copy.deepcopy(
        (family.users, family.categories, family.user_list_version)
    )
    list_versions = (family.device_list_version,)
    try:
        try:
            action = json.loads(request["encodedAction"])
        except ValueError as exc:
            raise ActionFailed("bad json") from exc
        if not isinstance(action, dict) or action.get("type") not in _DEFS:
            raise ActionFailed("unknown action type")
        if not schemas_valid(action):
            raise ActionFailed("invalid action parameters")
        if request["type"] == "appLogic":
            if action["type"] != "ADD_USED_TIME_V2":
                world.unsimulated.append(action["type"])
                raise ActionFailed("not simulated")
            _apply_used_time(family, action, out)
            return out
        if request["type"] != "parent":
            world.unsimulated.append(f"{request['type']}:{action['type']}")
            raise ActionFailed("not simulated")
        user = family.users.get(request["userId"])
        if user is None or user.type != "parent":
            raise ActionFailed("missing parent")
        if not check_parent_integrity(
            integrity=request["integrity"],
            sequence_number=seq,
            device_id=device_id,
            encoded_action=request["encodedAction"],
            second_hash=user.second_hash,
            device_ok=device.keep_signed_in and device.current_user_id == user.user_id,
        ):
            raise ActionFailed("integrity")
        kind = (
            "password"
            if request["integrity"].startswith("password:")
            else request["integrity"]
        )
        _apply(world, family, user, action, out, kind)
    except ActionFailed as exc:
        family.users, family.categories, family.user_list_version = snapshot
        family.device_list_version = list_versions[0]
        world.rejected_actions.append(str(exc))
        return Outcome(full_sync=True)
    return out


def schemas_valid(action: dict[str, Any]) -> bool:
    name = _DEFS[action["type"]]
    schema = {"$ref": f"#/definitions/{name}", "definitions": schemas.definitions()}
    from jsonschema import Draft7Validator

    return bool(Draft7Validator(schema).is_valid(action))
