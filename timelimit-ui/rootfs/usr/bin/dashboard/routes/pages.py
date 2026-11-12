"""The overview and settings pages (plan A7, E1)."""

from __future__ import annotations

from flask import Blueprint, current_app, redirect, render_template
from flask.typing import ResponseReturnValue

from dashboard.config import Settings
from dashboard.services.link import READY, SESSION_INVALID, LinkService

bp = Blueprint("pages", __name__)


def timings() -> dict[str, float]:
    settings: Settings = current_app.extensions["dashboard"]["settings"]
    return {
        "healthTimeout": settings.health_timeout,
        "healthInterval": settings.health_interval,
        "backoffInitial": settings.backoff_initial,
        "backoffMax": settings.backoff_max,
        "browserTimeout": settings.browser_timeout,
    }


@bp.get("/")
def overview_page() -> ResponseReturnValue:
    """Without a finished link the only page is the settings/link screen (plan E1)."""
    link: LinkService = current_app.extensions["dashboard"]["link"]
    if link.state() not in (READY, SESSION_INVALID):
        return redirect("/settings")
    return render_template("overview.html", timings=timings())


@bp.get("/settings")
def settings_page() -> ResponseReturnValue:
    return render_template("settings.html", timings=timings())
