"""In-memory family state of the fake TimeLimit server and the sync answer built from it (plan A5).

Mirrors ``get-server-data-status`` of the real server: every part of a family has a version id and is
only sent when the client's version differs.
"""

from __future__ import annotations

import secrets
import threading
import time
from dataclasses import dataclass, field
from typing import Any

API_LEVEL_DEFAULT = 9


def version_id() -> str:
    return secrets.token_hex(8)


def auth_token() -> str:
    return secrets.token_hex(16)


def short_id() -> str:
    return secrets.token_hex(3)


class HttpError(Exception):
    """An error the real server answers with an HTML error page of this status."""

    def __init__(self, status: int) -> None:
        super().__init__(status)
        self.status = status


@dataclass
class User:
    user_id: str
    name: str
    type: str
    password_hash: str
    second_hash: str
    second_salt: str
    mail: str = ""
    time_zone: str = "Europe/Amsterdam"
    disable_limits_until: int = 0
    current_device: str = ""
    category_for_unassigned: str = ""
    relax_primary_device: bool = False
    mail_notification_flags: int = 0
    flags: int = 0


@dataclass
class Device:
    device_id: str
    name: str
    model: str
    auth_token: str
    current_user_id: str = ""
    keep_signed_in: bool = False
    next_sequence_number: int = 0
    added_at: int = field(default_factory=lambda: int(time.time() * 1000))
    last_connectivity: int = 0


@dataclass
class Rule:
    rule_id: str
    extra_time: bool
    day_mask: int
    max_time: int
    start: int
    end: int
    session: int
    pause: int
    per_day: bool
    expires: int | None = None


@dataclass
class Category:
    category_id: str
    child_id: str
    title: str
    blocked_times: str = ""
    extra_time: int = 0
    extra_time_day: int = -1
    temp_blocked: bool = False
    temp_block_end: int = 0
    parent_id: str = ""
    block_all_notifications: bool = False
    time_warnings: int = 0
    min_battery_charging: int = 0
    min_battery_mobile: int = 0
    sort: int = 0
    disable_limits_until: int = 0
    flags: int = 0
    block_notification_delay: int = 0
    apps: list[str] = field(default_factory=list)
    rules: dict[str, Rule] = field(default_factory=dict)
    # day-of-epoch -> {(start, end): used time in ms}
    used_times: dict[int, dict[tuple[int, int], int]] = field(default_factory=dict)
    base_version: str = field(default_factory=version_id)
    apps_version: str = field(default_factory=version_id)
    rules_version: str = field(default_factory=version_id)
    used_times_version: str = field(default_factory=version_id)
    tasks_version: str = field(default_factory=version_id)


@dataclass
class Family:
    family_id: str
    users: dict[str, User] = field(default_factory=dict)
    devices: dict[str, Device] = field(default_factory=dict)
    categories: dict[str, Category] = field(default_factory=dict)
    user_list_version: str = field(default_factory=version_id)
    device_list_version: str = field(default_factory=version_id)
    full_version_until: int = 0
    has_full_version: bool = True
    add_device_token: tuple[str, str] | None = None  # (token, device id)


@dataclass
class MailLogin:
    mail: str
    code: str
    remaining_attempts: int = 3


def _norm_words(text: str) -> str:
    return text.replace(" ", "").replace("*", "").lower()


