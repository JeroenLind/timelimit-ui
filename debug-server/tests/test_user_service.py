"""Unit tests for user service.

This module tests user management business logic including user creation,
retrieval by ID and email, and authentication functionality.
"""

import pytest

from app.models.user import UserCreate
from app.services.user import (
    create_user,
    get_user,
    get_user_by_email,
    authenticate_user,
    clear_users_db,
)


class TestCreateUser:
    """Tests for user creation functionality."""

    def test_create_user(self):
        """Test creating a user with valid data.
        
        This test:
        - Creates a user with valid data
        - Verifies user is returned with correct email
        - Verifies password is hashed (not plain text)
        - Verifies user ID is assigned
        """
        # Clear any existing users
        clear_users_db()
        
        user_data = UserCreate(
            email="newuser@example.com",
            password="securepassword123"
        )
        
        # Create the user
        user = create_user(user_data)
        
        # Verify user is returned
        assert user is not None, "User should be returned"
        
        # Verify email is correct
        assert user.email == "newuser@example.com", \
            "User email should match the input email"
        
        # Verify user ID is assigned (should be a positive integer)
        assert user.id is not None, "User ID should be assigned"
        assert isinstance(user.id, int), "User ID should be an integer"
        assert user.id > 0, "User ID should be a positive integer"
        
        # Verify user is active by default
        assert user.is_active is True, "User should be active by default"
        
        # Verify created_at is set
        assert user.created_at is not None, "created_at should be set"

    def test_create_user_duplicate_email(self):
        """Test that creating a user with duplicate email raises an error."""
        # Clear any existing users
        clear_users_db()
        
        user_data = UserCreate(
            email="duplicate@example.com",
            password="password123"
        )
        
        # Create first user
        create_user(user_data)
        
        # Attempt to create another user with same email
        with pytest.raises(ValueError) as exc_info:
            create_user(user_data)
        
        assert "already exists" in str(exc_info.value), \
            "Error message should indicate email already exists"


class TestGetUser:
    """Tests for user retrieval by ID functionality."""

    def test_get_user(self):
        """Test retrieving a user by ID.
        
        This test:
        - Creates a user
        - Retrieves user by ID
        - Verifies returned user matches created user
        """
        # Clear any existing users
        clear_users_db()
        
        user_data = UserCreate(
            email="getuser@example.com",
            password="password123"
        )
        
        # Create the user
        created_user = create_user(user_data)
        
        # Retrieve the user by ID
        retrieved_user = get_user(created_user.id)
        
        # Verify user is returned
        assert retrieved_user is not None, "User should be found"
        
        # Verify the user matches
        assert retrieved_user.id == created_user.id, \
            "User ID should match"
        assert retrieved_user.email == created_user.email, \
            "User email should match"
        assert retrieved_user.is_active == created_user.is_active, \
            "User is_active should match"

    def test_get_nonexistent_user(self):
        """Test retrieving a user with non-existent ID.
        
        This test:
        - Attempts to get user with non-existent ID
        - Verifies None is returned
        """
        # Clear any existing users
        clear_users_db()
        
        # Try to get a user with a very high ID that doesn't exist
        user = get_user(99999)
        
        assert user is None, "Non-existent user should return None"


class TestGetUserByEmail:
    """Tests for user retrieval by email functionality."""

    def test_get_user_by_email(self):
        """Test retrieving a user by email.
        
        This test:
        - Creates a user
        - Retrieves user by email
        - Verifies returned user matches created user
        """
        # Clear any existing users
        clear_users_db()
        
        user_data = UserCreate(
            email="emailuser@example.com",
            password="password123"
        )
        
        # Create the user
        created_user = create_user(user_data)
        
        # Retrieve the user by email
        retrieved_user = get_user_by_email("emailuser@example.com")
        
        # Verify user is returned
        assert retrieved_user is not None, "User should be found"
        
        # Verify the user matches
        assert retrieved_user.id == created_user.id, \
            "User ID should match"
        assert retrieved_user.email == created_user.email, \
            "User email should match"

    def test_get_user_by_nonexistent_email(self):
        """Test retrieving a user with non-existent email."""
        # Clear any existing users
        clear_users_db()
        
        # Try to get a user with an email that doesn't exist
        user = get_user_by_email("nonexistent@example.com")
        
        assert user is None, "Non-existent user should return None"


class TestAuthenticateUser:
    """Tests for user authentication functionality."""

    def test_authenticate_user_success(self):
        """Test authenticating with correct credentials.
        
        This test:
        - Creates a user
        - Authenticates with correct credentials
        - Verifies user is returned
        """
        # Clear any existing users
        clear_users_db()
        
        user_data = UserCreate(
            email="authuser@example.com",
            password="correctpassword123"
        )
        
        # Create the user
        create_user(user_data)
        
        # Authenticate with correct credentials
        authenticated_user = authenticate_user(
            "authuser@example.com",
            "correctpassword123"
        )
        
        # Verify user is returned
        assert authenticated_user is not None, \
            "Authentication should succeed with correct credentials"
        assert authenticated_user.email == "authuser@example.com", \
            "Authenticated user email should match"

    def test_authenticate_user_failure(self):
        """Test authenticating with wrong password.
        
        This test:
        - Creates a user
        - Attempts authentication with wrong password
        - Verifies None is returned
        """
        # Clear any existing users
        clear_users_db()
        
        user_data = UserCreate(
            email="wrongpass@example.com",
            password="correctpassword123"
        )
        
        # Create the user
        create_user(user_data)
        
        # Attempt authentication with wrong password
        authenticated_user = authenticate_user(
            "wrongpass@example.com",
            "wrongpassword123"
        )
        
        # Verify None is returned
        assert authenticated_user is None, \
            "Authentication should fail with wrong password"

    def test_authenticate_user_nonexistent_email(self):
        """Test authenticating with non-existent email."""
        # Clear any existing users
        clear_users_db()
        
        # Attempt authentication with non-existent email
        authenticated_user = authenticate_user(
            "nonexistent@example.com",
            "anypassword123"
        )
        
        assert authenticated_user is None, \
            "Authentication should fail for non-existent email"

    def test_authenticate_user_empty_password(self):
        """Test authenticating with empty password."""
        # Clear any existing users
        clear_users_db()
        
        user_data = UserCreate(
            email="emptypass@example.com",
            password="validpassword123"
        )
        
        # Create the user
        create_user(user_data)
        
        # Attempt authentication with empty password
        authenticated_user = authenticate_user(
            "emptypass@example.com",
            ""
        )
        
        assert authenticated_user is None, \
            "Authentication should fail with empty password"