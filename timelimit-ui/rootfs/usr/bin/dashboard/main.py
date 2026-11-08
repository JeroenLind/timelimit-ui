"""Start-up: settings, data folder, logging, secret key, app, server (``py -3 app.py``)."""

from __future__ import annotations

import socket
import sys

from werkzeug.serving import BaseWSGIServer, make_server

from dashboard.config import (
    ConfigError,
    Settings,
    ensure_data_dir,
    load_secret_key,
    load_settings,
)
from dashboard.factory import create_app
from dashboard.logs import configure_logging, fields, get_logger, shutdown_logging

EXIT_BAD_CONFIG = 2
EXIT_CANNOT_BIND = 1


def build_server(settings: Settings, app: object) -> BaseWSGIServer:
    """Bind the server to ``settings.host:settings.port`` (port 0 picks a free port).

    Werkzeug exits the process itself when the port is taken; a probe first turns that into an
    ``OSError`` that ``main`` reports with our own message.
    """
    if settings.port:
        socket.create_server((settings.host, settings.port)).close()
    return make_server(settings.host, settings.port, app, threaded=True)  # type: ignore[arg-type]


def main() -> int:
    try:
        settings = load_settings()
    except ConfigError as error:
        print(error, file=sys.stderr)
        return EXIT_BAD_CONFIG

    ensure_data_dir(settings)
    configure_logging(settings)
    log = get_logger("main")
    try:
        app = create_app(settings, load_secret_key(settings))
        server = build_server(settings, app)
    except OSError as error:
        log.error(
            "cannot listen",
            extra=fields(host=settings.host, port=settings.port, error=str(error)),
        )
        print(
            f"Cannot listen on {settings.host}:{settings.port}: {error}",
            file=sys.stderr,
        )
        shutdown_logging()
        return EXIT_CANNOT_BIND

    log.info(
        "started",
        extra=fields(
            host=settings.host, port=settings.port, data_dir=str(settings.data_dir)
        ),
    )
    print(
        f"Dashboard running on http://{settings.host}:{server.server_port}  (Ctrl+C to stop)"
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        log.info("stopped")
    finally:
        server.server_close()
        shutdown_logging()
    return 0
