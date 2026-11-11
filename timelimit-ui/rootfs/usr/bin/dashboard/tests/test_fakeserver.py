"""Conformance suite of the fake TimeLimit server (plan A5, TR-501).

These tests pin the behaviour of the real server that the dashboard depends on, as read from its source
(commit fe90617). Later the same scenarios can be run against a real server (plan step M).
"""

from __future__ import annotations

import json
import threading
import time
from typing import Any

import pytest
import requests

from .fakeserver import FakeTimeLimitServer, integrity, schemas

HASH = "$2a$10$" + "a" * 53
SECOND_HASH = "$2a$10$" + "b" * 53
SALT = "$2a$10$" + "c" * 22
VECTOR_KEY = "$2a$12$abcdefghijklmnopqrstuuABCDEFGHIJKLMNOPQRSTUVWXYZ01234"


def blank_status(level: int = 9) -> dict[str, Any]:
    """The smallest ClientDataStatus the real server accepts (all four parts are required)."""
    return {
        "apps": {},
        "categories": {},
        "devices": "",
        "users": "",
        "clientLevel": level,
    }


class Api:
    """Tiny client for the fake; deliberately independent of the dashboard code."""

    def __init__(self, server: FakeTimeLimitServer) -> None:
        self.server = server
        self.token = ""
        self.device_id = ""
        self.parent_id = ""
        self.seq = 0

    def post(self, path: str, body: dict[str, Any]) -> requests.Response:
        return requests.post(self.server.url + path, json=body, timeout=5)

    def mail_auth(self, mail: str = "p@example.org") -> str:
        login = self.post(
            "/auth/send-mail-login-code-v2", {"mail": mail, "locale": "en"}
        ).json()
        code = self.server.inbox[-1][1]
        return str(
            self.post(
                "/auth/sign-in-by-mail-code",
                {"mailLoginToken": login["mailLoginToken"], "receivedCode": code},
            ).json()["mailAuthToken"]
        )

    def create_family(self, mail: str = "p@example.org") -> dict[str, Any]:
        body = {
            "mailAuthToken": self.mail_auth(mail),
            "parentDevice": {"model": "test"},
            "parentPassword": {
                "hash": HASH,
                "secondHash": SECOND_HASH,
                "secondSalt": SALT,
            },
            "deviceName": "dash",
            "parentName": "Parent",
            "timeZone": "Europe/Amsterdam",
            "clientLevel": 9,
        }
        answer: dict[str, Any] = self.post("/parent/create-family", body).json()
        self.token = answer["deviceAuthToken"]
        self.device_id = answer["ownDeviceId"]
        self.parent_id = answer["data"]["users"]["data"][0]["id"]
        return answer

    def pull(self, status: dict[str, Any] | None = None) -> dict[str, Any]:
        r = self.post(
            "/sync/pull-status",
            {"deviceAuthToken": self.token, "status": status or blank_status()},
        )
        assert r.status_code == 200, r.text
        data: dict[str, Any] = r.json()
        return data

    def push(
        self,
        action: dict[str, Any],
        *,
        integrity_value: str = "device",
        seq: int | None = None,
    ) -> dict[str, Any]:
        number = self.seq if seq is None else seq
        self.seq = number + 1
        wire = {
            "type": "parent",
            "userId": self.parent_id,
            "sequenceNumber": number,
            "encodedAction": json.dumps(action, separators=(",", ":")),
            "integrity": integrity_value,
        }
        r = self.post(
            "/sync/push-actions", {"deviceAuthToken": self.token, "actions": [wire]}
        )
        assert r.status_code == 200, r.text
        result: dict[str, Any] = r.json()
        return result


@pytest.fixture
def api(fake_server: FakeTimeLimitServer) -> Api:
    client = Api(fake_server)
    client.create_family()
    return client


def make_child(api: Api, child: str = "child1", category: str = "cat001") -> None:
    api.push(
        {
            "type": "ADD_USER",
            "userId": child,
            "name": "Kid",
            "userType": "child",
            "timeZone": "Europe/Amsterdam",
        }
    )
    api.push(
        {
            "type": "CREATE_CATEGORY",
            "categoryId": category,
            "childId": child,
            "title": "Games",
        }
    )


