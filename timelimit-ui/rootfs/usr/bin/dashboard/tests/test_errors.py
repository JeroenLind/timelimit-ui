"""Plan step A4: one error envelope for all API routes, with a request id found in the log (TR-307)."""

from __future__ import annotations

import ast
import json
import re
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from flask import Flask, request
from flask.testing import FlaskClient

from dashboard.config import DATA_DIR_ENV, load_settings
from dashboard.domain.errors import DashboardError, ErrorCode
from dashboard.domain.secret import Secret
from dashboard.factory import create_app
from dashboard.logs import configure_logging, shutdown_logging
from dashboard.routes.errors import GENERIC_MESSAGE, HTTP_STATUS

ROUTES_DIR = Path(__file__).resolve().parents[1] / "routes"

# Design section 6 (decision Q3).
EXPECTED_STATUS = {
    "INVALID_INPUT": 400,
    "SESSION_INVALID": 401,
    "INVALID_PASSWORD": 403,
    "NOT_FOUND": 404,
    "NOT_LINKED": 409,
    "CONFLICT": 409,
    "READ_ONLY_OFFLINE": 503,
    "SERVER_UNREACHABLE": 502,
    "SERVER_TIMEOUT": 504,
    "ACTION_NOT_CONFIRMED": 502,
    "INTERNAL_ERROR": 500,
}
ENVELOPE_KEYS = {"status", "code", "message", "requestId"}


@pytest.fixture
def app(data_dir: Path) -> Iterator[Flask]:
    settings = load_settings(
        {DATA_DIR_ENV: str(data_dir), "DASHBOARD_LOG_LEVEL": "debug"}
    )
    configure_logging(settings, console=False)
    flask_app = create_app(settings, Secret("k" * 40))
    flask_app.testing = False  # let the handlers answer, as in production

    @flask_app.get("/api/_test/raise/<code>")
    def _raise_domain(code: str) -> str:
        raise DashboardError(ErrorCode(code), f"message for {code}")

    @flask_app.get("/api/_test/boom")
    def _boom() -> str:
        raise RuntimeError("secret internals: token=abc123")

    @flask_app.post("/api/_test/json")
    def _json() -> Any:
        return {"got": request.get_json()}

    @flask_app.get("/page")
    def _page() -> str:
        return "<html>ok</html>"

    yield flask_app
    shutdown_logging()


@pytest.fixture
def client(app: Flask) -> FlaskClient:
    return app.test_client()


def _log_entries(app: Flask) -> list[dict[str, Any]]:
    shutdown_logging()
    path = app.extensions["dashboard"]["settings"].log_file
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line
    ]


def test_every_code_has_the_agreed_status() -> None:
    assert {
        code.value: status for code, status in HTTP_STATUS.items()
    } == EXPECTED_STATUS
    assert {code.value for code in ErrorCode} == set(EXPECTED_STATUS)


@pytest.mark.parametrize("code", sorted(EXPECTED_STATUS))
def test_domain_error_gives_the_envelope(code: str, client: FlaskClient) -> None:
    response = client.get(f"/api/_test/raise/{code}")
    body = response.get_json()
    assert response.status_code == EXPECTED_STATUS[code]
    assert set(body) == ENVELOPE_KEYS
    assert body["status"] == "error"
    assert body["code"] == code
    assert body["message"] == f"message for {code}"
    assert body["requestId"] == response.headers["X-Request-ID"]


def test_unknown_exception_is_generic_500_without_internals(
    client: FlaskClient,
) -> None:
    response = client.get("/api/_test/boom")
    body = response.get_json()
    assert response.status_code == 500
    assert body["code"] == "INTERNAL_ERROR"
    assert body["message"] == GENERIC_MESSAGE
    text = response.get_data(as_text=True)
    assert (
        "Traceback" not in text and "RuntimeError" not in text and "abc123" not in text
    )


def test_the_trace_goes_to_the_log_with_the_request_id(
    app: Flask, client: FlaskClient
) -> None:
    request_id = client.get("/api/_test/boom").get_json()["requestId"]
    entry = next(e for e in _log_entries(app) if e["message"] == "unexpected error")
    assert entry["requestId"] == request_id
    assert "RuntimeError" in entry["exception"]


def test_request_id_of_a_domain_error_is_found_in_the_log(
    app: Flask, client: FlaskClient
) -> None:
    request_id = client.get("/api/_test/raise/CONFLICT").get_json()["requestId"]
    entries = [e for e in _log_entries(app) if e.get("requestId") == request_id]
    assert any(
        e["message"] == "request failed" and e["code"] == "CONFLICT" for e in entries
    )
    assert any(e["message"] == "request" and e["status"] == 409 for e in entries)


