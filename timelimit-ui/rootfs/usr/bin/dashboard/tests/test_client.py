"""Plan step A6: the server client against the fake (TR-100, 104, 106, 303, 514, SEC-002)."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import pytest

from ..client.server import (
    CLIENT_LEVEL,
    ServerHttpError,
    TimeLimitClient,
    validate_server_url,
)
from ..domain.errors import DashboardError, ErrorCode
from ..domain.secret import Secret
from .fakeserver import FakeTimeLimitServer

PASSWORD = {
    "hash": "$2a$10$" + "a" * 53,
    "secondHash": "$2a$10$" + "b" * 53,
    "secondSalt": "$2a$10$" + "c" * 22,
}
BLANK = {"apps": {}, "categories": {}, "devices": "", "users": ""}
PACKAGE = Path(__file__).resolve().parents[1]


@pytest.fixture
def client(fake_server: FakeTimeLimitServer) -> TimeLimitClient:
    return TimeLimitClient(fake_server.url, timeout=2.0)


def link(client: TimeLimitClient, fake: FakeTimeLimitServer) -> tuple[Secret, str, str]:
    login = client.send_login_code("p@example.org", "en")
    auth = client.sign_in_by_code(login, fake.inbox[-1][1])
    answer = client.create_family(
        mail_auth_token=auth,
        parent_name="Parent",
        device_name="dash",
        device_model="test",
        time_zone="Europe/Amsterdam",
        password=PASSWORD,
    )
    parent_id = answer["data"]["users"]["data"][0]["id"]
    return Secret(answer["deviceAuthToken"]), answer["ownDeviceId"], parent_id


# -- SEC-002 ---------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "url",
    [
        "https://api.timelimit.io",
        "https://timelimit.example.org:8443/",
        "http://localhost:8080",
        "http://127.0.0.1:8080",
        "http://[::1]:8080",
        "http://192.168.1.20:8080",
        "http://10.0.0.5",
        "http://172.16.3.4",
        "http://homeassistant.local:8080",
        "http://homeassistant:8080",
    ],
)
def test_accepted_server_urls(url: str) -> None:
    assert validate_server_url(url).rstrip("/") == url.rstrip("/")


@pytest.mark.parametrize(
    "url",
    [
        "http://api.timelimit.io",
        "http://8.8.8.8",
        "http://example.org:8080",
        "ftp://localhost",
        "localhost:8080",
        "",
        "https://user:pw@example.org",
        "https://example.org/?a=1",
        "http://localhost:99999",
    ],
)
def test_rejected_server_urls(url: str) -> None:
    with pytest.raises(DashboardError) as info:
        validate_server_url(url)
    assert info.value.code is ErrorCode.INVALID_INPUT


def test_a_non_local_plain_http_url_gets_a_clear_message() -> None:
    with pytest.raises(DashboardError, match="https://"):
        TimeLimitClient("http://example.org", timeout=1)


# -- failures are mapped to error codes -------------------------------------------------------------------


def test_a_slow_server_gives_server_timeout_after_the_configured_time(
    fake_server: FakeTimeLimitServer,
) -> None:
    fake_server.faults.delay_seconds = 1.0
    short = TimeLimitClient(fake_server.url, timeout=0.2)
    started = time.monotonic()
    with pytest.raises(DashboardError) as info:
        short.server_time()
    assert info.value.code is ErrorCode.SERVER_TIMEOUT
    assert time.monotonic() - started < 0.9


def test_a_per_call_timeout_overrides_the_default(
    fake_server: FakeTimeLimitServer, client: TimeLimitClient
) -> None:
    fake_server.faults.delay_seconds = 0.6
    with pytest.raises(DashboardError) as info:
        client.server_time(timeout=0.1)
    assert info.value.code is ErrorCode.SERVER_TIMEOUT


def test_connection_refused_gives_server_unreachable(
    fake_server: FakeTimeLimitServer, client: TimeLimitClient
) -> None:
    fake_server.stop()
    with pytest.raises(DashboardError) as info:
        client.server_time()
    assert info.value.code is ErrorCode.SERVER_UNREACHABLE


def test_unknown_device_token_gives_session_invalid(client: TimeLimitClient) -> None:
    with pytest.raises(ServerHttpError) as info:
        client.pull_status(Secret("unknown"), BLANK)
    assert (info.value.code, info.value.status) == (ErrorCode.SESSION_INVALID, 401)


@pytest.mark.parametrize(
    ("status", "code"),
    [
        (403, ErrorCode.INVALID_PASSWORD),
        (404, ErrorCode.NOT_FOUND),
        (409, ErrorCode.CONFLICT),
        (410, ErrorCode.NOT_FOUND),
        (429, ErrorCode.SERVER_UNREACHABLE),
        (500, ErrorCode.SERVER_UNREACHABLE),
        (503, ErrorCode.SERVER_UNREACHABLE),
        (400, ErrorCode.INTERNAL_ERROR),
    ],
)
def test_http_statuses_are_mapped(
    fake_server: FakeTimeLimitServer,
    client: TimeLimitClient,
    status: int,
    code: ErrorCode,
) -> None:
    fake_server.faults.fail_next.append(status)
    with pytest.raises(ServerHttpError) as info:
        client.is_device_removed(Secret("x"))
    assert (info.value.code, info.value.status) == (code, status)


def test_an_html_answer_with_status_200_is_not_trusted(
    fake_server: FakeTimeLimitServer, client: TimeLimitClient
) -> None:
    class Page:
        status_code = 200

        def json(self) -> Any:
            raise ValueError

    class Stub:
        def request(self, *_: Any, **__: Any) -> Page:
            return Page()

    broken = TimeLimitClient(fake_server.url, timeout=1, session=Stub())  # type: ignore[arg-type]
    with pytest.raises(DashboardError) as info:
        broken.server_time()
    assert info.value.code is ErrorCode.SERVER_UNREACHABLE


def test_a_wrong_mail_code_keeps_its_status_for_the_caller(
    fake_server: FakeTimeLimitServer, client: TimeLimitClient
) -> None:
    login = client.send_login_code("a@b.c", "en")
    with pytest.raises(ServerHttpError) as info:
        client.sign_in_by_code(login, "wrong")
    assert info.value.status == 403  # 403 = try again, 410 = no attempts left


# -- gzip, 411, clientLevel -------------------------------------------------------------------------------


def test_bodies_are_gzipped(
    fake_server: FakeTimeLimitServer, client: TimeLimitClient
) -> None:
    link(client, fake_server)
    assert set(fake_server.world.request_encodings) == {"gzip"}


def test_http_411_is_repeated_without_compression(
    fake_server: FakeTimeLimitServer, client: TimeLimitClient
) -> None:
    fake_server.faults.fail_next.append(411)
    assert client.is_device_removed(Secret("x")) is False
    assert fake_server.world.request_encodings[-2:] == ["gzip", ""]


def test_requests_carry_client_level_7(
    fake_server: FakeTimeLimitServer, client: TimeLimitClient
) -> None:
    token, _, _ = link(client, fake_server)
    client.pull_status(token, BLANK)
    assert CLIENT_LEVEL == 7
    assert fake_server.world.client_levels == [7, 7]
    client.pull_status(token, {**BLANK, "clientLevel": 99})  # ours always wins
    assert fake_server.world.client_levels[-1] == 7


# -- the whole flow, and the "one HTTP function" rules -----------------------------------------------------


def test_link_pull_push_and_remove_a_device(
    fake_server: FakeTimeLimitServer, client: TimeLimitClient
) -> None:
    token, own_id, parent_id = link(client, fake_server)
    assert (
        client.status_by_mail(
            client.sign_in_by_code(
                client.send_login_code("p@example.org", "en"), fake_server.inbox[-1][1]
            )
        )["status"]
        == "with family"
    )
    add = client.create_add_device_token(
        device_token=token, parent_id=parent_id, second_hash="device"
    )
    child = client.add_child_device(
        register_token=add["token"], device_name="phone", device_model="x"
    )
    status = client.pull_status(token, BLANK)
    assert len(status["devices"]["data"]) == 2
    wire = {
        "type": "parent",
        "userId": parent_id,
        "sequenceNumber": 0,
        "integrity": "device",
        "encodedAction": '{"type":"ADD_USER","userId":"child1","name":"K","userType":"child","timeZone":"UTC"}',
    }
    assert client.push_actions(token, [wire]) is False
    client.remove_device(
        device_token=token,
        device_id=child["ownDeviceId"],
        parent_id=parent_id,
        second_hash=Secret("device"),
    )
    assert client.is_device_removed(Secret(child["deviceAuthToken"])) is True
    assert own_id


def test_only_the_client_module_talks_http() -> None:
    allowed = PACKAGE / "client" / "server.py"
    offenders = []
    for path in PACKAGE.rglob("*.py"):
        if "tests" in path.parts or path == allowed:
            continue
        text = path.read_text(encoding="utf-8")
        if any(
            word in text
            for word in (
                "import requests",
                "from requests",
                "urllib.request",
                "http.client",
                "import httpx",
            )
        ):
            offenders.append(str(path.relative_to(PACKAGE)))
    assert offenders == []


def test_every_call_passes_a_timeout() -> None:
    seen: list[Any] = []

    class Response:
        status_code = 200

        def json(self) -> Any:
            return {
                "ms": 1,
                "mailLoginToken": "t",
                "mailAuthToken": "a",
                "shouldDoFullSync": False,
                "isDeviceRemoved": False,
            }

    class Stub:
        def request(self, *args: Any, **kwargs: Any) -> Response:
            seen.append(kwargs.get("timeout"))
            return Response()

    c = TimeLimitClient("https://example.org", timeout=7, session=Stub())  # type: ignore[arg-type]
    token, auth = Secret("t"), Secret("a")
    c.server_time()
    c.send_login_code("a@b.c", "en")
    c.sign_in_by_code(token, "x")
    c.status_by_mail(auth)
    c.create_family(
        mail_auth_token=auth,
        parent_name="p",
        device_name="d",
        device_model="m",
        time_zone="UTC",
        password=PASSWORD,
    )
    c.sign_in_into_family(mail_auth_token=auth, device_name="d", device_model="m")
    c.create_add_device_token(device_token=token, parent_id="p", second_hash="device")
    c.remove_device(
        device_token=token, device_id="d", parent_id="p", second_hash="device"
    )
    c.add_child_device(register_token="w", device_name="d", device_model="m")
    c.pull_status(token, BLANK)
    c.push_actions(token, [])
    c.is_device_removed(token)
    assert seen == [7] * 12


def test_a_timeout_must_be_positive() -> None:
    with pytest.raises(ValueError, match="positive"):
        TimeLimitClient("https://example.org", timeout=0)