class World:
    """All state of the fake server. One lock guards everything (the real server uses transactions)."""

    def __init__(
        self, *, api_level: int = API_LEVEL_DEFAULT, premium: bool = True
    ) -> None:
        self.lock = threading.RLock()
        self.api_level = api_level
        self.premium = premium
        self.families: dict[str, Family] = {}
        self.mail_logins: dict[str, MailLogin] = {}
        self.mail_auth: dict[str, str] = {}  # mailAuthToken -> mail
        self.old_device_tokens: set[str] = set()
        self.inbox: list[tuple[str, str]] = []  # (mail, code) of "sent" mails
        self.unsimulated: list[
            str
        ] = []  # schema-valid actions the fake does not implement
        self.rejected_actions: list[
            str
        ] = []  # actions that failed silently (for tests)

    # -- lookups -----------------------------------------------------------------------------
    def family_of_token(self, token: str) -> tuple[Family, Device]:
        for family in self.families.values():
            for device in family.devices.values():
                if device.auth_token == token:
                    return family, device
        raise HttpError(401)

    def family_of_mail(self, mail: str) -> Family | None:
        for family in self.families.values():
            if any(u.mail == mail for u in family.users.values()):
                return family
        return None

    # -- mail login ----------------------------------------------------------------------------
    def send_login_code(self, mail: str) -> str:
        token = auth_token()
        words = " ".join(secrets.choice(_WORDS) for _ in range(3))
        self.mail_logins[token] = MailLogin(mail=mail, code=words)
        self.inbox.append((mail, words))
        return token

    def sign_in_by_code(self, login_token: str, received: str) -> str:
        entry = self.mail_logins.get(login_token)
        if entry is None or entry.remaining_attempts == 0:
            raise HttpError(410)
        if _norm_words(entry.code) != _norm_words(received):
            entry.remaining_attempts -= 1
            raise HttpError(410 if entry.remaining_attempts == 0 else 403)
        del self.mail_logins[login_token]
        token = auth_token()
        self.mail_auth[token] = entry.mail
        return token

    def mail_of_auth(self, token: str, *, invalidate: bool) -> str:
        mail = self.mail_auth.get(token)
        if mail is None:
            raise HttpError(401)
        if invalidate:
            del self.mail_auth[token]
        return mail

    # -- family and devices ----------------------------------------------------------------------
    def create_family(self, body: dict[str, Any]) -> tuple[Family, Device]:
        import re

        pw = body["parentPassword"]
        if (
            not pw["hash"]
            or not pw["secondHash"]
            or not pw["secondSalt"]
            or not re.fullmatch(r"\$2a\$[123][0-9]\$[./A-Za-z0-9]{53}", pw["hash"])
            or not re.fullmatch(
                r"\$2a\$[123][0-9]\$[./A-Za-z0-9]{22}", pw["secondSalt"]
            )
            or not re.fullmatch(
                r"\$2a\$[123][0-9]\$[./A-Za-z0-9]{53}", pw["secondHash"]
            )
        ):
            raise HttpError(400)
        mail = self.mail_of_auth(body["mailAuthToken"], invalidate=True)
        if self.family_of_mail(mail):
            raise HttpError(409)
        family = Family(
            family_id=auth_token()[:6],
            full_version_until=int(time.time() * 1000) + 14 * 24 * 3600 * 1000,
            has_full_version=self.premium,
        )
        user = User(
            user_id=short_id(),
            name=body["parentName"],
            type="parent",
            password_hash=pw["hash"],
            second_hash=pw["secondHash"],
            second_salt=pw["secondSalt"],
            mail=mail,
            time_zone=body["timeZone"],
            mail_notification_flags=7,
        )
        family.users[user.user_id] = user
        device = Device(
            device_id=short_id(),
            name=body["deviceName"],
            model=body["parentDevice"]["model"],
            auth_token=auth_token(),
            current_user_id=user.user_id,
            keep_signed_in=True,
        )
        family.devices[device.device_id] = device
        self.families[family.family_id] = family
        return family, device

    def sign_in_into_family(self, body: dict[str, Any]) -> tuple[Family, Device]:
        mail = self.mail_of_auth(body["mailAuthToken"], invalidate=True)
        family = self.family_of_mail(mail)
        if family is None:
            raise HttpError(409)
        user = next(u for u in family.users.values() if u.mail == mail)
        device = Device(
            device_id=short_id(),
            name=body["deviceName"],
            model=body["parentDevice"]["model"],
            auth_token=auth_token(),
            current_user_id=user.user_id,
            keep_signed_in=True,
        )
        family.devices[device.device_id] = device
        family.device_list_version = version_id()
        return family, device

    def create_add_device_token(self, family: Family) -> tuple[str, str]:
        words = " ".join(secrets.choice(_WORDS) for _ in range(5))
        device_id = short_id()
        family.add_device_token = (words.lower(), device_id)
        return words, device_id

    def add_child_device(self, body: dict[str, Any]) -> tuple[Family, Device]:
        wanted = body["registerToken"].lower()
        for family in self.families.values():
            if family.add_device_token and family.add_device_token[0] == wanted:
                _, device_id = family.add_device_token
                family.add_device_token = None
                device = Device(
                    device_id=device_id,
                    name=body["deviceName"],
                    model=body["childDevice"]["model"],
                    auth_token=auth_token(),
                )
                family.devices[device_id] = device
                family.device_list_version = version_id()
                return family, device
        raise HttpError(401)

    def remove_device(self, family: Family, device_id: str) -> None:
        device = family.devices.get(device_id)
        if device is None:
            raise HttpError(409)
        for user in family.users.values():
            if user.current_device == device_id:
                user.current_device = ""
        self.old_device_tokens.add(device.auth_token)
        del family.devices[device_id]
        family.device_list_version = version_id()
        family.user_list_version = version_id()

    def assert_parent_auth(
        self, token: str, parent_id: str, second_hash: str
    ) -> tuple[Family, Device, User]:
        family, device = self.family_of_token(token)
        if second_hash == "device":
            user = family.users.get(device.current_user_id)
            if not device.keep_signed_in or user is None or user.type != "parent":
                raise HttpError(401)
            return family, device, user
        if second_hash.startswith("u2f:"):
            raise HttpError(401)
        user = family.users.get(parent_id)
        if user is None or user.type != "parent" or user.second_hash != second_hash:
            raise HttpError(401)
        return family, device, user

    # -- sync answer -------------------------------------------------------------------------------
    def server_status(self, family: Family, client: dict[str, Any]) -> dict[str, Any]:
        level = client.get("clientLevel") or 0
        out: dict[str, Any] = {
            "fullVersion": (
                int(family.full_version_until) if family.has_full_version else 0
            ),
            "apiLevel": self.api_level,
        }
        if family.device_list_version != client.get("devices"):
            out["devices"] = {
                "version": family.device_list_version,
                "data": [_device_entry(d) for d in family.devices.values()],
            }
        if family.user_list_version != client.get("users"):
            out["users"] = {
                "version": family.user_list_version,
                "data": [_user_entry(u) for u in family.users.values()],
            }
        known: dict[str, Any] = client.get("categories") or {}
        removed = [cid for cid in known if cid not in family.categories]
        if removed:
            out["rmCategories"] = removed
        base, apps, rules, used, tasks = [], [], [], [], []
        for cid, cat in family.categories.items():
            mine = known.get(cid)
            if mine is None or mine.get("base") != cat.base_version:
                base.append(_base_entry(cat))
            if mine is None or mine.get("apps") != cat.apps_version:
                apps.append(
                    {
                        "categoryId": cid,
                        "apps": list(cat.apps),
                        "version": cat.apps_version,
                    }
                )
            if mine is None or mine.get("rules") != cat.rules_version:
                rules.append(_rules_entry(cat))
            if mine is None or mine.get("usedTime") != cat.used_times_version:
                used.append(_used_entry(cat))
            if mine is None or mine.get("tasks") != cat.tasks_version:
                tasks.append(
                    {"categoryId": cid, "tasks": [], "version": cat.tasks_version}
                )
        if base:
            out["categoryBase"] = base
        if apps:
            out["categoryApp"] = apps
        if rules:
            out["rules"] = rules
        if used:
            out["usedTimes"] = used
        if tasks and level >= 3:
            out["tasks"] = tasks
        return out


