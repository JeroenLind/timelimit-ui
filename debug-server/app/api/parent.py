"""Parent management API endpoints for TimeLimit backend API simulation.

This module implements parent management endpoints:
- POST /parent/create-add-device-token — Create add-device token
- POST /parent/remove-device — Remove a device
- POST /parent/link-mail-address — Link email to parent account
- POST /parent/create-identity-token — Create identity token
- POST /parent/delete-account — Delete account
"""

import secrets
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, status

from app.core.deps import get_state_manager
from app.core.exceptions import AuthenticationError
from app.models.parent import (
    CreateAddDeviceTokenRequest,
    CreateAddDeviceTokenResponse,
    DeleteAccountRequest,
    DeleteAccountResponse,
    LinkMailAddressRequest,
    LinkMailAddressResponse,
    RemoveDeviceRequest,
    RemoveDeviceResponse,
    CreateIdentityTokenRequest,
    CreateIdentityTokenResponse,
)

router = APIRouter()


# ============================================================================
# Device Authentication Dependency
# ============================================================================

async def get_device_auth_token(
    state = Depends(get_state_manager),
    authorization: Optional[str] = Header(default=None)
) -> dict:
    """Get and validate device auth token from Authorization header.
    
    Args:
        state: The state manager instance.
        authorization: The Authorization header value.
    
    Returns:
        The device auth token data.
    
    Raises:
        AuthenticationError: If token is missing or invalid.
    """
    if authorization is None:
        raise AuthenticationError("Missing authentication token")
    
    # Extract token from "Bearer <token>" format
    if not authorization.startswith("Bearer "):
        raise AuthenticationError("Invalid authorization header format")
    
    token = authorization[7:]  # Remove "Bearer " prefix
    
    token_data = await state.get_device_auth_token(token)
    if token_data is None:
        raise AuthenticationError("Invalid or expired device auth token")
    
    return token_data


# ============================================================================
# Parent Management Endpoints
# ============================================================================

@router.post("/parent/create-add-device-token", response_model=CreateAddDeviceTokenResponse)
async def create_add_device_token(
    request: CreateAddDeviceTokenRequest,
    state = Depends(get_state_manager),
    device_token_data: dict = Depends(get_device_auth_token)
) -> CreateAddDeviceTokenResponse:
    """Create an add-device token for a child device.
    
    This endpoint allows a parent to create a token that can be used
    to register a new child device.
    
    Args:
        request: The create add-device token request.
        state: The state manager for token storage.
        device_token_data: The device auth token data from dependency.
    
    Returns:
        CreateAddDeviceTokenResponse: Contains token and deviceId.
    
    Raises:
        HTTPException: 401 if device auth token is invalid.
        HTTPException: 400 if parent password second hash is invalid.
    """
    family_id = device_token_data.get("family_id")
    device_id = device_token_data.get("device_id")
    
    if not family_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid device token"
        )
    
    # Get the family to verify parent password second hash
    family = await state.get_family(family_id)
    if family is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Family not found"
        )
    
    # Verify the parent password second hash
    stored_second_hash = family.get("parent_password_second_hash", "")
    if stored_second_hash != request.parentPasswordSecondHash:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid parent password"
        )
    
    # Generate a new add-device token
    add_device_token = secrets.token_urlsafe(32)
    
    # Generate a new device ID for the child
    child_device_id = f"device_{secrets.token_urlsafe(16)}"
    
    # Store the add-device token
    await state.create_add_device_token(
        token=add_device_token,
        device_id=child_device_id,
        parent_id=device_id or family_id,
        expires_at=datetime.now(timezone.utc) + __import__('datetime').timedelta(hours=24)
    )
    
    return CreateAddDeviceTokenResponse(
        token=add_device_token,
        deviceId=child_device_id
    )


@router.post("/parent/remove-device", response_model=RemoveDeviceResponse)
async def remove_device(
    request: RemoveDeviceRequest,
    state = Depends(get_state_manager),
    device_token_data: dict = Depends(get_device_auth_token)
) -> RemoveDeviceResponse:
    """Remove a device from the family.
    
    This endpoint allows a parent to remove a device from their family.
    
    Args:
        request: The remove device request.
        state: The state manager for device storage.
        device_token_data: The device auth token data from dependency.
    
    Returns:
        RemoveDeviceResponse: Status of the operation.
    
    Raises:
        HTTPException: 401 if device auth token is invalid.
        HTTPException: 400 if device ID is invalid.
    """
    family_id = device_token_data.get("family_id")
    
    if not family_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid device token"
        )
    
    # Delete the device
    deleted = await state.delete_device(request.deviceId)
    
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Device not found"
        )
    
    # Delete the device auth token if it exists
    await state.delete_device_auth_token(request.deviceId)
    
    return RemoveDeviceResponse(status="ok")


