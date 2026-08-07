"""Authentication API endpoints for TimeLimit backend API simulation.

This module implements both:
- Legacy generic user authentication endpoints (for backward compatibility)
- Full TimeLimit authentication flow (new endpoints)

Legacy endpoints:
- POST /register — Register a new user
- POST /login — Authenticate a user

TimeLimit endpoints:
- POST /time — Return server time in milliseconds
- POST /auth/send-mail-login-code-v2 — Generate and store email login code
- POST /auth/sign-in-by-mail-code — Validate code, return mailAuthToken
- POST /parent/get-status-by-mail-address — Check family status
- POST /parent/create-family — Create family with parent password
- POST /parent/sign-in-into-family — Sign in to existing family
- POST /parent/recover-parent-password — Recover parent password
"""

import secrets
import time
from datetime import datetime, timedelta, timezone
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm

from app.core.config import settings
from app.core.deps import get_state_manager
from app.core.security import hash_password, hash_password_with_salt
from app.models.auth import (
    CreateFamilyRequest,
    CreateFamilyResponse,
    GetStatusByMailAddressRequest,
    GetStatusByMailAddressResponse,
    ParentPassword,
    RecoverParentPasswordRequest,
    RecoverParentPasswordResponse,
    SendMailLoginCodeRequest,
    SendMailLoginCodeResponse,
    SignInByMailCodeRequest,
    SignInByMailCodeResponse,
    SignInIntoFamilyRequest,
    SignInIntoFamilyResponse,
    TimeResponse,
)
from app.models.user import Token, User, UserCreate
from app.services.security import create_access_token
from app.services.user import authenticate_user, create_user

router = APIRouter()


# ============================================================================
# Legacy Generic User Authentication Endpoints (for backward compatibility)
# ============================================================================

@router.post("/register", response_model=User)
async def register_user(user_in: UserCreate) -> User:
    """Register a new user.

    This is a legacy endpoint for backward compatibility with existing tests.

    Args:
        user_in: The user creation data containing email and password.

    Returns:
        The created user.

    Raises:
        HTTPException: 400 if user with email already exists.
    """
    try:
        user = create_user(user_in)
        return user
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post("/login", response_model=Token)
async def login(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()]
) -> Token:
    """Authenticate a user and return an access token.

    This is a legacy endpoint for backward compatibility with existing tests.

    Args:
        form_data: OAuth2 password request form containing username and password.

    Returns:
        Token containing access_token and token_type.

    Raises:
        HTTPException: 401 if authentication fails.
    """
    user = authenticate_user(form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token_expires = timedelta(
        minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
    )
    access_token = create_access_token(
        data={"sub": str(user.id)},
        expires_delta=access_token_expires
    )

    return Token(access_token=access_token, token_type="bearer")


# ============================================================================
# TimeLimit Authentication Endpoints
# ============================================================================

# ============================================================================
# Time Endpoint
# ============================================================================

@router.post("/time", response_model=TimeResponse)
async def get_server_time() -> TimeResponse:
    """Return server time in milliseconds.

    This endpoint is used by clients to synchronize their clocks.

    Returns:
        TimeResponse: Server time in milliseconds.
    """
    return TimeResponse(time=int(time.time() * 1000))


# ============================================================================
# Mail Login Code Endpoints
# ============================================================================

@router.post("/auth/send-mail-login-code-v2", response_model=SendMailLoginCodeResponse)
async def send_mail_login_code(
    request: SendMailLoginCodeRequest,
    state = Depends(get_state_manager),
) -> SendMailLoginCodeResponse:
    """Generate and store email login code.

    This is the first step in the mail-based authentication flow.
    The server generates a verification code and stores it with the email.

    Args:
        request: The mail login code request containing email and optional device token.
        state: The state manager for token storage.

    Returns:
        SendMailLoginCodeResponse: Contains mailLoginToken for subsequent steps.

    Raises:
        HTTPException: 400 if mail server is blacklisted or other integrity issues.
    """
    # Generate a secure random code (6 digits)
    code = f"{secrets.randbelow(1000000):06d}"

    # Generate a secure mail login token
    mail_login_token = secrets.token_urlsafe(32)

    # Store the mail login token with the email and code
    await state.store_mail_login_token(
        token=mail_login_token,
        mail=request.mail,
        code=code,
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=10),
    )

    # In a real implementation, we would send the code to the email
    # For the test server, we return success with the token
    return SendMailLoginCodeResponse(
        mailLoginToken=mail_login_token,
        mailServerBlacklisted=False,
        mailAddressNotWhitelisted=False,
        blockedForIntegrityReasons=False,
        mailServerBlacklistedTemporarily=False,
    )


