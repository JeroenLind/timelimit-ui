"""Push parent actions to the TimeLimit server (see docs/ServerAPI.md section 5).

The server never reports a failed action: it skips it and answers ``shouldDoFullSync:
true`` with HTTP 200. This module therefore reports three separate outcomes instead of one
boolean:

* the request failed (network error, 400, 401, ...): ``request_ok`` is False;
* the server says at least one action was not applied: ``confirmed`` is False;
* everything was accepted: ``confirmed`` is True.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import action_builder
from action_builder import ActionError, MAX_ACTIONS_PER_REQUEST
from database import get_database, get_parent_user_id, reserve_sequence_numbers
from utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class PushResult:
    request_ok: bool
    confirmed: bool = False
    should_do_full_sync: bool = False
    sent: int = 0
    sequence_numbers: List[int] = field(default_factory=list)
    error_message: Optional[str] = None

    @property
    def summary(self) -> str:
        if not self.request_ok:
            return f"request failed: {self.error_message}"
        if not self.confirmed:
            return "server did not confirm all actions (shouldDoFullSync=true); at least one was not applied"
        return "all actions accepted"


def resolve_parent_user_id(db, device_auth_token: str, own_device_id: Optional[str]) -> Optional[str]:
    """The user this device is signed in as (``currentUserId`` of the own device).

    The device method of the server requires ``action.userId == currentUserId``. The
    synced devices table is the best source; the family record is the fallback.
    """
    if own_device_id:
        with db._lock:
            cursor = db.get_connection().cursor()
            cursor.execute(
                'SELECT current_user_id FROM devices WHERE id = ? AND device_auth_token = ?',
                (own_device_id, device_auth_token)
            )
            row = cursor.fetchone()
        if row and row[0] and action_builder.is_valid_id(row[0]):
            return row[0]
    return get_parent_user_id(db, device_auth_token)


def push_parent_actions(
    client,
    device_auth_token: str,
    own_device_id: Optional[str],
    actions: List[Dict[str, Any]],
    db=None,
    second_hash: Optional[str] = None,
) -> PushResult:
    """Sign and push parent actions.

    Uses ``integrity: "device"`` unless ``second_hash`` is given. Sequence numbers are
    reserved (and stored) before sending. Actions go out in batches of at most 25.

    Raises ActionError when the parent user cannot be determined or an action is
    malformed (nothing is sent in that case).
    """
    if not actions:
        return PushResult(request_ok=True, confirmed=True)
    db = db or get_database()
    parent_user_id = resolve_parent_user_id(db, device_auth_token, own_device_id)
    if not parent_user_id:
        raise ActionError("cannot determine the parent user id of this device; sync first")

    # Validate everything before a sequence number is reserved: a malformed action must not
    # consume numbers (the check uses a throw-away item with sequence number 0).
    for action in actions:
        action_builder.parent_item(
            action, 0, parent_user_id, own_device_id=own_device_id, second_hash=second_hash)

    first = reserve_sequence_numbers(db, device_auth_token, len(actions))
    items = [
        action_builder.parent_item(
            action, first + i, parent_user_id, own_device_id=own_device_id, second_hash=second_hash
        )
        for i, action in enumerate(actions)
    ]

    result = PushResult(request_ok=True, confirmed=True)
    for start in range(0, len(items), MAX_ACTIONS_PER_REQUEST):
        batch = items[start:start + MAX_ACTIONS_PER_REQUEST]
        response = client.push_actions(device_auth_token, batch)
        if not response.success:
            result.request_ok = False
            result.confirmed = False
            result.error_message = response.error_message or f"HTTP {response.status_code}"
            logger.warning("Push of parent actions failed", error=result.error_message, sent=result.sent)
            return result
        result.sent += len(batch)
        result.sequence_numbers.extend(i["sequenceNumber"] for i in batch)
        data = response.data if isinstance(response.data, dict) else {}
        if data.get("shouldDoFullSync"):
            result.should_do_full_sync = True
            result.confirmed = False
    if not result.confirmed:
        logger.warning("Server did not confirm all actions", sequence_numbers=result.sequence_numbers)
    return result
