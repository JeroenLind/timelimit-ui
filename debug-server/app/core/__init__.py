"""Core module for the debug server.

This module provides core infrastructure including:
- Configuration management
- Security and crypto operations
- Authentication and session management
- State management
- Custom exceptions
- Dependency injection
"""

from app.core.config import Settings, settings
from app.core.exceptions import (
    AuthenticationError,
    AuthorizationError,
    BadRequestError,
    ConflictError,
    CryptoError,
    GoneError,
    InternalServerError,
    NotFoundError,
    RateLimitError,
    ValidationError,
    create_exception_handlers,
)
from app.core.security import (
    calculate_hmac_sha256,
    calculate_hmac_sha512,
    calculate_sha512_hex,
    decrypt_data,
    dh_encrypt,
    dh_handshake,
    encrypt_data,
    generate_token,
    generate_keypair,
    hash_password,
    hash_password_with_salt,
    shared_secret,
    sign,
    validate_token,
    verify,
    verify_password,
)

__all__ = [
    # Configuration
    "Settings",
    "settings",
    # Exceptions
    "AuthenticationError",
    "AuthorizationError",
    "BadRequestError",
    "ConflictError",
    "CryptoError",
    "GoneError",
    "InternalServerError",
    "NotFoundError",
    "RateLimitError",
    "ValidationError",
    "create_exception_handlers",
    # Security
    "calculate_hmac_sha256",
    "calculate_hmac_sha512",
    "calculate_sha512_hex",
    "decrypt_data",
    "dh_encrypt",
    "dh_handshake",
    "encrypt_data",
    "generate_token",
    "generate_keypair",
    "hash_password",
    "hash_password_with_salt",
    "shared_secret",
    "sign",
    "validate_token",
    "verify",
    "verify_password",
]