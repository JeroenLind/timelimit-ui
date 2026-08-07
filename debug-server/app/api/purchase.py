"""Purchase management API endpoints for TimeLimit backend API simulation.

This module implements purchase management endpoints:
- POST /purchase/can-do-purchase — Check purchase eligibility
- POST /purchase/finish-purchase-by-google-play — Finish Google Play purchase
"""

from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, status

from app.core.deps import get_state_manager
from app.core.exceptions import AuthenticationError
from app.models.purchase import (
    CanDoPurchaseRequest,
    CanDoPurchaseResponse,
    FinishPurchaseByGooglePlayRequest,
    FinishPurchaseByGooglePlayResponse,
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
# Purchase Management Endpoints
# ============================================================================

@router.post("/purchase/can-do-purchase", response_model=CanDoPurchaseResponse)
async def can_do_purchase(
    request: CanDoPurchaseRequest,
    state = Depends(get_state_manager),
    device_token_data: dict = Depends(get_device_auth_token)
) -> CanDoPurchaseResponse:
    """Check if a purchase can be done for a given product.
    
    This endpoint checks if the device is eligible to purchase a specific product.
    
    Args:
        request: The can-do-purchase request.
        state: The state manager for device and family data.
        device_token_data: The device auth token data from dependency.
    
    Returns:
        CanDoPurchaseResponse: Contains canDoPurchase boolean.
    
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
    
    # Get the device to check purchase eligibility
    device = await state.get_device(device_id)
    if device is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Device not found"
        )
    
    # Check if the family already has full version unlocked
    family = await state.get_family(family_id)
    if family is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Family not found"
        )
    
    # Check if full version is already unlocked
    full_version_until = family.get("full_version_until")
    if full_version_until:
        # Check if the full version is still valid
        if isinstance(full_version_until, str):
            full_version_until = datetime.fromisoformat(full_version_until.replace("Z", "+00:00"))
        
        if full_version_until > datetime.now(timezone.utc):
            # Already have full version, cannot purchase
            return CanDoPurchaseResponse(canDoPurchase=False)
    
    # For the test server, we allow purchase for any product
    # In a real implementation, this would check product availability,
    # user eligibility, etc.
    can_purchase = True
    
    return CanDoPurchaseResponse(canDoPurchase=can_purchase)


@router.post("/purchase/finish-purchase-by-google-play", response_model=FinishPurchaseByGooglePlayResponse)
async def finish_purchase_by_google_play(
    request: FinishPurchaseByGooglePlayRequest,
    state = Depends(get_state_manager),
    device_token_data: dict = Depends(get_device_auth_token)
) -> FinishPurchaseByGooglePlayResponse:
    """Finish a Google Play purchase.
    
    This endpoint processes a completed Google Play purchase and unlocks
    the full version for the family.
    
    Args:
        request: The finish purchase request.
        state: The state manager for family data.
        device_token_data: The device auth token data from dependency.
    
    Returns:
        FinishPurchaseByGooglePlayResponse: Contains status and fullVersionUntil timestamp.
    
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
    
    # Get the family
    family = await state.get_family(family_id)
    if family is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Family not found"
        )
    
    # Validate the purchase (in a real implementation, this would verify
    # the purchase token with Google Play)
    # For the test server, we accept any purchase
    
    # Set full version until timestamp (1 year from now)
    full_version_until = datetime.now(timezone.utc) + timedelta(days=365)
    
    # Update the family with full version status
    await state.update_family(family_id, {
        "full_version_until": full_version_until.isoformat(),
        "last_purchase_product_id": request.productId,
        "last_purchase_token": request.purchaseToken,
        "last_purchase_at": datetime.now(timezone.utc).isoformat(),
    })
    
    return FinishPurchaseByGooglePlayResponse(
        status="ok",
        fullVersionUntil=full_version_until
    )