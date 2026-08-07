"""Security module for cryptographic operations and JWT management.

This module provides comprehensive security functionality including:
- JWT token generation and validation
- bcrypt password hashing
- HMAC signing (SHA256, SHA512)
- AES-GCM encryption with CryptContainer
- Curve25519 operations
- DH key exchange (secp256r1)
"""

import base64
import hashlib
import hmac
import os
import secrets
import struct
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, Tuple

import bcrypt
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.asymmetric import ec, x25519
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from cryptography.hazmat.primitives import serialization
from jose import jwt

from app.core.config import settings


# ============================================================================
# JWT Manager
# ============================================================================

def generate_token(
    user_id: str,
    device_id: Optional[str] = None,
    expires_delta: Optional[timedelta] = None,
    additional_claims: Optional[Dict[str, Any]] = None
) -> str:
    """Generate a JWT access token.

    Args:
        user_id: The user ID to include in the token subject claim.
        device_id: Optional device ID to include in the token.
        expires_delta: Optional time delta for token expiration.
        additional_claims: Optional additional claims to include in the token.

    Returns:
        The encoded JWT token string.
    """
    to_encode = {"sub": user_id, "jti": secrets.token_urlsafe(16)}

    if device_id:
        to_encode["device_id"] = device_id

    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(
            minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
        )

    to_encode.update({"exp": expire, "iat": datetime.now(timezone.utc)})

    encoded_jwt = jwt.encode(
        to_encode,
        settings.SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM
    )

    return encoded_jwt


def validate_token(token: str) -> Dict[str, Any]:
    """Validate a JWT token and return its claims.

    Args:
        token: The JWT token string to validate.

    Returns:
        The decoded token claims as a dictionary.

    Raises:
        jwt.JWTError: If the token is invalid, expired, or malformed.
    """
    payload = jwt.decode(
        token,
        settings.SECRET_KEY,
        algorithms=[settings.JWT_ALGORITHM]
    )
    return payload


def decode_token(token: str) -> Dict[str, Any]:
    """Decode a JWT token without verification (for debugging).

    Args:
        token: The JWT token string to decode.

    Returns:
        The decoded token claims as a dictionary.
    """
    return jwt.decode(
        token,
        settings.SECRET_KEY,
        algorithms=[settings.JWT_ALGORITHM],
        options={"verify_signature": True}
    )


# ============================================================================
# Bcrypt Hasher
# ============================================================================

