"""Parents and password actions (plan E10)."""

from __future__ import annotations

from flask import Blueprint, current_app, jsonify, request
from flask.typing import ResponseReturnValue

from dashboard.services.parents import ParentsService

bp = Blueprint("parents", __name__)


def service() -> ParentsService:
    found: ParentsService = current_app.extensions["dashboard"]["parents"]
    return found


@bp.get("/api/parents")
def parents() -> ResponseReturnValue:
    return jsonify(service().overview())


@bp.post("/api/parents/<parent_id>/password")
def change_password(parent_id: str) -> ResponseReturnValue:
    service().change_password(parent_id, request.get_json(silent=True))
    return jsonify({"status": "ok"})
