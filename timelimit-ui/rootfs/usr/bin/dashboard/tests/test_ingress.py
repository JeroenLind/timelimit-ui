"""Plan step F1: the app under a path prefix (Home Assistant ingress)."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest

from ..config import Settings
from ..domain.secret import Secret
from ..factory import create_app
from .ingress_proxy import PREFIX, IngressProxy

PAGES = ["/settings"]


@pytest.fixture
def app(data_dir: Path) -> Any:
    app = create_app(Settings(data_dir=data_dir), Secret("s"))
    yield app
    app.extensions["dashboard"]["backend"].close()


def page(app: Any, path: str, prefix: str | None) -> str:
    headers = {"X-Ingress-Path": prefix} if prefix is not None else {}
    response = app.test_client().get(path, headers=headers)
    assert response.status_code == 200, path
    html: str = response.get_data(as_text=True)
    return html


@pytest.mark.parametrize("path", PAGES)
def test_without_a_prefix_nothing_changes(app: Any, path: str) -> None:
    html = page(app, path, None)
    assert '<meta name="base-path" content="">' in html
    assert 'href="/settings"' in html
    assert 'src="/static/js/main.js"' in html


@pytest.mark.parametrize("path", PAGES)
def test_with_a_prefix_every_link_and_asset_carries_it(app: Any, path: str) -> None:
    html = page(app, path, PREFIX)
    assert f'<meta name="base-path" content="{PREFIX}">' in html
    # no root-absolute URL is left in an attribute
    assert re.findall(r'(?:href|src|action)="/(?!/|api/hassio_ingress/)', html) == []
    assert f'href="{PREFIX}/settings"' in html
    assert f'src="{PREFIX}/static/js/main.js"' in html


@pytest.mark.parametrize(
    "value",
    [
        "//evil.example",
        "/a b",
        "http://evil.example",
        "/a/../b",
        "/a;b",
        "javascript:1",
    ],
)
def test_a_strange_prefix_is_ignored(app: Any, value: str) -> None:
    html = page(app, "/settings", value)
    assert '<meta name="base-path" content="">' in html


def test_a_trailing_slash_is_dropped(app: Any) -> None:
    assert f'content="{PREFIX}"' in page(app, "/settings", PREFIX + "/")


def test_the_redirect_to_settings_keeps_the_prefix(app: Any) -> None:
    response = app.test_client().get("/", headers={"X-Ingress-Path": PREFIX})
    assert response.status_code == 302
    assert response.headers["Location"].endswith(f"{PREFIX}/settings")


def test_the_proxy_records_requests_outside_the_prefix(data_dir: Path) -> None:
    import http.client
    import threading

    from werkzeug.serving import make_server

    app = create_app(Settings(data_dir=data_dir), Secret("s"))
    server = make_server("127.0.0.1", 0, app)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    proxy = IngressProxy(server.server_port)
    try:
        host_port = proxy.url.split("/")[2]
        conn = http.client.HTTPConnection(host_port, timeout=5)
        conn.request("GET", "/api/health")
        assert conn.getresponse().status == 404
        conn.request("GET", f"{PREFIX}/api/health")
        assert conn.getresponse().status == 200
        assert proxy.stray == ["GET /api/health"]
    finally:
        proxy.stop()
        server.shutdown()
        app.extensions["dashboard"]["backend"].close()
