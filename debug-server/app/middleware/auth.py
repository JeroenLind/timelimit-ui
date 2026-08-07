"""JWT authentication middleware for protected endpoints.

This middleware intercepts requests to protected endpoints and validates
JWT tokens from the Authorization header. Protected endpoints include:
- /sync/*
- /parent/*
- /child/*
- /purchase/*
"""

from typing import Callable, Dict, Optional

from fastapi import HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.security import validate_token


# Protected endpoint prefixes that require JWT authentication
# Note: /child, /parent, /sync, and /purchase endpoints have their own device auth mechanism
# and should not be checked by this middleware
JWT_PROTECTED_PREFIXES = []

# Endpoints with their own authentication mechanism (device auth tokens)
DEVICE_AUTH_PREFIXES = ["/child", "/parent", "/sync", "/purchase"]


class AuthMiddleware(BaseHTTPMiddleware):
    """Middleware for JWT authentication on protected endpoints."""

    def __init__(self, app):
        """Initialize the authentication middleware.

        Args:
            app: The FastAPI/Starlette application.
        """
        super().__init__(app)
        self.bearer = HTTPBearer()

    async def dispatch(self, request: Request, call_next: Callable):
        """Process the request with authentication check.

        Args:
            request: The incoming HTTP request.
            call_next: The next middleware or route handler.

        Returns:
            The response from the next handler.

        Raises:
            HTTPException: 401 if token is missing or invalid for protected endpoints.
        """
        # Check if this is a protected endpoint requiring JWT auth
        path = request.url.path
        is_jwt_protected = any(path.startswith(prefix) for prefix in JWT_PROTECTED_PREFIXES)

        if is_jwt_protected:
            # Extract and validate token
            try:
                credentials: HTTPAuthorizationCredentials = await self.bearer(request)
                token = credentials.credentials

                # Validate the token
                payload = validate_token(token)

                # Attach user info to request state
                request.state.user_id = payload.get("sub")
                request.state.device_id = payload.get("device_id")
                request.state.token_payload = payload

            except JWTError as e:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid authentication token",
                    headers={"WWW-Authenticate": "Bearer"},
                )
            except Exception as e:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authentication failed",
                    headers={"WWW-Authenticate": "Bearer"},
                )

        # Continue to the next handler
        response = await call_next(request)
        return response


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


def get_token_payload(request: Request) -> Optional[Dict]:
    """Get the full token payload from request state.

    Args:
        request: The FastAPI request object.

    Returns:
        The token payload if authenticated, None otherwise.
    """
    return getattr(request.state, "token_payload", None)


def require_auth(request: Request) -> str:
    """Require authentication and return user ID.

    Args:
        request: The FastAPI request object.

    Returns:
        The user ID.

    Raises:
        HTTPException: 401 if not authenticated.
    """
    user_id = get_current_user_id(request)
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user_id


# FastAPI dependency for protected endpoints
def get_current_user() -> Callable:
    """Create a dependency that extracts the current user from the token.

    Returns:
        A FastAPI dependency function.
    """
    def dependency(request: Request) -> Dict:
        user_id = get_current_user_id(request)
        device_id = get_current_device_id(request)

        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token",
                headers={"WWW-Authenticate": "Bearer"},
            )

        return {
            "user_id": user_id,
            "device_id": device_id,
        }

    return dependency