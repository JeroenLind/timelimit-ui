"""Categories of a child (plan E6a)."""

from __future__ import annotations

from flask import Blueprint, current_app, jsonify, request
from flask.typing import ResponseReturnValue

from dashboard.services.apps import AppsService
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


@bp.put("/api/children/<child_id>/categories/<category_id>/extra-time")
def extra_time(child_id: str, category_id: str) -> ResponseReturnValue:
    service().set_extra_time(child_id, category_id, request.get_json(silent=True))
    return _ok()


@bp.put("/api/children/<child_id>/categories/<category_id>/temp-block")
def block(child_id: str, category_id: str) -> ResponseReturnValue:
    service().block_temporarily(child_id, category_id, request.get_json(silent=True))
    return _ok()


@bp.delete("/api/children/<child_id>/categories/<category_id>/temp-block")
def unblock(child_id: str, category_id: str) -> ResponseReturnValue:
    service().unblock(child_id, category_id)
    return _ok()


@bp.put("/api/children/<child_id>/categories/<category_id>/disable-limits")
def disable_limits(child_id: str, category_id: str) -> ResponseReturnValue:
    service().disable_limits(child_id, category_id, request.get_json(silent=True))
    return _ok()


@bp.put("/api/children/<child_id>/disable-limits")
def disable_child_limits(child_id: str) -> ResponseReturnValue:
    service().disable_child_limits(child_id, request.get_json(silent=True))
    return _ok()


@bp.put("/api/children/<child_id>/unassigned-category")
def unassigned(child_id: str) -> ResponseReturnValue:
    service().set_unassigned(child_id, request.get_json(silent=True))
    return _ok()


@bp.put("/api/children/<child_id>/categories/<category_id>/notifications")
def notifications(child_id: str, category_id: str) -> ResponseReturnValue:
    service().set_notifications(child_id, category_id, request.get_json(silent=True))
    return _ok()


@bp.put("/api/children/<child_id>/categories/<category_id>/time-warnings")
def time_warnings(child_id: str, category_id: str) -> ResponseReturnValue:
    service().set_time_warnings(child_id, category_id, request.get_json(silent=True))
    return _ok()


@bp.put("/api/children/<child_id>/categories/<category_id>/battery")
def battery(child_id: str, category_id: str) -> ResponseReturnValue:
    service().set_battery(child_id, category_id, request.get_json(silent=True))
    return _ok()


@bp.put("/api/children/<child_id>/categories/<category_id>/network-list")
def network_list(child_id: str, category_id: str) -> ResponseReturnValue:
    service().set_network_list(child_id, category_id, request.get_json(silent=True))
    return _ok()


@bp.delete("/api/children/<child_id>/categories/<category_id>/networks")
def reset_networks(child_id: str, category_id: str) -> ResponseReturnValue:
    service().reset_networks(child_id, category_id)
    return _ok()


def apps_service() -> AppsService:
    found: AppsService = current_app.extensions["dashboard"]["apps"]
    return found


@bp.get("/api/children/<child_id>/apps")
def apps(child_id: str) -> ResponseReturnValue:
    return jsonify(apps_service().overview(child_id))


@bp.post("/api/children/<child_id>/categories/<category_id>/apps")
def assign_apps(child_id: str, category_id: str) -> ResponseReturnValue:
    apps_service().assign(child_id, category_id, request.get_json(silent=True))
    return _ok()


@bp.post("/api/children/<child_id>/categories/<category_id>/apps/remove")
def remove_apps(child_id: str, category_id: str) -> ResponseReturnValue:
    apps_service().unassign(child_id, category_id, request.get_json(silent=True))
    return _ok()
