"""Child device management API endpoints for TimeLimit backend API simulation.

This module implements child device management endpoints:
- POST /child/add-device — Register child device
- POST /child/update-primary-device — Update primary device
- POST /child/logout-at-primary-device — Sign out at primary device
"""

import secrets
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, status

from app.core.deps import get_state_manager
from app.core.exceptions import AuthenticationError
from app.models.child import (
    AddDeviceRequest,
    AddDeviceResponse,
    UpdatePrimaryDeviceRequest,
    UpdatePrimaryDeviceResponse,
    LogoutAtPrimaryDeviceRequest,
    LogoutAtPrimaryDeviceResponse,
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
# Child Device Endpoints
# ============================================================================

@router.post("/child/add-device", response_model=AddDeviceResponse)
async def add_device(
    request: AddDeviceRequest,
    state = Depends(get_state_manager),
    device_token_data: dict = Depends(get_device_auth_token)
) -> AddDeviceResponse:
    """Register a child device.
    
    This endpoint allows a parent to register a new child device using an add-device token.
    
    Args:
        request: The add device request containing registerToken and device info.
        state: The state manager for token storage.
        device_token_data: The device auth token data from dependency.
    
    Returns:
        AddDeviceResponse: Contains deviceAuthToken, ownDeviceId, and optional ServerDataStatus.
    
    Raises:
        HTTPException: 401 if device auth token is invalid.
        HTTPException: 400 if register token is invalid or expired.
    """
    # Get the add-device token
    add_device_token_data = await state.get_add_device_token(request.registerToken)
    
    if add_device_token_data is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired register token"
        )
    
    # Get the parent device ID from the token
    parent_device_id = add_device_token_data.get("device_id")
    parent_family_id = device_token_data.get("family_id")
    
    if not parent_family_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid parent device token"
        )
    
    # Generate a new device ID for the child
    child_device_id = f"device_{secrets.token_urlsafe(16)}"
    
    # Generate a device auth token for the child
    device_auth_token = secrets.token_urlsafe(32)
    
    # Create the child device data
    device_data = {
        "device_id": child_device_id,
        "name": request.deviceName or "Child Device",
        "model": request.deviceModel or "Unknown",
        "added_at": datetime.now(timezone.utc),
        "current_user_id": parent_family_id,
        "current_protection_level": 0,
        "highest_protection_level": 0,
        "current_app_version": "1.0.0",
        "highest_app_version": "1.0.0",
        "public_key": "",
        "platform_type": "android",
        "platform_level": 1,
        "family_id": parent_family_id,
    }
    
    # Store the device
    await state.create_device(child_device_id, device_data)
    
    # Store the device auth token
    await state.store_device_auth_token(
        token=device_auth_token,
        device_id=child_device_id,
        family_id=parent_family_id,
    )
    
    # Delete the used add-device token
    await state.delete_add_device_token(request.registerToken)
    
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
    
    return AddDeviceResponse(
        deviceAuthToken=device_auth_token,
        ownDeviceId=child_device_id,
        data=server_data,
    )


@router.post("/child/update-primary-device", response_model=UpdatePrimaryDeviceResponse)
async def update_primary_device(
    request: UpdatePrimaryDeviceRequest,
    state = Depends(get_state_manager),
    device_token_data: dict = Depends(get_device_auth_token)
) -> UpdatePrimaryDeviceResponse:
    """Update primary device.
    
    This endpoint allows a device to update its primary device status.
    
    Args:
        request: The update primary device request containing primaryDeviceId.
        state: The state manager for device storage.
        device_token_data: The device auth token data from dependency.
    
    Returns:
        UpdatePrimaryDeviceResponse: Status of the operation.
    
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
    
    # Update the device's primary device status
    # In a real implementation, this would update the family's primary device setting
    # For the test server, we just return success
    
    return UpdatePrimaryDeviceResponse(status="ok")


@router.post("/child/logout-at-primary-device", response_model=LogoutAtPrimaryDeviceResponse)
async def logout_at_primary_device(
    request: LogoutAtPrimaryDeviceRequest,
    state = Depends(get_state_manager),
    device_token_data: dict = Depends(get_device_auth_token)
) -> LogoutAtPrimaryDeviceResponse:
    """Sign out at primary device.
    
    This endpoint allows a device to sign out at the primary device.
    
    Args:
        request: The logout request (currently empty, for future use).
        state: The state manager for device storage.
        device_token_data: The device auth token data from dependency.
    
    Returns:
        LogoutAtPrimaryDeviceResponse: Status of the operation.
    
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
    
    # In a real implementation, this would:
    # 1. Mark the device as logged out at primary device
    # 2. Clear any primary device session
    # 3. Update the family's primary device setting
    
    return LogoutAtPrimaryDeviceResponse(status="ok")