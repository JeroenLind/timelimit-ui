"""Integrity values and password containers (B2, TR-101, TR-102)."""

from __future__ import annotations

import base64
import hashlib

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from dashboard.domain import integrity as ig

from .fakeserver import integrity as fake_integrity

KEY = "$2a$12$abcdefghijklmnopqrstuuABCDEFGHIJKLMNOPQRSTUVWXYZ01234"
SALT = "$2a$12$abcdefghijklmnopqrstuu"
FIRST_HASH = "$2a$12$" + "A" * 53
OLD_SECOND = "$2a$12$" + "B" * 53
NEW_SECOND = "$2a$12$" + "C" * 53


def fixed_random(count: int) -> bytes:
    return bytes(range(1, count + 1))


@pytest.mark.parametrize(
    ("seq", "device", "action", "expected"),
    [
        (
            7,
            "dev123",
            '{"type":"CREATE_TIMELIMIT_RULE","rule":{"ruleId":"r1"}}',
            "password:n10GZyWfMKiUKda4gXQEWgvlFYpTnKC3OG6zM6Jl6ms=",
        ),
        (
            0,
            "äöü",
            '{"a":"é"}',
            "password:eC7BY0YnRSRFX8stS6q4iG32JSNSb1p6KU4X92BFsz0=",
        ),
    ],
)
def test_hmac_matches_the_verified_vectors(
    seq: int, device: str, action: str, expected: str
) -> None:
    assert (
        ig.password_integrity(
            sequence_number=seq,
            device_id=device,
            encoded_action=action,
            second_hash=KEY,
        )
        == expected
    )


def test_hmac_agrees_with_the_fake_server() -> None:
    for seq in (0, 1, 2**40):
        mine = ig.password_integrity(
            sequence_number=seq,
            device_id="abc123",
            encoded_action="{}",
            second_hash=KEY,
        )
        theirs = fake_integrity.password_integrity(
            sequence_number=seq, device_id="abc123", encoded_action="{}", secret=KEY
        )
        assert mine == theirs


@pytest.mark.parametrize("seq", [-1, 2**64, True])
def test_hmac_rejects_bad_sequence(seq: int) -> None:
    with pytest.raises(ig.IntegrityError):
        ig.action_hmac(
            sequence_number=seq,
            device_id="abc123",
            encoded_action="{}",
            second_hash=KEY,
        )


def test_remove_user_authentication_matches_the_fake() -> None:
    assert ig.remove_user_authentication(
        "abc123", KEY
    ) == fake_integrity.remove_user_authentication("abc123", KEY)
    assert len(ig.remove_user_authentication("abc123", KEY)) == 16


def test_second_hash_round_trip_and_shape() -> None:
    encrypted = ig.encrypt_second_hash(
        old_second_hash=OLD_SECOND,
        new_second_hash=NEW_SECOND,
        random_bytes=fixed_random,
    )
    assert len(encrypted) == 32 + 32 + 120 and len(encrypted) > 70
    assert encrypted[:32] == fixed_random(16).hex()
    assert (
        ig.decrypt_second_hash(old_second_hash=OLD_SECOND, encrypted=encrypted)
        == NEW_SECOND
    )
    assert (
        ig.decrypt_second_hash(old_second_hash=KEY, encrypted=encrypted) != NEW_SECOND
    )


def test_second_hash_must_be_a_bcrypt_hash() -> None:
    with pytest.raises(ig.IntegrityError):
        ig.encrypt_second_hash(old_second_hash=OLD_SECOND, new_second_hash="short")


def test_change_password_integrity_is_sha512_of_the_concatenation() -> None:
    value = ig.change_password_integrity(
        old_second_hash=OLD_SECOND,
        user_id="abc123",
        new_hash=FIRST_HASH,
        new_second_salt=SALT,
        second_hash_encrypted="ff" * 40,
    )
    expected = hashlib.sha512(
        (OLD_SECOND + "abc123" + FIRST_HASH + SALT + "ff" * 40).encode()
    ).hexdigest()
    assert value == expected and len(value) == 128


def test_parent_password_container_can_be_opened_by_the_server_side() -> None:
    """Act as the server: it holds the private key behind the published DH key."""
    server_private = ec.generate_private_key(ec.SECP256R1())
    server_public = base64.b64encode(
        server_private.public_key().public_bytes(
            serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo
        )
    ).decode()
    container = ig.encrypt_parent_password(
        server_public_key=server_public,
        key_id="ab12",
        password_hash=FIRST_HASH,
        second_salt=SALT,
        second_hash=NEW_SECOND,
    )
    sealed_b64, client_public_b64, key_id = container.split(".")
    assert key_id == "ab12"
    client_public = serialization.load_der_public_key(
        base64.b64decode(client_public_b64)
    )
    assert isinstance(client_public, ec.EllipticCurvePublicKey)
    shared = server_private.exchange(ec.ECDH(), client_public)
    sealed = base64.b64decode(sealed_b64)
    plain = AESGCM(shared[:16]).decrypt(
        sealed[:12], sealed[12:], f"ParentPassword:{FIRST_HASH}:{SALT}".encode("ascii")
    )
    assert plain.decode() == NEW_SECOND
    # the associated data binds the hash and salt: a different salt must not open it
    with pytest.raises(Exception, match=r".*"):
        AESGCM(shared[:16]).decrypt(sealed[:12], sealed[12:], b"ParentPassword:x:y")


@pytest.mark.parametrize("key_id", ["abc", "abcde", "ab-1", ""])
def test_container_rejects_bad_key_id(key_id: str) -> None:
    with pytest.raises(ig.IntegrityError):
        ig.encrypt_parent_password(
            server_public_key="AAAA",
            key_id=key_id,
            password_hash=FIRST_HASH,
            second_salt=SALT,
            second_hash=NEW_SECOND,
        )


def test_container_rejects_a_wrong_curve_and_garbage() -> None:
    other = (
        ec.generate_private_key(ec.SECP384R1())
        .public_key()
        .public_bytes(
            serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo
        )
    )
    for key in (
        base64.b64encode(other).decode(),
        "not base64!!",
        base64.b64encode(b"junk").decode(),
    ):
        with pytest.raises(ig.IntegrityError):
            ig.encrypt_parent_password(
                server_public_key=key,
                key_id="ab12",
                password_hash=FIRST_HASH,
                second_salt=SALT,
                second_hash=NEW_SECOND,
            )
