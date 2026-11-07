"""Unit tests for key_manager module.

Tests for Curve25519 signing key generation and management.
"""

import base64
import json
import os
import tempfile

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import x25519


@pytest.fixture
def temp_persistence_dir():
    """Create a temporary directory for key storage."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture
def key_manager():
    """Import key_manager module for testing."""
    from key_manager import get_or_create_signing_key, get_public_key_from_private

    return {
        "get_or_create_signing_key": get_or_create_signing_key,
        "get_public_key_from_private": get_public_key_from_private,
    }


class TestKeyGeneration:
    """Tests for Curve25519 key pair generation."""

    @pytest.mark.timeout(10)
    def test_generate_key_pair_returns_valid_keys(
        self, temp_persistence_dir, key_manager
    ):
        """Test that key generation returns valid base64-encoded keys."""
        private_key_b64, public_key_b64 = key_manager["get_or_create_signing_key"](
            temp_persistence_dir
        )

        # Verify keys are base64-encoded strings
        assert isinstance(private_key_b64, str)
        assert isinstance(public_key_b64, str)

        # Verify keys can be decoded
        private_key_bytes = base64.b64decode(private_key_b64)
        public_key_bytes = base64.b64decode(public_key_b64)

        # Verify key lengths (Curve25519 uses 32-byte keys)
        assert len(private_key_bytes) == 32
        assert len(public_key_bytes) == 32

    @pytest.mark.timeout(10)
    def test_generate_key_pair_creates_key_file(
        self, temp_persistence_dir, key_manager
    ):
        """Test that key generation creates a key file."""
        key_manager["get_or_create_signing_key"](temp_persistence_dir)

        key_file_path = os.path.join(temp_persistence_dir, "dashboard_signing_key.json")
        assert os.path.exists(key_file_path)

        # Verify file contents
        with open(key_file_path, "r", encoding="utf-8") as f:
            key_data = json.load(f)

        assert "private_key" in key_data
        assert "created_at" in key_data

    @pytest.mark.timeout(10)
    def test_generate_key_pair_creates_unique_keys(
        self, temp_persistence_dir, key_manager
    ):
        """Test that each key generation creates a unique key pair."""
        private_key1, public_key1 = key_manager["get_or_create_signing_key"](
            temp_persistence_dir
        )

        # Remove the key file to force new key generation
        key_file_path = os.path.join(temp_persistence_dir, "dashboard_signing_key.json")
        os.remove(key_file_path)

        private_key2, public_key2 = key_manager["get_or_create_signing_key"](
            temp_persistence_dir
        )

        # Keys should be different
        assert private_key1 != private_key2
        assert public_key1 != public_key2


class TestKeyPersistence:
    """Tests for key persistence across restarts."""

    @pytest.mark.timeout(10)
    def test_load_existing_key(self, temp_persistence_dir, key_manager):
        """Test that existing keys are loaded from file."""
        # Generate a key
        private_key1, public_key1 = key_manager["get_or_create_signing_key"](
            temp_persistence_dir
        )

        # Load the key again (should load from file)
        private_key2, public_key2 = key_manager["get_or_create_signing_key"](
            temp_persistence_dir
        )

        # Keys should be the same
        assert private_key1 == private_key2
        assert public_key1 == public_key2

    @pytest.mark.timeout(10)
    def test_persistence_file_format(self, temp_persistence_dir, key_manager):
        """Test that the persistence file has the correct format."""
        key_manager["get_or_create_signing_key"](temp_persistence_dir)

        key_file_path = os.path.join(temp_persistence_dir, "dashboard_signing_key.json")
        with open(key_file_path, "r", encoding="utf-8") as f:
            key_data = json.load(f)

        # Verify structure
        assert isinstance(key_data, dict)
        assert "private_key" in key_data
        assert "created_at" in key_data
        assert isinstance(key_data["private_key"], str)
        assert isinstance(key_data["created_at"], int)


class TestPublicKeyDerivation:
    """Tests for public key derivation from private key."""

    @pytest.mark.timeout(10)
    def test_derive_public_key_from_private(self, key_manager):
        """Test that public key can be derived from private key."""
        # Generate a key pair
        private_key = x25519.X25519PrivateKey.generate()
        private_key_bytes = private_key.private_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PrivateFormat.Raw,
            encryption_algorithm=serialization.NoEncryption(),
        )
        private_key_b64 = base64.b64encode(private_key_bytes).decode("utf-8")

        # Derive public key
        derived_public_key_b64 = key_manager["get_public_key_from_private"](
            private_key_b64
        )

        # Get expected public key
        public_key = private_key.public_key()
        expected_public_key_bytes = public_key.public_bytes(
            encoding=serialization.Encoding.Raw, format=serialization.PublicFormat.Raw
        )
        expected_public_key_b64 = base64.b64encode(expected_public_key_bytes).decode(
            "utf-8"
        )

        assert derived_public_key_b64 == expected_public_key_b64

    @pytest.mark.timeout(10)
    def test_derived_key_matches_generated_key(self, temp_persistence_dir, key_manager):
        """Test that derived public key matches the one from key generation."""
        # Generate a key pair
        private_key_b64, public_key_b64 = key_manager["get_or_create_signing_key"](
            temp_persistence_dir
        )

        # Derive public key from private key
        derived_public_key_b64 = key_manager["get_public_key_from_private"](
            private_key_b64
        )

        # Should match
        assert public_key_b64 == derived_public_key_b64


class TestKeyConsistency:
    """Tests for key consistency and integrity."""

    @pytest.mark.timeout(10)
    def test_key_pair_is_valid_curve25519(self, temp_persistence_dir, key_manager):
        """Test that generated keys are valid Curve25519 keys."""
        private_key_b64, public_key_b64 = key_manager["get_or_create_signing_key"](
            temp_persistence_dir
        )

        private_key_bytes = base64.b64decode(private_key_b64)
        public_key_bytes = base64.b64decode(public_key_b64)

        # Should be able to reconstruct the private key
        private_key = x25519.X25519PrivateKey.from_private_bytes(private_key_bytes)

        # Should be able to derive the public key
        derived_public_key = private_key.public_key()
        derived_public_key_bytes = derived_public_key.public_bytes(
            encoding=serialization.Encoding.Raw, format=serialization.PublicFormat.Raw
        )

        assert public_key_bytes == derived_public_key_bytes

    @pytest.mark.timeout(10)
    def test_multiple_calls_return_same_key(self, temp_persistence_dir, key_manager):
        """Test that multiple calls return the same key pair."""
        keys = []
        for _ in range(3):
            private_key, public_key = key_manager["get_or_create_signing_key"](
                temp_persistence_dir
            )
            keys.append((private_key, public_key))

        # All keys should be the same
        for i in range(1, len(keys)):
            assert keys[i][0] == keys[0][0], f"Private key {i} differs from key 0"
            assert keys[i][1] == keys[0][1], f"Public key {i} differs from key 0"
