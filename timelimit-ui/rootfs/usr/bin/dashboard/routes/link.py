"""The link flow: mail code, join an existing family or create one on a test server (plan E1)."""

from __future__ import annotations

from flask import Blueprint, current_app, jsonify
from flask.typing import ResponseReturnValue

from dashboard.routes.settings import json_body
from dashboard.services.link import LinkService

bp = Blueprint("link", __name__)


def service() -> LinkService:
    found: LinkService = current_app.extensions["dashboard"]["link"]
    return found


def _text(data: dict[str, object], name: str) -> str:
    value = data.get(name, "")
    return value if isinstance(value, str) else ""


@bp.post("/api/link/mail-code")
def send_code() -> ResponseReturnValue:
    data = json_body()
    service().send_code(_text(data, "mail"), _text(data, "locale"))
    return jsonify(service().view())


@bp.post("/api/link/confirm-code")
def confirm_code() -> ResponseReturnValue:
    service().confirm_code(_text(json_body(), "code"))
    return jsonify(service().view())


@bp.post("/api/link/join")
def join() -> ResponseReturnValue:
    data = json_body()
    service().join(_text(data, "password"), _text(data, "time_zone"))
    return jsonify(service().view())


@bp.post("/api/link/finish")
def finish() -> ResponseReturnValue:
    service().finish(_text(json_body(), "password"))
    return jsonify(service().view())


@bp.post("/api/link/create-family")
def create_family() -> ResponseReturnValue:
    data = json_body()
    service().create_family(_text(data, "password"), _text(data, "time_zone"))
    return jsonify(service().view())


@bp.post("/api/link/unlink")
def unlink() -> ResponseReturnValue:
    service().unlink()
    return jsonify(service().view())
