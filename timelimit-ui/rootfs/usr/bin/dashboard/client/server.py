"""The only module that talks HTTP to the TimeLimit server (plan A6; TR-100, 104, 106, 303, 514, SEC-002).

Every call goes through :meth:`TimeLimitClient._post`, which always passes a timeout, gzips the body,
retries once without compression on HTTP 411 and maps every failure to a ``DashboardError``.
"""

from __future__ import annotations

import gzip
import ipaddress
import json
import logging
from typing import Any
from urllib.parse import urlsplit

import requests

from ..domain.errors import DashboardError, ErrorCode
from ..domain.secret import Secret

log = logging.getLogger("dashboard.client")

CLIENT_LEVEL = 7  # TR-104: the dashboard only uses what is available at this level
OFFICIAL_SERVER_URL = "https://api.timelimit.io"


class ServerHttpError(DashboardError):
    """A DashboardError that also remembers the HTTP status the server answered with."""

    def __init__(self, code: ErrorCode, message: str, status: int) -> None:
        super().__init__(code, message)
        self.status = status


def _is_local_host(host: str) -> bool:
    """localhost, loopback, private and link-local addresses, ``.local`` and dot-less LAN names."""
    name = host.strip("[]").lower()
    if name == "localhost" or name.endswith(
        (".localhost", ".local", ".lan", ".home.arpa")
    ):
        return True
    try:
        address = ipaddress.ip_address(name)
    except ValueError:
        return "." not in name  # a bare host name such as "homeassistant" is on the LAN
    return address.is_loopback or address.is_private or address.is_link_local


def validate_server_url(url: str) -> str:
    """Normalised base URL (no trailing slash); plain HTTP only for the local network (SEC-002)."""
    parts = urlsplit(url.strip())
    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise DashboardError(
            ErrorCode.INVALID_INPUT,
            "The server address must start with http:// or https://.",
        )
    if parts.query or parts.fragment or parts.username or parts.password:
        raise DashboardError(
            ErrorCode.INVALID_INPUT,
            "The server address may only contain protocol, host, port and path.",
        )
    if parts.scheme == "http" and not _is_local_host(parts.hostname):
        raise DashboardError(
            ErrorCode.INVALID_INPUT,
            "Plain http:// is only allowed for servers on this computer or the local network; use https://.",
        )
    try:
        port = parts.port
    except ValueError as exc:
        raise DashboardError(
            ErrorCode.INVALID_INPUT, "The server port is not valid."
        ) from exc
    host = f"[{parts.hostname}]" if ":" in parts.hostname else parts.hostname
    return (
        f"{parts.scheme}://{host}{f':{port}' if port else ''}{parts.path.rstrip('/')}"
    )


_STATUS_CODES: dict[int, ErrorCode] = {
    401: ErrorCode.SESSION_INVALID,
    403: ErrorCode.INVALID_PASSWORD,
    404: ErrorCode.NOT_FOUND,
    410: ErrorCode.NOT_FOUND,
    409: ErrorCode.CONFLICT,
    429: ErrorCode.SERVER_UNREACHABLE,
}


def _error_for_status(status: int) -> ServerHttpError:
    if status in _STATUS_CODES:
        code = _STATUS_CODES[status]
    elif status >= 500:
        code = ErrorCode.SERVER_UNREACHABLE
    else:
        code = (
            ErrorCode.INTERNAL_ERROR
        )  # 400 and the like: our request is wrong, a bug on our side
    messages = {
        ErrorCode.SESSION_INVALID: "The server no longer accepts this device. Link the dashboard again.",
        ErrorCode.INVALID_PASSWORD: "The server refused the request (wrong password or code).",
        ErrorCode.NOT_FOUND: "The server does not know this item (any more).",
        ErrorCode.CONFLICT: "The server reports a conflict with its current data.",
        ErrorCode.SERVER_UNREACHABLE: f"The server answered with an error (HTTP {status}).",
    }
    return ServerHttpError(
        code,
        messages.get(code, f"The server rejected the request (HTTP {status})."),
        status,
    )


