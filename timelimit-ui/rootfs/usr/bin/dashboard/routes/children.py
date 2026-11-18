"""Children overview and child detail data, served from the cache (plan E2)."""

from __future__ import annotations

from flask import Blueprint, current_app, jsonify, redirect, render_template
from flask.typing import ResponseReturnValue

from dashboard.routes.pages import timings
from dashboard.services.audit import AuditService
from dashboard.services.children import ChildrenService
from dashboard.services.link import READY, SESSION_INVALID, LinkService
from dashboard.services.usage import UsageService

bp = Blueprint("children", __name__)


def service() -> ChildrenService:
    found: ChildrenService = current_app.extensions["dashboard"]["children"]
    return found


@bp.get("/api/children")
def children() -> ResponseReturnValue:
    return jsonify(service().overview())


@bp.get("/api/children/<child_id>")
def child(child_id: str) -> ResponseReturnValue:
    return jsonify(service().detail(child_id))


@bp.get("/api/children/<child_id>/usage")
def usage(child_id: str) -> ResponseReturnValue:
    found: UsageService = current_app.extensions["dashboard"]["usage"]
    return jsonify(found.usage(child_id))


@bp.get("/api/children/<child_id>/audit")
def child_audit(child_id: str) -> ResponseReturnValue:
    found: AuditService = current_app.extensions["dashboard"]["audit"]
    return jsonify(found.entries(child_id))


@bp.get("/api/audit")
def general_audit() -> ResponseReturnValue:
    found: AuditService = current_app.extensions["dashboard"]["audit"]
    return jsonify(found.entries(None))


@bp.get("/children/<child_id>")
def child_page(child_id: str) -> ResponseReturnValue:
    link: LinkService = current_app.extensions["dashboard"]["link"]
    if link.state() not in (READY, SESSION_INVALID):
        return redirect("/settings")
    return render_template("child.html", timings=timings(), child_id=child_id)
