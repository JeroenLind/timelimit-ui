"""Live updates: the Socket.IO listener, the polling fallback and the session state (plan B6, FR-207).

* A listener thread keeps one Socket.IO connection to the TimeLimit server (``devicelogin`` after every
  connect, ``should sync`` -> pull, ``sign out`` -> the session is over). It reconnects with a growing
  wait (:class:`Backoff`) and uses its own loop, not the library's reconnect, so the waits are exactly
  the configured ones.
* While the socket is down a polling thread asks the worker for a pull every ``poll_interval`` seconds
  (TR-105 safety net). When the socket is back, polling stops by itself.
* Pulls are always jobs on the sync worker; bursts of ``should sync`` are coalesced into one queued pull.
* When a pull changed the cache, one event goes to the SSE hub.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from typing import Any
from urllib.parse import urlsplit

import socketio

from dashboard.domain.errors import DashboardError, ErrorCode
from dashboard.domain.secret import Secret
from dashboard.logs import fields, get_logger
from dashboard.sync.hub import EventHub
from dashboard.sync.pull import PullResult
from dashboard.sync.worker import Backoff, SyncWorker, WorkerStopped

log = get_logger("sync.live")

STATE_OK = "ok"
STATE_SESSION_INVALID = "session_invalid"

PullFunction = Callable[[], PullResult]


class LiveSync:
    def __init__(
        self,
        *,
        server_url: str,
        device_token: Secret,
        pull: PullFunction,
        worker: SyncWorker,
        hub: EventHub,
        poll_interval: float,
        backoff_initial: float,
        backoff_max: float,
        connect_timeout: float = 5.0,
        transports: tuple[str, ...] = ("websocket",),
    ) -> None:
        parts = urlsplit(server_url)
        self._origin = f"{parts.scheme}://{parts.netloc}"
        self._socket_path = f"{parts.path.rstrip('/')}/socket.io".lstrip("/")
        self._token = device_token
        self._pull = pull
        self._worker = worker
        self._hub = hub
        self._poll_interval = poll_interval
        self._backoff = Backoff(backoff_initial, backoff_max)
        self._connect_timeout = connect_timeout
        self._transports = list(transports)
        self._stop = threading.Event()
        self._connected = threading.Event()
        self._session_invalid = threading.Event()
        self._pull_queued = threading.Lock()
        self._pull_is_queued = False
        self._threads: list[threading.Thread] = []
        self.connect_attempts: list[
            float
        ] = []  # monotonic times, for diagnostics and tests
        self.pulls_started = 0

    # -- state ------------------------------------------------------------------------------------------------------
    @property
    def socket_connected(self) -> bool:
        return self._connected.is_set()

    @property
    def state(self) -> str:
        return STATE_SESSION_INVALID if self._session_invalid.is_set() else STATE_OK

    # -- life cycle -------------------------------------------------------------------------------------------------
    def start(self) -> None:
        for name, target in (("socket-listener", self._listen), ("poller", self._poll)):
            thread = threading.Thread(target=target, name=name, daemon=True)
            thread.start()
            self._threads.append(thread)

    def stop(self, timeout: float = 5.0) -> bool:
        self._stop.set()
        deadline = time.monotonic() + timeout
        for thread in self._threads:
            thread.join(max(0.0, deadline - time.monotonic()))
        return not any(thread.is_alive() for thread in self._threads)

    # -- pulls ----------------------------------------------------------------------------------------------------
    def request_pull(self) -> None:
        """Queue one pull on the worker unless one is already waiting."""
        if self._session_invalid.is_set() or self._stop.is_set():
            return
        with self._pull_queued:
            if self._pull_is_queued:
                return
            self._pull_is_queued = True
        try:
            future = self._worker.submit(self._run_pull, retry=True)
        except WorkerStopped:
            with self._pull_queued:
                self._pull_is_queued = False
            return
        future.add_done_callback(self._pull_done)

    def _run_pull(self) -> PullResult:
        with self._pull_queued:
            self._pull_is_queued = (
                False  # a new should-sync during this pull queues the next one
            )
        self.pulls_started += 1
        return self._pull()

    def _pull_done(self, future: Any) -> None:
        try:
            result: PullResult = future.result()
        except WorkerStopped:
            return
        except DashboardError as error:
            if error.code is ErrorCode.SESSION_INVALID:
                self._end_session()
            else:
                log.info("background pull failed", extra=fields(code=error.code.value))
            return
        except Exception:
            log.exception("background pull crashed")
            return
        if result.changed:
            self._hub.publish({"type": "changed", "parts": sorted(result.changed)})

    def _end_session(self) -> None:
        if not self._session_invalid.is_set():
            self._session_invalid.set()
            log.warning("the server ended this session; link again")
            self._hub.publish({"type": "session_invalid"})

    # -- the socket -----------------------------------------------------------------------------------------------------
    def _set_connected(self, value: bool) -> None:
        if value == self._connected.is_set():
            return
        if value:
            self._connected.set()
        else:
            self._connected.clear()
        log.info("socket state changed", extra=fields(connected=value))
        self._hub.publish({"type": "live", "connected": value})

    def _listen(self) -> None:
        while not self._stop.is_set() and not self._session_invalid.is_set():
            self.connect_attempts.append(time.monotonic())
            self._one_connection()
            if self._stop.wait(self._backoff.next_delay()):
                return

    def _one_connection(self) -> None:
        """Connect, log in and stay until the socket drops, the session ends or we are stopped."""
        dropped = threading.Event()
        ready = threading.Event()
        client = socketio.Client(reconnection=False)

        @client.on("connect")  # type: ignore[untyped-decorator]
        def connected(*_: Any) -> None:
            ready.set()

        @client.on("connect_error")  # type: ignore[untyped-decorator]
        def connect_error(*_: Any) -> None:
            dropped.set()

        @client.on("should sync")  # type: ignore[untyped-decorator]
        def should_sync(*_: Any) -> None:
            self.request_pull()

        @client.on("sign out")  # type: ignore[untyped-decorator]
        def sign_out(*_: Any) -> None:
            self._end_session()
            dropped.set()

        @client.on("disconnect")  # type: ignore[untyped-decorator]
        def disconnect(*_: Any) -> None:
            dropped.set()

        try:
            client.connect(
                self._origin,
                socketio_path=self._socket_path,
                transports=self._transports,
                wait=False,  # waiting inside the library can block for a long time when the server refuses
            )
            deadline = time.monotonic() + self._connect_timeout
            while not ready.wait(0.05):
                if (
                    dropped.is_set()
                    or self._stop.is_set()
                    or time.monotonic() > deadline
                ):
                    raise ConnectionError("the socket did not open")
            if self._stop.is_set():
                raise ConnectionError("stopped while connecting")
            client.emit("devicelogin", self._token.reveal())
            self._backoff.reset()
            self._set_connected(True)
            self.request_pull()  # connect, login, pull once (ServerAPI section 6)
            while not dropped.wait(0.2):
                if self._stop.is_set():
                    break
        except Exception as error:  # noqa: BLE001 - any connection problem means "try again later"
            log.info("socket connect failed", extra=fields(error=type(error).__name__))
        finally:
            self._set_connected(False)
            try:
                # abort=True: do not wait for the library's read loop; it can sit in a long poll
                client.eio.disconnect(abort=True)
            except Exception:  # noqa: BLE001, S110 - the connection is gone anyway
                pass

    # -- the fallback -----------------------------------------------------------------------------------------------------
    def _poll(self) -> None:
        while not self._stop.wait(self._poll_interval):
            if self._session_invalid.is_set():
                return
            if not self._connected.is_set():
                self.request_pull()
