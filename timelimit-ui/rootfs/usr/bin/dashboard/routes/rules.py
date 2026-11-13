"""Create, change and delete time limit rules (plan E3)."""

from __future__ import annotations

from flask import Blueprint, current_app, jsonify, request
from flask.typing import ResponseReturnValue

from dashboard.services.rule_today import RuleTodayService
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
    service().delete(child_id, rule_id, request.args.get("version"))
    return jsonify({"status": "ok"})


def today() -> RuleTodayService:
    found: RuleTodayService = current_app.extensions["dashboard"]["rule_today"]
    return found


@bp.put("/api/children/<child_id>/rules/<rule_id>/off-today")
def off_today(child_id: str, rule_id: str) -> ResponseReturnValue:
    today().switch_off(child_id, rule_id)
    return jsonify({"status": "ok"})


@bp.delete("/api/children/<child_id>/rules/<rule_id>/off-today")
def on_again(child_id: str, rule_id: str) -> ResponseReturnValue:
    outcome = today().switch_on(child_id, rule_id)
    return jsonify({"status": "ok", "outcome": outcome.outcome})