def _device_entry(d: Device) -> dict[str, Any]:
    return {
        "deviceId": d.device_id,
        "name": d.name,
        "model": d.model,
        "addedAt": d.added_at,
        "currentUserId": d.current_user_id,
        "networkTime": "disabled",
        "cProtectionLevel": "none",
        "hProtectionLevel": "none",
        "cUsageStats": "not granted",
        "hUsageStats": "not granted",
        "cNotificationAccess": "not granted",
        "hNotificationAccess": "not granted",
        "cAppVersion": 0,
        "hAppVersion": 0,
        "tDisablingAdmin": False,
        "reboot": False,
        "hadManipulation": False,
        "hadManipulationFlags": 0,
        "reportUninstall": False,
        "isUserKeptSignedIn": d.keep_signed_in,
        "showDeviceConnected": False,
        "defUser": "",
        "defUserTimeout": 0,
        "rebootIsManipulation": False,
        "cOverlay": "not granted",
        "hOverlay": "not granted",
        "asEnabled": False,
        "wasAsEnabled": False,
        "activityLevelBlocking": False,
        "qOrLater": False,
        "mFlags": 0,
        "pLevel": 0,
    }


def _user_entry(u: User) -> dict[str, Any]:
    return {
        "id": u.user_id,
        "name": u.name,
        "password": u.password_hash,
        "secondPasswordSalt": u.second_salt,
        "type": u.type,
        "timeZone": u.time_zone,
        "disableLimitsUntil": u.disable_limits_until,
        "mail": u.mail,
        "currentDevice": u.current_device,
        "categoryForNotAssignedApps": u.category_for_unassigned,
        "relaxPrimaryDevice": u.relax_primary_device,
        "mailNotificationFlags": u.mail_notification_flags,
        "blockedTimes": "",
        "flags": u.flags,
    }


