"""Unit tests for crypto_utils module.

This module tests the password hash generation and crypto utilities
used in the create family flow.
"""

import bcrypt
import pytest

from crypto_utils import generate_family_hashes, regenerate_second_hash


class TestGenerateFamilyHashes:
    """Tests for generate_family_hashes function."""

    @pytest.mark.timeout(10)
    def test_generate_family_hashes_returns_dict(self):
        """Test that generate_family_hashes returns a dictionary."""
        result = generate_family_hashes("testpassword123")

        assert isinstance(result, dict)

    @pytest.mark.timeout(10)
    def test_generate_family_hashes_has_required_keys(self):
        """Test that result contains hash, secondHash, and secondSalt."""
        result = generate_family_hashes("testpassword123")

        assert "hash" in result
        assert "secondHash" in result
        assert "secondSalt" in result

    @pytest.mark.timeout(10)
    def test_generate_family_hashes_hash_is_bcrypt(self):
        """Test that hash is a valid bcrypt hash."""
        result = generate_family_hashes("testpassword123")

        # Bcrypt hashes start with $2a$ or $2b$
        assert result["hash"].startswith("$2")
        assert result["secondHash"].startswith("$2")

    @pytest.mark.timeout(10)
    def test_generate_family_hashes_different_salts(self):
        """Test that two different salts are generated."""
        result = generate_family_hashes("testpassword123")

        # The two salts should be different
        # We can verify by checking that the hashes are different
        assert result["hash"] != result["secondHash"]

    @pytest.mark.timeout(10)
    def test_generate_family_hashes_verifiable(self):
        """Test that generated hashes can be verified against the original password."""
        password = "testpassword123"
        result = generate_family_hashes(password)

        # Verify first hash
        assert bcrypt.checkpw(password.encode("utf-8"), result["hash"].encode("utf-8"))

        # Verify second hash
        assert bcrypt.checkpw(
            password.encode("utf-8"), result["secondHash"].encode("utf-8")
        )

    @pytest.mark.timeout(10)
    def test_generate_family_hashes_different_passwords_different_hashes(self):
        """Test that different passwords produce different hashes."""
        result1 = generate_family_hashes("password1")
        result2 = generate_family_hashes("password2")

        assert result1["hash"] != result2["hash"]
        assert result1["secondHash"] != result2["secondHash"]

    @pytest.mark.timeout(10)
    def test_generate_family_hashes_same_password_different_hashes(self):
        """Test that same password produces different hashes (due to random salts)."""
        result1 = generate_family_hashes("samepassword")
        result2 = generate_family_hashes("samepassword")

        # Hashes should be different due to random salts
        assert result1["hash"] != result2["hash"]
        assert result1["secondHash"] != result2["secondHash"]

        # But both should verify against the same password
        assert bcrypt.checkpw(b"samepassword", result1["hash"].encode("utf-8"))
        assert bcrypt.checkpw(b"samepassword", result2["hash"].encode("utf-8"))

    @pytest.mark.timeout(10)
    def test_generate_family_hashes_empty_password(self):
        """Test that empty password is handled."""
        result = generate_family_hashes("")

        assert "hash" in result
        assert "secondHash" in result
        assert "secondSalt" in result

        # Empty password should still produce valid bcrypt hashes
        assert bcrypt.checkpw(b"", result["hash"].encode("utf-8"))

    @pytest.mark.timeout(10)
    def test_generate_family_hashes_special_characters(self):
        """Test that special characters in password are handled correctly."""
        password = "p@ssw0rd!#$%^&*()_+-=[]{}|;:,.<>?"
        result = generate_family_hashes(password)

        assert bcrypt.checkpw(password.encode("utf-8"), result["hash"].encode("utf-8"))
        assert bcrypt.checkpw(
            password.encode("utf-8"), result["secondHash"].encode("utf-8")
        )

    @pytest.mark.timeout(10)
    def test_generate_family_hashes_unicode_password(self):
        """Test that unicode characters in password are handled correctly."""
        password = "密码测试🔐"
        result = generate_family_hashes(password)

        assert bcrypt.checkpw(password.encode("utf-8"), result["hash"].encode("utf-8"))
        assert bcrypt.checkpw(
            password.encode("utf-8"), result["secondHash"].encode("utf-8")
        )


class TestRegenerateSecondHash:
    """Tests for regenerate_second_hash function."""

    @pytest.mark.timeout(10)
    def test_regenerate_second_hash_returns_string(self):
        """Test that regenerate_second_hash returns a string."""
        password = "testpassword123"
        result = generate_family_hashes(password)

        regenerated = regenerate_second_hash(password, result["secondSalt"])

        assert isinstance(regenerated, str)

    @pytest.mark.timeout(10)
    def test_regenerate_second_hash_matches_original(self):
        """Test that regenerated hash matches the original secondHash."""
        password = "testpassword123"
        result = generate_family_hashes(password)

        regenerated = regenerate_second_hash(password, result["secondSalt"])

        assert regenerated == result["secondHash"]

    @pytest.mark.timeout(10)
    def test_regenerate_second_hash_verifiable(self):
        """Test that regenerated hash can be verified against password."""
        password = "testpassword123"
        result = generate_family_hashes(password)

        regenerated = regenerate_second_hash(password, result["secondSalt"])

        assert bcrypt.checkpw(password.encode("utf-8"), regenerated.encode("utf-8"))

    @pytest.mark.timeout(10)
    def test_regenerate_second_hash_wrong_password_fails(self):
        """Test that wrong password fails verification against original hash."""
        password = "testpassword123"
        result = generate_family_hashes(password)

        # Regenerate with wrong password
        regenerated = regenerate_second_hash("wrongpassword", result["secondSalt"])

        # The regenerated hash should match 'wrongpassword' (since we hashed it)
        assert bcrypt.checkpw(b"wrongpassword", regenerated.encode("utf-8"))

        # But the regenerated hash should NOT match the original password
        assert not bcrypt.checkpw(password.encode("utf-8"), regenerated.encode("utf-8"))

        # And the original secondHash should NOT match 'wrongpassword'
        assert not bcrypt.checkpw(
            b"wrongpassword", result["secondHash"].encode("utf-8")
        )


class TestPasswordHashFormat:
    """Tests for password hash format compatibility."""

    @pytest.mark.timeout(10)
    def test_hash_format_compatible_with_bcrypt(self):
        """Test that hash format is compatible with bcrypt library."""
        password = "testpassword123"
        result = generate_family_hashes(password)

        # Should be able to verify using bcrypt.checkpw
        assert bcrypt.checkpw(password.encode("utf-8"), result["hash"].encode("utf-8"))
        assert bcrypt.checkpw(
            password.encode("utf-8"), result["secondHash"].encode("utf-8")
        )

    @pytest.mark.timeout(10)
    def test_hash_roundtrip(self):
        """Test that hash can be verified multiple times."""
        password = "testpassword123"
        result = generate_family_hashes(password)

        # Verify multiple times
        for _ in range(5):
            assert bcrypt.checkpw(
                password.encode("utf-8"), result["hash"].encode("utf-8")
            )
            assert bcrypt.checkpw(
                password.encode("utf-8"), result["secondHash"].encode("utf-8")
            )

    @pytest.mark.timeout(10)
    def test_salt_is_valid_bcrypt_salt(self):
        """Test that secondSalt is a valid bcrypt salt."""
        password = "testpassword123"
        result = generate_family_hashes(password)

        # Salt should start with $2a$ or $2b$
        assert result["secondSalt"].startswith("$2")

        # Salt should be 29 characters (bcrypt salt format)
        assert len(result["secondSalt"]) == 29