@router.post("/auth/sign-in-by-mail-code", response_model=SignInByMailCodeResponse)
async def sign_in_by_mail_code(
    request: SignInByMailCodeRequest,
    state = Depends(get_state_manager),
) -> SignInByMailCodeResponse:
    """Validate code and return mailAuthToken.

    This is the second step in the mail-based authentication flow.
    The client provides the mailLoginToken and the received code.

    Args:
        request: The sign-in request containing mailLoginToken and receivedCode.
        state: The state manager for token storage.

    Returns:
        SignInByMailCodeResponse: Contains mailAuthToken for subsequent steps.

    Raises:
        HTTPException: 401 if the code is invalid or expired.
    """
    # Get the stored mail login token
    token_data = await state.get_mail_login_token(request.mailLoginToken)

    if token_data is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired mail login token",
        )

    # Verify the code
    if token_data.get("code") != request.receivedCode:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid verification code",
        )

    # Generate a mail auth token
    mail_auth_token = secrets.token_urlsafe(32)

    # Store the mail auth token with the email and family info
    await state.store_mail_auth_token(
        token=mail_auth_token,
        mail=token_data.get("mail", ""),
        family_id="",  # Will be set when family is created or user signs in
    )

    # Delete the used mail login token
    await state.delete_mail_login_token(request.mailLoginToken)

    return SignInByMailCodeResponse(mailAuthToken=mail_auth_token)


# ============================================================================
# Parent Status Endpoints
# ============================================================================

@router.post("/parent/get-status-by-mail-address", response_model=GetStatusByMailAddressResponse)
async def get_status_by_mail_address(
    request: GetStatusByMailAddressRequest,
    state = Depends(get_state_manager),
) -> GetStatusByMailAddressResponse:
    """Check family status by mail auth token.

    This endpoint checks if the email is linked to a family and whether
    the user can create a new family or needs to sign in to an existing one.

    Args:
        request: The status request containing mailAuthToken.
        state: The state manager for token storage.

    Returns:
        GetStatusByMailAddressResponse: Family status information.

    Raises:
        HTTPException: 401 if the mail auth token is invalid.
    """
    # Get the stored mail auth token
    token_data = await state.get_mail_auth_token(request.mailAuthToken)

    if token_data is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid mail auth token",
        )

    mail = token_data.get("mail", "")
    family_id = token_data.get("family_id", "")

    # Check if there's an existing family for this email
    has_family = family_id != "" and await state.get_family(family_id) is not None

    return GetStatusByMailAddressResponse(
        mail=mail,
        status="with family" if has_family else "without family",
        canCreateFamily=not has_family,
        alwaysPro=False,  # Test server doesn't have premium
    )


# ============================================================================
# Family Creation Endpoints
# ============================================================================

@router.post("/parent/create-family", response_model=CreateFamilyResponse)
async def create_family(
    request: CreateFamilyRequest,
    state = Depends(get_state_manager),
) -> CreateFamilyResponse:
    """Create a new family with parent password.

    This is the third step in the mail-based authentication flow for new families.
    The parent password is hashed and stored securely.

    Args:
        request: The create family request containing mailAuthToken and parent password.
        state: The state manager for token storage.

    Returns:
        CreateFamilyResponse: Contains deviceAuthToken and ownDeviceId.

    Raises:
        HTTPException: 401 if the mail auth token is invalid.
        HTTPException: 400 if family already exists.
    """
    # Get the stored mail auth token
    token_data = await state.get_mail_auth_token(request.mailAuthToken)

    if token_data is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid mail auth token",
        )

    mail = token_data.get("mail", "")

    # Check if a family already exists for this email
    existing_family = await state.get_family_by_mail(mail)
    if existing_family is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Family already exists for this email",
        )

    # Generate a unique family ID
    family_id = f"family_{secrets.token_urlsafe(16)}"

    # Generate a unique device ID
    own_device_id = f"device_{secrets.token_urlsafe(16)}"

    # Generate a device auth token
    device_auth_token = secrets.token_urlsafe(32)

    # Hash the parent password
    password_hash = hash_password(request.parentPassword.hash)
    second_hash = hash_password_with_salt(
        request.parentPassword.hash,
        request.parentPassword.secondSalt,
    )

    # Create the family data
    family_data = {
        "family_id": family_id,
        "mail": mail,
        "created_at": datetime.now(timezone.utc),
        "parent_password_hash": password_hash,
        "parent_password_second_hash": second_hash,
        "parent_password_second_salt": request.parentPassword.secondSalt,
        "parent_password_encrypted": request.parentPassword.encrypted,
    }

    # Store the family
    await state.create_family(family_id, family_data)

    # Store the device auth token
    await state.store_device_auth_token(
        token=device_auth_token,
        device_id=own_device_id,
        family_id=family_id,
    )

    # Update the mail auth token with the family ID
    await state.store_mail_auth_token(
        token=request.mailAuthToken,
        mail=mail,
        family_id=family_id,
    )

    # Create initial server data status
    server_data = {
        "devices": {"version": "1", "data": []},
        "users": {"version": "1", "data": []},
        "apps": [],
        "rmCategories": [],
        "categoryBase": [],
        "categoryApp": [],
        "usedTimes": [],
        "rules": [],
        "tasks": [],
        "krq": [],
        "kr": [],
        "pings": [],
        "dh": {"v": "1", "k": ""},
        "u2f": {"v": "1", "d": []},
        "fullVersion": 0,
        "message": "",
        "apiLevel": 1,
    }

    return CreateFamilyResponse(
        deviceAuthToken=device_auth_token,
        ownDeviceId=own_device_id,
        data=server_data,
    )


