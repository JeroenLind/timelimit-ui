"""The test section (plan E11): routes answer 404 unless the test-server switch is on."""

from __future__ import annotations

from flask import Blueprint, current_app, jsonify, render_template, request
from flask.typing import ResponseReturnValue

from dashboard.routes.pages import timings
from dashboard.services.testsection import TestSectionService

bp = Blueprint("testsection", __name__)


def service() -> TestSectionService:
    found: TestSectionService = current_app.extensions["dashboard"]["testsection"]
    return found


@bp.get("/test")
def page() -> ResponseReturnValue:
    service().require()
    return render_template("test.html", timings=timings())


@bp.get("/test/database")
def database_page() -> ResponseReturnValue:
    service().require()
    return render_template("debug_database.html", timings=timings())


@bp.get("/api/test/users")
def users() -> ResponseReturnValue:
    return jsonify(service().users())


@bp.post("/api/test/users")
def add_user() -> ResponseReturnValue:
    user_id = service().add_user(request.get_json(silent=True))
    return jsonify({"status": "ok", "user_id": user_id}), 201


@bp.get("/api/test/database")
def database() -> ResponseReturnValue:
    return jsonify(service().database())
