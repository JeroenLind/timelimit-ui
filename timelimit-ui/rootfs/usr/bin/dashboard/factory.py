"""Builds the Flask application (routes only; every layer below is wired in later plan steps)."""

from __future__ import annotations

import re
from typing import Any

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
    parents,
    rules,
    server,
    stream,
    testsection,
)
from dashboard.routes import settings as settings_routes
from dashboard.routes.errors import register_error_handling
from dashboard.services.apps import AppsService
from dashboard.services.audit import AuditService
from dashboard.services.categories import CategoriesService
from dashboard.services.changes import ChangeService
from dashboard.services.children import ChildrenService
from dashboard.services.clock import SystemClock
from dashboard.services.connection import ConnectionService
from dashboard.services.link import LinkService
from dashboard.services.parents import ParentsService
from dashboard.services.profiles import ServerProfiles
from dashboard.services.rule_today import RestoreTimer, RuleTodayService
from dashboard.services.rules import RulesService
from dashboard.services.settings import SettingsService
from dashboard.services.testsection import TestSectionService
from dashboard.services.usage import UsageService
from dashboard.sync.backend import Backend
from dashboard.sync.hub import EventHub

_INGRESS_PATH = re.compile(r"^(/[A-Za-z0-9._~-]+)+$")


class IngressPrefix:
    """Home Assistant ingress strips its path prefix and sends it in ``X-Ingress-Path``. The prefix is only
    needed to build links, so it becomes SCRIPT_NAME (``url_for``, ``request.script_root``). A value that
    is not a plain path is ignored."""

    def __init__(self, app: Any) -> None:
        self._app = app

    def __call__(self, environ: dict[str, Any], start_response: Any) -> Any:
        prefix = str(environ.get("HTTP_X_INGRESS_PATH", "")).rstrip("/")
        if prefix and _INGRESS_PATH.match(prefix) and ".." not in prefix.split("/"):
            environ["SCRIPT_NAME"] = prefix
        return self._app(environ, start_response)


def create_app(
    settings: Settings, secret_key: Secret, clock: Clock | None = None
) -> Flask:
    """Create the app. Tests pass their own settings and a fake clock."""
    app = Flask("dashboard", static_folder="static", template_folder="templates")
    app.wsgi_app = IngressPrefix(app.wsgi_app)  # type: ignore[method-assign]
    app.config["SECRET_KEY"] = secret_key.reveal()
    clock = clock or SystemClock()
    hub = EventHub()
    backend = Backend(settings, hub, clock)
    profiles = ServerProfiles(backend.store, settings)
    link_service = LinkService(backend, profiles)
    connection = ConnectionService(settings, profiles)
    audit = AuditService(backend, profiles, clock)
    changes = ChangeService(backend, profiles, connection, audit)
    rule_today = RuleTodayService(backend, profiles, changes, connection, clock)
    app.extensions["dashboard"] = {
        "settings": settings,
        "clock": clock,
        "connection": connection,
        "changes": changes,
        "rules": RulesService(backend, profiles, changes, rule_today),
        "categories": CategoriesService(backend, profiles, changes, clock),
        "apps": AppsService(backend, profiles, changes),
        "parents": ParentsService(backend, profiles, changes),
        "audit": audit,
        "usage": UsageService(backend, profiles, clock),
        "testsection": TestSectionService(backend, profiles, changes),
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

    @app.context_processor
    def _test_section() -> dict[str, bool]:
        return {"test_section": app.extensions["dashboard"]["testsection"].enabled()}

    app.register_blueprint(health.bp)
    app.register_blueprint(server.bp)
    app.register_blueprint(stream.bp)
    app.register_blueprint(settings_routes.bp)
    app.register_blueprint(link.bp)
    app.register_blueprint(children.bp)
    app.register_blueprint(rules.bp)
    app.register_blueprint(categories.bp)
    app.register_blueprint(testsection.bp)
    app.register_blueprint(parents.bp)
    app.register_blueprint(pages.bp)
    link_service.resume()
    timer = RestoreTimer(rule_today)
    backend.on_close(timer.stop)
    timer.start()  # first tick at once: overdue restores run at start (W4)
    return app
