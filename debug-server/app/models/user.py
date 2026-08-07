"""User authentication models for the debug server."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field


class UserBase(BaseModel):
    """Base user model with common fields."""

    email: EmailStr


class UserCreate(UserBase):
    """Model for creating a new user."""

    password: str = Field(..., min_length=8, max_length=128)


class User(UserBase):
    """Model representing a user in the system."""

    id: int
    is_active: bool = True
    created_at: datetime


class Token(BaseModel):
    """Model for authentication token response."""

    access_token: str
    token_type: str = "bearer"


class TokenPayload(BaseModel):
    """Model for JWT token payload."""

    sub: Optional[str] = None
    exp: Optional[int] = None
    device_id: Optional[str] = None