"""The HTML pages and the read-only overview data (plan A7)."""

from __future__ import annotations

from flask import Blueprint, current_app, jsonify, render_template
from flask.typing import ResponseReturnValue

from dashboard.config import Settings
from dashboard.services.overview import overview_items

bp = Blueprint("pages", __name__)


@bp.get("/")
def overview_page() -> ResponseReturnValue:
    settings: Settings = current_app.extensions["dashboard"]["settings"]
    return render_template(
        "overview.html",
        timings={
            "healthTimeout": settings.health_timeout,
            "healthInterval": settings.health_interval,
            "backoffInitial": settings.backoff_initial,
            "backoffMax": settings.backoff_max,
            "browserTimeout": settings.browser_timeout,
        },
    )


@bp.get("/api/overview")
def overview_data() -> ResponseReturnValue:
    """Served from the cache, so it works while the server is down."""
    return jsonify({"items": overview_items()})
