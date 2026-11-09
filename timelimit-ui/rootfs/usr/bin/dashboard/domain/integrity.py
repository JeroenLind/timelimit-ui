"""Integrity values and password containers for parent actions (TR-101, TR-102).

Pure functions; randomness can be injected so tests are deterministic. Algorithms verified in the
server source (``apply-actions/integrity.ts``, ``changeparentpassword.ts``, ``function/dh/*``):

* Action integrity with the password method: ``"password:" + base64(HMAC-SHA256)``, key = the
  parent's second hash.
* ``CHANGE_PARENT_PASSWORD``: sha512 hex integrity and the new second hash encrypted with
  AES-128-CTR (key = first 16 bytes of ``sha512(oldSecondHash + salt)``).
* ``ADD_USER`` of a parent: the second hash is sent as an ECDH(P-256)/AES-128-GCM container.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import os
import struct
from collections.abc import Callable

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

RandomBytes = Callable[[int], bytes]

_BCRYPT_HASH_LENGTH = 60
_MIN_ENCRYPTED_LENGTH = 71  # the server requires more than 70 hex characters


class IntegrityError(ValueError):
    """Raised when input for an integrity value or container is invalid."""


def action_hmac(
    *, sequence_number: int, device_id: str, encoded_action: str, second_hash: str
) -> bytes:
    """HMAC-SHA256 over sequence (u64 BE), len+device id, len+action; key = the second hash."""
    if isinstance(sequence_number, bool) or not 0 <= sequence_number < 2**64:
        raise IntegrityError("sequence number out of range")
    if not device_id:
        raise IntegrityError("device id is required")
    device = device_id.encode("utf-8")
    action = encoded_action.encode("utf-8")
    mac = hmac.new(second_hash.encode("utf-8"), digestmod=hashlib.sha256)
    mac.update(struct.pack(">Q", sequence_number))
    mac.update(struct.pack(">I", len(device)))
    mac.update(device)
    mac.update(struct.pack(">I", len(action)))
    mac.update(action)
    return mac.digest()


def password_integrity(
    *, sequence_number: int, device_id: str, encoded_action: str, second_hash: str
) -> str:
    """The ``integrity`` of a parent action signed with the password method."""
    mac = action_hmac(
        sequence_number=sequence_number,
        device_id=device_id,
        encoded_action=encoded_action,
        second_hash=second_hash,
    )
    return "password:" + base64.b64encode(mac).decode("ascii")


def remove_user_authentication(user_id: str, second_hash: str) -> str:
    """``authentication`` of ``REMOVE_USER`` for a parent: first 16 hex chars of sha512(id+hash+"remove")."""
    return hashlib.sha512(
        (user_id + second_hash + "remove").encode("utf-8")
    ).hexdigest()[:16]


def encrypt_second_hash(
    *,
    old_second_hash: str,
    new_second_hash: str,
    random_bytes: RandomBytes = os.urandom,
) -> str:
    """Hex ``iv(16) + salt(16, as 32 hex chars) + ciphertext`` as ``CHANGE_PARENT_PASSWORD`` expects."""
    plain = new_second_hash.encode("utf-8")
    if len(plain) != _BCRYPT_HASH_LENGTH:
        raise IntegrityError("a second hash is a 60 character bcrypt string")
    iv = random_bytes(16)
    salt = random_bytes(16).hex()
    key = hashlib.sha512((old_second_hash + salt).encode("utf-8")).digest()[:16]
    encryptor = Cipher(algorithms.AES(key), modes.CTR(iv)).encryptor()
    ciphertext = encryptor.update(plain) + encryptor.finalize()
    result = iv.hex() + salt + ciphertext.hex()
    if len(result) < _MIN_ENCRYPTED_LENGTH:
        raise IntegrityError("encrypted second hash too short")
    return result


def decrypt_second_hash(*, old_second_hash: str, encrypted: str) -> str:
    """Inverse of :func:`encrypt_second_hash` (used by tests and the fake server)."""
    iv = bytes.fromhex(encrypted[:32])
    salt = encrypted[32:64]
    key = hashlib.sha512((old_second_hash + salt).encode("utf-8")).digest()[:16]
    decryptor = Cipher(algorithms.AES(key), modes.CTR(iv)).decryptor()
    return (
        decryptor.update(bytes.fromhex(encrypted[64:])) + decryptor.finalize()
    ).decode("utf-8")


def change_password_integrity(
    *,
    old_second_hash: str,
    user_id: str,
    new_hash: str,
    new_second_salt: str,
    second_hash_encrypted: str,
) -> str:
    """sha512 hex over ``oldSecondHash + userId + hash + secondSalt + secondHashEncrypted``."""
    data = (
        old_second_hash + user_id + new_hash + new_second_salt + second_hash_encrypted
    )
    return hashlib.sha512(data.encode("utf-8")).hexdigest()


def encrypt_parent_password(
    *,
    server_public_key: str,
    key_id: str,
    password_hash: str,
    second_salt: str,
    second_hash: str,
    private_key: ec.EllipticCurvePrivateKey | None = None,
    random_bytes: RandomBytes = os.urandom,
) -> str:
    """The ``secondHash`` container of ``ADD_USER`` (parent) with ``encrypted: true``.

    ``server_public_key`` and ``key_id`` come from the ``dh`` entry (``k``, ``v``) of the pull-status
    response. Format: ``base64(iv || ciphertext || tag) "." base64(own SPKI public key) "." keyId``.
    """
    if len(key_id) != 4 or not key_id.isalnum() or not key_id.isascii():
        raise IntegrityError("key id must be 4 alphanumeric characters")
    try:
        server_key = serialization.load_der_public_key(
            base64.b64decode(server_public_key, validate=True)
        )
    except ValueError as error:
        raise IntegrityError("server DH key is not valid base64 SPKI") from error
    if not isinstance(server_key, ec.EllipticCurvePublicKey) or not isinstance(
        server_key.curve, ec.SECP256R1
    ):
        raise IntegrityError("server DH key must be an EC P-256 key")
    own_key = private_key or ec.generate_private_key(ec.SECP256R1())
    shared = own_key.exchange(ec.ECDH(), server_key)
    iv = random_bytes(12)
    aad = f"ParentPassword:{password_hash}:{second_salt}".encode("ascii")
    sealed = AESGCM(shared[:16]).encrypt(iv, second_hash.encode("ascii"), aad)
    own_public = own_key.public_key().public_bytes(
        serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo
    )
    return ".".join(
        [
            base64.b64encode(iv + sealed).decode("ascii"),
            base64.b64encode(own_public).decode("ascii"),
            key_id,
        ]
    )


__all__ = [
    "IntegrityError",
    "action_hmac",
    "change_password_integrity",
    "decrypt_second_hash",
    "encrypt_parent_password",
    "encrypt_second_hash",
    "password_integrity",
    "remove_user_authentication",
]
