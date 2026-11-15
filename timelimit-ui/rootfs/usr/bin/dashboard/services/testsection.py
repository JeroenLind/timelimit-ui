"""The test section: add family members on a test server and look into the database (plan E11, FR-800, FR-801).

Only available while the switch "This is a test server" is on (Q9, Q11); otherwise every route here answers
404. A parent needs the password container for the server's DH key (FR-801); the typed password is used in
memory only. Adding a user is pushed through the same path as every change, so a server that does not
confirm gives ``ACTION_NOT_CONFIRMED`` (502).
"""

from __future__ import annotations

from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from dashboard.domain import actions, passwords
from dashboard.domain.errors import DashboardError, ErrorCode
from dashboard.domain.integrity import encrypt_parent_password
from dashboard.repository.cache import Scope
from dashboard.repository.inspector import DatabaseInspector
from dashboard.services.changes import ChangeService
from dashboard.services.profiles import ServerProfiles
from dashboard.sync.backend import Backend

MAX_ROWS = 200


def _invalid(field: str, message: str) -> DashboardError:
    return DashboardError(ErrorCode.INVALID_INPUT, message, field)


class TestSectionService:
    __test__ = False  # not a pytest class

    def __init__(
        self, backend: Backend, profiles: ServerProfiles, changes: ChangeService
    ) -> None:
        self._backend = backend
        self._profiles = profiles
        self._changes = changes

    # -- the gate ----------------------------------------------------------------------------------------------------
    def enabled(self) -> bool:
        return bool(self._profiles.url()) and self._profiles.test_server()

    def require(self) -> None:
        if not self.enabled():
            raise DashboardError(ErrorCode.NOT_FOUND, "This page does not exist.")

    def _scope(self) -> Scope:
        scope = self._backend.scope(self._profiles.url())
        if scope is None:
            raise DashboardError(
                ErrorCode.NOT_LINKED, "This dashboard is not linked to a family yet."
            )
        return scope

    # -- users ----------------------------------------------------------------------------------------------------------
    def users(self) -> dict[str, Any]:
        self.require()
        scope = self._scope()
        found: list[dict[str, Any]] = [
            {
                "id": str(u.data.get("id", "")),
                "name": str(u.data.get("name", "")),
                "type": str(u.data.get("type", "")),
                "time_zone": str(u.data.get("timeZone", "")),
                "on_server": u.on_server,
            }
            for u in self._backend.cache.users(scope)
        ]
        found.sort(key=lambda u: (str(u["type"]), str(u["name"]).casefold()))
        return {"status": "ok", "users": found}

    def add_user(self, body: object) -> str:
        self.require()
        if not isinstance(body, dict):
            raise _invalid("body", "Send a JSON object.")
        kind = body.get("type")
        if kind not in ("child", "parent"):
            raise _invalid("type", "Choose child or parent.")
        name = str(body.get("name") or "").strip()
        if not name or len(name) > 50:
            raise _invalid("name", "Enter a name of 1 to 50 characters.")
        zone = str(body.get("time_zone") or "").strip() or "UTC"
        try:
            ZoneInfo(zone)
        except (ZoneInfoNotFoundError, ValueError, OSError) as error:
            raise _invalid("time_zone", "This time zone is not known.") from error
        user_id = actions.new_id()
        if kind == "child":
            action = actions.add_child_user(user_id, name, zone)
        else:
            action = self._parent_action(user_id, name, zone, body.get("password"))
        self._changes.push([action])
        return user_id

    def _parent_action(
        self, user_id: str, name: str, zone: str, password: object
    ) -> dict[str, Any]:
        if not isinstance(password, str) or len(password) < 4:
            raise _invalid("password", "Choose a password of at least 4 characters.")
        key = self._backend.cache.dh_key(self._scope())
        if key is None:
            raise DashboardError(
                ErrorCode.INTERNAL_ERROR,
                "The server sent no key for a new parent (client level too low for this server).",
            )
        hashes = passwords.new_password(password)
        container = encrypt_parent_password(
            server_public_key=key[0],
            key_id=key[1],
            password_hash=hashes.hash,
            second_salt=hashes.second_salt,
            second_hash=hashes.second_hash,
        )
        return actions.add_parent_user(
            user_id, name, zone, hashes.hash, hashes.second_salt, container
        )

    # -- the database page -----------------------------------------------------------------------------------------
    def database(self) -> dict[str, Any]:
        """Every table with up to ``MAX_ROWS`` rows; columns that look like secrets are masked."""
        self.require()
        tables = DatabaseInspector(self._backend.db).tables(MAX_ROWS)
        return {"status": "ok", "tables": tables, "max_rows": MAX_ROWS}
