"""Categories of a child (plan E6a)."""

from __future__ import annotations

from flask import Blueprint, current_app, jsonify, request
from flask.typing import ResponseReturnValue

from dashboard.services.categories import CategoriesService

bp = Blueprint("categories", __name__)


def service() -> CategoriesService:
    found: CategoriesService = current_app.extensions["dashboard"]["categories"]
    return found


def _ok() -> ResponseReturnValue:
    return jsonify({"status": "ok"})


@bp.post("/api/children/<child_id>/categories")
def create(child_id: str) -> ResponseReturnValue:
    category_id = service().create(child_id, request.get_json(silent=True))
    return jsonify({"status": "ok", "category_id": category_id}), 201


@bp.put("/api/children/<child_id>/categories/<category_id>")
def update(child_id: str, category_id: str) -> ResponseReturnValue:
    service().update(child_id, category_id, request.get_json(silent=True))
    return _ok()


@bp.delete("/api/children/<child_id>/categories/<category_id>")
def delete(child_id: str, category_id: str) -> ResponseReturnValue:
    service().delete(child_id, category_id)
    return _ok()


@bp.post("/api/children/<child_id>/categories/<category_id>/move")
def move(child_id: str, category_id: str) -> ResponseReturnValue:
    service().move(child_id, category_id, request.get_json(silent=True))
    return _ok()


@bp.put("/api/children/<child_id>/categories/<category_id>/disable-limits")
def disable_limits(child_id: str, category_id: str) -> ResponseReturnValue:
    service().disable_limits(child_id, category_id, request.get_json(silent=True))
    return _ok()


@bp.put("/api/children/<child_id>/unassigned-category")
def unassigned(child_id: str) -> ResponseReturnValue:
    service().set_unassigned(child_id, request.get_json(silent=True))
    return _ok()
