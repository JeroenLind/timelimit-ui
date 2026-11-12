"""Time limit rule off for today (FR-307, plan E3a, decisions W1-W6).

Switching off pushes ``UPDATE_TIMELIMIT_RULE`` without today's weekday bit and records a pending restore
in the database (it survives restarts and cache resets, W4). At the dashboard's midnight the bit is put
back by a timer; when the dashboard was not running, the overdue restore runs at the next start and a
notice says so. At restore the rule on the server is compared with the state the dashboard set: if it
differs or is gone, nothing is sent and a notice asks the parent to look (W5). Editing or deleting an off
rule restores it first, in the same push (W6). The server only ever sees ``UPDATE_TIMELIMIT_RULE``.
"""

from __future__ import annotations

import json
import threading
from dataclasses import dataclass
from typing import Any

from dashboard.domain import rule_today as pure
from dashboard.domain.actions import Action
from dashboard.domain.clock import Clock
from dashboard.domain.errors import DashboardError, ErrorCode
from dashboard.logs import fields, get_logger
from dashboard.repository.cache import Scope
from dashboard.repository.restores import PendingRestore
from dashboard.services.changes import ChangeService
from dashboard.services.connection import ConnectionService
from dashboard.services.profiles import ServerProfiles
from dashboard.services.rule_lookup import find_rule
from dashboard.sync.backend import Backend

log = get_logger("rule_today")

TICK_SECONDS = 30.0
LATE_AFTER_MS = (
    2 * 60 * 1000
)  # a restore this long after its due time is reported as late (dashboard was off)

NOTICE_RESTORED_LATE = "RULE_RESTORED_LATE"
NOTICE_SKIPPED = "RULE_RESTORE_SKIPPED"
NOTICE_OFF_ENDED = "RULE_OFF_ENDED"
MAX_NOTICES = 20


def _now_ms(clock: Clock) -> int:
    return int(clock.now().timestamp() * 1000)


@dataclass(frozen=True)
class Restore:
    """What a restore attempt did (for the callers and the tests)."""

    rule_id: str
    outcome: str  # "restored" | "skipped"