@router.post("/parent/link-mail-address", response_model=LinkMailAddressResponse)
async def link_mail_address(
    request: LinkMailAddressRequest,
    state = Depends(get_state_manager),
    device_token_data: dict = Depends(get_device_auth_token)
) -> LinkMailAddressResponse:
    """Link an email address to the parent account.
    
    This endpoint allows a parent to link an email address to their account
    using a mail auth token.
    
    Args:
        request: The link mail address request.
        state: The state manager for token storage.
        device_token_data: The device auth token data from dependency.
    
    Returns:
        LinkMailAddressResponse: Status of the operation.
    
    Raises:
        HTTPException: 401 if device auth token or mail auth token is invalid.
    """
    family_id = device_token_data.get("family_id")
    
    if not family_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid device token"
        )
    
    # Get the mail auth token
    mail_token_data = await state.get_mail_auth_token(request.mailAuthToken)
    
    if mail_token_data is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid mail auth token"
        )
    
    # Get the family
    family = await state.get_family(family_id)
    if family is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Family not found"
        )
    
    # Update the family with the linked email
    mail = mail_token_data.get("mail", "")
    await state.update_family(family_id, {"linked_mail": mail})
    
    return LinkMailAddressResponse(status="ok")


@router.post("/parent/create-identity-token", response_model=CreateIdentityTokenResponse)
async def create_identity_token(
    request: CreateIdentityTokenRequest,
    state = Depends(get_state_manager),
    device_token_data: dict = Depends(get_device_auth_token)
) -> CreateIdentityTokenResponse:
    """Create an identity token for external authentication.
    
    This endpoint creates an identity token that can be used for
    external authentication systems.
    
    Args:
        request: The create identity token request.
        state: The state manager for token storage.
        device_token_data: The device auth token data from dependency.
    
    Returns:
        CreateIdentityTokenResponse: Contains the identity token.
    
    Raises:
        HTTPException: 401 if device auth token is invalid.
    """
    family_id = device_token_data.get("family_id")
    device_id = device_token_data.get("device_id")
    
    if not family_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid device token"
        )
    
    # Generate an identity token
    identity_token = secrets.token_urlsafe(32)
    
    # Store the identity token (in a real implementation, this would be stored
    # with expiration and associated with the family)
    # For the test server, we just return the token
    
    return CreateIdentityTokenResponse(identityToken=identity_token)


@router.post("/parent/delete-account", response_model=DeleteAccountResponse)
async def delete_account(
    request: DeleteAccountRequest,
    state = Depends(get_state_manager),
    device_token_data: dict = Depends(get_device_auth_token)
) -> DeleteAccountResponse:
    """Delete the parent account and all associated data.
    
    This endpoint deletes the entire family account, including all devices,
    users, and associated data.
    
    Args:
        request: The delete account request.
        state: The state manager for account storage.
        device_token_data: The device auth token data from dependency.
    
    Returns:
        DeleteAccountResponse: Status of the operation.
    
    Raises:
        HTTPException: 401 if device auth token is invalid.
    """
    family_id = device_token_data.get("family_id")
    
    if not family_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid device token"
        )
    
    # Get all devices in the family
    devices = await state.get_devices_by_family(family_id)
    
    # Delete all devices
    for device in devices:
        device_id = device.get("device_id")
        if device_id:
            await state.delete_device(device_id)
    
    # Get all users in the family
    users = await state.get_users_by_family(family_id)
    
    # Delete all users
    for user in users:
        user_id = user.get("user_id") or user.get("id")
        if user_id:
            await state.delete_user(user_id)
    
    # Delete all categories
    for category in state._categories.values():
        if category.get("family_id") == family_id:
            cat_id = category.get("category_id") or category.get("id")
            if cat_id:
                await state.delete_category(cat_id)
    
    # Delete the family
    await state.delete_family(family_id)
    
    # Delete the device auth token
    device_id = device_token_data.get("device_id")
    if device_id:
        await state.delete_device_auth_token(device_id)
    
    return DeleteAccountResponse(status="ok")