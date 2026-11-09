"""The sync worker: one thread, one queue, strictly serial (plan B5, TR-309, TR-304, NFR-001/002).

Everything that talks to the TimeLimit server for syncing (a user change, the socket listener, the poller)
is a job on this queue. Jobs run one at a time in the order they were submitted, so two syncs never
overlap and sequence numbers are used in order.

Retrying: a job submitted with ``retry=True`` is repeated after a network failure
(``SERVER_UNREACHABLE`` / ``SERVER_TIMEOUT``) up to ``retries`` times, ``retry_delay`` seconds apart. Only
jobs that are safe to repeat (pulls) may do that. A push is never repeated by the worker: the server may
have applied it already and a second run would, for example, add extra time twice, so the caller gets
the error and decides. After the retries the caller receives the last error. :class:`Backoff` gives the
growing wait for background loops (the poller, B6).
"""

from __future__ import annotations

import queue
import threading
from collections.abc import Callable
from concurrent.futures import Future
from concurrent.futures import TimeoutError as FutureTimeout
from typing import Any, TypeVar

from dashboard.domain.errors import DashboardError, ErrorCode
from dashboard.logs import fields, get_logger

log = get_logger("sync.worker")

T = TypeVar("T")
RETRYABLE = {ErrorCode.SERVER_UNREACHABLE, ErrorCode.SERVER_TIMEOUT}
_STOP = object()


class WorkerStopped(RuntimeError):
    """The worker is shutting down; the job was not (fully) run."""


class Backoff:
    """Waits that double from ``initial`` up to ``maximum`` and start over after :meth:`reset`."""

    def __init__(self, initial: float, maximum: float) -> None:
        if initial <= 0 or maximum < initial:
            raise ValueError("backoff needs 0 < initial <= maximum")
        self._initial = initial
        self._maximum = maximum
        self._next = initial

    def next_delay(self) -> float:
        delay = self._next
        self._next = min(self._next * 2, self._maximum)
        return delay

    def reset(self) -> None:
        self._next = self._initial


class _Job:
    def __init__(self, fn: Callable[[], Any], retry: bool) -> None:
        self.fn = fn
        self.retry = retry
        self.future: Future[Any] = Future()


class SyncWorker:
    def __init__(self, *, retries: int = 2, retry_delay: float = 0.25) -> None:
        self._retries = retries
        self._retry_delay = retry_delay
        self._queue: queue.Queue[Any] = queue.Queue()
        self._thread: threading.Thread | None = None
        self._stopping = threading.Event()
        self._lock = threading.Lock()

    def start(self) -> None:
        with self._lock:
            if self._thread is not None:
                return
            self._thread = threading.Thread(
                target=self._loop, name="sync-worker", daemon=True
            )
            self._thread.start()

    def stop(self, timeout: float = 5.0) -> bool:
        """Stop after the running job; queued jobs fail with :class:`WorkerStopped`. True when stopped."""
        with self._lock:
            self._stopping.set()
            thread = self._thread
            self._queue.put(_STOP)
        if thread is None:
            self._drain()
            return True
        thread.join(timeout)
        return not thread.is_alive()

    def submit(self, fn: Callable[[], T], *, retry: bool = False) -> Future[T]:
        """Queue a job; the future carries its result or its exception."""
        job = _Job(fn, retry)
        with self._lock:
            if self._stopping.is_set():
                raise WorkerStopped("the sync worker is stopped")
            if self._thread is None:
                raise WorkerStopped("the sync worker was not started")
            self._queue.put(job)
        return job.future

    def run(
        self, fn: Callable[[], T], *, retry: bool = False, timeout: float | None = None
    ) -> T:
        """Submit and wait for the result (a request waits for its job). Errors are re-raised as they are."""
        future = self.submit(fn, retry=retry)
        try:
            return future.result(timeout)
        except FutureTimeout as error:
            raise DashboardError(
                ErrorCode.SERVER_TIMEOUT, "The sync took too long."
            ) from error

    # -- the thread -----------------------------------------------------------------------------------------------
    def _loop(self) -> None:
        while True:
            item = self._queue.get()
            if item is _STOP:
                self._drain()
                return
            if self._stopping.is_set():
                item.future.set_exception(
                    WorkerStopped("the sync worker stopped before this job ran")
                )
                continue
            self._execute(item)

    def _drain(self) -> None:
        while True:
            try:
                item = self._queue.get_nowait()
            except queue.Empty:
                return
            if isinstance(item, _Job):
                item.future.set_exception(
                    WorkerStopped("the sync worker stopped before this job ran")
                )

    def _execute(self, job: _Job) -> None:
        if not job.future.set_running_or_notify_cancel():
            return
        attempts_left = self._retries if job.retry else 0
        while True:
            try:
                job.future.set_result(job.fn())
                return
            except DashboardError as error:
                if (
                    error.code in RETRYABLE
                    and attempts_left > 0
                    and not self._stopping.is_set()
                ):
                    attempts_left -= 1
                    log.info(
                        "sync job failed, retrying", extra=fields(code=error.code.value)
                    )
                    if self._stopping.wait(self._retry_delay):
                        job.future.set_exception(error)
                        return
                    continue
                job.future.set_exception(error)
                return
            except BaseException as error:  # noqa: BLE001 - a job's failure belongs to its caller
                job.future.set_exception(error)
                return
