"""Parent management request and response models for TimeLimit API."""

from typing import Optional

from pydantic import BaseModel, Field


# ============================================================================
# Create Add-Device Token Request/Response
# ============================================================================

class CreateAddDeviceTokenRequest(BaseModel):
    """Request model for creating an add-device token."""

    deviceAuthToken: str = Field(..., description="Device auth token for authentication")
    parentId: Optional[str] = Field(None, description="Parent user ID")
    parentPasswordSecondHash: str = Field(..., description="Parent password second hash for verification")


class CreateAddDeviceTokenResponse(BaseModel):
    """Response model for create add-device token endpoint."""

    status: str = Field(default="ok", description="Status of the operation")
    token: str = Field(..., description="Add-device token for child to use")
    deviceId: str = Field(..., description="Device ID that the token is associated with")


# ============================================================================
# Remove Device Request/Response
# ============================================================================

class RemoveDeviceRequest(BaseModel):
    """Request model for removing a device."""

    deviceAuthToken: str = Field(..., description="Device auth token for authentication")
    deviceId: str = Field(..., description="ID of the device to remove")


class RemoveDeviceResponse(BaseModel):
    """Response model for remove device endpoint."""

    status: str = Field(default="ok", description="Status of the operation")


# ============================================================================
# Link Mail Address Request/Response
# ============================================================================

class LinkMailAddressRequest(BaseModel):
    """Request model for linking email address to parent account."""

    deviceAuthToken: str = Field(..., description="Device auth token for authentication")
    mailAuthToken: str = Field(..., description="Mail auth token from sign-in")


class LinkMailAddressResponse(BaseModel):
    """Response model for link mail address endpoint."""

    status: str = Field(default="ok", description="Status of the operation")


# ============================================================================
# Create Identity Token Request/Response
# ============================================================================

class CreateIdentityTokenRequest(BaseModel):
    """Request model for creating an identity token."""

    deviceAuthToken: str = Field(..., description="Device auth token for authentication")


class CreateIdentityTokenResponse(BaseModel):
    """Response model for create identity token endpoint."""

    status: str = Field(default="ok", description="Status of the operation")
    identityToken: str = Field(..., description="Identity token for external authentication")


# ============================================================================
# Delete Account Request/Response
# ============================================================================

class DeleteAccountRequest(BaseModel):
    """Request model for deleting an account."""

    deviceAuthToken: str = Field(..., description="Device auth token for authentication")


class DeleteAccountResponse(BaseModel):
    """Response model for delete account endpoint."""

    status: str = Field(default="ok", description="Status of the operation")