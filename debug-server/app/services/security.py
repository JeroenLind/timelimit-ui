"""Security service for password hashing and JWT token management."""

import base64
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
from jose import jwt

from app.core.config import settings


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its bcrypt hash.
    
    Args:
        plain_password: The plain text password to verify.
        hashed_password: The bcrypt hashed password to compare against.
        
    Returns:
        True if the password matches, False otherwise.
    """
    try:
        # Handle both bytes and string hashed passwords
        if isinstance(hashed_password, str):
            hashed_password = hashed_password.encode('utf-8')
        
        # bcrypt requires bytes for both password and hash
        plain_bytes = plain_password.encode('utf-8')
        
        return bcrypt.checkpw(plain_bytes, hashed_password)
    except Exception:
        return False


def get_password_hash(password: str) -> str:
    """Generate a bcrypt hash for a password.
    
    Args:
        password: The plain text password to hash.
        
    Returns:
        The bcrypt hashed password as a string.
    """
    # bcrypt requires bytes
    password_bytes = password.encode('utf-8')
    
    # Generate salt with the configured cost factor
    salt = bcrypt.gensalt(rounds=settings.BCRYPT_COST)
    
    # Hash the password
    hashed = bcrypt.hashpw(password_bytes, salt)
    
    # Return as string for storage
    return hashed.decode('utf-8')


def create_access_token(
    data: dict,
    expires_delta: Optional[timedelta] = None
) -> str:
    """Create a JWT access token.
    
    Args:
        data: The data to encode in the token (typically includes 'sub' for subject).
        expires_delta: Optional time delta for token expiration. If not provided,
                      uses ACCESS_TOKEN_EXPIRE_MINUTES from settings.
        
    Returns:
        The encoded JWT token string.
    """
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(
            minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
        )
    
    to_encode.update({"exp": expire})
    
    encoded_jwt = jwt.encode(
        to_encode,
        settings.SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM
    )
    
    return encoded_jwt