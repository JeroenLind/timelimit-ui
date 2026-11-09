"""Plan step B6: socket listener, polling fallback, SSE hub (FR-207, TR-105)."""

from __future__ import annotations

import itertools
import json
import threading
import time
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest

from ..domain.errors import DashboardError, ErrorCode
from ..sync.hub import EventHub
from ..sync.live import STATE_OK, STATE_SESSION_INVALID, LiveSync
from ..sync.pull import PullResult
from ..sync.worker import SyncWorker
from .fakeserver import FakeTimeLimitServer
from .fakeserver.state import version_id
from .test_pull import PROFILE
from .test_push import PushHarness


def wait_for(condition: Callable[[], bool], timeout: float = 5.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if condition():
            return True
        time.sleep(0.01)
    return condition()


class Live:
    def __init__(self, h: PushHarness, **overrides: float) -> None:
        self.h = h
        self.worker = SyncWorker(retries=0, retry_delay=0.01)
        self.worker.start()
        self.hub = EventHub()
        self.sub = self.hub.subscribe()
        settings = {
            "poll_interval": 0.2,
            "backoff_initial": 0.05,
            "backoff_max": 0.2,
            **overrides,
        }
        self.live = LiveSync(
            server_url=h.fake.url,
            device_token=h.token,
            pull=lambda: h.puller.pull(PROFILE, h.token, h.family_id),
            worker=self.worker,
            hub=self.hub,
            transports=("polling",),
            **settings,
        )

    def events(self) -> list[dict[str, object]]:
        found = []
        while not self.sub.events.empty():
            found.append(self.sub.events.get_nowait())
        return found

    def stop(self) -> None:
        assert self.live.stop(timeout=5.0), "listener threads did not stop"
        assert self.worker.stop(timeout=5.0)


@pytest.fixture
def h(fake_server: FakeTimeLimitServer, db_path: Path) -> Iterator[PushHarness]:
    yield PushHarness(fake_server, db_path)


@pytest.fixture
def live(h: PushHarness) -> Iterator[Live]:
    box = Live(h)
    box.live.start()
    assert wait_for(lambda: box.live.socket_connected)
    assert wait_for(lambda: box.live.pulls_started >= 1)  # the pull after connect
    time.sleep(0.2)
    box.events()
    yield box
    box.stop()


def rename_on_server(h: PushHarness, title: str) -> None:
    """A change made by someone else: the server data and its version change."""
    cat = h.family.categories["cat001"]
    cat.title = title
    cat.base_version = version_id()


def with_category(h: PushHarness) -> None:
    from ..domain import actions as act

    h.send(
        act.add_child_user("chd001", "Kid", "UTC"),
        act.create_category("chd001", "cat001", "Games"),
    )


def test_should_sync_runs_one_pull_and_one_event_reaches_the_browser(
    h: PushHarness, live: Live
) -> None:
    with_category(h)
    live.events()
    started = live.live.pulls_started
    rename_on_server(h, "Renamed")
    began = time.monotonic()
    h.fake.should_sync(h.token.reveal())
    assert wait_for(
        lambda: any(e["type"] == "changed" for e in live.events()), timeout=3.0
    )
    assert time.monotonic() - began < 5.0, "within the sync target"
    assert live.live.pulls_started == started + 1
    scope = h.cache.activate(PROFILE, h.family_id)
    assert [i.data["title"] for i in h.cache.categories(scope)] == ["Renamed"]


def test_a_burst_of_should_sync_is_coalesced(h: PushHarness, live: Live) -> None:
    h.fake.faults.delay_seconds = 0.1
    started = live.live.pulls_started
    for _ in range(10):
        h.fake.should_sync(h.token.reveal())
    assert wait_for(lambda: live.live.pulls_started > started)
    time.sleep(0.8)
    assert live.live.pulls_started - started <= 4, "ten notices must not mean ten pulls"


def test_polling_starts_when_the_socket_is_down_and_stops_when_it_is_back(
    h: PushHarness, live: Live
) -> None:
    h.fake.faults.refuse_socket = True
    h.fake.kick_sockets()
    assert wait_for(lambda: not live.live.socket_connected)
    before = live.live.pulls_started
    assert wait_for(lambda: live.live.pulls_started >= before + 2, timeout=3.0), (
        "polls while the socket is down"
    )
    h.fake.faults.refuse_socket = False
    assert wait_for(lambda: live.live.socket_connected, timeout=3.0)
    time.sleep(0.3)  # let the pull after the reconnect finish
    settled = live.live.pulls_started
    time.sleep(0.7)  # three poll intervals
    assert live.live.pulls_started == settled, "no polling while the socket works"
    events = [e for e in live.events() if e["type"] == "live"]
    assert [e["connected"] for e in events] == [False, True]


def test_sign_out_ends_the_session_and_stops_reconnecting(
    h: PushHarness, live: Live
) -> None:
    h.fake.sign_out(h.token.reveal())
    assert wait_for(lambda: live.live.state == STATE_SESSION_INVALID)
    assert any(e["type"] == "session_invalid" for e in live.events())
    attempts = len(live.live.connect_attempts)
    time.sleep(0.5)
    assert len(live.live.connect_attempts) == attempts
    started = live.live.pulls_started
    live.live.request_pull()
    time.sleep(0.2)
    assert live.live.pulls_started == started, "no pulls with an ended session"


def test_a_session_invalid_answer_to_a_pull_ends_the_session(h: PushHarness) -> None:
    box = Live(h)

    def refused() -> PullResult:
        raise DashboardError(ErrorCode.SESSION_INVALID, "gone")

    box.live._pull = refused
    try:
        box.live.request_pull()
        assert wait_for(lambda: box.live.state == STATE_SESSION_INVALID)
        assert [e["type"] for e in box.events()] == ["session_invalid"]
    finally:
        box.worker.stop()


def test_reconnect_waits_grow_up_to_the_maximum(h: PushHarness) -> None:
    h.fake.faults.refuse_socket = True
    box = Live(h, backoff_initial=0.05, backoff_max=0.2)
    box.live.start()
    try:
        assert wait_for(lambda: len(h.fake.world.socket_connects) >= 6, timeout=5.0)
        times = h.fake.world.socket_connects  # the fake records every connect attempt
        gaps = [b - a for a, b in itertools.pairwise(times)]
        assert gaps[0] >= 0.05 and gaps[1] >= 0.1 and gaps[2] >= 0.2, gaps
        assert max(gaps) < 0.2 + 0.25, f"capped at the maximum: {gaps}"
        assert state_ok(box)
    finally:
        box.stop()


def state_ok(box: Live) -> bool:
    return box.live.state == STATE_OK and not box.live.socket_connected


def test_a_good_connection_resets_the_wait(h: PushHarness, live: Live) -> None:
    h.fake.kick_sockets()
    assert wait_for(lambda: not live.live.socket_connected)
    assert wait_for(lambda: live.live.socket_connected, timeout=3.0)
    times = live.live.connect_attempts
    assert times[-1] - times[-2] < 0.5


def test_the_base_path_of_the_server_url_is_used_for_the_socket() -> None:
    def path(url: str) -> str:
        return LiveSync(
            server_url=url,
            device_token=None,  # type: ignore[arg-type]
            pull=lambda: None,  # type: ignore[arg-type, return-value]
            worker=None,  # type: ignore[arg-type]
            hub=EventHub(),
            poll_interval=1,
            backoff_initial=1,
            backoff_max=2,
        )._socket_path

    assert path("https://host.example") == "socket.io"
    assert path("https://host.example/timelimit/") == "timelimit/socket.io"


# -- the hub and the stream ---------------------------------------------------------------------------------------------


def test_hub_delivers_to_every_subscriber_and_forgets_closed_ones() -> None:
    hub = EventHub()
    a, b = hub.subscribe(), hub.subscribe()
    hub.publish({"type": "changed", "parts": ["rules"]})
    assert (
        a.events.get_nowait()
        == b.events.get_nowait()
        == {"type": "changed", "parts": ["rules"]}
    )
    hub.unsubscribe(a)
    assert hub.subscribers == 1


def test_a_stuck_subscriber_never_blocks_the_publisher_and_loses_the_oldest() -> None:
    hub = EventHub()
    sub = hub.subscribe()
    for n in range(250):
        hub.publish({"type": "changed", "n": n})
    kept = [sub.events.get_nowait()["n"] for _ in range(sub.events.qsize())]
    assert kept[-1] == 249 and len(kept) == 100 and kept == sorted(kept)


def test_stream_format_and_keepalive() -> None:
    hub = EventHub()
    sub = hub.subscribe()
    lines = hub.stream(sub, keepalive=0.05)
    assert next(lines) == "retry: 3000\n\n"
    assert next(lines) == ": keepalive\n\n"
    hub.publish({"type": "live", "connected": True})
    text = next(lines)
    assert text.startswith("event: live\ndata: ")
    assert json.loads(text.split("data: ")[1]) == {"type": "live", "connected": True}
    hub.unsubscribe(sub)
    assert list(lines) == []


def test_the_stream_route_sends_events_to_the_browser(data_dir: Path) -> None:
    from ..config import Settings
    from ..domain.secret import Secret
    from ..factory import create_app

    app = create_app(Settings(data_dir=data_dir), Secret("s"))
    hub: EventHub = app.extensions["dashboard"]["hub"]
    threading.Timer(
        0.2, hub.publish, args=({"type": "changed", "parts": ["devices"]},)
    ).start()
    with app.test_client() as client:
        response = client.get("/api/dashboard/stream", buffered=False)
        assert response.mimetype == "text/event-stream"
        chunks = iter(response.response)
        text = ""
        for _ in range(5):
            chunk = next(chunks)
            text += chunk.decode() if isinstance(chunk, bytes) else str(chunk)
            if "changed" in text:
                break
        assert "event: changed" in text
        response.close()
    assert wait_for(lambda: hub.subscribers == 0), (
        "the subscription ends with the browser"
    )