class RuleTodayService:
    def __init__(
        self,
        backend: Backend,
        profiles: ServerProfiles,
        changes: ChangeService,
        connection: ConnectionService,
        clock: Clock,
    ) -> None:
        self._backend = backend
        self._profiles = profiles
        self._changes = changes
        self._connection = connection
        self._clock = clock
        self._lock = threading.Lock()  # one switch-off or restore at a time

    # -- helpers ---------------------------------------------------------------------------------------------------
    def _scope(self) -> Scope:
        scope = self._backend.scope(self._profiles.url())
        if scope is None:
            raise DashboardError(
                ErrorCode.NOT_LINKED, "This dashboard is not linked to a family yet."
            )
        return scope

    def pending(self, rule_id: str) -> PendingRestore | None:
        return self._backend.restores.get(self._profiles.url(), rule_id)

    def pending_map(self) -> dict[str, PendingRestore]:
        url = self._profiles.url()
        return (
            {r.rule_id: r for r in self._backend.restores.for_profile(url)}
            if url
            else {}
        )

    def _audit(
        self, action: str, scope: Scope, category_id: str, detail: dict[str, Any]
    ) -> None:
        child_id = next(
            (
                str(c.data.get("childId", ""))
                for c in self._backend.cache.categories(scope)
                if str(c.data.get("categoryId")) == category_id
            ),
            None,
        )
        self._backend.audit.append(
            scope.profile_key,
            at=_now_ms(self._clock),
            action=action,
            child_id=child_id,
            category_id=category_id,
            detail=detail,
        )

    # -- the two things a parent does ----------------------------------------------------------------------------
    def switch_off(self, child_id: str, rule_id: str) -> None:
        with self._lock:
            scope = self._scope()
            category_id, rule = find_rule(self._backend, scope, child_id, rule_id)
            if self.pending(rule_id) is not None:
                raise DashboardError(
                    ErrorCode.CONFLICT, "This rule is already off for today.", "rule"
                )
            now = self._clock.now()
            mask = int(rule.get("dayMask", 0))
            if not pure.applies_on(mask, now):
                raise DashboardError(
                    ErrorCode.INVALID_INPUT, "This rule does not apply today.", "rule"
                )
            new_mask = pure.day_off(mask, now)
            restore = PendingRestore(
                profile_key=scope.profile_key,
                family_id=scope.family_id,
                category_id=category_id,
                rule_id=rule_id,
                day_bit=1 << now.weekday(),
                mask_set=new_mask,
                restore_at=int(pure.next_midnight(now).timestamp() * 1000),
                created_at=_now_ms(self._clock),
                rule_set=json.dumps(pure.snapshot(rule, new_mask), sort_keys=True),
            )
            # recorded first: a crash after the push must not leave the rule off for good
            self._backend.restores.add(restore)
            try:
                self._changes.push([pure.rule_action(rule_id, rule, new_mask)])
            except BaseException:
                self._backend.restores.remove(scope.profile_key, rule_id)
                raise
            self._audit(
                "rule_off_today",
                scope,
                category_id,
                {"rule_id": rule_id, "day_mask_before": mask},
            )

    def switch_on(self, child_id: str, rule_id: str) -> Restore:
        """Switch a rule on again before midnight."""
        with self._lock:
            scope = self._scope()
            pending = self.pending(rule_id)
            if pending is None:
                raise DashboardError(
                    ErrorCode.NOT_FOUND, "This rule is not off for today."
                )
            find_rule(self._backend, scope, child_id, rule_id)
            self._connection.require_online()
            return self._restore(scope, pending, late=False)

    # -- restoring --------------------------------------------------------------------------------------------------
    def _restore(self, scope: Scope, pending: PendingRestore, *, late: bool) -> Restore:
        current = next(
            (
                r.data
                for r in self._backend.cache.rules(scope, pending.category_id)
                if r.data.get("id") == pending.rule_id and r.on_server
            ),
            None,
        )
        expected = json.loads(pending.rule_set)
        if current is None or not pure.same_rule(expected, current):
            self._backend.restores.remove(scope.profile_key, pending.rule_id)
            self._notice(scope, NOTICE_SKIPPED, pending)
            self._audit(
                "rule_restore_skipped",
                scope,
                pending.category_id,
                {"rule_id": pending.rule_id, "missing": current is None},
            )
            self._backend.hub.publish({"type": "changed", "parts": ["notices"]})
            return Restore(pending.rule_id, "skipped")
        original = pure.day_back(pending.mask_set, pending.day_bit)
        self._changes.push([pure.rule_action(pending.rule_id, current, original)])
        self._backend.restores.remove(scope.profile_key, pending.rule_id)
        self._audit(
            "rule_restored",
            scope,
            pending.category_id,
            {"rule_id": pending.rule_id, "late": late},
        )
        if late:
            self._notice(scope, NOTICE_RESTORED_LATE, pending)
        return Restore(pending.rule_id, "restored")

    def tick(self) -> list[Restore]:
        """Restore everything that is due. Called by the timer and once at start; harmless when nothing is due."""
        url = self._profiles.url()
        link = self._backend.links.get(url) if url else None
        if not url or link is None:
            return []
        now_ms = _now_ms(self._clock)
        due = self._backend.restores.due(url, now_ms)
        if not due:
            return []
        done: list[Restore] = []
        with self._lock:
            try:
                self._connection.require_online()
                puller = self._backend.puller(url)
                self._backend.worker.run(
                    lambda: puller.pull(url, link.device_token, link.family_id),
                    timeout=30.0,
                )
            except DashboardError as error:
                log.info(
                    "restore waits: %s", error.code.value, extra=fields(due=len(due))
                )
                return []
            scope = Scope(url, link.family_id)
            for pending in due:
                late = now_ms - pending.restore_at > LATE_AFTER_MS
                try:
                    done.append(self._restore(scope, pending, late=late))
                except DashboardError as error:
                    # stays pending and is tried again at the next tick
                    log.warning(
                        "restore failed: %s",
                        error.code.value,
                        extra=fields(rule=pending.rule_id),
                    )
        return done

    # -- edit or delete of a rule that is off (W6) ------------------------------------------------------------
    def actions_before_change(
        self, rule_id: str, rule: dict[str, Any]
    ) -> tuple[list[Action], PendingRestore | None]:
        """The restore action to push in front of an edit or delete, and the pending record it ends."""
        pending = self.pending(rule_id)
        if pending is None:
            return [], None
        original = pure.day_back(pending.mask_set, pending.day_bit)
        return [pure.rule_action(rule_id, rule, original)], pending

    def ended_by_change(self, pending: PendingRestore) -> None:
        scope = self._scope()
        self._backend.restores.remove(scope.profile_key, pending.rule_id)
        self._notice(scope, NOTICE_OFF_ENDED, pending)
        self._audit(
            "rule_off_ended", scope, pending.category_id, {"rule_id": pending.rule_id}
        )

    # -- notices (kept until dismissed) ---------------------------------------------------------------------------------
    def _key(self, profile_key: str) -> str:
        return f"rule_notices:{profile_key}"

    def _load(self, profile_key: str) -> list[dict[str, Any]]:
        raw = self._backend.store.get(self._key(profile_key), "[]") or "[]"
        try:
            found = json.loads(raw)
        except ValueError:
            return []
        return found if isinstance(found, list) else []

    def _notice(self, scope: Scope, code: str, pending: PendingRestore) -> None:
        cache = self._backend.cache
        category = next(
            (
                c.data
                for c in cache.categories(scope)
                if str(c.data.get("categoryId")) == pending.category_id
            ),
            {},
        )
        child = next(
            (
                u.data.get("name", "")
                for u in cache.users(scope)
                if u.data.get("id") == category.get("childId")
            ),
            "",
        )
        items = self._load(scope.profile_key)
        next_id = max((int(i.get("id", 0)) for i in items), default=0) + 1
        items.append(
            {
                "id": next_id,
                "code": code,
                "child": child,
                "category": category.get("title", ""),
                "at": _now_ms(self._clock),
            }
        )
        self._backend.store.set(
            self._key(scope.profile_key), json.dumps(items[-MAX_NOTICES:])
        )

    def notices(self) -> list[dict[str, Any]]:
        url = self._profiles.url()
        return self._load(url) if url else []

    def dismiss(self, notice_id: int) -> None:
        url = self._profiles.url()
        if not url:
            return
        kept = [i for i in self._load(url) if int(i.get("id", 0)) != notice_id]
        self._backend.store.set(self._key(url), json.dumps(kept))


class RestoreTimer:
    """Calls ``tick`` now and then; one thread for the whole app. Stops with the backend."""

    def __init__(
        self, service: RuleTodayService, interval: float = TICK_SECONDS
    ) -> None:
        self._service = service
        self._interval = interval
        self._stop = threading.Event()
        self._thread = threading.Thread(
            target=self._run, name="rule-restore-timer", daemon=True
        )

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread.is_alive():
            self._thread.join(timeout=5.0)

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                self._service.tick()
            except Exception:  # a failed tick must never end the timer
                log.exception("restore tick failed")
            self._stop.wait(self._interval)
