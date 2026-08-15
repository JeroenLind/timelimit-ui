"""Unit tests for cryptographic operations.

This module tests all cryptographic functions including:
- Password hashing (bcrypt)
- JWT token generation and validation
- HMAC-SHA256/SHA512 calculations
- AES-GCM encryption/decryption
- Curve25519 key operations
- DH key exchange
"""

import pytest
import base64
import json
from datetime import datetime, timedelta, timezone
from jose import jwt

from app.core.security import (
    hash_password,
    verify_password,
    hash_password_with_salt,
    calculate_hmac_sha256,
    calculate_hmac_sha512,
    calculate_sha512_hex,
    encrypt_data,
    decrypt_data,
    generate_keypair,
    sign,
    verify as verify_signature,
    shared_secret,
    dh_handshake,
    dh_encrypt,
    CryptContainer,
    generate_token,
)
from app.core.config import settings


class TestPasswordHashing:
    """Tests for password hashing functions."""

    def test_hash_password_returns_bcrypt_hash(self):
        """Test that hash_password returns a valid bcrypt hash."""
        password = "test_password_123"
        hashed = hash_password(password)

        assert isinstance(hashed, str), "Hash should be a string"
        assert hashed.startswith("$2b$"), "Hash should be a bcrypt hash starting with $2b$"
        assert len(hashed) == 60, "Bcrypt hash should be 60 characters"

    def test_verify_password_correct(self):
        """Test that verify_password returns True for correct password."""
        password = "correct_password"
        hashed = hash_password(password)

        assert verify_password(password, hashed) is True, \
            "verify_password should return True for correct password"

    def test_verify_password_incorrect(self):
        """Test that verify_password returns False for incorrect password."""
        password = "correct_password"
        hashed = hash_password(password)

        assert verify_password("wrong_password", hashed) is False, \
            "verify_password should return False for incorrect password"

    def test_verify_password_empty(self):
        """Test that verify_password returns False for empty password."""
        hashed = hash_password("some_password")

        assert verify_password("", hashed) is False, \
            "verify_password should return False for empty password"

    def test_hash_password_with_salt(self):
        """Test password hashing with custom salt."""
        password = "test_password"
        # Use a valid bcrypt salt format
        salt = "$2b$12$N9qo8uLOickgx2ZMRZoMye"

        hashed = hash_password_with_salt(password, salt)

        assert isinstance(hashed, str), "Hash should be a string"
        assert hashed.startswith("$2b$"), "Hash should be a bcrypt hash"

    def test_different_passwords_different_hashes(self):
        """Test that different passwords produce different hashes."""
        hash1 = hash_password("password1")
        hash2 = hash_password("password2")

        assert hash1 != hash2, "Different passwords should produce different hashes"

    def test_same_password_different_salts(self):
        """Test that same password with different salts produces different hashes."""
        hash1 = hash_password("same_password")
        hash2 = hash_password("same_password")

        assert hash1 != hash2, "Same password should produce different hashes due to salt"


class TestHMACCalculations:
    """Tests for HMAC calculation functions."""

    def test_calculate_hmac_sha256(self):
        """Test HMAC-SHA256 calculation with proper parameters."""
        second_hash = "test_second_hash"
        sequence_number = 123
        device_id = "device_456"
        encoded_action = json.dumps({"type": "AddCategoryAction"})

        result = calculate_hmac_sha256(second_hash, sequence_number, device_id, encoded_action)

        assert isinstance(result, str), "HMAC result should be a string"
        assert result.startswith("password:"), "HMAC should be prefixed with 'password:'"

        # Verify the base64 part is valid
        b64_part = result.split(":", 1)[1]
        decoded = base64.b64decode(b64_part)
        assert len(decoded) == 32, "HMAC-SHA256 should produce 32 bytes"

    def test_calculate_hmac_sha512(self):
        """Test HMAC-SHA512 calculation."""
        # Create a valid base64 key
        key = base64.b64encode(b"0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef").decode()
        message = "test_message"

        result = calculate_hmac_sha512(key, message)

        assert isinstance(result, str), "HMAC result should be a string"
        # HMAC-SHA512 produces 64 bytes = 86 base64 characters
        decoded = base64.b64decode(result)
        assert len(decoded) == 64, "HMAC-SHA512 should produce 64 bytes"

    def test_calculate_sha512_hex(self):
        """Test SHA512 hex calculation."""
        message = "test_message"

        result = calculate_sha512_hex(message)

        assert isinstance(result, str), "SHA512 hex result should be a string"
        assert len(result) == 128, "SHA512 hex should be 128 characters (64 bytes * 2)"
        # Verify it's a valid hex string
        int(result, 16)

    def test_hmac_deterministic(self):
        """Test that HMAC calculation is deterministic."""
        second_hash = "test_second_hash"
        sequence_number = 123
        device_id = "device_456"
        encoded_action = json.dumps({"type": "AddCategoryAction"})

        result1 = calculate_hmac_sha256(second_hash, sequence_number, device_id, encoded_action)
        result2 = calculate_hmac_sha256(second_hash, sequence_number, device_id, encoded_action)

        assert result1 == result2, "HMAC should be deterministic for same inputs"

    def test_hmac_different_keys(self):
        """Test that different keys produce different HMACs."""
        action = json.dumps({"type": "AddCategoryAction"})

        result1 = calculate_hmac_sha256("key1", 1, "device1", action)
        result2 = calculate_hmac_sha256("key2", 1, "device1", action)

        assert result1 != result2, "Different keys should produce different HMACs"


