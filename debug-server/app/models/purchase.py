"""Purchase management request and response models for TimeLimit API."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


# ============================================================================
# Can Do Purchase Request/Response
# ============================================================================

class CanDoPurchaseRequest(BaseModel):
    """Request model for checking purchase eligibility."""

    deviceAuthToken: Optional[str] = Field(None, description="Device auth token for authentication (optional, can be provided via Authorization header)")
    productId: str = Field(..., description="Product ID to check purchase eligibility for")


class CanDoPurchaseResponse(BaseModel):
    """Response model for can-do-purchase endpoint."""

    status: str = Field(default="ok", description="Status of the operation")
    canDoPurchase: bool = Field(..., description="Whether the purchase can be done")


# ============================================================================
# Finish Purchase By Google Play Request/Response
# ============================================================================

class FinishPurchaseByGooglePlayRequest(BaseModel):
    """Request model for finishing a Google Play purchase."""

    deviceAuthToken: Optional[str] = Field(None, description="Device auth token for authentication (optional, can be provided via Authorization header)")
    productId: str = Field(..., description="Product ID of the purchased item")
    purchaseToken: str = Field(..., description="Google Play purchase token")
    signature: str = Field(..., description="Signature of the purchase")


class FinishPurchaseByGooglePlayResponse(BaseModel):
    """Response model for finish-purchase-by-google-play endpoint."""

    status: str = Field(default="ok", description="Status of the operation")
    fullVersionUntil: Optional[datetime] = Field(
        default=None,
        description="Timestamp until full version is unlocked"
    )