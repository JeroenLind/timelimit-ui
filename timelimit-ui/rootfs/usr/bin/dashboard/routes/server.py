"""``GET /api/server/status``: the state of the TimeLimit server for the offline banner (FR-1000)."""

from __future__ import annotations

from flask import Blueprint, current_app, jsonify
from flask.typing import ResponseReturnValue

from dashboard.services.connection import ConnectionService

bp = Blueprint("server", __name__)


def connection() -> ConnectionService:
    service: ConnectionService = current_app.extensions["dashboard"]["connection"]
    return service


@bp.get("/api/server/status")
def server_status() -> ResponseReturnValue:
    return jsonify(connection().status().to_json())
