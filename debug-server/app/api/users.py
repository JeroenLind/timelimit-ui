"""User management API endpoints for the debug server."""

from fastapi import APIRouter, HTTPException, status

from app.models.user import User
from app.services.user import get_user, get_user_by_email

router = APIRouter()


@router.get(
    "/users/{user_id}",
    response_model=User,
    responses={404: {"description": "User not found"}},
    tags=["users"],
)
async def get_user_by_id(user_id: int) -> User:
    """Get a user by their ID.

    Args:
        user_id: The ID of the user to retrieve.

    Returns:
        The user with the specified ID.

    Raises:
        HTTPException: 404 if user is not found.
    """
    user = get_user(user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with id {user_id} not found",
        )
    return user


@router.get(
    "/users/email/{email}",
    response_model=User,
    responses={404: {"description": "User not found"}},
    tags=["users"],
)
async def get_user_by_email_endpoint(email: str) -> User:
    """Get a user by their email address.

    Args:
        email: The email address of the user to retrieve.

    Returns:
        The user with the specified email.

    Raises:
        HTTPException: 404 if user is not found.
    """
    user = get_user_by_email(email)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with email {email} not found",
        )
    return user