def hash_password(password: str) -> str:
    """Generate a bcrypt hash for a password.

    Args:
        password: The plain text password to hash.

    Returns:
        The bcrypt hashed password as a string.
    """
    password_bytes = password.encode('utf-8')
    salt = bcrypt.gensalt(rounds=settings.BCRYPT_COST)
    hashed = bcrypt.hashpw(password_bytes, salt)
    return hashed.decode('utf-8')


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its bcrypt hash.

    Args:
        plain_password: The plain text password to verify.
        hashed_password: The bcrypt hashed password to compare against.

    Returns:
        True if the password matches, False otherwise.
    """
    try:
        plain_bytes = plain_password.encode('utf-8')
        hashed_bytes = hashed_password.encode('utf-8')
        return bcrypt.checkpw(plain_bytes, hashed_bytes)
    except Exception:
        return False


def hash_password_with_salt(password: str, salt: str) -> str:
    """Hash a password with a specific salt.

    Args:
        password: The plain text password to hash.
        salt: The salt to use for hashing (should be a bcrypt hash string).

    Returns:
        The bcrypt hashed password as a string.
    """
    password_bytes = password.encode('utf-8')
    salt_bytes = salt.encode('utf-8')
    hashed = bcrypt.hashpw(password_bytes, salt_bytes)
    return hashed.decode('utf-8')


# ============================================================================
# HMAC Signer
# ============================================================================

def calculate_hmac_sha256(
    second_hash: str,
    sequence_number: int,
    device_id: str,
    encoded_action: str
) -> str:
    """Calculate HMAC-SHA256 for sync action integrity.

    The message format is:
    seq_bytes (8) + device_id_len (4) + device_id_bytes + action_len (4) + action_bytes

    Args:
        second_hash: The key (UTF-8 bytes) for HMAC calculation.
        sequence_number: The action sequence number.
        device_id: The device ID.
        encoded_action: The encoded action string.

    Returns:
        The HMAC signature in format "password:" + base64(hmac_digest).
    """
    key = second_hash.encode('utf-8')
    message = (
        struct.pack('>q', sequence_number) +
        struct.pack('>i', len(device_id)) +
        device_id.encode('utf-8') +
        struct.pack('>i', len(encoded_action)) +
        encoded_action.encode('utf-8')
    )
    digest = hmac.new(key, message, hashlib.sha256).digest()
    return "password:" + base64.b64encode(digest).decode('utf-8')


def calculate_hmac_sha512(key_base64: str, message: str) -> str:
    """Calculate HMAC-SHA512 for legacy sync action signing.

    Args:
        key_base64: The key as a base64-encoded string.
        message: The message to sign.

    Returns:
        The base64-encoded HMAC signature.
    """
    key = base64.b64decode(key_base64)
    digest = hmac.new(key, message.encode('utf-8'), hashlib.sha512).digest()
    return base64.b64encode(digest).decode('utf-8')


def calculate_sha512_hex(message: str) -> str:
    """Calculate SHA512 hex digest for legacy integrity.

    Args:
        message: The message to hash.

    Returns:
        The hex-encoded SHA512 digest.
    """
    return hashlib.sha512(message.encode('utf-8')).hexdigest()


# ============================================================================
# AES-GCM CryptContainer
# ============================================================================

class CryptContainer:
    """AES-GCM encryption container for encrypted app lists.

    Supports multiple format versions:
    - FORMAT_LEGACY (0)
    - FORMAT_APP_LIST_V2 (1)
    - FORMAT_APP_DIFF_V2 (2)
    """

    FORMAT_LEGACY = 0
    FORMAT_APP_LIST_V2 = 1
    FORMAT_APP_DIFF_V2 = 2

    @staticmethod
    def encrypt_data(
        plaintext: bytes,
        key: bytes,
        generation: int,
        counter: int,
        format_version: int
    ) -> bytes:
        """Encrypt data using AES-GCM with the CryptContainer format.

        Args:
            plaintext: The data to encrypt.
            key: The 16-byte AES key.
            generation: The generation number for key rotation.
            counter: The counter for replay attack prevention.
            format_version: The format version (0, 1, or 2).

        Returns:
            The encrypted data with header: generation (8) + counter (8) + IV (4) + ciphertext + tag.
        """
        iv = os.urandom(4)
        full_iv = iv + struct.pack('>q', counter)
        aad = struct.pack('>q', generation) + struct.pack('>h', format_version)
        aesgcm = AESGCM(key)
        ciphertext = aesgcm.encrypt(full_iv, plaintext, aad)
        header = struct.pack('>q', generation) + struct.pack('>q', counter) + iv + struct.pack('>h', format_version)
        return header + ciphertext

    @staticmethod
    def decrypt_data(data: bytes, key: bytes) -> bytes:
        """Decrypt data using AES-GCM with the CryptContainer format.

        Args:
            data: The encrypted data with header.
            key: The 16-byte AES key.

        Returns:
            The decrypted plaintext.
        """
        generation = struct.unpack('>q', data[:8])[0]
        counter = struct.unpack('>q', data[8:16])[0]
        iv = data[16:20]
        full_iv = iv + struct.pack('>q', counter)
        format_version = struct.unpack('>h', data[20:22])[0]
        aad = struct.pack('>q', generation) + struct.pack('>h', format_version)
        ciphertext = data[22:]
        aesgcm = AESGCM(key)
        return aesgcm.decrypt(full_iv, ciphertext, aad)


def encrypt_data(plaintext: bytes, key: bytes) -> bytes:
    """Encrypt data using AES-GCM.

    Args:
        plaintext: The data to encrypt.
        key: The 16-byte AES key.

    Returns:
        The encrypted data with 12-byte IV and 16-byte auth tag.
    """
    iv = os.urandom(12)
    aesgcm = AESGCM(key)
    return iv + aesgcm.encrypt(iv, plaintext, None)


def decrypt_data(ciphertext: bytes, key: bytes) -> bytes:
    """Decrypt data using AES-GCM.

    Args:
        ciphertext: The encrypted data with 12-byte IV and 16-byte auth tag.
        key: The 16-byte AES key.

    Returns:
        The decrypted plaintext.
    """
    iv = ciphertext[:12]
    actual_ciphertext = ciphertext[12:]
    aesgcm = AESGCM(key)
    return aesgcm.decrypt(iv, actual_ciphertext, None)


# ============================================================================
# Curve25519 Operations
# ============================================================================

def generate_keypair() -> Tuple[bytes, bytes]:
    """Generate a Curve25519 key pair.

    Returns:
        A tuple of (public_key_bytes, private_key_bytes), each 32 bytes.
    """
    private_key = Ed25519PrivateKey.generate()
    public_key = private_key.public_key()

    private_bytes = private_key.private_bytes_raw()
    public_bytes = public_key.public_bytes_raw()

    return public_bytes, private_bytes


def sign(private_key: bytes, message: bytes) -> bytes:
    """Sign a message using Curve25519.

    Args:
        private_key: The 32-byte private key.
        message: The message to sign.

    Returns:
        The 64-byte signature.
    """
    private_key_obj = Ed25519PrivateKey.from_private_bytes(private_key)
    return private_key_obj.sign(message)


def verify(public_key: bytes, message: bytes, signature: bytes) -> bool:
    """Verify a signature using Curve25519.

    Args:
        public_key: The 32-byte public key.
        message: The original message.
        signature: The 64-byte signature to verify.

    Returns:
        True if the signature is valid, False otherwise.
    """
    try:
        public_key_obj = Ed25519PublicKey.from_public_bytes(public_key)
        public_key_obj.verify(signature, message)
        return True
    except Exception:
        return False


def shared_secret(private_key: bytes, public_key: bytes) -> bytes:
    """Compute ECDH shared secret using X25519.

    Args:
        private_key: The 32-byte private key.
        public_key: The 32-byte public key.

    Returns:
        The 32-byte shared secret.
    """
    private_key_obj = x25519.X25519PrivateKey.from_private_bytes(private_key)
    public_key_obj = x25519.X25519PublicKey.from_public_bytes(public_key)
    return private_key_obj.exchange(public_key_obj)


# ============================================================================
# DH Key Exchange (secp256r1)
# ============================================================================

def dh_handshake(server_dh_key: Dict[str, str]) -> Dict[str, Any]:
    """Perform ECDH key exchange with secp256r1 curve.

    Args:
        server_dh_key: Dictionary with 'v' (key version) and 'k' (base64 encoded public key).

    Returns:
        Dictionary with private_key, public_key, shared_secret, and key_version.
    """
    server_public_key_bytes = base64.b64decode(server_dh_key["k"])
    server_public_key = ec.EllipticCurvePublicKey.from_encoded_point(
        ec.SECP256R1(),
        server_public_key_bytes
    )

    own_private_key = ec.generate_private_key(ec.SECP256R1())
    own_public_key = own_private_key.public_key()

    shared_secret = own_private_key.exchange(ec.ECDH(), server_public_key)

    return {
        "private_key": own_private_key,
        "public_key": own_public_key,
        "shared_secret": shared_secret,
        "key_version": server_dh_key["v"]
    }


def dh_encrypt(
    crypt_data: bytes,
    auth_data: bytes,
    server_dh_key: Dict[str, str]
) -> str:
    """Encrypt data using DH key exchange.

    Args:
        crypt_data: The data to encrypt.
        auth_data: Additional authenticated data.
        server_dh_key: Dictionary with 'v' (key version) and 'k' (base64 encoded public key).

    Returns:
        Encrypted data in format: base64(iv + encryptedData) + "." + base64(ownPublicKey) + "." + keyVersion
    """
    handshake = dh_handshake(server_dh_key)
    key = handshake["shared_secret"][:16]
    iv = os.urandom(12)
    aesgcm = AESGCM(key)
    encrypted = aesgcm.encrypt(iv, crypt_data, auth_data)

    public_key_bytes = handshake["public_key"].public_bytes(
        encoding=serialization.Encoding.X962,
        format=serialization.PublicFormat.UncompressedPoint
    )

    return (
        base64.b64encode(iv + encrypted).decode('utf-8') + "." +
        base64.b64encode(public_key_bytes).decode('utf-8') + "." +
        handshake["key_version"]
    )


# ============================================================================
# Utility Functions
# ============================================================================

def generate_secure_token(length: int = 32) -> str:
    """Generate a secure random token.

    Args:
        length: The length of the token in bytes.

    Returns:
        A URL-safe base64-encoded random token.
    """
    return secrets.token_urlsafe(length)


def constant_time_compare(a: str, b: str) -> bool:
    """Compare two strings in constant time to prevent timing attacks.

    Args:
        a: First string.
        b: Second string.

    Returns:
        True if the strings are equal, False otherwise.
    """
    return secrets.compare_digest(a, b)