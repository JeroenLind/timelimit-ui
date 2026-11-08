"""Action integrity checks of the real server (``apply-actions/integrity.ts``)."""

from __future__ import annotations

import base64
import hashlib
import hmac
import struct


def action_hmac(
    *, sequence_number: int, device_id: str, encoded_action: str, secret: str
) -> bytes:
    """HMAC-SHA256 over sequence (u64 BE), len+device id, len+action; key = the parent's second hash.

    Two verified test vectors of this are in docs/ServerAPI.md section 5.4 and in the conformance suite.
    """
    device = device_id.encode("utf-8")
    action = encoded_action.encode("utf-8")
    mac = hmac.new(secret.encode("utf-8"), digestmod=hashlib.sha256)
    mac.update(struct.pack(">Q", sequence_number))
    mac.update(struct.pack(">I", len(device)))
    mac.update(device)
    mac.update(struct.pack(">I", len(action)))
    mac.update(action)
    return mac.digest()


def password_integrity(
    *, sequence_number: int, device_id: str, encoded_action: str, secret: str
) -> str:
    """The ``integrity`` value a client sends: ``password:`` + base64 of the HMAC."""
    mac = action_hmac(
        sequence_number=sequence_number,
        device_id=device_id,
        encoded_action=encoded_action,
        secret=secret,
    )
    return "password:" + base64.b64encode(mac).decode("ascii")


def legacy_integrity(
    *, sequence_number: int, device_id: str, encoded_action: str, secret: str
) -> str:
    """The older sha512 variant the server still accepts."""
    data = str(sequence_number) + device_id + secret + encoded_action
    return hashlib.sha512(data.encode("utf-8")).hexdigest()


def remove_user_authentication(user_id: str, second_hash: str) -> str:
    """``authentication`` of REMOVE_USER for a parent: first 16 hex chars of sha512(id + hash + 'remove')."""
    return hashlib.sha512(
        (user_id + second_hash + "remove").encode("utf-8")
    ).hexdigest()[:16]


def check_parent_integrity(
    *,
    integrity: str,
    sequence_number: int,
    device_id: str,
    encoded_action: str,
    second_hash: str,
    device_ok: bool,
) -> bool:
    """True when the integrity value is acceptable for a parent action of this device."""
    if integrity == "device":
        return device_ok
    if integrity == "childDevice":
        return False  # child self-limits are not simulated
    if integrity.startswith("u2f:"):
        return False
    if integrity.startswith("password:"):
        try:
            provided = base64.b64decode(integrity[len("password:") :], validate=True)
        except ValueError:
            return False
        expected = action_hmac(
            sequence_number=sequence_number,
            device_id=device_id,
            encoded_action=encoded_action,
            secret=second_hash,
        )
        return hmac.compare_digest(provided, expected)
    expected_legacy = legacy_integrity(
        sequence_number=sequence_number,
        device_id=device_id,
        encoded_action=encoded_action,
        secret=second_hash,
    )
    return integrity == expected_legacy
