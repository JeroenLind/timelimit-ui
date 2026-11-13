"""Builds the Flask application (routes only; every layer below is wired in later plan steps)."""

from __future__ import annotations

from flask import Flask

from dashboard.config import Settings
from dashboard.domain.clock import Clock
from dashboard.domain.secret import Secret
from dashboard.routes import (
    categories,
    children,
    health,
    link,
    pages,
    rules,
    server,
    stream,
)
from dashboard.routes import settings as settings_routes
from dashboard.routes.errors import register_error_handling
from dashboard.services.categories import CategoriesService
from dashboard.services.changes import ChangeService
from dashboard.services.children import ChildrenService
from dashboard.services.clock import SystemClock
from dashboard.services.connection import ConnectionService
from dashboard.services.link import LinkService
from dashboard.services.profiles import ServerProfiles
from dashboard.services.rule_today import RestoreTimer, RuleTodayService
from dashboard.services.rules import RulesService
from dashboard.services.settings import SettingsService
from dashboard.sync.backend import Backend
from dashboard.sync.hub import EventHub


def create_app(
    settings: Settings, secret_key: Secret, clock: Clock | None = None
) -> Flask:
    """Create the app. Tests pass their own settings and a fake clock."""
    app = Flask("dashboard", static_folder="static", template_folder="templates")
    app.config["SECRET_KEY"] = secret_key.reveal()
    clock = clock or SystemClock()
    hub = EventHub()
    backend = Backend(settings, hub, clock)
    profiles = ServerProfiles(backend.store, settings)
    link_service = LinkService(backend, profiles)
    connection = ConnectionService(settings, profiles)
    changes = ChangeService(backend, profiles, connection)
    rule_today = RuleTodayService(backend, profiles, changes, connection, clock)
    app.extensions["dashboard"] = {
        "settings": settings,
        "clock": clock,
        "connection": connection,
        "changes": changes,
        "rules": RulesService(backend, profiles, changes, rule_today),
        "categories": CategoriesService(backend, profiles, changes, clock),
        "rule_today": rule_today,
        "hub": hub,
        "backend": backend,
        "profiles": profiles,
        "link": link_service,
        "children": ChildrenService(backend, profiles, clock, rule_today),
        "settings_service": SettingsService(
            settings, backend, profiles, link_service, clock, rule_today
        ),
    }
    register_error_handling(app)
    app.register_blueprint(health.bp)
    app.register_blueprint(server.bp)
    app.register_blueprint(stream.bp)
    app.register_blueprint(settings_routes.bp)
    app.register_blueprint(link.bp)
    app.register_blueprint(children.bp)
    app.register_blueprint(rules.bp)
    app.register_blueprint(categories.bp)
    app.register_blueprint(pages.bp)
    link_service.resume()
    timer = RestoreTimer(rule_today)
    backend.on_close(timer.stop)
    timer.start()  # first tick at once: overdue restores run at start (W4)
    return app
