"""Parents and password actions (plan E10, FR-901, FR-902).

Rules, categories and extra time need no password (device integrity). Only two things do: signing the device
in as "Dashboard" again (``SET_KEEP_SIGNED_IN``, done by ``LinkService.finish``) and changing a parent's password
(``CHANGE_PARENT_PASSWORD``). The typed password is used in memory only; it goes to the log under a sensitive field name,
which masks it at info level and shows it at debug level only (Q13).
"""

from __future__ import annotations

import logging
from typing import Any

from dashboard.domain import actions, passwords
from dashboard.domain.errors import DashboardError, ErrorCode
from dashboard.domain.integrity import change_password_integrity, encrypt_second_hash
from dashboard.logs import fields
from dashboard.repository.cache import Scope
from dashboard.services.changes import ChangeService
from dashboard.services.profiles import ServerProfiles
from dashboard.sync.backend import Backend
from dashboard.sync.linking import DASHBOARD_NAME

log = logging.getLogger(__name__)
MIN_PASSWORD_LENGTH = 4


class ParentsService:
    def __init__(
        self, backend: Backend, profiles: ServerProfiles, changes: ChangeService
    ) -> None:
        self._backend = backend
        self._profiles = profiles
        self._changes = changes

    def _scope(self) -> Scope:
        scope = self._backend.scope(self._profiles.url())
        if scope is None:
            raise DashboardError(
                ErrorCode.NOT_LINKED, "This dashboard is not linked to a family yet."
            )
        return scope

    def overview(self) -> dict[str, Any]:
        """The parents of the family and the state of the "Dashboard" parent on this device."""
        scope = self._scope()
        cache = self._backend.cache
        link = self._backend.links.get(self._profiles.url())
        device = next(
            (
                d
                for d in cache.devices(scope)
                if link and d.data.get("deviceId") == link.own_device_id
            ),
            None,
        )
        parents: list[dict[str, Any]] = [
            {
                "id": str(u.data["id"]),
                "name": str(u.data.get("name", "")),
                "is_dashboard": u.data.get("name") == DASHBOARD_NAME,
            }
            for u in cache.users(scope)
            if u.data.get("type") == "parent" and u.on_server
        ]
        parents.sort(key=lambda p: (not p["is_dashboard"], str(p["name"]).casefold()))
        dashboard = next((p for p in parents if p["is_dashboard"]), None)
        signed_in = bool(
            device and dashboard and device.data.get("currentUserId") == dashboard["id"]
        )
        kept = bool(signed_in and device and device.data.get("isUserKeptSignedIn"))
        return {
            "status": "ok",
            "parents": parents,
            "dashboard": {
                "id": dashboard["id"] if dashboard else None,
                "signed_in": signed_in,
                "keep_signed_in": kept,
            },
        }

    def change_password(self, parent_id: str, body: object) -> None:
        """Change the password of a parent; needs the current one (the server checks it through the integrity value)."""
        if not isinstance(body, dict):
            raise DashboardError(ErrorCode.INVALID_INPUT, "Send a JSON object.", "body")
        current = body.get("current_password")
        new = body.get("new_password")
        if not isinstance(current, str) or not current:
            raise DashboardError(
                ErrorCode.INVALID_INPUT,
                "Enter the current password.",
                "current_password",
            )
        if not isinstance(new, str) or len(new) < MIN_PASSWORD_LENGTH:
            raise DashboardError(
                ErrorCode.INVALID_INPUT,
                f"Choose a new password of at least {MIN_PASSWORD_LENGTH} characters.",
                "new_password",
            )
        scope = self._scope()
        user = next(
            (
                u
                for u in self._backend.cache.users(scope)
                if u.data.get("id") == parent_id
                and u.data.get("type") == "parent"
                and u.on_server
            ),
            None,
        )
        if user is None:
            raise DashboardError(ErrorCode.NOT_FOUND, "This parent is not known.")
        log.info(
            "parent password change",
            extra=fields(
                user_id=parent_id,
                password=current,
                new_password=new,
            ),
        )
        if not passwords.password_matches(current, str(user.data["password"])):
            raise DashboardError(
                ErrorCode.INVALID_PASSWORD,
                "The current password is not correct.",
                "current_password",
            )
        old_second = passwords.second_hash_for(
            current, str(user.data["secondPasswordSalt"])
        )
        fresh = passwords.new_password(new)
        encrypted = encrypt_second_hash(
            old_second_hash=old_second, new_second_hash=fresh.second_hash
        )
        integrity = change_password_integrity(
            old_second_hash=old_second,
            user_id=parent_id,
            new_hash=fresh.hash,
            new_second_salt=fresh.second_salt,
            second_hash_encrypted=encrypted,
        )
        self._changes.push(
            [
                actions.change_parent_password(
                    parent_id, fresh.hash, fresh.second_salt, encrypted, integrity
                )
            ]
        )
