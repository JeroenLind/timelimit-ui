"""Authentication request and response models for TimeLimit API."""

import re
from typing import Optional

from pydantic import BaseModel, Field, field_validator


# ============================================================================
# Time Endpoint
# ============================================================================

class TimeResponse(BaseModel):
    """Response model for server time endpoint."""

    time: int = Field(..., description="Server time in milliseconds")


# ============================================================================
# Mail Login Code Endpoints
# ============================================================================

# Email validation regex pattern
EMAIL_PATTERN = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')


class SendMailLoginCodeRequest(BaseModel):
    """Request model for sending mail login code."""

    mail: str = Field(..., description="Email address to send code to")
    locale: Optional[str] = Field(None, description="Locale string")
    deviceAuthToken: Optional[str] = Field(None, description="Optional existing device auth token")

    @field_validator('mail')
    @classmethod
    def validate_email(cls, v: str) -> str:
        """Validate email format.

        Args:
            v: The email address to validate.

        Returns:
            The validated email address.

        Raises:
            ValueError: If the email format is invalid.
        """
        if not EMAIL_PATTERN.match(v):
            raise ValueError('Invalid email format')
        return v


class SendMailLoginCodeResponse(BaseModel):
    """Response model for send mail login code endpoint."""

    status: str = Field(default="ok", description="Status of the operation")
    mailLoginToken: str = Field(..., description="Token for subsequent auth steps")
    mailServerBlacklisted: bool = Field(default=False, description="If true, mail server is blacklisted")
    mailAddressNotWhitelisted: bool = Field(default=False, description="If true, email is not whitelisted")
    blockedForIntegrityReasons: bool = Field(default=False, description="If true, blocked for integrity reasons")
    mailServerBlacklistedTemporarily: bool = Field(default=False, description="If true, temporarily blacklisted")


class SignInByMailCodeRequest(BaseModel):
    """Request model for signing in by mail code."""

    mailLoginToken: str = Field(..., description="Token from send-mail-login-code-v2")
    receivedCode: str = Field(..., description="Verification code received by email")


class SignInByMailCodeResponse(BaseModel):
    """Response model for sign in by mail code endpoint."""

    status: str = Field(default="ok", description="Status of the operation")
    mailAuthToken: str = Field(..., description="Token for subsequent auth steps")


# ============================================================================
# Parent Status Endpoints
# ============================================================================

class GetStatusByMailAddressRequest(BaseModel):
    """Request model for getting status by mail address."""

    mailAuthToken: str = Field(..., description="Mail auth token from sign-in")


class GetStatusByMailAddressResponse(BaseModel):
    """Response model for get status by mail address endpoint."""

    status: str = Field(..., description="Family status: 'with family' or 'without family'")
    mail: str = Field(..., description="Email address")
    canCreateFamily: bool = Field(..., description="Whether can create a new family")
    alwaysPro: bool = Field(..., description="Whether always has premium features")


# ============================================================================
# Parent Password Model
# ============================================================================

class ParentPassword(BaseModel):
    """Model for parent password data."""

    hash: str = Field(..., description="Bcrypt hash of password")
    secondHash: str = Field(..., description="Second bcrypt hash with separate salt")
    secondSalt: str = Field(..., description="Salt for second hash")
    encrypted: bool = Field(default=False, description="Whether secondHash is DH-encrypted")


# ============================================================================
# Family Creation Endpoints
# ============================================================================

class CreateFamilyRequest(BaseModel):
    """Request model for creating a family."""

    mailAuthToken: str = Field(..., description="Mail auth token from sign-in")
    parentPassword: ParentPassword = Field(..., description="Parent password data")
    locale: Optional[str] = Field(None, description="Locale string")
    deviceName: Optional[str] = Field(None, description="Device name")
    deviceModel: Optional[str] = Field(None, description="Device model")


class CreateFamilyResponse(BaseModel):
    """Response model for create family endpoint."""

    status: str = Field(default="ok", description="Status of the operation")
    deviceAuthToken: str = Field(..., description="Device auth token for subsequent requests")
    ownDeviceId: str = Field(..., description="This device's ID")
    data: Optional[dict] = Field(None, description="Server data status (ServerDataStatus)")


class SignInIntoFamilyRequest(BaseModel):
    """Request model for signing into an existing family."""

    mailAuthToken: str = Field(..., description="Mail auth token from sign-in")
    parentPasswordSecondHash: str = Field(..., description="Second password hash")
    locale: Optional[str] = Field(None, description="Locale string")
    deviceName: Optional[str] = Field(None, description="Device name")
    deviceModel: Optional[str] = Field(None, description="Device model")


class SignInIntoFamilyResponse(BaseModel):
    """Response model for sign in into family endpoint."""

    status: str = Field(default="ok", description="Status of the operation")
    deviceAuthToken: str = Field(..., description="Device auth token for subsequent requests")
    ownDeviceId: str = Field(..., description="This device's ID")
    data: Optional[dict] = Field(None, description="Server data status (ServerDataStatus)")


# ============================================================================
# Password Recovery Endpoint
# ============================================================================

class RecoverParentPasswordRequest(BaseModel):
    """Request model for recovering parent password."""

    mailAuthToken: str = Field(..., description="Mail auth token from sign-in")
    newPassword: ParentPassword = Field(..., description="New parent password data")


class RecoverParentPasswordResponse(BaseModel):
    """Response model for recover parent password endpoint."""

    status: str = Field(default="ok", description="Status of the operation")