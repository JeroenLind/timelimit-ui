"""Authentication logic and session management.

This module provides authentication services including:
- Token validation and extraction
- Session management
- Authentication flow orchestration
"""

import logging
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from fastapi import Request
from jose import JWTError, jwt

from app.core.config import settings
from app.core.exceptions import AuthenticationError
from app.core.security import validate_token

logger = logging.getLogger(__name__)


class SessionManager:
    """Manages user sessions and authentication tokens."""

    def __init__(self):
        self._sessions: Dict[str, Dict[str, Any]] = {}

    def create_session(
        self,
        user_id: str,
        device_id: Optional[str] = None,
        expires_delta: Optional[timedelta] = None
    ) -> str:
        """Create a new session.

        Args:
            user_id: The user ID for the session.
            device_id: Optional device ID for the session.
            expires_delta: Optional expiration time delta.

        Returns:
            The session ID.
        """
        session_id = secrets.token_urlsafe(32)

        if expires_delta is None:
            expires_delta = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

        expires_at = datetime.now(timezone.utc) + expires_delta

        self._sessions[session_id] = {
            "user_id": user_id,
            "device_id": device_id,
            "created_at": datetime.now(timezone.utc),
            "expires_at": expires_at,
            "is_active": True,
        }

        logger.info(
            "Session created",
            extra={
                "event": "session_created",
                "session_id": session_id,
                "user_id": user_id,
                "device_id": device_id,
                "expires_at": expires_at.isoformat(),
            }
        )

        return session_id

    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get a session by ID.

        Args:
            session_id: The session ID.

        Returns:
            The session data, or None if not found or expired.
        """
        session = self._sessions.get(session_id)

        if session is None:
            return None

        # Check if session is expired
        if datetime.now(timezone.utc) > session["expires_at"]:
            self.invalidate_session(session_id)
            return None

        return session

    def validate_session(self, session_id: str) -> bool:
        """Validate a session.

        Args:
            session_id: The session ID.

        Returns:
            True if the session is valid, False otherwise.
        """
        session = self.get_session(session_id)
        return session is not None and session.get("is_active", False)

    def invalidate_session(self, session_id: str) -> None:
        """Invalidate a session.

        Args:
            session_id: The session ID to invalidate.
        """
        if session_id in self._sessions:
            self._sessions[session_id]["is_active"] = False
            logger.info(
                "Session invalidated",
                extra={
                    "event": "session_invalidated",
                    "session_id": session_id,
                }
            )

    def delete_session(self, session_id: str) -> None:
        """Delete a session.

        Args:
            session_id: The session ID to delete.
        """
        if session_id in self._sessions:
            del self._sessions[session_id]
            logger.info(
                "Session deleted",
                extra={
                    "event": "session_deleted",
                    "session_id": session_id,
                }
            )

    def refresh_session(self, session_id: str) -> bool:
        """Refresh a session's expiration time.

        Args:
            session_id: The session ID to refresh.

        Returns:
            True if the session was refreshed, False otherwise.
        """
        session = self.get_session(session_id)
        if session is None:
            return False

        expires_delta = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        session["expires_at"] = datetime.now(timezone.utc) + expires_delta

        logger.info(
            "Session refreshed",
            extra={
                "event": "session_refreshed",
                "session_id": session_id,
            }
        )

        return True

    def clear_expired_sessions(self) -> int:
        """Clear all expired sessions.

        Returns:
            The number of sessions cleared.
        """
        now = datetime.now(timezone.utc)
        expired = [
            sid for sid, session in self._sessions.items()
            if session["expires_at"] < now
        ]

        for sid in expired:
            self.delete_session(sid)

        if expired:
            logger.info(
                "Expired sessions cleared",
                extra={
                    "event": "expired_sessions_cleared",
                    "count": len(expired),
                }
            )

        return len(expired)

    def clear_all_sessions(self) -> None:
        """Clear all sessions."""
        count = len(self._sessions)
        self._sessions.clear()
        logger.info(
            "All sessions cleared",
            extra={
                "event": "all_sessions_cleared",
                "count": count,
            }
        )


class TokenManager:
    """Manages JWT tokens for authentication."""

    def __init__(self):
        self._token_blacklist: set = set()

    def is_token_revoked(self, token: str) -> bool:
        """Check if a token is revoked.

        Args:
            token: The JWT token to check.

        Returns:
            True if the token is revoked, False otherwise.
        """
        return token in self._token_blacklist

    def revoke_token(self, token: str) -> None:
        """Revoke a token.

        Args:
            token: The JWT token to revoke.
        """
        self._token_blacklist.add(token)
        logger.info("Token revoked", extra={"event": "token_revoked"})

    def clear_revoked_tokens(self) -> None:
        """Clear all revoked tokens."""
        count = len(self._token_blacklist)
        self._token_blacklist.clear()
        logger.info(
            "Revoked tokens cleared",
            extra={
                "event": "revoked_tokens_cleared",
                "count": count,
            }
        )


# Global instances
session_manager = SessionManager()
token_manager = TokenManager()


def extract_token_from_request(request: Request) -> Optional[str]:
    """Extract JWT token from request Authorization header.

    Args:
        request: The FastAPI request object.

    Returns:
        The token string, or None if not found.
    """
    authorization = request.headers.get("Authorization")
    if not authorization:
        return None

    if not authorization.startswith("Bearer "):
        return None

    return authorization[7:]  # Remove "Bearer " prefix


def validate_and_extract_token(request: Request) -> Dict[str, Any]:
    """Validate JWT token and extract claims.

    Args:
        request: The FastAPI request object.

    Returns:
        The token payload/claims.

    Raises:
        AuthenticationError: If the token is invalid or missing.
    """
    token = extract_token_from_request(request)

    if not token:
        raise AuthenticationError("Missing authentication token")

    if token_manager.is_token_revoked(token):
        raise AuthenticationError("Token has been revoked")

    try:
        payload = validate_token(token)
    except JWTError as e:
        logger.warning("Token validation failed", extra={"error": str(e)})
        raise AuthenticationError("Invalid authentication token")

    # Attach payload to request state
    request.state.token_payload = payload
    request.state.user_id = payload.get("sub")
    request.state.device_id = payload.get("device_id")

    return payload


def get_current_user_id(request: Request) -> Optional[str]:
    """Get the current user ID from request state.

    Args:
        request: The FastAPI request object.

    Returns:
        The user ID if authenticated, None otherwise.
    """
    return getattr(request.state, "user_id", None)


def get_current_device_id(request: Request) -> Optional[str]:
    """Get the current device ID from request state.

    Args:
        request: The FastAPI request object.

    Returns:
        The device ID if authenticated, None otherwise.
    """
    return getattr(request.state, "device_id", None)


def get_token_payload(request: Request) -> Optional[Dict[str, Any]]:
    """Get the full token payload from request state.

    Args:
        request: The FastAPI request object.

    Returns:
        The token payload if authenticated, None otherwise.
    """
    return getattr(request.state, "token_payload", None)