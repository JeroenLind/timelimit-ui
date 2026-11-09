"""HTTP and Socket.IO layer of the fake TimeLimit server (plan A5).

Paths, bodies, status codes and the HTML error pages follow the real server (``src/api``).
Faults for tests are injected through ``Faults`` (see ``FakeTimeLimitServer``).
"""

from __future__ import annotations

import gzip
import json
import threading
import time
from dataclasses import dataclass, field
from typing import Any

import socketio
from flask import Flask, Response, jsonify, request

from . import schemas
from .actions import apply_action
from .state import Family, HttpError, World

_REASONS = {
    400: "Bad Request",
    401: "Unauthorized",
    403: "Forbidden",
    404: "Not Found",
    409: "Conflict",
    410: "Gone",
    429: "Too Many Requests",
    500: "Internal Server Error",
    503: "Service Unavailable",
}


@dataclass
class Faults:
    """Switches a test can flip to make the fake misbehave."""

    delay_seconds: float = 0.0
    fail_next: list[int] = field(default_factory=list)  # statuses for the next requests
    drop_connection: bool = False  # close the connection without answering
    active: int = 0  # requests being handled right now
    max_parallel: int = (
        0  # highest value `active` reached (tests assert serial use of the server)
    )
    lock: threading.Lock = field(default_factory=threading.Lock)


def html_error(status: int) -> Response:
    reason = _REASONS.get(status, "Error")
    body = f"<!DOCTYPE html><html><head><title>Error</title></head><body><pre>{reason}</pre></body></html>"
    return Response(body, status=status, mimetype="text/html")


def strip_expiry(status: dict[str, Any]) -> dict[str, Any]:
    """Copy of a status without rule ``e``: the variant with expiry is not in reference A's schema."""
    copy = dict(status)
    copy["rules"] = [
        {
            **entry,
            "rules": [{k: v for k, v in r.items() if k != "e"} for r in entry["rules"]],
        }
        for entry in status.get("rules", [])
    ]
    return copy


