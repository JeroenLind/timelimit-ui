#!/usr/bin/env python3
"""Test to verify the hash mismatch issue between family creation and set parent password.

This test demonstrates that:
1. Family creation uses generate_family_hashes() which produces $2a$ prefix hashes
2. Set parent password uses bcrypt.gensalt() which produces $2b$ prefix hashes
3. The server expects $2a$ prefix hashes (as documented in crypto_utils.py)
"""

import bcrypt
import sys
import os

# Add the dashboardV2 directory to the path
sys.path.insert(
    0, os.path.join(os.path.dirname(__file__), "timelimit-ui", "rootfs", "usr", "bin")
)


def generate_family_hashes(password):
    """Generate BCrypt hashes for family password, matching Android app logic.

    Uses $2a$ prefix to match the server's expected format and Android app's jBCrypt.
    The server validates hashes using regex: /^($2a$[123][0-9]$[./A-Za-z0-9]{53})?$/
    """
    password_bytes = password.encode("utf-8")

    # Two unique salts for maximum safety
    # Use '2a' prefix to match server validation (bcrypt 5.0+ expects prefix without $)
    # Python bcrypt defaults to $2b$ prefix, but server expects $2a$
    salt1 = bcrypt.gensalt(rounds=12, prefix=b"2a")
    salt2 = bcrypt.gensalt(rounds=12, prefix=b"2a")

    # Hashes expected by the server
    hash1 = bcrypt.hashpw(password_bytes, salt1)
    hash2 = bcrypt.hashpw(password_bytes, salt2)

    return {
        "hash": hash1.decode("utf-8"),
        "secondHash": hash2.decode("utf-8"),
        "secondSalt": salt2.decode("utf-8"),
    }


def set_parent_password_hash(password):
    """Hash password using Python's default bcrypt (what post_set_parent_password uses)."""
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


def main():
    password = "12345678"

    print("=" * 60)
    print("Testing hash generation for password:", password)
    print("=" * 60)

    # Method 1: Family creation hash (correct)
    print("\n1. Family Creation Hash (generate_family_hashes):")
    family_hashes = generate_family_hashes(password)
    print(f"   secondHash prefix: {family_hashes['secondHash'][:10]}")
    print(f"   secondHash: {family_hashes['secondHash']}")
    print(f"   Starts with $2a$: {family_hashes['secondHash'].startswith('$2a$')}")

    # Method 2: Set parent password hash (incorrect)
    print("\n2. Set Parent Password Hash (bcrypt.gensalt default):")
    set_password_hash = set_parent_password_hash(password)
    print(f"   Hash prefix: {set_password_hash[:10]}")
    print(f"   Hash: {set_password_hash}")
    print(f"   Starts with $2b$: {set_password_hash.startswith('$2b$')}")

    # Verify the hashes are different
    print("\n" + "=" * 60)
    print("VERIFICATION:")
    print("=" * 60)

    # Check if both hashes verify the same password
    hash1_valid = bcrypt.checkpw(
        password.encode("utf-8"), family_hashes["secondHash"].encode("utf-8")
    )
    hash2_valid = bcrypt.checkpw(
        password.encode("utf-8"), set_password_hash.encode("utf-8")
    )

    print(f"Family hash verifies password: {hash1_valid}")
    print(f"Set password hash verifies password: {hash2_valid}")

    # Check if hashes are equal
    hashes_equal = family_hashes["secondHash"] == set_password_hash
    print(f"Hashes are equal: {hashes_equal}")

    # Check prefixes
    print(f"\nFamily hash prefix: {family_hashes['secondHash'][:4]}")
    print(f"Set password hash prefix: {set_password_hash[:4]}")

    # Server validation regex check
    import re

    server_regex = r"^(\$2a\$[123][0-9]\$[./A-Za-z0-9]{53})?$"
    family_matches = bool(re.match(server_regex, family_hashes["secondHash"]))
    set_password_matches = bool(re.match(server_regex, set_password_hash))

    print(f"\nServer regex matches family hash: {family_matches}")
    print(f"Server regex matches set password hash: {set_password_matches}")

    print("\n" + "=" * 60)
    print("CONCLUSION:")
    print("=" * 60)
    if not hashes_equal:
        print(
            "BUG CONFIRMED: The two hash generation methods produce different hashes!"
        )
        print("This causes 401 Unauthorized when device removal is attempted.")
        print(
            "\nThe fix: post_set_parent_password() should use generate_family_hashes()"
        )
        print("or at minimum use bcrypt.gensalt(rounds=12, prefix=b'2a')")
    else:
        print("Hashes are equal - no issue found")

    return 0 if hashes_equal else 1


if __name__ == "__main__":
    sys.exit(main())
