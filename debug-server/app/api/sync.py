"""Sync API endpoints for TimeLimit backend API simulation.

This module implements the sync protocol endpoints:
- POST /sync/push-actions — Push pending actions to server
- POST /sync/pull-status — Pull server status
- POST /sync/report-removed — Report device as removed
- POST /sync/is-device-removed — Check if device was removed
"""

import secrets
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.core.deps import get_state_manager
from app.core.exceptions import AuthenticationError
from app.models.sync import (
    ActionUploadItem,
    ActionUploadRequest,
    ActionUploadResponse,
    ClientDataStatus,
    IsDeviceRemovedRequest,
    IsDeviceRemovedResponse,
    PullStatusRequest,
    PullStatusResponse,
    ReportRemovedRequest,
    ReportRemovedResponse,
    ServerDataStatus,
)

router = APIRouter()


# ============================================================================
# Device Authentication Dependency
# ============================================================================

async def get_device_auth_token(
    request: "Request",
    state = Depends(get_state_manager)
) -> dict:
    """Get and validate device auth token from request body.
    
    Args:
        request: The FastAPI request object.
        state: The state manager instance.
    
    Returns:
        The device auth token data.
    
    Raises:
        AuthenticationError: If token is missing or invalid.
    """
    # Extract token from request body
    token = None
    if hasattr(request, 'body'):
        body = await request.body()
        import json
        try:
            data = json.loads(body)
            token = data.get("deviceAuthToken")
        except:
            pass
    
    if token is None:
        raise AuthenticationError("Missing device auth token")
    
    token_data = await state.get_device_auth_token(token)
    if token_data is None:
        raise AuthenticationError("Invalid or expired device auth token")
    
    return token_data


# ============================================================================
# Sync Endpoints
# ============================================================================

@router.post("/sync/push-actions", response_model=ActionUploadResponse)
async def push_actions(
    request: ActionUploadRequest,
    state = Depends(get_state_manager),
    device_token_data: dict = Depends(get_device_auth_token)
) -> ActionUploadResponse:
    """Push pending actions to server.
    
    This endpoint accepts a batch of actions (up to 25) and stores them
    for later processing. The sync protocol uses action-based CRDT where
    all changes are serialized as JSON actions.
    
    Args:
        request: The push actions request containing deviceAuthToken and actions.
        state: The state manager for action storage.
        device_token_data: The device auth token data from dependency.
    
    Returns:
        ActionUploadResponse: Contains shouldDoFullSync flag.
    
    Raises:
        HTTPException: 401 if device auth token is invalid.
    """
    # Validate device auth token matches
    token = request.deviceAuthToken
    token_data = await state.get_device_auth_token(token)
    if token_data is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired device auth token"
        )
    
    # Store each action and track sequence numbers
    for action in request.actions:
        # Store the action with its sequence number
        await state.add_pending_action({
            "encoded_action": action.encodedAction,
            "sequence_number": action.sequenceNumber,
            "integrity": action.integrity,
            "type": action.type,
            "user_id": action.userId,
            "family_id": token_data.get("family_id"),
            "created_at": datetime.now(timezone.utc),
        })
    
    # For the test server, we don't need to do full sync
    # In a real implementation, this would check for conflicts
    should_do_full_sync = False
    
    return ActionUploadResponse(shouldDoFullSync=should_do_full_sync)


@router.post("/sync/pull-status", response_model=PullStatusResponse)
async def pull_status(
    request: PullStatusRequest,
    state = Depends(get_state_manager),
    device_token_data: dict = Depends(get_device_auth_token)
) -> PullStatusResponse:
    """Pull server status.
    
    This endpoint returns the server's current state based on the client's
    sync status. The client sends its current version numbers, and the server
    returns only the changed data.
    
    The sync protocol uses action-based CRDT where:
    - Client sends ClientDataStatus with version numbers
    - Server returns ServerDataStatus with current data
    
    Args:
        request: The pull status request containing deviceAuthToken and client status.
        state: The state manager for data retrieval.
        device_token_data: The device auth token data from dependency.
    
    Returns:
        PullStatusResponse: Contains ServerDataStatus with current family state.
    
    Raises:
        HTTPException: 401 if device auth token is invalid.
    """
    # Validate device auth token matches
    token = request.deviceAuthToken
    token_data = await state.get_device_auth_token(token)
    if token_data is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired device auth token"
        )
    
    family_id = token_data.get("family_id")
    
    # Get all devices in the family
    devices = await state.get_devices_by_family(family_id)
    
    # Get all users in the family
    users = await state.get_users_by_family(family_id)
    
    # Get all categories for child users
    categories = []
    for user in users:
        if user.get("type") == "child":
            user_categories = await state.get_categories_by_user(user.get("id"))
            categories.extend(user_categories)
    
    # Get apps for each device
    apps = []
    for device in devices:
        device_id = device.get("device_id")
        device_apps = await state.get_apps(device_id)
        if device_apps:
            apps.append({
                "deviceId": device_id,
                "version": "1",
                "apps": device_apps
            })
    
    # Build ServerDataStatus response
    server_data = {
        "devices": {
            "version": "1",
            "data": devices
        },
        "users": {
            "version": "1",
            "data": users
        },
        "apps": apps,
        "rmCategories": [],
        "categoryBase": categories,
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
    
    return PullStatusResponse(data=server_data)


@router.post("/sync/report-removed", response_model=ReportRemovedResponse)
async def report_removed(
    request: ReportRemovedRequest,
    state = Depends(get_state_manager),
    device_token_data: dict = Depends(get_device_auth_token)
) -> ReportRemovedResponse:
    """Report device as removed.
    
    This endpoint allows a device to report that it has been removed
    from the family (e.g., after a factory reset or device change).
    
    Args:
        request: The report removed request containing deviceAuthToken.
        state: The state manager for device management.
        device_token_data: The device auth token data from dependency.
    
    Returns:
        ReportRemovedResponse: Status of the operation.
    
    Raises:
        HTTPException: 401 if device auth token is invalid.
    """
    # Validate device auth token matches
    token = request.deviceAuthToken
    token_data = await state.get_device_auth_token(token)
    if token_data is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired device auth token"
        )
    
    device_id = token_data.get("device_id")
    family_id = token_data.get("family_id")
    
    # Mark the device as removed in the family
    # In a real implementation, this would update the device status
    # For the test server, we just return success
    
    return ReportRemovedResponse(status="ok")


@router.post("/sync/is-device-removed", response_model=IsDeviceRemovedResponse)
async def is_device_removed(
    request: IsDeviceRemovedRequest,
    state = Depends(get_state_manager),
    device_token_data: dict = Depends(get_device_auth_token)
) -> IsDeviceRemovedResponse:
    """Check if device was removed.
    
    This endpoint checks if the current device has been removed from the family.
    This is used by the client to detect if it needs to re-register.
    
    Args:
        request: The is device removed request containing deviceAuthToken.
        state: The state manager for device management.
        device_token_data: The device auth token data from dependency.
    
    Returns:
        IsDeviceRemovedResponse: Contains isDeviceRemoved flag.
    
    Raises:
        HTTPException: 401 if device auth token is invalid.
    """
    # Validate device auth token matches
    token = request.deviceAuthToken
    token_data = await state.get_device_auth_token(token)
    if token_data is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired device auth token"
        )
    
    device_id = token_data.get("device_id")
    family_id = token_data.get("family_id")
    
    # Check if the device still exists in the family
    device = await state.get_device(device_id)
    
    # For the test server, device is not removed unless explicitly deleted
    is_removed = device is None
    
    return IsDeviceRemovedResponse(isDeviceRemoved=is_removed)