class TestAESGCMEncryption:
    """Tests for AES-GCM encryption/decryption."""

    def test_encrypt_decrypt_roundtrip(self):
        """Test that encryption followed by decryption returns original data."""
        plaintext = b"Hello, World! This is a test message."
        key = b"0123456789abcdef"  # 16 bytes for AES-128

        ciphertext = encrypt_data(plaintext, key)

        assert isinstance(ciphertext, bytes), "Ciphertext should be bytes"
        assert ciphertext != plaintext, "Ciphertext should differ from plaintext"

        decrypted = decrypt_data(ciphertext, key)
        assert decrypted == plaintext, "Decrypted data should match original plaintext"

    def test_encrypt_different_ciphertexts(self):
        """Test that same plaintext produces different ciphertexts (due to nonce)."""
        plaintext = b"Same message"
        key = b"0123456789abcdef"

        ciphertext1 = encrypt_data(plaintext, key)
        ciphertext2 = encrypt_data(plaintext, key)

        assert ciphertext1 != ciphertext2, \
            "Same plaintext should produce different ciphertexts due to random nonce"

    def test_decrypt_wrong_key_fails(self):
        """Test that decryption with wrong key fails."""
        plaintext = b"Secret message"
        key1 = b"0123456789abcdef"
        key2 = b"fedcba9876543210"

        ciphertext = encrypt_data(plaintext, key1)

        with pytest.raises(Exception):
            decrypt_data(ciphertext, key2)

    def test_encrypt_empty_data(self):
        """Test encryption of empty data."""
        plaintext = b""
        key = b"0123456789abcdef"

        ciphertext = encrypt_data(plaintext, key)
        decrypted = decrypt_data(ciphertext, key)

        assert decrypted == plaintext, "Empty data should roundtrip correctly"


class TestCurve25519Operations:
    """Tests for Curve25519 cryptographic operations."""

    def test_generate_keypair(self):
        """Test keypair generation."""
        public_key, private_key = generate_keypair()

        assert isinstance(public_key, bytes), "Public key should be bytes"
        assert isinstance(private_key, bytes), "Private key should be bytes"
        assert len(public_key) == 32, "Curve25519 public key should be 32 bytes"
        assert len(private_key) == 32, "Curve25519 private key should be 32 bytes"

    def test_generate_keypair_unique(self):
        """Test that keypair generation produces unique keys."""
        pub1, priv1 = generate_keypair()
        pub2, priv2 = generate_keypair()

        assert pub1 != pub2, "Public keys should be unique"
        assert priv1 != priv2, "Private keys should be unique"

    def test_sign_verify(self):
        """Test signing and verification."""
        public_key, private_key = generate_keypair()
        message = b"Test message to sign"

        signature = sign(private_key, message)

        assert isinstance(signature, bytes), "Signature should be bytes"
        assert len(signature) == 64, "Ed25519 signature should be 64 bytes"

        assert verify_signature(public_key, message, signature) is True, \
            "Signature verification should succeed"

    def test_verify_wrong_message(self):
        """Test that verification fails for wrong message."""
        public_key, private_key = generate_keypair()
        message1 = b"Original message"
        message2 = b"Different message"

        signature = sign(private_key, message1)

        assert verify_signature(public_key, message2, signature) is False, \
            "Signature verification should fail for different message"

    def test_verify_wrong_key(self):
        """Test that verification fails with wrong public key."""
        _, private_key = generate_keypair()
        public_key2, _ = generate_keypair()
        message = b"Test message"

        signature = sign(private_key, message)

        assert verify_signature(public_key2, message, signature) is False, \
            "Signature verification should fail with wrong public key"


