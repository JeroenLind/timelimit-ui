"""Child device management request and response models for TimeLimit API."""

from typing import Optional

from pydantic import BaseModel, Field


# ============================================================================
# Add Device Request/Response
# ============================================================================

class AddDeviceRequest(BaseModel):
    """Request model for adding a child device."""

    registerToken: str = Field(..., description="Add-device token from parent")
    deviceName: Optional[str] = Field(None, description="Name of the child device")
    deviceModel: Optional[str] = Field(None, description="Model of the child device")
    clientLevel: Optional[int] = Field(None, description="Client level/version")


class AddDeviceResponse(BaseModel):
    """Response model for add device endpoint."""

    status: str = Field(default="ok", description="Status of the operation")
    deviceAuthToken: str = Field(..., description="Device auth token for subsequent requests")
    ownDeviceId: str = Field(..., description="This device's ID")
    data: Optional[dict] = Field(None, description="Server data status (ServerDataStatus)")


# ============================================================================
# Update Primary Device Request/Response
# ============================================================================

class UpdatePrimaryDeviceRequest(BaseModel):
    """Request model for updating primary device."""

    deviceAuthToken: str = Field(..., description="Device auth token")
    primaryDeviceId: str = Field(..., description="ID of the new primary device")


class UpdatePrimaryDeviceResponse(BaseModel):
    """Response model for update primary device endpoint."""

    status: str = Field(default="ok", description="Status of the operation")


# ============================================================================
# Logout at Primary Device Request/Response
# ============================================================================

class LogoutAtPrimaryDeviceRequest(BaseModel):
    """Request model for logging out at primary device."""

    deviceAuthToken: str = Field(..., description="Device auth token")


class LogoutAtPrimaryDeviceResponse(BaseModel):
    """Response model for logout at primary device endpoint."""

    status: str = Field(default="ok", description="Status of the operation")