"""Settings, notices and the debug export (plan E1, FR-100, FR-102, FR-104, TR-402)."""

from __future__ import annotations

from typing import Any

from flask import Blueprint, Response, current_app, jsonify, request
from flask.typing import ResponseReturnValue

from dashboard.domain.errors import DashboardError, ErrorCode
from dashboard.services.settings import SettingsService

bp = Blueprint("settings", __name__)


def service() -> SettingsService:
    found: SettingsService = current_app.extensions["dashboard"]["settings_service"]
    return found


def json_body() -> dict[str, Any]:
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        raise DashboardError(
            ErrorCode.INVALID_INPUT, "The request must be a JSON object."
        )
    return data


@bp.get("/api/settings")
def read_settings() -> ResponseReturnValue:
    return jsonify(service().view())


@bp.put("/api/settings/server")
def choose_server() -> ResponseReturnValue:
    data = json_body()
    port = data.get("port")
    if port in ("", None):
        port = None
    elif isinstance(port, str) and port.isdigit():
        port = int(port)
    service().select_server(
        str(data.get("mode", "")),
        str(data.get("protocol", "http")),
        str(data.get("address", "")),
        port,
    )
    return jsonify(service().view())


@bp.put("/api/settings/test-server")
def test_server_switch() -> ResponseReturnValue:
    data = json_body()
    if not isinstance(data.get("enabled"), bool):
        raise DashboardError(ErrorCode.INVALID_INPUT, "enabled must be true or false.")
    service().set_test_server(data["enabled"])
    return jsonify(service().view())


@bp.get("/api/notices")
def notices() -> ResponseReturnValue:
    return jsonify({"notices": service().notices()})


@bp.get("/api/settings/debug-export")
def debug_export() -> ResponseReturnValue:
    return Response(
        service().debug_export(),
        mimetype="text/plain",
        headers={"Content-Disposition": 'attachment; filename="dashboard-debug.txt"'},
    )
