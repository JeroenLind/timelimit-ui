"""Parent password hashes as the server expects them (ServerAPI section 8, plan E1).

The server stores two bcrypt values per parent: ``hash`` (checks the password) and ``secondHash`` with its
``secondSalt`` (the key of the password integrity method). Both use the ``$2a$`` prefix with cost 10 to 31
(the server validates ``$2a$[123][0-9]$...``). Nothing here stores or logs a password.
"""

from __future__ import annotations

from dataclasses import dataclass

import bcrypt

DEFAULT_ROUNDS = 10


@dataclass(frozen=True)
class PasswordHashes:
    hash: str
    second_hash: str
    second_salt: str


def new_password(password: str, rounds: int = DEFAULT_ROUNDS) -> PasswordHashes:
    """Fresh ``hash`` and ``secondHash`` (own random salts) for a new or changed password."""
    raw = password.encode("utf-8")
    salt_one = bcrypt.gensalt(rounds=rounds, prefix=b"2a")
    salt_two = bcrypt.gensalt(rounds=rounds, prefix=b"2a")
    return PasswordHashes(
        hash=bcrypt.hashpw(raw, salt_one).decode("ascii"),
        second_hash=bcrypt.hashpw(raw, salt_two).decode("ascii"),
        second_salt=salt_two.decode("ascii"),
    )


def password_matches(password: str, stored_hash: str) -> bool:
    """True when ``password`` belongs to ``stored_hash`` (the ``password`` field of a server user)."""
    try:
        return bcrypt.checkpw(password.encode("utf-8"), stored_hash.encode("ascii"))
    except ValueError:
        return False


def second_hash_for(password: str, second_salt: str) -> str:
    """The ``secondHash`` of an existing parent: bcrypt of the password with the salt the server keeps."""
    return bcrypt.hashpw(password.encode("utf-8"), second_salt.encode("ascii")).decode(
        "ascii"
    )
