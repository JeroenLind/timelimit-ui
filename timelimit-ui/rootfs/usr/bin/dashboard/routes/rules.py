"""Create, change and delete time limit rules (plan E3)."""

from __future__ import annotations

from flask import Blueprint, current_app, jsonify, request
from flask.typing import ResponseReturnValue

from dashboard.services.rules import RulesService

bp = Blueprint("rules", __name__)


def service() -> RulesService:
    found: RulesService = current_app.extensions["dashboard"]["rules"]
    return found


@bp.post("/api/children/<child_id>/categories/<category_id>/rules")
def create(child_id: str, category_id: str) -> ResponseReturnValue:
    rule_id = service().create(child_id, category_id, request.get_json(silent=True))
    return jsonify({"status": "ok", "rule_id": rule_id}), 201


@bp.put("/api/children/<child_id>/rules/<rule_id>")
def update(child_id: str, rule_id: str) -> ResponseReturnValue:
    service().update(child_id, rule_id, request.get_json(silent=True))
    return jsonify({"status": "ok"})


@bp.delete("/api/children/<child_id>/rules/<rule_id>")
def delete(child_id: str, rule_id: str) -> ResponseReturnValue:
    service().delete(child_id, rule_id)
    return jsonify({"status": "ok"})
