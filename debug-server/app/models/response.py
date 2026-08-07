"""Standardized API response models for TimeLimit API."""

from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class APIResponse(BaseModel):
    """Standardized API response wrapper.
    
    All responses are wrapped in this format for consistency.
    """
    
    status: str = Field(..., description="Response status: 'ok' or 'error'")
    data: Optional[Any] = Field(None, description="Response data")
    error: Optional[str] = Field(None, description="Error message if status is 'error'")


class ErrorResponse(BaseModel):
    """Error response model."""
    
    status: str = Field(default="error", description="Response status")
    error: str = Field(..., description="Error message")
    code: Optional[int] = Field(None, description="Error code")


class SuccessResponse(BaseModel):
    """Success response model."""
    
    status: str = Field(default="ok", description="Response status")
    data: Optional[Any] = Field(None, description="Response data")


class HealthCheckResponse(BaseModel):
    """Health check response model."""
    
    status: str = Field(..., description="Server status")
    version: Optional[str] = Field(None, description="Server version")
    uptime: Optional[int] = Field(None, description="Server uptime in seconds")


class MetricsResponse(BaseModel):
    """Metrics response model."""
    
    status: str = Field(default="ok", description="Response status")
    data: Dict[str, Any] = Field(default_factory=dict, description="Metrics data")
    totalRequests: int = Field(default=0, description="Total requests processed")
    totalErrors: int = Field(default=0, description="Total errors")
    activeSessions: int = Field(default=0, description="Active sessions")


class TimeResponse(BaseModel):
    """Server time response model."""
    
    time: int = Field(..., description="Server time in milliseconds")


class TokenResponse(BaseModel):
    """Token response model."""
    
    access_token: str = Field(..., description="Access token")
    token_type: str = Field(default="bearer", description="Token type")


class DeviceAuthTokenResponse(BaseModel):
    """Device auth token response model."""
    
    deviceAuthToken: str = Field(..., description="Device authentication token")
    ownDeviceId: str = Field(..., description="Own device ID")
    data: Optional[Dict[str, Any]] = Field(None, description="Server data status")


class MailLoginTokenResponse(BaseModel):
    """Mail login token response model."""
    
    mailLoginToken: str = Field(..., description="Mail login token")
    mailServerBlacklisted: bool = Field(default=False, description="Mail server blacklisted")
    mailAddressNotWhitelisted: bool = Field(default=False, description="Mail address not whitelisted")
    blockedForIntegrityReasons: bool = Field(default=False, description="Blocked for integrity reasons")
    mailServerBlacklistedTemporarily: bool = Field(default=False, description="Mail server blacklisted temporarily")


class MailAuthTokenResponse(BaseModel):
    """Mail auth token response model."""
    
    mailAuthToken: str = Field(..., description="Mail authentication token")


class FamilyStatusResponse(BaseModel):
    """Family status response model."""
    
    mail: str = Field(..., description="Email address")
    status: str = Field(..., description="Family status")
    canCreateFamily: bool = Field(default=True, description="Can create family")
    alwaysPro: bool = Field(default=False, description="Always pro status")


class AddDeviceTokenResponse(BaseModel):
    """Add device token response model."""
    
    token: str = Field(..., description="Add device token")
    deviceId: str = Field(..., description="Device ID")


class IdentityTokenResponse(BaseModel):
    """Identity token response model."""
    
    identityToken: str = Field(..., description="Identity token")


class PurchaseResponse(BaseModel):
    """Purchase response model."""
    
    status: str = Field(default="ok", description="Response status")
    fullVersionUntil: Optional[int] = Field(None, description="Full version expiration timestamp")


class CanDoPurchaseResponse(BaseModel):
    """Can do purchase response model."""
    
    canDoPurchase: bool = Field(..., description="Whether purchase can be done")


class FinishPurchaseResponse(BaseModel):
    """Finish purchase response model."""
    
    status: str = Field(default="ok", description="Response status")
    fullVersionUntil: Optional[int] = Field(None, description="Full version expiration timestamp")


class SyncResponse(BaseModel):
    """Sync response model."""
    
    shouldDoFullSync: bool = Field(..., description="Whether full sync is needed")