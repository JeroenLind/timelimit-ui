"""Plan step B5: the sync worker (TR-309, TR-304, NFR-001, NFR-002)."""

from __future__ import annotations

import itertools
import threading
import time
from collections.abc import Iterator
from functools import partial
from pathlib import Path

import pytest

from ..domain import actions as act
from ..domain.errors import DashboardError, ErrorCode
from ..sync.worker import Backoff, SyncWorker, WorkerStopped
from .fakeserver import FakeTimeLimitServer
from .test_pull import PROFILE
from .test_push import PushHarness


@pytest.fixture
def worker() -> Iterator[SyncWorker]:
    w = SyncWorker(retries=2, retry_delay=0.05)
    w.start()
    yield w
    assert w.stop(timeout=3.0)


def unreachable() -> DashboardError:
    return DashboardError(ErrorCode.SERVER_UNREACHABLE, "down")


def test_twenty_concurrent_enqueues_run_serially_and_in_order(
    worker: SyncWorker,
) -> None:
    order: list[int] = []
    running = 0
    peak = 0
    guard = threading.Lock()

    def job(n: int) -> int:
        nonlocal running, peak
        with guard:
            running += 1
            peak = max(peak, running)
        time.sleep(0.002)
        order.append(n)
        with guard:
            running -= 1
        return n

    futures = [worker.submit(partial(job, n)) for n in range(20)]
    results = [f.result(timeout=5) for f in futures]
    assert results == list(range(20)) and order == list(range(20))
    assert peak == 1


def test_parallel_callers_never_make_the_server_see_parallel_requests(
    fake_server: FakeTimeLimitServer, db_path: Path, worker: SyncWorker
) -> None:
    h = PushHarness(fake_server, db_path)
    h.send(act.add_child_user("chd001", "Kid", "Europe/Amsterdam"))
    fake_server.faults.delay_seconds = 0.02
    fake_server.faults.max_parallel = 0
    threads = [
        threading.Thread(
            target=lambda: worker.run(
                lambda: h.puller.pull(PROFILE, h.token, h.family_id)
            )
        )
        for _ in range(20)
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=20)
    assert fake_server.faults.max_parallel == 1


def test_a_retryable_job_is_retried_twice_then_succeeds(worker: SyncWorker) -> None:
    calls = []

    def flaky() -> str:
        calls.append(time.monotonic())
        if len(calls) < 3:
            raise unreachable()
        return "ok"

    assert worker.run(flaky, retry=True) == "ok"
    assert len(calls) == 3
    assert all(later - earlier >= 0.045 for earlier, later in itertools.pairwise(calls))


def test_after_the_retries_the_caller_gets_server_unreachable(
    worker: SyncWorker,
) -> None:
    calls = []

    def down() -> None:
        calls.append(1)
        raise unreachable()

    with pytest.raises(DashboardError) as raised:
        worker.run(down, retry=True)
    assert raised.value.code is ErrorCode.SERVER_UNREACHABLE
    assert len(calls) == 3, "one run and two retries"


def test_a_job_without_retry_runs_once(worker: SyncWorker) -> None:
    calls = []

    def down() -> None:
        calls.append(1)
        raise unreachable()

    with pytest.raises(DashboardError):
        worker.run(down)
    assert len(calls) == 1


def test_errors_that_are_not_network_errors_are_not_retried(worker: SyncWorker) -> None:
    calls = []

    def refused() -> None:
        calls.append(1)
        raise DashboardError(ErrorCode.SESSION_INVALID, "no")

    with pytest.raises(DashboardError):
        worker.run(refused, retry=True)
    assert len(calls) == 1


def test_a_failing_job_does_not_stop_the_worker(worker: SyncWorker) -> None:
    with pytest.raises(ZeroDivisionError):
        worker.run(lambda: 1 / 0)
    assert worker.run(lambda: "still alive") == "still alive"


def test_a_slow_job_gives_the_caller_a_timeout_error(worker: SyncWorker) -> None:
    with pytest.raises(DashboardError) as raised:
        worker.run(lambda: time.sleep(0.3), timeout=0.05)
    assert raised.value.code is ErrorCode.SERVER_TIMEOUT


def test_a_change_is_in_the_cache_within_the_sync_target(
    fake_server: FakeTimeLimitServer, db_path: Path, worker: SyncWorker
) -> None:
    from ..config import Settings

    target = Settings().sync_target
    h = PushHarness(fake_server, db_path)
    started = time.monotonic()
    result = worker.run(
        lambda: h.pusher.push(
            PROFILE, h.parent_id, [act.add_child_user("chd001", "Kid", "UTC")]
        )
    )
    elapsed = time.monotonic() - started
    assert {i.data["id"] for i in h.cache.users(result.pull.scope)} >= {"chd001"}
    assert elapsed < target, f"{elapsed:.2f}s against a target of {target}s"


def test_stop_is_clean_and_fails_queued_jobs(worker: SyncWorker) -> None:
    release = threading.Event()
    blocker = worker.submit(release.wait)
    queued = worker.submit(lambda: "never")
    threading.Timer(0.1, release.set).start()
    assert worker.stop(timeout=3.0)
    assert blocker.result(timeout=1) is True
    with pytest.raises(WorkerStopped):
        queued.result(timeout=1)
    with pytest.raises(WorkerStopped):
        worker.submit(lambda: 1)


def test_stop_interrupts_a_retry_wait() -> None:
    slow = SyncWorker(retries=5, retry_delay=30.0)
    slow.start()
    future = slow.submit(lambda: (_ for _ in ()).throw(unreachable()), retry=True)
    time.sleep(0.1)
    started = time.monotonic()
    assert slow.stop(timeout=3.0)
    assert time.monotonic() - started < 2.0
    with pytest.raises(DashboardError):
        future.result(timeout=1)


def test_submitting_before_start_is_refused() -> None:
    with pytest.raises(WorkerStopped):
        SyncWorker().submit(lambda: 1)


def test_backoff_doubles_up_to_the_maximum_and_resets() -> None:
    backoff = Backoff(10.0, 30.0)
    assert [backoff.next_delay() for _ in range(4)] == [10.0, 20.0, 30.0, 30.0]
    backoff.reset()
    assert backoff.next_delay() == 10.0
    with pytest.raises(ValueError):
        Backoff(10.0, 5.0)
