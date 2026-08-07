"""Middleware modules for the debug server.

This package contains middleware components including:
- auth: JWT authentication middleware for protected endpoints
- encryption: Encryption handshake monitoring middleware
- security_headers: Security header injection middleware
- logging: Request/response logging middleware
- gzip: Gzip compression/decompression middleware
"""

from app.middleware.auth import (
    AuthMiddleware,
    get_current_device_id,
    get_current_user_id,
    get_token_payload,
    require_auth,
)
from app.middleware.encryption import (
    EncryptionHandshakeMiddleware,
    get_encryption_middleware,
)
from app.middleware.security_headers import (
    SecurityHeadersMiddleware,
    add_security_headers,
)
from app.middleware.gzip import (
    GzipMiddleware,
    get_gzip_middleware,
)

__all__ = [
    # Auth middleware
    "AuthMiddleware",
    "get_current_device_id",
    "get_current_user_id",
    "get_token_payload",
    "require_auth",
    # Encryption middleware
    "EncryptionHandshakeMiddleware",
    "get_encryption_middleware",
    # Security headers middleware
    "SecurityHeadersMiddleware",
    "add_security_headers",
    # Gzip middleware
    "GzipMiddleware",
    "get_gzip_middleware",
]