def category(status: dict[str, Any], category_id: str = "cat001") -> dict[str, Any]:
    return next(c for c in status["categoryBase"] if c["categoryId"] == category_id)


# -- integrity --------------------------------------------------------------------------------------


def test_hmac_vectors_of_the_server_documentation() -> None:
    assert (
        integrity.password_integrity(
            sequence_number=7,
            device_id="dev123",
            encoded_action='{"type":"CREATE_TIMELIMIT_RULE","rule":{"ruleId":"r1"}}',
            secret=VECTOR_KEY,
        )
        == "password:n10GZyWfMKiUKda4gXQEWgvlFYpTnKC3OG6zM6Jl6ms="
    )
    assert (
        integrity.password_integrity(
            sequence_number=0,
            device_id="äöü",
            encoded_action='{"a":"é"}',
            secret=VECTOR_KEY,
        )
        == "password:eC7BY0YnRSRFX8stS6q4iG32JSNSb1p6KU4X92BFsz0="
    )


# -- basics, faults, strictness -------------------------------------------------------------------------


def test_starts_fast_and_answers_time() -> None:
    started = time.monotonic()
    with FakeTimeLimitServer() as server:
        body = requests.get(server.url + "/time", timeout=5).json()
    assert time.monotonic() - started < 1.0
    assert abs(body["ms"] - time.time() * 1000) < 5000


def test_unknown_fields_are_rejected_like_the_real_server(
    fake_server: FakeTimeLimitServer,
) -> None:
    r = requests.post(
        fake_server.url + "/sync/pull-status",
        json={"deviceAuthToken": "x", "status": {}, "extra": 1},
        timeout=5,
    )
    assert r.status_code == 400
    assert r.headers["content-type"].startswith("text/html")


def test_unknown_device_token_is_unauthorized(fake_server: FakeTimeLimitServer) -> None:
    r = requests.post(
        fake_server.url + "/sync/pull-status",
        json={"deviceAuthToken": "nope", "status": blank_status()},
        timeout=5,
    )
    assert r.status_code == 401


def test_fault_injection(api: Api) -> None:
    api.server.faults.fail_next.append(503)
    assert (
        api.post(
            "/sync/pull-status",
            {"deviceAuthToken": api.token, "status": blank_status()},
        ).status_code
        == 503
    )
    assert api.pull()["apiLevel"] == 9
    api.server.faults.delay_seconds = 0.3
    started = time.monotonic()
    api.pull()
    assert time.monotonic() - started >= 0.3


def test_server_down_and_up_again(api: Api) -> None:
    url = api.server.url
    api.server.stop()
    with pytest.raises(requests.ConnectionError):
        requests.get(url + "/time", timeout=2)
    api.server.start()
    assert api.pull()["apiLevel"] == 9


@pytest.mark.parametrize("level", [7, 9])
def test_api_level_is_configurable(level: int) -> None:
    with FakeTimeLimitServer(api_level=level) as server:
        api = Api(server)
        assert api.create_family()["data"]["apiLevel"] == level


# -- mail login and family creation ------------------------------------------------------------------------


def test_mail_code_allows_three_attempts(fake_server: FakeTimeLimitServer) -> None:
    api = Api(fake_server)
    login = api.post(
        "/auth/send-mail-login-code-v2", {"mail": "a@b.c", "locale": "en"}
    ).json()["mailLoginToken"]
    codes = [
        api.post(
            "/auth/sign-in-by-mail-code",
            {"mailLoginToken": login, "receivedCode": "wrong"},
        ).status_code
        for _ in range(3)
    ]
    assert codes == [403, 403, 410]
    right = fake_server.inbox[-1][1]
    assert (
        api.post(
            "/auth/sign-in-by-mail-code",
            {"mailLoginToken": login, "receivedCode": right},
        ).status_code
        == 410
    )