def _base_entry(c: Category) -> dict[str, Any]:
    return {
        "categoryId": c.category_id,
        "childId": c.child_id,
        "title": c.title,
        "blockedTimes": c.blocked_times,
        "extraTime": c.extra_time,
        "extraTimeDay": c.extra_time_day,
        "tempBlocked": c.temp_blocked,
        "version": c.base_version,
        "parentCategoryId": c.parent_id,
        "blockAllNotifications": c.block_all_notifications,
        "timeWarnings": c.time_warnings,
        "mblMobile": c.min_battery_mobile,
        "mblCharging": c.min_battery_charging,
        "tempBlockTime": c.temp_block_end,
        "sort": c.sort,
        "networks": [],
        "dlu": c.disable_limits_until,
        "flags": c.flags,
        "blockNotificationDelay": c.block_notification_delay,
        "atw": [],
    }


def _rules_entry(c: Category) -> dict[str, Any]:
    rules = []
    for r in c.rules.values():
        item: dict[str, Any] = {
            "id": r.rule_id,
            "extraTime": r.extra_time,
            "dayMask": r.day_mask,
            "maxTime": r.max_time,
            "start": r.start,
            "end": r.end,
            "session": r.session,
            "pause": r.pause,
            "perDay": r.per_day,
        }
        if r.expires is not None:
            item["e"] = r.expires
        rules.append(item)
    return {"categoryId": c.category_id, "rules": rules, "version": c.rules_version}


def _used_entry(c: Category) -> dict[str, Any]:
    times = [
        {"day": day, "time": t, "start": s, "end": e}
        for day, per in sorted(c.used_times.items())
        for (s, e), t in sorted(per.items())
    ]
    return {
        "categoryId": c.category_id,
        "times": times,
        "sessionDurations": [],
        "version": c.used_times_version,
    }


_WORDS = [
    "alpha",
    "bravo",
    "canal",
    "dragon",
    "eagle",
    "forest",
    "garden",
    "harbor",
    "island",
    "jungle",
    "kettle",
    "lantern",
    "meadow",
    "nectar",
    "orchid",
    "pepper",
    "quartz",
    "river",
    "saddle",
    "tunnel",
    "umbrella",
    "valley",
    "window",
    "yonder",
    "zephyr",
]
