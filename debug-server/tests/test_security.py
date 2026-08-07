"""Unit tests for security services.

This module tests password hashing and JWT token creation functionality
including verification, token generation, and expiration handling.
"""

import pytest
from datetime import datetime, timedelta, timezone
from jose import jwt

from app.services.security import get_password_hash, verify_password, create_access_token
from app.core.config import settings


class TestPasswordHash:
    """Tests for password hashing and verification functions."""

    def test_password_hash(self):
        """Test password hashing and verification.
        
        This test:
        - Hashes a test password
        - Verifies the hash is not the plain password
        - Verifies verify_password returns True for correct password
        - Verifies verify_password returns False for incorrect password
        """
        test_password = "my_secure_password_123"
        
        # Hash the password
        hashed = get_password_hash(test_password)
        
        # Verify the hash is not the plain password
        assert hashed != test_password, "Hash should not be the same as plain password"
        
        # Verify the hash is a string
        assert isinstance(hashed, str), "Hash should be a string"
        
        # Verify the hash looks like a bcrypt hash (starts with $2b$)
        assert hashed.startswith("$2b$"), "Hash should be a bcrypt hash starting with $2b$"
        
        # Verify correct password returns True
        assert verify_password(test_password, hashed) is True, \
            "verify_password should return True for correct password"
        
        # Verify incorrect password returns False
        assert verify_password("wrong_password", hashed) is False, \
            "verify_password should return False for incorrect password"
        
        # Verify empty password returns False
        assert verify_password("", hashed) is False, \
            "verify_password should return False for empty password"

    def test_password_hash_different_salts(self):
        """Test that same password produces different hashes (different salts)."""
        test_password = "same_password_123"
        
        # Hash the same password twice
        hash1 = get_password_hash(test_password)
        hash2 = get_password_hash(test_password)
        
        # Hashes should be different due to different salts
        assert hash1 != hash2, "Same password should produce different hashes due to salt"
        
        # But both should verify correctly
        assert verify_password(test_password, hash1) is True
        assert verify_password(test_password, hash2) is True

    def test_password_hash_bcrypt_cost(self):
        """Test that bcrypt uses the configured cost factor."""
        test_password = "test_password_cost"
        hashed = get_password_hash(test_password)
        
        # Extract the cost factor from the hash
        # bcrypt hash format: $2b$XX$... where XX is the cost
        parts = hashed.split('$')
        assert len(parts) >= 3, "Hash should have proper bcrypt format"
        
        cost = int(parts[2])
        assert cost == settings.BCRYPT_COST, \
            f"Bcrypt cost should be {settings.BCRYPT_COST}, got {cost}"


class TestAccessToken:
    """Tests for JWT access token creation and validation."""

    def test_create_access_token(self):
        """Test JWT token creation.
        
        This test:
        - Creates a token with test data
        - Verifies token is a string
        - Verifies token can be decoded with jwt.decode
        - Verifies decoded data matches original data
        """
        test_data = {
            "sub": "test_user_id",
            "device_id": "test_device_123",
            "custom_claim": "custom_value"
        }
        
        # Create the token
        token = create_access_token(test_data)
        
        # Verify token is a string
        assert isinstance(token, str), "Token should be a string"
        
        # Verify token is not empty
        assert len(token) > 0, "Token should not be empty"
        
        # Decode the token with verification to check contents
        decoded = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM]
        )
        
        # Verify the subject matches
        assert decoded.get("sub") == test_data["sub"], \
            "Token subject should match original data"
        
        # Verify custom claims are preserved
        assert decoded.get("device_id") == test_data["device_id"], \
            "Token device_id should match original data"
        assert decoded.get("custom_claim") == test_data["custom_claim"], \
            "Token custom_claim should match original data"

    def test_token_expiration(self):
        """Test that token expiration is properly set.
        
        This test:
        - Creates a token
        - Decodes it and verifies expiration time is set
        - Verifies expiration is approximately ACCESS_TOKEN_EXPIRE_MINUTES in the future
        """
        test_data = {"sub": "test_user_for_expiration"}
        
        # Create the token
        token = create_access_token(test_data)
        
        # Decode the token with verification to get expiration
        decoded = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM]
        )
        
        # Verify expiration claim exists
        assert "exp" in decoded, "Token should have expiration claim"
        
        # Get the expiration time
        exp_timestamp = decoded["exp"]
        exp_datetime = datetime.fromtimestamp(exp_timestamp, tz=timezone.utc)
        
        # Calculate expected expiration
        now = datetime.now(timezone.utc)
        expected_exp = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        
        # Verify expiration is approximately the expected time (within 10 seconds tolerance)
        time_diff = abs((exp_datetime - expected_exp).total_seconds())
        assert time_diff < 10, \
            f"Token expiration should be approximately {settings.ACCESS_TOKEN_EXPIRE_MINUTES} minutes from now, got {time_diff} seconds difference"

    def test_token_with_custom_expiration(self):
        """Test token creation with custom expiration time."""
        test_data = {"sub": "test_user_custom_exp"}
        
        # Create token with custom expiration (5 minutes)
        custom_expiry = timedelta(minutes=5)
        token = create_access_token(test_data, expires_delta=custom_expiry)
        
        # Decode and verify
        decoded = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM]
        )
        
        # Verify expiration is approximately 5 minutes from now
        exp_timestamp = decoded["exp"]
        exp_datetime = datetime.fromtimestamp(exp_timestamp, tz=timezone.utc)
        now = datetime.now(timezone.utc)
        expected_exp = now + custom_expiry
        
        time_diff = abs((exp_datetime - expected_exp).total_seconds())
        assert time_diff < 10, \
            f"Custom token expiration should be approximately 5 minutes, got {time_diff} seconds difference"

    def test_token_algorithm(self):
        """Test that token uses the configured algorithm."""
        test_data = {"sub": "test_user_algorithm"}
        
        token = create_access_token(test_data)
        
        # Decode header to check algorithm
        header = jwt.get_unverified_header(token)
        
        assert header.get("alg") == settings.JWT_ALGORITHM, \
            f"Token algorithm should be {settings.JWT_ALGORITHM}, got {header.get('alg')}"

    def test_token_signature_verification(self):
        """Test that token signature can be verified."""
        test_data = {"sub": "test_user_signature"}
        
        token = create_access_token(test_data)
        
        # Verify signature by decoding with the secret key
        decoded = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM]
        )
        
        assert decoded.get("sub") == test_data["sub"], \
            "Token signature verification should succeed"

    def test_token_invalid_signature(self):
        """Test that token with invalid signature is rejected."""
        test_data = {"sub": "test_user_invalid_sig"}
        
        token = create_access_token(test_data)
        
        # Try to decode with wrong secret
        with pytest.raises(jwt.JWTError):
            jwt.decode(
                token,
                "wrong_secret_key",
                algorithms=[settings.JWT_ALGORITHM]
            )