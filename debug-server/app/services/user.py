"""User service for user management and authentication."""

from datetime import datetime, timezone
from typing import Optional

from app.models.user import User, UserCreate
from app.services.security import get_password_hash, verify_password


# In-memory user storage
fake_users_db: dict[int, User] = {}

# Auto-incrementing ID counter
_user_id_counter: int = 0


def _get_next_user_id() -> int:
    """Get the next available user ID.
    
    Returns:
        The next user ID.
    """
    global _user_id_counter
    _user_id_counter += 1
    return _user_id_counter


def get_user(user_id: int) -> Optional[User]:
    """Get a user by their ID.
    
    Args:
        user_id: The ID of the user to retrieve.
        
    Returns:
        The User if found, None otherwise.
    """
    return fake_users_db.get(user_id)


def get_user_by_email(email: str) -> Optional[User]:
    """Get a user by their email address.
    
    Args:
        email: The email address of the user to retrieve.
        
    Returns:
        The User if found, None otherwise.
    """
    for user in fake_users_db.values():
        if user.email == email:
            return user
    return None


def create_user(user_in: UserCreate) -> User:
    """Create a new user.
    
    Args:
        user_in: The user creation data containing email and password.
        
    Returns:
        The created User instance.
        
    Raises:
        ValueError: If a user with the same email already exists.
    """
    # Check if email already exists
    existing_user = get_user_by_email(user_in.email)
    if existing_user is not None:
        raise ValueError(f"User with email {user_in.email} already exists")
    
    # Hash the password
    hashed_password = get_password_hash(user_in.password)
    
    # Create new user with auto-incremented ID
    user_id = _get_next_user_id()
    user = User(
        id=user_id,
        email=user_in.email,
        is_active=True,
        created_at=datetime.now(timezone.utc)
    )
    
    # Store in fake database
    fake_users_db[user_id] = user
    
    # Store the hashed password for authentication
    store_password_hash(user_in.email, hashed_password)
    
    return user


def authenticate_user(email: str, password: str) -> Optional[User]:
    """Authenticate a user by email and password.
    
    Args:
        email: The email address of the user.
        password: The plain text password to verify.
        
    Returns:
        The User if authentication is successful, None otherwise.
    """
    user = get_user_by_email(email)
    if user is None:
        return None
    
    # For authentication, we need to verify against the stored hashed password
    # Since we don't store the hashed password in the User model, we need to
    # re-hash the password and compare. In a real implementation, we'd store
    # the hashed password.
    # For this mock implementation, we'll use a simple approach:
    # We need to track the hashed password separately
    
    # Get the hashed password from our storage
    # We need to store this somewhere - let's use a separate dict
    if not hasattr(authenticate_user, '_password_hashes'):
        authenticate_user._password_hashes = {}  # type: ignore
    
    stored_hash = authenticate_user._password_hashes.get(email)
    if stored_hash is None:
        return None
    
    if verify_password(password, stored_hash):
        return user
    
    return None


def store_password_hash(email: str, hashed_password: str) -> None:
    """Store a password hash for a user (used during user creation).
    
    Args:
        email: The email address of the user.
        hashed_password: The hashed password to store.
    """
    if not hasattr(authenticate_user, '_password_hashes'):
        authenticate_user._password_hashes = {}  # type: ignore
    authenticate_user._password_hashes[email] = hashed_password


def clear_users_db() -> None:
    """Clear the in-memory user database (useful for testing).
    
    This function resets the user database and ID counter.
    """
    global _user_id_counter
    fake_users_db.clear()
    _user_id_counter = 0
    if hasattr(authenticate_user, '_password_hashes'):
        authenticate_user._password_hashes = {}  # type: ignore