def create_app(
    world: World, faults: Faults, calls: list[tuple[str, str]]
) -> tuple[Flask, socketio.Server]:
    app = Flask("fake-timelimit-server")
    sio = socketio.Server(async_mode="threading", cors_allowed_origins="*")
    rooms: dict[str, str] = {}  # socket sid -> device auth token

    def emit_to_token(token: str, event: str, data: Any = None) -> None:
        for sid, tok in list(rooms.items()):
            if tok == token:
                sio.emit(event, data, to=sid)

    @sio.on("devicelogin")  # type: ignore[untyped-decorator]
    def devicelogin(sid: str, token: Any, ack: Any = None) -> None:
        if isinstance(token, str):
            rooms[sid] = token

    @sio.on("disconnect")  # type: ignore[untyped-decorator]
    def disconnect(sid: str, *_: Any) -> None:
        rooms.pop(sid, None)

    @app.before_request
    def inject_faults() -> Response | None:
        calls.append((request.method, request.path))
        with faults.lock:
            faults.active += 1
            faults.max_parallel = max(faults.max_parallel, faults.active)
        world.request_encodings.append(request.headers.get("Content-Encoding", ""))
        if faults.delay_seconds:
            time.sleep(faults.delay_seconds)
        if faults.drop_connection:
            raise ConnectionAbortedError
        if faults.fail_next:
            return html_error(faults.fail_next.pop(0))
        return None

    @app.teardown_request
    def request_done(_: BaseException | None) -> None:
        with faults.lock:
            faults.active -= 1

    @app.errorhandler(HttpError)
    def on_http_error(exc: HttpError) -> Response:
        return html_error(exc.status)

    def body(validator: str) -> dict[str, Any]:
        raw = request.get_data()
        if request.headers.get("Content-Encoding") == "gzip":
            try:
                raw = gzip.decompress(raw)
            except OSError as exc:
                raise HttpError(400) from exc
        try:
            data = json.loads(raw)
        except ValueError as exc:
            raise HttpError(400) from exc
        if not schemas.is_valid(validator, data):
            raise HttpError(400)
        assert isinstance(data, dict)
        return data

    def full_status(family: Family, client_level: int | None) -> dict[str, Any]:
        return world.server_status(family, {"clientLevel": client_level or 0})

    def checked(status: dict[str, Any]) -> dict[str, Any]:
        problems = schemas.status_errors(
            strip_expiry(status) if world.rule_expiry else status
        )
        assert not problems, (
            problems
        )  # the fake must never send what a strict client would reject
        return status

    @app.get("/time")
    def server_time() -> Response:
        return jsonify({"ms": int(time.time() * 1000)})

    @app.post("/auth/send-mail-login-code-v2")
    def send_code() -> Response:
        data = body("isSendMailLoginCodeRequest")
        mail = data["mail"].strip().lower()
        if "@" not in mail:
            raise HttpError(400)
        with world.lock:
            return jsonify({"mailLoginToken": world.send_login_code(mail)})

    @app.post("/auth/sign-in-by-mail-code")
    def sign_in_by_code() -> Response:
        data = body("isSignInByMailCodeRequest")
        with world.lock:
            return jsonify(
                {
                    "mailAuthToken": world.sign_in_by_code(
                        data["mailLoginToken"], data["receivedCode"]
                    )
                }
            )

    @app.post("/parent/get-status-by-mail-address")
    def status_by_mail() -> Response:
        data = body("isMailAuthTokenRequestBody")
        with world.lock:
            mail = world.mail_of_auth(data["mailAuthToken"], invalidate=False)
            status = "with family" if world.family_of_mail(mail) else "without family"
        return jsonify(
            {
                "status": status,
                "mail": mail,
                "canCreateFamily": True,
                "alwaysPro": False,
            }
        )

    def new_device_answer(
        family: Family, device_id: str, token: str, level: int | None
    ) -> Response:
        return jsonify(
            {
                "deviceAuthToken": token,
                "ownDeviceId": device_id,
                "data": checked(full_status(family, level)),
            }
        )

    @app.post("/parent/create-family")
    def create_family() -> Response:
        data = body("isCreateFamilyByMailTokenRequest")
        world.client_levels.append(data.get("clientLevel"))
        with world.lock:
            family, device = world.create_family(data)
            return new_device_answer(
                family, device.device_id, device.auth_token, data.get("clientLevel")
            )

    @app.post("/parent/sign-in-into-family")
    def sign_in_into_family() -> Response:
        data = body("isSignIntoFamilyRequest")
        with world.lock:
            family, device = world.sign_in_into_family(data)
            return new_device_answer(
                family, device.device_id, device.auth_token, data.get("clientLevel")
            )

    @app.post("/parent/create-add-device-token")
    def add_device_token() -> Response:
        data = body("isCreateRegisterDeviceTokenRequest")
        with world.lock:
            family, _, _ = world.assert_parent_auth(
                data["deviceAuthToken"],
                data["parentId"],
                data["parentPasswordSecondHash"],
            )
            token, device_id = world.create_add_device_token(family)
        return jsonify({"token": token, "deviceId": device_id})

    @app.post("/parent/remove-device")
    def remove_device() -> Response:
        data = body("isRemoveDeviceRequest")
        with world.lock:
            family, _, _ = world.assert_parent_auth(
                data["deviceAuthToken"],
                data["parentUserId"],
                data["parentPasswordSecondHash"],
            )
            gone = family.devices.get(data["deviceId"])
            gone_token = gone.auth_token if gone else ""
            world.remove_device(family, data["deviceId"])
            others = [d.auth_token for d in family.devices.values()]
        emit_to_token(gone_token, "sign out")
        for token in others:
            emit_to_token(token, "should sync", {"isImportant": True})
        return jsonify({"ok": True})

    @app.post("/child/add-device")
    def add_child_device() -> Response:
        data = body("isRegisterChildDeviceRequest")
        with world.lock:
            family, device = world.add_child_device(data)
            others = [d.auth_token for d in family.devices.values() if d is not device]
            answer = new_device_answer(
                family, device.device_id, device.auth_token, data.get("clientLevel")
            )
        for token in others:
            emit_to_token(token, "should sync", {"isImportant": True})
        return answer

    @app.post("/sync/pull-status")
    def pull_status() -> Response:
        data = body("isClientPullChangesRequest")
        world.client_levels.append(data["status"].get("clientLevel"))
        with world.lock:
            family, device = world.family_of_token(data["deviceAuthToken"])
            device.last_connectivity = int(time.time() * 1000)
            return jsonify(checked(world.server_status(family, data["status"])))

    @app.post("/sync/push-actions")
    def push_actions() -> Response:
        data = body("isClientPushChangesRequest")
        if len(data["actions"]) > 50:
            raise HttpError(400)
        full_sync = False
        level = 0
        with world.lock:
            family, device = world.family_of_token(data["deviceAuthToken"])
            for action in data["actions"]:
                outcome = apply_action(world, family, device.device_id, action)
                full_sync = full_sync or outcome.full_sync
                level = max(level, outcome.triggered_level)
            others = [d.auth_token for d in family.devices.values() if d is not device]
        if level:
            for token in others:
                emit_to_token(token, "should sync", {"isImportant": level == 2})
        return jsonify({"shouldDoFullSync": full_sync})

    @app.post("/sync/is-device-removed")
    def is_device_removed() -> Response:
        data = body("isRequestWithAuthToken")
        with world.lock:
            return jsonify(
                {"isDeviceRemoved": data["deviceAuthToken"] in world.old_device_tokens}
            )

    return app, sio


class ServerThread:
    """Runs the WSGI app (with Socket.IO) on an ephemeral port in a background thread."""

    def __init__(self, app: Flask, sio: socketio.Server, host: str, port: int) -> None:
        from werkzeug.serving import make_server

        wsgi = socketio.WSGIApp(sio, app)
        self._server = make_server(host, port, wsgi, threaded=True)
        self.port: int = self._server.server_port
        self._thread = threading.Thread(
            target=lambda: self._server.serve_forever(poll_interval=0.02),
            daemon=True,
            name="fake-timelimit",
        )

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._server.shutdown()
        self._server.server_close()
        self._thread.join(timeout=5)
