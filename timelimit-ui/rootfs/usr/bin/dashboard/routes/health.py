"""``GET /api/health``: the dashboard itself is up (extended with the server state in plan step A7)."""

from __future__ import annotations

from flask import Blueprint, jsonify
from flask.typing import ResponseReturnValue

bp = Blueprint("health", __name__)


@bp.get("/api/health")
def health() -> ResponseReturnValue:
    return jsonify({"status": "ok"})
