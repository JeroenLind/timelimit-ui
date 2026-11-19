"""A test reverse proxy that behaves like Home Assistant ingress (plan step F1).

It serves the app under ``/api/hassio_ingress/<token>/``: the prefix is stripped, the app gets it in
``X-Ingress-Path``, and every request outside the prefix is recorded in ``stray`` (and answered 404), so
a test fails when the page ever asks for the root of the host.
"""

from __future__ import annotations

import http.client
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

TOKEN = "abcDEF123_test-token"
PREFIX = f"/api/hassio_ingress/{TOKEN}"
_HOP_BY_HOP = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailers",
    "transfer-encoding",
    "upgrade",
    "host",
}


class IngressProxy:
    def __init__(self, upstream_port: int) -> None:
        self.stray: list[str] = []
        self.requests: list[str] = []
        proxy = self

        class Handler(BaseHTTPRequestHandler):
            protocol_version = (
                "HTTP/1.0"  # the body of a stream ends when the connection closes
            )

            def log_message(self, format: str, *args: object) -> None:
                return

            def _forward(self) -> None:
                path = self.path
                if path != PREFIX and not path.startswith(PREFIX + "/"):
                    proxy.stray.append(f"{self.command} {path}")
                    self.send_error(404, "outside the ingress prefix")
                    return
                proxy.requests.append(f"{self.command} {path}")
                inner = path[len(PREFIX) :] or "/"
                length = int(self.headers.get("Content-Length") or 0)
                body = self.rfile.read(length) if length else None
                headers = {
                    k: v
                    for k, v in self.headers.items()
                    if k.lower() not in _HOP_BY_HOP
                }
                headers["X-Ingress-Path"] = PREFIX
                conn = http.client.HTTPConnection(
                    "127.0.0.1", upstream_port, timeout=60
                )
                try:
                    conn.request(self.command, inner, body=body, headers=headers)
                    response = conn.getresponse()
                    self.send_response(response.status)
                    for key, value in response.getheaders():
                        if key.lower() not in _HOP_BY_HOP:
                            self.send_header(key, value)
                    self.end_headers()
                    while True:
                        chunk = response.read1(8192)
                        if not chunk:
                            break
                        self.wfile.write(chunk)
                        self.wfile.flush()
                except (BrokenPipeError, ConnectionResetError):
                    pass
                finally:
                    conn.close()

            do_GET = do_POST = do_PUT = do_DELETE = _forward

        self._server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self._server.daemon_threads = True
        self.url = f"http://127.0.0.1:{self._server.server_port}{PREFIX}"
        self._thread = threading.Thread(
            target=lambda: self._server.serve_forever(poll_interval=0.02), daemon=True
        )
        self._thread.start()

    def stop(self) -> None:
        self._server.shutdown()
        self._server.server_close()
        self._thread.join(timeout=5)
