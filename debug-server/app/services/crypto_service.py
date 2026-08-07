"""Crypto service wrapper for TimeLimit API.

This module provides a service wrapper for cryptographic operations
including JWT management, password hashing, HMAC signing, and
encryption/decryption.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, Tuple

from app.core.security import (
    calculate_hmac_sha256,
    calculate_hmac_sha512,
    calculate_sha512_hex,
    decrypt_data,
    dh_encrypt,
    dh_handshake,
    encrypt_data,
    generate_keypair,
    generate_secure_token,
    hash_password,
    shared_secret,
    sign,
    verify,
    validate_token,
)

logger = logging.getLogger(__name__)


class CryptoService:
    """Crypto service wrapper for TimeLimit API.
    
    Provides high-level cryptographic operations for the API.
    """
    
    def __init__(self):
        """Initialize the crypto service."""
        pass
    
    # ========================================================================
    # JWT Operations
    # ========================================================================
    
    def generate_token(
        self,
        user_id: str,
        device_id: str = None,
        expires_delta: timedelta = None
    ) -> str:
        """Generate a JWT token.
        
        Args:
            user_id: User ID for the token subject.
            device_id: Optional device ID.
            expires_delta: Optional expiration delta.
            
        Returns:
            JWT token string.
        """
        from app.core.security import generate_token as _generate_token
        return _generate_token(user_id, device_id, expires_delta)
    
    def validate_token(self, token: str) -> Dict[str, Any]:
        """Validate a JWT token.
        
        Args:
            token: JWT token string.
            
        Returns:
            Token payload dictionary.
        """
        return validate_token(token)
    
    # ========================================================================
    # Password Operations
    # ========================================================================
    
    def hash_password(self, password: str) -> str:
        """Hash a password using bcrypt.
        
        Args:
            password: Plain text password.
            
        Returns:
            Bcrypt hash string.
        """
        return hash_password(password)
    
    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Verify a password against its hash.
        
        Args:
            plain_password: Plain text password.
            hashed_password: Bcrypt hash string.
            
        Returns:
            True if password matches, False otherwise.
        """
        from app.core.security import verify_password as _verify_password
        return _verify_password(plain_password, hashed_password)
    
    # ========================================================================
    # HMAC Operations
    # ========================================================================
    
    def calculate_hmac_sha256(
        self,
        second_hash: str,
        sequence_number: int,
        device_id: str,
        encoded_action: str
    ) -> str:
        """Calculate HMAC-SHA256 for action integrity.
        
        Args:
            second_hash: Second password hash (key).
            sequence_number: Action sequence number.
            device_id: Device ID.
            encoded_action: Encoded action string.
            
        Returns:
            HMAC string in format "password:" + base64(hmac).
        """
        return calculate_hmac_sha256(second_hash, sequence_number, device_id, encoded_action)
    
    def calculate_hmac_sha512(self, key_base64: str, message: str) -> str:
        """Calculate HMAC-SHA512.
        
        Args:
            key_base64: Base64 encoded key.
            message: Message to sign.
            
        Returns:
            HMAC string.
        """
        return calculate_hmac_sha512(key_base64, message)
    
    def calculate_sha512_hex(self, message: str) -> str:
        """Calculate SHA512 hex digest.
        
        Args:
            message: Message to hash.
            
        Returns:
            Hex digest string.
        """
        return calculate_sha512_hex(message)
    
    # ========================================================================
    # AES-GCM Operations
    # ========================================================================
    
    def encrypt_data(self, plaintext: bytes, key: bytes) -> bytes:
        """Encrypt data using AES-GCM.
        
        Args:
            plaintext: Data to encrypt.
            key: Encryption key.
            
        Returns:
            Encrypted data.
        """
        return encrypt_data(plaintext, key)
    
    def decrypt_data(self, ciphertext: bytes, key: bytes) -> bytes:
        """Decrypt data using AES-GCM.
        
        Args:
            ciphertext: Data to decrypt.
            key: Decryption key.
            
        Returns:
            Decrypted data.
        """
        return decrypt_data(ciphertext, key)
    
    # ========================================================================
    # Curve25519 Operations
    # ========================================================================
    
    def generate_keypair(self) -> Tuple[str, str]:
        """Generate a Curve25519 key pair.
        
        Returns:
            Tuple of (public_key, private_key) as base64 strings.
        """
        public_key, private_key = generate_keypair()
        return public_key, private_key
    
    def sign(self, private_key: bytes, message: bytes) -> bytes:
        """Sign a message using Curve25519.
        
        Args:
            private_key: Private key bytes.
            message: Message to sign.
            
        Returns:
            Signature bytes.
        """
        return sign(private_key, message)
    
    def verify(self, public_key: bytes, message: bytes, signature: bytes) -> bool:
        """Verify a signature using Curve25519.
        
        Args:
            public_key: Public key bytes.
            message: Original message.
            signature: Signature bytes.
            
        Returns:
            True if signature is valid, False otherwise.
        """
        return verify(public_key, message, signature)
    
    def shared_secret(self, private_key: bytes, public_key: bytes) -> bytes:
        """Compute ECDH shared secret.
        
        Args:
            private_key: Private key bytes.
            public_key: Public key bytes.
            
        Returns:
            Shared secret bytes.
        """
        return shared_secret(private_key, public_key)
    
    # ========================================================================
    # DH Key Exchange
    # ========================================================================
    
    def dh_handshake(self, server_dh_key: Dict[str, str]) -> Dict[str, Any]:
        """Perform DH key exchange.
        
        Args:
            server_dh_key: Server DH key dictionary with 'v' (version) and 'k' (public key).
            
        Returns:
            DH handshake result dictionary.
        """
        return dh_handshake(server_dh_key)
    
    def dh_encrypt(
        self,
        crypt_data: Dict[str, Any],
        auth_data: Dict[str, Any],
        server_dh_key: Dict[str, str]
    ) -> str:
        """Encrypt data using DH shared secret.
        
        Args:
            crypt_data: Data to encrypt.
            auth_data: Authentication data.
            server_dh_key: Server DH key.
            
        Returns:
            Encrypted data string.
        """
        return dh_encrypt(crypt_data, auth_data, server_dh_key)
    
    # ========================================================================
    # Utility Functions
    # ========================================================================
    
    def generate_secure_token(self, length: int = 32) -> str:
        """Generate a secure random token.
        
        Args:
            length: Token length.
            
        Returns:
            Secure random token string.
        """
        return generate_secure_token(length)
    
    def constant_time_compare(self, a: str, b: str) -> bool:
        """Compare two strings in constant time.
        
        Args:
            a: First string.
            b: Second string.
            
        Returns:
            True if strings are equal, False otherwise.
        """
        from app.core.security import constant_time_compare as _constant_time_compare
        return _constant_time_compare(a, b)


# Global crypto service instance
crypto_service = CryptoService()