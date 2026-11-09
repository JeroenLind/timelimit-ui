"""Builds the Flask application (routes only; every layer below is wired in later plan steps)."""

from __future__ import annotations

from flask import Flask

from dashboard.config import Settings
from dashboard.domain.clock import Clock
from dashboard.domain.secret import Secret
from dashboard.routes import health, pages, server, stream
from dashboard.routes.errors import register_error_handling
from dashboard.services.clock import SystemClock
from dashboard.services.connection import ConnectionService
from dashboard.sync.hub import EventHub


def create_app(
    settings: Settings, secret_key: Secret, clock: Clock | None = None
) -> Flask:
    """Create the app. Tests pass their own settings and a fake clock."""
    app = Flask("dashboard", static_folder="static", template_folder="templates")
    app.config["SECRET_KEY"] = secret_key.reveal()
    app.extensions["dashboard"] = {
        "settings": settings,
        "clock": clock or SystemClock(),
        "connection": ConnectionService(settings),
        "hub": EventHub(),
    }
    register_error_handling(app)
    app.register_blueprint(health.bp)
    app.register_blueprint(server.bp)
    app.register_blueprint(stream.bp)
    app.register_blueprint(pages.bp)
    return app
