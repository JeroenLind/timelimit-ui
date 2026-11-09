"""``GET /api/dashboard/stream``: server-sent events for the browser (plan B6, design section 3)."""

from __future__ import annotations

from collections.abc import Iterator

from flask import Blueprint, Response, current_app, stream_with_context
from flask.typing import ResponseReturnValue

from dashboard.sync.hub import EventHub

bp = Blueprint("stream", __name__)


@bp.get("/api/dashboard/stream")
def stream() -> ResponseReturnValue:
    hub: EventHub = current_app.extensions["dashboard"]["hub"]
    subscription = hub.subscribe()

    def generate() -> Iterator[str]:
        try:
            yield from hub.stream(subscription)
        finally:
            hub.unsubscribe(subscription)

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
