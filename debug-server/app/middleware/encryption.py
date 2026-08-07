"""Encryption handshake monitoring middleware.

This middleware monitors encryption handshake events for WebSocket connections,
logging DH key exchange, key request/response protocol steps, AES-GCM operations,
and Curve25519 signing/verification.
"""

import json
import logging
from typing import Callable, Dict, Optional

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)


class EncryptionHandshakeMiddleware(BaseHTTPMiddleware):
    """Middleware for monitoring encryption handshake events."""

    def __init__(self, app):
        super().__init__(app)
        self._encryption_sessions: Dict[str, Dict] = {}

    async def dispatch(self, request: Request, call_next: Callable):
        """Process the request with encryption monitoring.

        Args:
            request: The incoming HTTP request.
            call_next: The next middleware or route handler.

        Returns:
            The response from the next handler.
        """
        # Log encryption handshake initiation for WebSocket upgrade requests
        if request.url.path == "/ws":
            logger.info(
                "Encryption handshake initiated",
                extra={
                    "event": "encryption_handshake_initiated",
                    "path": request.url.path,
                    "client_host": request.client.host if request.client else None,
                }
            )

        # Process the request
        response = await call_next(request)

        # Log encryption handshake completion
        if hasattr(response, "headers"):
            if "x-encryption-handshake" in response.headers:
                logger.info(
                    "Encryption handshake completed",
                    extra={
                        "event": "encryption_handshake_completed",
                        "path": request.url.path,
                    }
                )

        return response

    def log_dh_key_exchange(
        self,
        session_id: str,
        server_dh_key: Dict,
        own_public_key: bytes,
        shared_secret: bytes
    ) -> None:
        """Log DH key exchange event.

        Args:
            session_id: The session identifier.
            server_dh_key: The server's DH key.
            own_public_key: The client's public key.
            shared_secret: The computed shared secret.
        """
        logger.info(
            "DH key exchange completed",
            extra={
                "event": "dh_key_exchange",
                "session_id": session_id,
                "key_version": server_dh_key.get("v"),
                "shared_secret_preview": shared_secret[:8].hex() if shared_secret else None,
            }
        )

    def log_key_request(
        self,
        session_id: str,
        device_id: str,
        category_id: str,
        temp_key: bytes
    ) -> None:
        """Log key request event.

        Args:
            session_id: The session identifier.
            device_id: The requesting device ID.
            category_id: The category ID for the key request.
            temp_key: The temporary key.
        """
        logger.info(
            "Key request initiated",
            extra={
                "event": "key_request",
                "session_id": session_id,
                "device_id": device_id,
                "category_id": category_id,
                "temp_key_preview": temp_key[:8].hex() if temp_key else None,
            }
        )

    def log_key_response(
        self,
        session_id: str,
        device_id: str,
        encrypted_key: bytes,
        signature: bytes
    ) -> None:
        """Log key response event.

        Args:
            session_id: The session identifier.
            device_id: The responding device ID.
            encrypted_key: The encrypted key.
            signature: The signature.
        """
        logger.info(
            "Key response sent",
            extra={
                "event": "key_response",
                "session_id": session_id,
                "device_id": device_id,
                "encrypted_key_preview": encrypted_key[:8].hex() if encrypted_key else None,
                "signature_preview": signature[:8].hex() if signature else None,
            }
        )

    def log_aes_gcm_operation(
        self,
        session_id: str,
        operation: str,
        key_version: str,
        success: bool,
        data_size: Optional[int] = None
    ) -> None:
        """Log AES-GCM encryption/decryption operation.

        Args:
            session_id: The session identifier.
            operation: The operation type (encrypt/decrypt).
            key_version: The key version used.
            success: Whether the operation succeeded.
            data_size: The size of the data processed.
        """
        level = logging.INFO if success else logging.WARNING
        logger.log(
            level,
            f"AES-GCM {operation} operation",
            extra={
                "event": "aes_gcm_operation",
                "session_id": session_id,
                "operation": operation,
                "key_version": key_version,
                "success": success,
                "data_size": data_size,
            }
        )

    def log_curve25519_operation(
        self,
        session_id: str,
        operation: str,
        success: bool,
        key_preview: Optional[bytes] = None
    ) -> None:
        """Log Curve25519 signing/verification operation.

        Args:
            session_id: The session identifier.
            operation: The operation type (sign/verify).
            success: Whether the operation succeeded.
            key_preview: A preview of the key used.
        """
        level = logging.INFO if success else logging.WARNING
        logger.log(
            level,
            f"Curve25519 {operation} operation",
            extra={
                "event": "curve25519_operation",
                "session_id": session_id,
                "operation": operation,
                "success": success,
                "key_preview": key_preview[:8].hex() if key_preview else None,
            }
        )

    def log_encryption_failure(
        self,
        session_id: str,
        operation: str,
        error: str,
        details: Optional[Dict] = None
    ) -> None:
        """Log encryption failure with diagnostics.

        Args:
            session_id: The session identifier.
            operation: The operation that failed.
            error: The error message.
            details: Additional error details.
        """
        logger.error(
            "Encryption operation failed",
            extra={
                "event": "encryption_failure",
                "session_id": session_id,
                "operation": operation,
                "error": error,
                "details": details,
            }
        )

    def track_encryption_state(
        self,
        session_id: str,
        state: Dict
    ) -> None:
        """Track encryption state per session.

        Args:
            session_id: The session identifier.
            state: The encryption state to track.
        """
        self._encryption_sessions[session_id] = state
        logger.debug(
            "Encryption state updated",
            extra={
                "event": "encryption_state_update",
                "session_id": session_id,
                "state": state,
            }
        )

    def get_encryption_state(self, session_id: str) -> Optional[Dict]:
        """Get the encryption state for a session.

        Args:
            session_id: The session identifier.

        Returns:
            The encryption state, or None if not found.
        """
        return self._encryption_sessions.get(session_id)

    def clear_encryption_state(self, session_id: str) -> None:
        """Clear the encryption state for a session.

        Args:
            session_id: The session identifier.
        """
        if session_id in self._encryption_sessions:
            del self._encryption_sessions[session_id]
            logger.debug(
                "Encryption state cleared",
                extra={
                    "event": "encryption_state_cleared",
                    "session_id": session_id,
                }
            )


# Global middleware instance
encryption_middleware: Optional[EncryptionHandshakeMiddleware] = None


def get_encryption_middleware() -> EncryptionHandshakeMiddleware:
    """Get or create the global encryption middleware instance.

    Returns:
        The encryption middleware instance.
    """
    global encryption_middleware
    if encryption_middleware is None:
        encryption_middleware = EncryptionHandshakeMiddleware(None)
    return encryption_middleware