def test_create_family_consumes_the_mail_token_and_validates_hashes(
    fake_server: FakeTimeLimitServer,
) -> None:
    api = Api(fake_server)
    token = api.mail_auth()
    base = {
        "parentDevice": {"model": "m"},
        "deviceName": "d",
        "parentName": "P",
        "timeZone": "Europe/Amsterdam",
    }
    bad = {
        **base,
        "mailAuthToken": token,
        "parentPassword": {
            "hash": "plain",
            "secondHash": SECOND_HASH,
            "secondSalt": SALT,
        },
    }
    assert api.post("/parent/create-family", bad).status_code == 400
    good = {
        **base,
        "mailAuthToken": token,
        "parentPassword": {"hash": HASH, "secondHash": SECOND_HASH, "secondSalt": SALT},
    }
    assert api.post("/parent/create-family", good).status_code == 200
    assert (
        api.post("/parent/create-family", good).status_code == 401
    )  # token was used up


def test_status_by_mail_address(fake_server: FakeTimeLimitServer) -> None:
    api = Api(fake_server)
    token = api.mail_auth("new@example.org")
    assert (
        api.post("/parent/get-status-by-mail-address", {"mailAuthToken": token}).json()[
            "status"
        ]
        == "without family"
    )
    Api(fake_server).create_family("old@example.org")
    token = api.mail_auth("old@example.org")
    assert (
        api.post("/parent/get-status-by-mail-address", {"mailAuthToken": token}).json()[
            "status"
        ]
        == "with family"
    )


def test_sign_in_into_existing_family(api: Api) -> None:
    other = Api(api.server)
    token = other.mail_auth("p@example.org")
    r = other.post(
        "/parent/sign-in-into-family",
        {
            "mailAuthToken": token,
            "parentDevice": {"model": "m"},
            "deviceName": "second",
        },
    )
    assert r.status_code == 200
    assert r.json()["ownDeviceId"] != api.device_id


# -- pull-status ---------------------------------------------------------------------------------------------


def test_pull_sends_only_what_changed(api: Api) -> None:
    make_child(api)
    first = api.pull()
    assert len(first["categoryBase"]) == 1
    status = {
        **blank_status(),
        "devices": first["devices"]["version"],
        "users": first["users"]["version"],
        "apps": {a["deviceId"]: a["version"] for a in first["apps"]},
        "dh": first["dh"]["v"],
        "categories": {
            "cat001": {
                "base": first["categoryBase"][0]["version"],
                "apps": first["categoryApp"][0]["version"],
                "rules": first["rules"][0]["version"],
                "usedTime": first["usedTimes"][0]["version"],
                "tasks": first["tasks"][0]["version"],
            }
        },
    }
    second = api.pull(status)
    assert set(second) == {"fullVersion", "apiLevel"}
    assert "tasks" in first
    assert first["dh"]["v"] and first["dh"]["k"]  # level 5 and up gets the server's DH key
    assert "tasks" not in api.pull(blank_status(2))


# -- actions -----------------------------------------------------------------------------------------------


def test_actions_change_the_family(api: Api) -> None:
    make_child(api)
    api.push(
        {
            "type": "UPDATE_CATEGORY_TITLE",
            "categoryId": "cat001",
            "newTitle": "Spelletjes",
        }
    )
    api.push(
        {
            "type": "ADD_CATEGORY_APPS",
            "categoryId": "cat001",
            "packageNames": ["com.a", "com.b"],
        }
    )
    api.push(
        {
            "type": "CREATE_TIMELIMIT_RULE",
            "rule": {
                "ruleId": "rule01",
                "categoryId": "cat001",
                "time": 3600000,
                "days": 127,
                "extraTime": False,
            },
        }
    )
    api.push(
        {
            "type": "UPDATE_CATEGORY_BLOCKED_TIMES",
            "categoryId": "cat001",
            "times": "0,60",
        }
    )
    status = api.pull()
    assert category(status)["title"] == "Spelletjes"
    assert category(status)["blockedTimes"] == "0,60"
    assert status["categoryApp"][0]["apps"] == ["com.a", "com.b"]
    rule = status["rules"][0]["rules"][0]
    assert (rule["maxTime"], rule["dayMask"], rule["start"], rule["end"]) == (
        3600000,
        127,
        0,
        1439,
    )
    api.push(
        {
            "type": "REMOVE_CATEGORY_APPS",
            "categoryId": "cat001",
            "packageNames": ["com.a"],
        }
    )
    api.push({"type": "DELETE_TIMELIMIT_RULE", "ruleId": "rule01"})
    api.push({"type": "RENAME_CHILD", "childId": "child1", "newName": "Sam"})
    status = api.pull()
    assert status["categoryApp"][0]["apps"] == ["com.b"]
    assert status["rules"][0]["rules"] == []
    assert any(u["name"] == "Sam" for u in status["users"]["data"])
    api.push({"type": "DELETE_CATEGORY", "categoryId": "cat001"})
    assert api.pull(
        {
            **blank_status(),
            "categories": {
                "cat001": {
                    "base": "",
                    "apps": "",
                    "rules": "",
                    "usedTime": "",
                    "tasks": "",
                }
            },
        }
    )["rmCategories"] == ["cat001"]
    api.push({"type": "REMOVE_USER", "userId": "child1"})
    assert [u["id"] for u in api.pull()["users"]["data"]] == [api.parent_id]