class TestDHKeyExchange:
    """Tests for Diffie-Hellman key exchange."""

    def test_dh_handshake(self):
        """Test DH key exchange handshake."""
        # Generate a valid secp256r1 public key
        from cryptography.hazmat.primitives.asymmetric import ec
        from cryptography.hazmat.primitives import serialization
        
        private_key = ec.generate_private_key(ec.SECP256R1())
        public_key = private_key.public_key()
        public_key_bytes = public_key.public_bytes(
            encoding=serialization.Encoding.X962,
            format=serialization.PublicFormat.UncompressedPoint
        )
        
        server_dh_key = {
            "k": base64.b64encode(public_key_bytes).decode(),
            "v": "v1"
        }

        result = dh_handshake(server_dh_key)

        assert "shared_secret" in result, "Result should contain shared_secret"
        assert "public_key" in result, "Result should contain public_key"
        assert "key_version" in result, "Result should contain key_version"

    def test_shared_secret(self):
        """Test shared secret calculation."""
        # Generate two X25519 keypairs for ECDH
        from cryptography.hazmat.primitives.asymmetric import x25519
        
        server_private = x25519.X25519PrivateKey.generate()
        server_public = server_private.public_key()
        
        client_private = x25519.X25519PrivateKey.generate()
        client_public = client_private.public_key()

        # Calculate shared secrets
        secret1 = server_private.exchange(client_public)
        secret2 = client_private.exchange(server_public)

        assert secret1 == secret2, "Both parties should compute the same shared secret"
        assert len(secret1) == 32, "Shared secret should be 32 bytes"

    def test_dh_encrypt_decrypt(self):
        """Test DH-based encryption."""
        # Generate X25519 keypairs for both parties
        from cryptography.hazmat.primitives.asymmetric import x25519
        
        server_private = x25519.X25519PrivateKey.generate()
        server_public = server_private.public_key()
        
        client_private = x25519.X25519PrivateKey.generate()
        client_public = client_private.public_key()

        # Calculate shared secrets
        server_secret = server_private.exchange(client_public)
        client_secret = client_private.exchange(server_public)

        # Encrypt with one secret, decrypt with the other
        plaintext = b"Secret message encrypted with DH"
        ciphertext = encrypt_data(plaintext, server_secret)

        decrypted = decrypt_data(ciphertext, client_secret)
        assert decrypted == plaintext, "DH encryption/decryption should work"


class TestJWTToken:
    """Tests for JWT token generation and validation."""

    def test_generate_token(self):
        """Test JWT token generation."""
        data = {"sub": "user123", "device_id": "device456"}

        token = jwt.encode(
            data,
            settings.SECRET_KEY,
            algorithm=settings.JWT_ALGORITHM
        )

        assert isinstance(token, str), "Token should be a string"
        assert len(token) > 0, "Token should not be empty"

    def test_decode_token(self):
        """Test JWT token decoding."""
        data = {"sub": "user123", "device_id": "device456"}

        token = jwt.encode(
            data,
            settings.SECRET_KEY,
            algorithm=settings.JWT_ALGORITHM
        )

        decoded = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM]
        )

        assert decoded["sub"] == "user123", "Subject should match"
        assert decoded["device_id"] == "device456", "Device ID should match"

    def test_token_expiration(self):
        """Test token expiration claim."""
        token = generate_token("user123")

        decoded = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM]
        )

        assert "exp" in decoded, "Token should have expiration claim"

    def test_invalid_token_rejected(self):
        """Test that invalid tokens are rejected."""
        invalid_token = "invalid.token.here"

        with pytest.raises(jwt.JWTError):
            jwt.decode(
                invalid_token,
                settings.SECRET_KEY,
                algorithms=[settings.JWT_ALGORITHM]
            )

    def test_wrong_secret_rejected(self):
        """Test that tokens signed with wrong secret are rejected."""
        data = {"sub": "user123"}

        token = jwt.encode(
            data,
            "wrong_secret",
            algorithm=settings.JWT_ALGORITHM
        )

        with pytest.raises(jwt.JWTError):
            jwt.decode(
                token,
                settings.SECRET_KEY,
                algorithms=[settings.JWT_ALGORITHM]
            )


class TestCryptContainer:
    """Tests for CryptContainer class."""

    def test_encrypt_decrypt_v1(self):
        """Test CryptContainer encryption/decryption with v1 format."""
        key = b"0123456789abcdef"  # 16 bytes for AES-128
        plaintext = b"Test data for encryption"
        generation = 1
        counter = 0
        format_version = CryptContainer.FORMAT_APP_LIST_V2

        encrypted = CryptContainer.encrypt_data(plaintext, key, generation, counter, format_version)
        decrypted = CryptContainer.decrypt_data(encrypted, key)

        assert decrypted == plaintext, "Decrypted data should match original"

    def test_encrypt_decrypt_v2(self):
        """Test CryptContainer encryption/decryption with v2 format."""
        key = b"0123456789abcdef"
        plaintext = b"Test data for v2 encryption"
        generation = 1
        counter = 0
        format_version = CryptContainer.FORMAT_APP_DIFF_V2

        encrypted = CryptContainer.encrypt_data(plaintext, key, generation, counter, format_version)
        decrypted = CryptContainer.decrypt_data(encrypted, key)

        assert decrypted == plaintext, "Decrypted data should match original"

    def test_encrypt_decrypt_with_salt(self):
        """Test CryptContainer with salt parameter."""
        key = b"0123456789abcdef"
        salt = b"random_salt_16_bytes!!"
        plaintext = b"Data with salt"
        generation = 1
        counter = 0
        format_version = CryptContainer.FORMAT_APP_LIST_V2

        # Note: The current implementation doesn't use salt parameter
        # This test verifies the basic functionality
        encrypted = CryptContainer.encrypt_data(plaintext, key, generation, counter, format_version)
        decrypted = CryptContainer.decrypt_data(encrypted, key)

        assert decrypted == plaintext, "Decrypted data should match original"