@router.post("/parent/sign-in-into-family", response_model=SignInIntoFamilyResponse)
async def sign_in_into_family(
    request: SignInIntoFamilyRequest,
    state = Depends(get_state_manager),
) -> SignInIntoFamilyResponse:
    """Sign in to an existing family.

    This is the second step in the mail-based authentication flow for existing families.
    The user provides the mail auth token and parent password second hash.

    Args:
        request: The sign-in request containing mailAuthToken and parent password second hash.
        state: The state manager for token storage.

    Returns:
        SignInIntoFamilyResponse: Contains deviceAuthToken and ownDeviceId.

    Raises:
        HTTPException: 401 if the mail auth token is invalid or password is wrong.
    """
    # Get the stored mail auth token
    token_data = await state.get_mail_auth_token(request.mailAuthToken)

    if token_data is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid mail auth token",
        )

    family_id = token_data.get("family_id", "")
    mail = token_data.get("mail", "")

    if not family_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No family exists for this email. Use create-family instead.",
        )

    # Get the family
    family = await state.get_family(family_id)
    if family is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Family not found",
        )

    # Verify the parent password second hash
    stored_second_hash = family.get("parent_password_second_hash", "")
    if stored_second_hash != request.parentPasswordSecondHash:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid parent password",
        )

    # Generate a unique device ID
    own_device_id = f"device_{secrets.token_urlsafe(16)}"

    # Generate a device auth token
    device_auth_token = secrets.token_urlsafe(32)

    # Store the device auth token
    await state.store_device_auth_token(
        token=device_auth_token,
        device_id=own_device_id,
        family_id=family_id,
    )

    # Create initial server data status
    server_data = {
        "devices": {"version": "1", "data": []},
        "users": {"version": "1", "data": []},
        "apps": [],
        "rmCategories": [],
        "categoryBase": [],
        "categoryApp": [],
        "usedTimes": [],
        "rules": [],
        "tasks": [],
        "krq": [],
        "kr": [],
        "pings": [],
        "dh": {"v": "1", "k": ""},
        "u2f": {"v": "1", "d": []},
        "fullVersion": 0,
        "message": "",
        "apiLevel": 1,
    }

    return SignInIntoFamilyResponse(
        deviceAuthToken=device_auth_token,
        ownDeviceId=own_device_id,
        data=server_data,
    )


# ============================================================================
# Password Recovery Endpoint
# ============================================================================

@router.post("/parent/recover-parent-password", response_model=RecoverParentPasswordResponse)
async def recover_parent_password(
    request: RecoverParentPasswordRequest,
    state = Depends(get_state_manager),
) -> RecoverParentPasswordResponse:
    """Recover parent password.

    This endpoint allows a parent to reset their password using the mail auth token.

    Args:
        request: The recovery request containing mailAuthToken and new password.
        state: The state manager for token storage.

    Returns:
        RecoverParentPasswordResponse: Status of the operation.

    Raises:
        HTTPException: 401 if the mail auth token is invalid.
    """
    # Get the stored mail auth token
    token_data = await state.get_mail_auth_token(request.mailAuthToken)

    if token_data is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid mail auth token",
        )

    family_id = token_data.get("family_id", "")

    if not family_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No family exists for this email",
        )

    # Get the family
    family = await state.get_family(family_id)
    if family is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Family not found",
        )

    # Hash the new password
    password_hash = hash_password(request.newPassword.hash)
    second_hash = hash_password_with_salt(
        request.newPassword.hash,
        request.newPassword.secondSalt,
    )

    # Update the family with the new password
    await state.update_family(family_id, {
        "parent_password_hash": password_hash,
        "parent_password_second_hash": second_hash,
        "parent_password_second_salt": request.newPassword.secondSalt,
        "parent_password_encrypted": request.newPassword.encrypted,
    })

    return RecoverParentPasswordResponse(status="ok")