def test_extra_time_and_temporary_block(api: Api) -> None:
    make_child(api)
    api.push(
        {
            "type": "INCREMENT_CATEGORY_EXTRATIME",
            "categoryId": "cat001",
            "addedExtraTime": 600000,
            "day": 5,
        }
    )
    api.push(
        {
            "type": "INCREMENT_CATEGORY_EXTRATIME",
            "categoryId": "cat001",
            "addedExtraTime": 600000,
            "day": 5,
        }
    )
    assert (
        category(api.pull())["extraTime"],
        category(api.pull())["extraTimeDay"],
    ) == (1200000, 5)
    api.push(
        {
            "type": "INCREMENT_CATEGORY_EXTRATIME",
            "categoryId": "cat001",
            "addedExtraTime": 1000,
            "day": 6,
        }
    )
    assert category(api.pull())["extraTime"] == 1000
    api.push(
        {
            "type": "SET_CATEGORY_EXTRA_TIME",
            "categoryId": "cat001",
            "newExtraTime": 0,
            "day": -1,
        }
    )
    api.push(
        {
            "type": "UPDATE_CATEGORY_TEMPORARILY_BLOCKED",
            "categoryId": "cat001",
            "blocked": True,
            "endTime": 99,
        }
    )
    assert category(api.pull())["tempBlocked"] is True


def test_premium_actions_fail_silently_without_premium() -> None:
    with FakeTimeLimitServer(premium=False) as server:
        api = Api(server)
        api.create_family()
        make_child(api)
        answer = api.push(
            {
                "type": "INCREMENT_CATEGORY_EXTRATIME",
                "categoryId": "cat001",
                "addedExtraTime": 1000,
                "day": 1,
            }
        )
        assert answer == {"shouldDoFullSync": True}  # HTTP 200, nothing changed
        assert category(api.pull())["extraTime"] == 0
        assert server.world.rejected_actions == ["premium version missing"]
        assert api.push(
            {
                "type": "UPDATE_CATEGORY_TEMPORARILY_BLOCKED",
                "categoryId": "cat001",
                "blocked": False,
            }
        ) == {"shouldDoFullSync": False}


def test_failed_actions_are_silent_but_consume_the_sequence_number(api: Api) -> None:
    make_child(api)
    seq_before = api.seq
    assert api.push(
        {"type": "UPDATE_CATEGORY_TITLE", "categoryId": "nocat1", "newTitle": "x"}
    ) == {"shouldDoFullSync": True}
    assert api.seq == seq_before + 1
    # reusing the consumed number: ignored without any effect and without a full-sync request
    assert api.push(
        {"type": "UPDATE_CATEGORY_TITLE", "categoryId": "cat001", "newTitle": "again"},
        seq=seq_before,
    ) == {"shouldDoFullSync": False}
    assert category(api.pull())["title"] == "Games"
    assert api.push(
        {"type": "UPDATE_CATEGORY_TITLE", "categoryId": "cat001", "newTitle": "next"},
        seq=api.seq,
    ) == {"shouldDoFullSync": False}
    assert category(api.pull())["title"] == "next"


def test_invalid_actions_fail_silently(api: Api) -> None:
    make_child(api)
    bad_bitmask = {
        "type": "UPDATE_CATEGORY_BLOCKED_TIMES",
        "categoryId": "cat001",
        "times": "60,0",
    }
    assert api.push(bad_bitmask) == {"shouldDoFullSync": True}
    assert api.push({"type": "UPDATE_CATEGORY_TITLE", "categoryId": "cat001"}) == {
        "shouldDoFullSync": True
    }  # schema
    assert api.push({"type": "NOT_AN_ACTION"}) == {"shouldDoFullSync": True}
    assert api.server.unsimulated == []


