"""Device data models for TimeLimit API."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class DeviceData(BaseModel):
    """Device data model for TimeLimit API.
    
    Represents a device in the TimeLimit system.
    """
    
    deviceId: str = Field(..., description="Unique device identifier")
    name: str = Field(..., description="Human-readable device name")
    model: str = Field(..., description="Device model")
    addedAt: int = Field(..., description="Timestamp when device was added (milliseconds)")
    currentUserId: str = Field(..., description="ID of current user on this device")
    currentProtectionLevel: str = Field(default="none", description="Current protection level")
    highestProtectionLevel: str = Field(default="none", description="Highest achieved protection level")
    currentAppVersion: int = Field(default=1, description="Current app version code")
    highestAppVersion: int = Field(default=1, description="Highest app version code")
    publicKey: Optional[str] = Field(None, description="Curve25519 public key (base64)")
    platformType: Optional[str] = Field(default="android", description="Platform type")
    platformLevel: Optional[int] = Field(default=30, description="Platform API level")
    familyId: Optional[str] = Field(None, description="Family ID this device belongs to")


class DeviceCreate(BaseModel):
    """Model for creating a new device."""
    
    deviceId: str = Field(..., description="Unique device identifier")
    name: str = Field(..., description="Human-readable device name")
    model: str = Field(default="Pixel 7", description="Device model")
    platformType: str = Field(default="android", description="Platform type")
    platformLevel: int = Field(default=30, description="Platform API level")


class DeviceUpdate(BaseModel):
    """Model for updating a device."""
    
    name: Optional[str] = Field(None, description="Updated device name")
    model: Optional[str] = Field(None, description="Updated device model")
    currentUserId: Optional[str] = Field(None, description="Updated current user ID")