def test_framework_errors_use_the_envelope_on_api_paths(client: FlaskClient) -> None:
    cases = [
        (client.get("/api/does-not-exist"), 404, "NOT_FOUND"),
        (client.post("/api/health"), 400, "INVALID_INPUT"),  # 405 -> INVALID_INPUT
        (
            client.post(
                "/api/_test/json", data="{not json", content_type="application/json"
            ),
            400,
            "INVALID_INPUT",
        ),
        (
            client.post("/api/_test/json", data="x", content_type="text/plain"),
            400,
            "INVALID_INPUT",
        ),
    ]
    for response, status, code in cases:
        body = response.get_json()
        assert response.status_code == status, response.get_data(as_text=True)
        assert set(body) == ENVELOPE_KEYS and body["code"] == code


def test_non_api_paths_keep_the_normal_pages(client: FlaskClient) -> None:
    assert client.get("/page").status_code == 200
    missing = client.get("/no-such-page")
    assert missing.status_code == 404
    assert missing.get_json(silent=True) is None


def test_request_ids_are_unique_and_a_valid_incoming_one_is_kept(
    client: FlaskClient,
) -> None:
    first = client.get("/api/health").headers["X-Request-ID"]
    second = client.get("/api/health").headers["X-Request-ID"]
    assert first != second and re.fullmatch(r"[0-9a-f]{32}", first)
    kept = client.get("/api/health", headers={"X-Request-ID": "browser-req-0001"})
    assert kept.headers["X-Request-ID"] == "browser-req-0001"
    bad = client.get(
        "/api/health", headers={"X-Request-ID": "bad id with spaces & <tags>"}
    )
    assert re.fullmatch(r"[0-9a-f]{32}", bad.headers["X-Request-ID"])


def _api_rules(app: Flask) -> list[Any]:
    return [r for r in app.url_map.iter_rules() if r.rule.startswith("/api/")]


def test_every_registered_api_route_answers_failures_with_the_envelope(
    app: Flask, client: FlaskClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    rules = _api_rules(app)
    assert len(rules) >= 3
    for rule in rules:
        if rule.rule.startswith("/api/_test/raise"):
            continue
        methods = sorted(rule.methods - {"HEAD", "OPTIONS"})
        path = re.sub(r"<[^>]+>", "1", rule.rule)
        original = app.view_functions[rule.endpoint]
        for failure in (
            RuntimeError("forced"),
            DashboardError(ErrorCode.NOT_LINKED, "forced"),
        ):

            def _fail(
                *_args: Any, _failure: Exception = failure, **_kwargs: Any
            ) -> Any:
                raise _failure

            monkeypatch.setitem(app.view_functions, rule.endpoint, _fail)
            response = client.open(path, method=methods[0])
            body = response.get_json()
            assert set(body) == ENVELOPE_KEYS, f"{rule.rule}: {body}"
            assert body["code"] == (
                "INTERNAL_ERROR" if isinstance(failure, RuntimeError) else "NOT_LINKED"
            )
        monkeypatch.setitem(app.view_functions, rule.endpoint, original)


def _builds_error_by_hand(tree: ast.AST) -> list[int]:
    """Line numbers where a route builds an error response itself instead of raising."""
    lines = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Dict):
            keys = {k.value for k in node.keys if isinstance(k, ast.Constant)}
            if "error" in keys or "requestId" in keys:
                lines.append(node.lineno)
        if isinstance(node, ast.Return) and isinstance(node.value, ast.Tuple):
            for item in node.value.elts:
                if (
                    isinstance(item, ast.Constant)
                    and isinstance(item.value, int)
                    and item.value >= 400
                ):
                    lines.append(node.lineno)
    return lines


def test_routes_never_build_error_responses_by_hand() -> None:
    offenders = {}
    for path in sorted(ROUTES_DIR.glob("*.py")):
        if path.name == "errors.py":
            continue
        lines = _builds_error_by_hand(ast.parse(path.read_text(encoding="utf-8")))
        if lines:
            offenders[path.name] = lines
    assert offenders == {}, f"raise DashboardError instead: {offenders}"


def test_the_hand_built_error_check_catches_the_old_style() -> None:
    old_style = "def f():\n    return jsonify({'error': 'x'}), 400\n"
    assert _builds_error_by_hand(ast.parse(old_style))
    assert not _builds_error_by_hand(
        ast.parse("def f():\n    return jsonify({'ok': True})\n")
    )
