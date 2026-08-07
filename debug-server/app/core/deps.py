"""Dependency injection for FastAPI.

This module provides FastAPI dependencies for:
- Authentication
- Database/State access
- Configuration
"""

from typing import Annotated, Callable, Dict, Optional

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import settings
from app.core.exceptions import AuthenticationError
from app.core.security import validate_token


# HTTP Bearer token security
bearer = HTTPBearer()


def get_settings() -> "Settings":
    """Get the application settings.

    Returns:
        The settings instance.
    """
    return settings


async def get_current_user_id(
    request: Request,
    credentials: Annotated[Optional[HTTPAuthorizationCredentials], Depends(bearer)] = None
) -> str:
    """Get the current user ID from the JWT token.

    Args:
        request: The FastAPI request object.
        credentials: The HTTP bearer credentials.

    Returns:
        The user ID from the token.

    Raises:
        AuthenticationError: If the token is missing or invalid.
    """
    if credentials is None:
        raise AuthenticationError("Missing authentication token")

    token = credentials.credentials

    try:
        payload = validate_token(token)
    except Exception:
        raise AuthenticationError("Invalid authentication token")

    user_id = payload.get("sub")
    if user_id is None:
        raise AuthenticationError("Token missing subject claim")

    # Store in request state
    request.state.user_id = user_id
    request.state.device_id = payload.get("device_id")
    request.state.token_payload = payload

    return user_id


async def get_current_device_id(
    request: Request,
    user_id: Annotated[str, Depends(get_current_user_id)]
) -> Optional[str]:
    """Get the current device ID from the JWT token.

    Args:
        request: The FastAPI request object.
        user_id: The current user ID (from dependency).

    Returns:
        The device ID from the token, or None if not present.
    """
    return getattr(request.state, "device_id", None)


async def get_token_payload(
    request: Request,
    user_id: Annotated[str, Depends(get_current_user_id)]
) -> Dict:
    """Get the full token payload.

    Args:
        request: The FastAPI request object.
        user_id: The current user ID (from dependency).

    Returns:
        The full token payload.
    """
    return getattr(request.state, "token_payload", {})


def require_auth() -> Callable:
    """Create a dependency that requires authentication.

    Returns:
        A FastAPI dependency function.
    """
    async def dependency(
        request: Request,
        credentials: Annotated[Optional[HTTPAuthorizationCredentials], Depends(bearer)] = None
    ) -> Dict:
        if credentials is None:
            raise AuthenticationError("Missing authentication token")

        token = credentials.credentials

        try:
            payload = validate_token(token)
        except Exception:
            raise AuthenticationError("Invalid authentication token")

        user_id = payload.get("sub")
        if user_id is None:
            raise AuthenticationError("Token missing subject claim")

        # Store in request state
        request.state.user_id = user_id
        request.state.device_id = payload.get("device_id")
        request.state.token_payload = payload

        return payload

    return dependency


# ============================================================================
# State Dependencies
# ============================================================================

async def get_state_manager():
    """Get the state manager instance.

    Returns:
        The global state manager instance.
    """
    from app.core.state import state_manager
    return state_manager


# ============================================================================
# Configuration Dependencies
# ============================================================================

async def get_server_config() -> Dict:
    """Get server configuration.

    Returns:
        Server configuration dictionary.
    """
    return {
        "host": settings.SERVER_HOST,
        "port": settings.SERVER_PORT,
        "enable_https": settings.ENABLE_HTTPS,
    }


async def get_security_config() -> Dict:
    """Get security configuration.

    Returns:
        Security configuration dictionary.
    """
    return {
        "jwt_algorithm": settings.JWT_ALGORITHM,
        "token_expire_minutes": settings.ACCESS_TOKEN_EXPIRE_MINUTES,
        "bcrypt_cost": settings.BCRYPT_COST,
        "enable_https": settings.ENABLE_HTTPS,
    }


async def get_logging_config() -> Dict:
    """Get logging configuration.

    Returns:
        Logging configuration dictionary.
    """
    return {
        "log_level": settings.LOG_LEVEL,
        "log_file_path": settings.LOG_FILE_PATH,
        "log_max_bytes": settings.LOG_MAX_BYTES,
        "log_backup_count": settings.LOG_BACKUP_COUNT,
        "log_format": settings.LOG_FORMAT,
    }


async def get_mock_data_config() -> Dict:
    """Get mock data configuration.

    Returns:
        Mock data configuration dictionary.
    """
    return {
        "seed": settings.MOCK_DATA_SEED,
        "family_count": settings.MOCK_FAMILY_COUNT,
        "child_count": settings.MOCK_CHILD_COUNT,
        "device_count": settings.MOCK_DEVICE_COUNT,
        "category_count": settings.MOCK_CATEGORY_COUNT,
        "app_count": settings.MOCK_APP_COUNT,
    }