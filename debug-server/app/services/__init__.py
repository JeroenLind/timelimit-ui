"""Services module for the debug server.

This module provides business logic services including:
- security: Password hashing and JWT (legacy)
- user: User service (legacy)
- mock_data: Mock data generator
- sync_service: Sync protocol logic
- auth_service: Authentication service
- crypto_service: Crypto service wrapper
"""

from app.services.auth_service import auth_service
from app.services.crypto_service import crypto_service
from app.services.mock_data import mock_data_generator
from app.services.security import (
    create_access_token,
    get_password_hash,
    verify_password,
)
from app.services.sync_service import sync_service
from app.services.user import (
    authenticate_user,
    clear_users_db,
    create_user,
    get_user,
    get_user_by_email,
    store_password_hash,
)

__all__ = [
    # Legacy security functions
    "create_access_token",
    "get_password_hash",
    "verify_password",
    # Legacy user functions
    "authenticate_user",
    "clear_users_db",
    "create_user",
    "get_user",
    "get_user_by_email",
    "store_password_hash",
    # New services
    "auth_service",
    "crypto_service",
    "mock_data_generator",
    "sync_service",
]