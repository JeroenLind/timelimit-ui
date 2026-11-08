"""The link to a server: device token, own device id, family id and the sequence counter (plan B1).

One link per server profile. The sequence counter is the number the server expects for the next action
of this device; it only ever goes up, and survives a cache reset (a counter that went back would make
the server skip actions silently).
"""

from __future__ import annotations

from dataclasses import dataclass

from ..domain.secret import Secret
from .db import Database
from .session_file import SessionFile

# After a recovery from the session file the counter may lag by the last reservation; the server accepts
# jumps forward, so we skip ahead a little instead of risking a number it already saw.
RECOVERY_MARGIN = 100


@dataclass(frozen=True)
class Link:
    profile_key: str
    device_token: Secret
    own_device_id: str
    family_id: str
    mail: str
    next_sequence: int
    linked_at: int


class LinkRepository:
    def __init__(self, db: Database, session_file: SessionFile | None = None) -> None:
        self._db = db
        self._session = session_file

    def get(self, profile_key: str) -> Link | None:
        row = (
            self._db.connection()
            .execute("SELECT * FROM link WHERE profile_key=?", (profile_key,))
            .fetchone()
        )
        if row is not None:
            return _link(row)
        return self._recover(profile_key)

    def _recover(self, profile_key: str) -> Link | None:
        """The database has no link (it was lost or replaced): take it from the session file."""
        if self._session is None:
            return None
        saved = self._session.read().get(profile_key)
        if not saved:
            return None
        try:
            token, device_id, family_id = (
                str(saved["device_token"]),
                str(saved["own_device_id"]),
                str(saved["family_id"]),
            )
            counter = int(saved.get("next_sequence", 0)) + RECOVERY_MARGIN
            linked_at = int(saved.get("linked_at", 0))
        except (KeyError, ValueError, TypeError):
            return None
        with self._db.transaction() as conn:
            conn.execute(
                "INSERT INTO link (profile_key, device_token, own_device_id, family_id, mail, next_sequence, linked_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    profile_key,
                    token,
                    device_id,
                    family_id,
                    str(saved.get("mail", "")),
                    counter,
                    linked_at,
                ),
            )
        self._remember(profile_key)
        return self.get(profile_key)

    def set(
        self,
        profile_key: str,
        *,
        device_token: Secret,
        own_device_id: str,
        family_id: str,
        now_ms: int,
        mail: str = "",
    ) -> Link:
        """Link (or re-link) a profile. The counter restarts at 0 only for a different device id."""
        with self._db.transaction() as conn:
            row = conn.execute(
                "SELECT own_device_id FROM link WHERE profile_key=?", (profile_key,)
            ).fetchone()
            if row is None:
                conn.execute(
                    "INSERT INTO link (profile_key, device_token, own_device_id, family_id, mail, next_sequence, linked_at)"
                    " VALUES (?, ?, ?, ?, ?, 0, ?)",
                    (
                        profile_key,
                        device_token.reveal(),
                        own_device_id,
                        family_id,
                        mail,
                        now_ms,
                    ),
                )
            else:
                counter_reset = (
                    ", next_sequence=0" if row["own_device_id"] != own_device_id else ""
                )
                conn.execute(
                    "UPDATE link SET device_token=?, own_device_id=?, family_id=?, mail=?, linked_at=?"
                    + counter_reset
                    + " WHERE profile_key=?",
                    (
                        device_token.reveal(),
                        own_device_id,
                        family_id,
                        mail,
                        now_ms,
                        profile_key,
                    ),
                )
        self._remember(profile_key)
        link = self.get(profile_key)
        assert link is not None
        return link

    def reserve_sequence(self, profile_key: str) -> int:
        """The sequence number to put on the next action; the counter moves on atomically."""
        with self._db.transaction() as conn:
            row = conn.execute(
                "SELECT next_sequence FROM link WHERE profile_key=?", (profile_key,)
            ).fetchone()
            if row is None:
                raise LookupError(f"no link for {profile_key}")
            number = int(row["next_sequence"])
            conn.execute(
                "UPDATE link SET next_sequence=? WHERE profile_key=?",
                (number + 1, profile_key),
            )
        self._remember(profile_key)
        return number

    def clear(self, profile_key: str) -> None:
        """Unlink (new registration needed). The counter goes with it: a new device starts at 0."""
        with self._db.transaction() as conn:
            conn.execute("DELETE FROM link WHERE profile_key=?", (profile_key,))
        if self._session is not None:
            self._session.save(profile_key, None)

    def _remember(self, profile_key: str) -> None:
        if self._session is None:
            return
        link = self.get(profile_key)
        if link is None:
            return
        self._session.save(
            profile_key,
            {
                "device_token": link.device_token.reveal(),
                "own_device_id": link.own_device_id,
                "family_id": link.family_id,
                "mail": link.mail,
                "next_sequence": link.next_sequence,
                "linked_at": link.linked_at,
            },
        )


def _link(row: object) -> Link:
    r = row  # sqlite3.Row
    return Link(
        profile_key=r["profile_key"],  # type: ignore[index]
        device_token=Secret(r["device_token"]),  # type: ignore[index]
        own_device_id=r["own_device_id"],  # type: ignore[index]
        family_id=r["family_id"],  # type: ignore[index]
        mail=r["mail"],  # type: ignore[index]
        next_sequence=int(r["next_sequence"]),  # type: ignore[index]
        linked_at=int(r["linked_at"]),  # type: ignore[index]
    )