class TimeLimitClient:
    """Typed calls to one TimeLimit server. Tokens and hashes are ``Secret`` values."""

    def __init__(
        self,
        base_url: str,
        *,
        timeout: float,
        session: requests.Session | None = None,
    ) -> None:
        if timeout <= 0:
            raise ValueError("timeout must be positive")
        self.base_url = validate_server_url(base_url)
        self.timeout = timeout
        self._session = session or requests.Session()

    # -- the one place that does HTTP ----------------------------------------------------------------
    def _request(
        self,
        method: str,
        path: str,
        body: dict[str, Any] | None,
        timeout: float | None,
    ) -> Any:
        url = self.base_url + path
        wait = self.timeout if timeout is None else timeout
        headers = {"Accept": "application/json"}
        data: bytes | None = None
        if body is not None:
            raw = json.dumps(body, separators=(",", ":")).encode("utf-8")
            data, headers = (
                gzip.compress(raw),
                {
                    **headers,
                    "Content-Type": "application/json",
                    "Content-Encoding": "gzip",
                },
            )
        try:
            response = self._session.request(
                method, url, data=data, headers=headers, timeout=wait
            )
            if response.status_code == 411 and body is not None:
                # Like the Android app: a server that wants a plain body with an explicit length.
                log.info(
                    "server answered 411, repeating without compression",
                    extra={"path": path},
                )
                plain = {
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                }
                response = self._session.request(
                    method, url, data=raw, headers=plain, timeout=wait
                )
        except requests.Timeout as exc:
            raise DashboardError(
                ErrorCode.SERVER_TIMEOUT,
                f"The server did not answer within {wait:g} seconds.",
            ) from exc
        except requests.RequestException as exc:
            raise DashboardError(
                ErrorCode.SERVER_UNREACHABLE, "The server cannot be reached."
            ) from exc
        if response.status_code != 200:
            log.warning(
                "server error", extra={"path": path, "status": response.status_code}
            )
            raise _error_for_status(response.status_code)
        try:
            return response.json()
        except ValueError as exc:
            raise DashboardError(
                ErrorCode.SERVER_UNREACHABLE,
                "The server sent an answer that is not JSON.",
            ) from exc

    def _post(
        self, path: str, body: dict[str, Any], timeout: float | None = None
    ) -> dict[str, Any]:
        answer = self._request("POST", path, body, timeout)
        if not isinstance(answer, dict):
            raise DashboardError(
                ErrorCode.SERVER_UNREACHABLE, "The server sent an unexpected answer."
            )
        return answer

    # -- calls -----------------------------------------------------------------------------------------
    def server_time(self, timeout: float | None = None) -> int:
        """Server clock in ms (``GET /time``); also usable as a cheap health probe."""
        answer = self._request("GET", "/time", None, timeout)
        return int(answer["ms"])

    def send_login_code(self, mail: str, locale: str) -> Secret:
        answer = self._post(
            "/auth/send-mail-login-code-v2", {"mail": mail, "locale": locale}
        )
        if "mailLoginToken" not in answer:
            raise DashboardError(
                ErrorCode.INVALID_INPUT, "The server does not accept this mail address."
            )
        return Secret(answer["mailLoginToken"])

    def sign_in_by_code(self, login_token: Secret, code: str) -> Secret:
        answer = self._post(
            "/auth/sign-in-by-mail-code",
            {"mailLoginToken": login_token.reveal(), "receivedCode": code},
        )
        return Secret(answer["mailAuthToken"])

    def status_by_mail(self, mail_auth_token: Secret) -> dict[str, Any]:
        return self._post(
            "/parent/get-status-by-mail-address",
            {"mailAuthToken": mail_auth_token.reveal()},
        )

    def create_family(
        self,
        *,
        mail_auth_token: Secret,
        parent_name: str,
        device_name: str,
        device_model: str,
        time_zone: str,
        password: dict[str, str],
    ) -> dict[str, Any]:
        """``password`` is ``{hash, secondHash, secondSalt}`` as built by the crypto module."""
        return self._post(
            "/parent/create-family",
            {
                "mailAuthToken": mail_auth_token.reveal(),
                "parentPassword": password,
                "parentName": parent_name,
                "deviceName": device_name,
                "parentDevice": {"model": device_model},
                "timeZone": time_zone,
                "clientLevel": CLIENT_LEVEL,
            },
        )

    def sign_in_into_family(
        self, *, mail_auth_token: Secret, device_name: str, device_model: str
    ) -> dict[str, Any]:
        return self._post(
            "/parent/sign-in-into-family",
            {
                "mailAuthToken": mail_auth_token.reveal(),
                "deviceName": device_name,
                "parentDevice": {"model": device_model},
                "clientLevel": CLIENT_LEVEL,
            },
        )

    def create_add_device_token(
        self, *, device_token: Secret, parent_id: str, second_hash: Secret | str
    ) -> dict[str, Any]:
        return self._post(
            "/parent/create-add-device-token",
            {
                "deviceAuthToken": device_token.reveal(),
                "parentId": parent_id,
                "parentPasswordSecondHash": _plain(second_hash),
            },
        )

    def remove_device(
        self,
        *,
        device_token: Secret,
        device_id: str,
        parent_id: str,
        second_hash: Secret | str,
    ) -> None:
        self._post(
            "/parent/remove-device",
            {
                "deviceAuthToken": device_token.reveal(),
                "deviceId": device_id,
                "parentUserId": parent_id,
                "parentPasswordSecondHash": _plain(second_hash),
            },
        )

    def add_child_device(
        self, *, register_token: str, device_name: str, device_model: str
    ) -> dict[str, Any]:
        return self._post(
            "/child/add-device",
            {
                "registerToken": register_token,
                "deviceName": device_name,
                "childDevice": {"model": device_model},
                "clientLevel": CLIENT_LEVEL,
            },
        )

    def pull_status(
        self, device_token: Secret, status: dict[str, Any]
    ) -> dict[str, Any]:
        """``status`` is the ClientDataStatus; ``clientLevel`` is always set to ours."""
        return self._post(
            "/sync/pull-status",
            {
                "deviceAuthToken": device_token.reveal(),
                "status": {**status, "clientLevel": CLIENT_LEVEL},
            },
        )

    def push_actions(self, device_token: Secret, actions: list[dict[str, Any]]) -> bool:
        """Returns the server's ``shouldDoFullSync``."""
        answer = self._post(
            "/sync/push-actions",
            {"deviceAuthToken": device_token.reveal(), "actions": actions},
        )
        return bool(answer["shouldDoFullSync"])

    def is_device_removed(self, device_token: Secret) -> bool:
        answer = self._post(
            "/sync/is-device-removed", {"deviceAuthToken": device_token.reveal()}
        )
        return bool(answer["isDeviceRemoved"])


def _plain(value: Secret | str) -> str:
    return value.reveal() if isinstance(value, Secret) else value