def test_wrong_integrity_is_rejected_silently(api: Api) -> None:
    action = {
        "type": "ADD_USER",
        "userId": "child1",
        "name": "K",
        "userType": "child",
        "timeZone": "Europe/Amsterdam",
    }
    assert api.push(action, integrity_value="password:AAAA") == {
        "shouldDoFullSync": True
    }
    assert len(api.pull()["users"]["data"]) == 1


def test_password_integrity_is_accepted(api: Api) -> None:
    action = {
        "type": "ADD_USER",
        "userId": "child1",
        "name": "K",
        "userType": "child",
        "timeZone": "Europe/Amsterdam",
    }
    encoded = json.dumps(action, separators=(",", ":"))
    value = integrity.password_integrity(
        sequence_number=api.seq,
        device_id=api.device_id,
        encoded_action=encoded,
        secret=SECOND_HASH,
    )
    assert api.push(action, integrity_value=value) == {"shouldDoFullSync": False}
    assert len(api.pull()["users"]["data"]) == 2


def test_more_than_fifty_actions_per_request_are_rejected(api: Api) -> None:
    wire = {
        "type": "parent",
        "userId": api.parent_id,
        "sequenceNumber": 0,
        "encodedAction": "{}",
        "integrity": "device",
    }
    assert (
        api.post(
            "/sync/push-actions", {"deviceAuthToken": api.token, "actions": [wire] * 51}
        ).status_code
        == 400
    )


def test_unsimulated_actions_are_reported(fake_server: FakeTimeLimitServer) -> None:
    api = Api(fake_server)
    api.create_family()
    assert api.push(
        {"type": "SET_USER_TIMEZONE", "userId": api.parent_id, "timezone": "UTC"}
    ) == {"shouldDoFullSync": True}
    assert fake_server.unsimulated == ["SET_USER_TIMEZONE"]
    fake_server.unsimulated.clear()  # this test provoked it on purpose


def test_used_time_from_a_child_device_reduces_extra_time(api: Api) -> None:
    make_child(api)
    api.push(
        {
            "type": "SET_CATEGORY_EXTRA_TIME",
            "categoryId": "cat001",
            "newExtraTime": 5000,
            "day": 1,
        }
    )
    wire = {
        "type": "appLogic",
        "userId": "",
        "sequenceNumber": api.seq,
        "encodedAction": json.dumps(
            {
                "type": "ADD_USED_TIME_V2",
                "d": 20000,
                "i": [{"categoryId": "cat001", "tta": 60000, "etts": 2000}],
            }
        ),
        "integrity": "",
    }
    api.seq += 1
    assert api.post(
        "/sync/push-actions", {"deviceAuthToken": api.token, "actions": [wire]}
    ).json() == {"shouldDoFullSync": False}
    status = api.pull()
    assert category(status)["extraTime"] == 3000
    assert status["usedTimes"][0]["times"][0]["time"] == 60000


# -- devices -----------------------------------------------------------------------------------------------


def register(api: Api) -> dict[str, Any]:
    token = api.post(
        "/parent/create-add-device-token",
        {
            "deviceAuthToken": api.token,
            "parentId": api.parent_id,
            "parentPasswordSecondHash": "device",
        },
    ).json()
    assert len(token["token"].split(" ")) == 5
    answer = api.post(
        "/child/add-device",
        {
            "registerToken": token["token"],
            "deviceName": "phone",
            "childDevice": {"model": "x"},
        },
    )
    assert answer.status_code == 200, answer.text
    result: dict[str, Any] = answer.json()
    assert result["ownDeviceId"] == token["deviceId"]
    return result


def test_add_child_device_and_remove_it(api: Api) -> None:
    child_device = register(api)
    assert len(api.pull()["devices"]["data"]) == 2
    removal = {
        "deviceAuthToken": api.token,
        "deviceId": child_device["ownDeviceId"],
        "parentUserId": api.parent_id,
        "parentPasswordSecondHash": "device",
    }
    assert api.post("/parent/remove-device", removal).json() == {"ok": True}
    assert api.post("/parent/remove-device", removal).status_code == 409
    assert api.post(
        "/sync/is-device-removed", {"deviceAuthToken": child_device["deviceAuthToken"]}
    ).json() == {"isDeviceRemoved": True}
    assert api.post(
        "/sync/is-device-removed", {"deviceAuthToken": api.token}
    ).json() == {"isDeviceRemoved": False}


def test_a_newer_add_device_token_replaces_the_older_one(api: Api) -> None:
    ask = {
        "deviceAuthToken": api.token,
        "parentId": api.parent_id,
        "parentPasswordSecondHash": "device",
    }
    old = api.post("/parent/create-add-device-token", ask).json()["token"]
    api.post("/parent/create-add-device-token", ask)
    r = api.post(
        "/child/add-device",
        {"registerToken": old, "deviceName": "phone", "childDevice": {"model": "x"}},
    )
    assert r.status_code == 401


def test_register_token_is_single_use(api: Api) -> None:
    ask = {
        "deviceAuthToken": api.token,
        "parentId": api.parent_id,
        "parentPasswordSecondHash": "device",
    }
    token = api.post("/parent/create-add-device-token", ask).json()["token"]
    body = {
        "registerToken": token,
        "deviceName": "phone",
        "childDevice": {"model": "x"},
    }
    assert api.post("/child/add-device", body).status_code == 200
    assert api.post("/child/add-device", body).status_code == 401


def test_wrong_second_hash_is_unauthorized(api: Api) -> None:
    ask = {
        "deviceAuthToken": api.token,
        "parentId": api.parent_id,
        "parentPasswordSecondHash": "$2a$10$" + "z" * 53,
    }
    assert api.post("/parent/create-add-device-token", ask).status_code == 401


# -- socket.io ---------------------------------------------------------------------------------------------


def test_other_devices_are_told_to_sync_but_not_the_sender(api: Api) -> None:
    import socketio

    child_device = register(api)
    events: dict[str, list[Any]] = {"sender": [], "other": []}
    ready = threading.Event()

    def connect(name: str, token: str) -> socketio.Client:
        client = socketio.Client()
        client.on("should sync", lambda data: events[name].append(data))
        client.connect(api.server.url, transports=["polling"], wait_timeout=5)
        client.emit("devicelogin", token, callback=ready.set)
        return client

    sender, other = (
        connect("sender", api.token),
        connect("other", child_device["deviceAuthToken"]),
    )
    try:
        time.sleep(0.5)
        make_child(api)  # unimportant changes (level 1)
        api.push(
            {"type": "UPDATE_CATEGORY_TITLE", "categoryId": "cat001", "newTitle": "x"}
        )
        deadline = time.monotonic() + 3
        while {"isImportant": True} not in events[
            "other"
        ] and time.monotonic() < deadline:
            time.sleep(0.05)
    finally:
        sender.disconnect()
        other.disconnect()
    assert events["other"], "the other device got no 'should sync'"
    assert events["sender"] == []
    assert {"isImportant": False} in events["other"]  # ADD_USER / CREATE_CATEGORY
    assert events["other"][-1] == {"isImportant": True}  # a title change is important


# -- the fake against its own schemas ------------------------------------------------------------------------


def test_every_answer_is_valid_for_a_strict_client(api: Api) -> None:
    make_child(api)
    api.push(
        {
            "type": "CREATE_TIMELIMIT_RULE",
            "rule": {
                "ruleId": "rule01",
                "categoryId": "cat001",
                "time": 1,
                "days": 1,
                "extraTime": True,
                "e": 5,
            },
        }
    )
    assert schemas.status_errors(api.pull()) == []


def test_rule_expiry_is_only_sent_by_the_server_variant_that_has_it() -> None:
    rule = {
        "type": "CREATE_TIMELIMIT_RULE",
        "rule": {
            "ruleId": "rule01",
            "categoryId": "cat001",
            "time": 1,
            "days": 1,
            "extraTime": True,
            "e": 5,
        },
    }
    for variant, expected in ((False, None), (True, 5)):
        with FakeTimeLimitServer(rule_expiry=variant) as server:
            api = Api(server)
            api.create_family()
            make_child(api)
            api.push(rule)
            assert api.pull()["rules"][0]["rules"][0].get("e") == expected
