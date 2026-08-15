"""Integration tests for API endpoints.

This module provides end-to-end tests for all API endpoints including
health checks, user registration, login, and user retrieval.
"""

import pytest
from fastapi.testclient import TestClient

from app.models.user import UserCreate
from app.services.user import clear_users_db


class TestHealthCheck:
    """Tests for health check endpoints."""

    def test_health_check(self, client: TestClient):
        """Test the health check endpoint.

        This test:
        - Makes GET request to /health
        - Verifies 200 status code
        - Verifies response JSON is {"status": "healthy"}
        """
        response = client.get("/health")

        assert response.status_code == 200, \
            f"Health check should return 200, got {response.status_code}"

        data = response.json()
        assert data == {"status": "healthy"}, \
            f"Health check response should be {{'status': 'healthy'}}, got {data}"

    def test_ready_check(self, client: TestClient):
        """Test the readiness check endpoint.

        This test:
        - Makes GET request to /ready
        - Verifies 200 status code
        - Verifies response JSON is {"status": "ready"}
        """
        response = client.get("/ready")

        assert response.status_code == 200, \
            f"Ready check should return 200, got {response.status_code}"

        data = response.json()
        assert data == {"status": "ready"}, \
            f"Ready check response should be {{'status': 'ready'}}, got {data}"


class TestUserRegistration:
    """Tests for user registration endpoint."""

    def test_register_user(self, client: TestClient):
        """Test user registration with valid data.

        This test:
        - Makes POST request to /register with valid user data
        - Verifies 200 status code
        - Verifies response contains user email
        """
        # Clear any existing users
        clear_users_db()

        user_data = {
            "email": "newuser@example.com",
            "password": "securepassword123"
        }

        response = client.post("/register", json=user_data)

        assert response.status_code == 200, \
            f"Registration should return 200, got {response.status_code}"

        data = response.json()
        assert "email" in data, "Response should contain email"
        assert data["email"] == "newuser@example.com", \
            f"Email should be 'newuser@example.com', got {data.get('email')}"

    def test_register_duplicate_user(self, client: TestClient):
        """Test user registration with duplicate email.

        This test:
        - Registers a user
        - Attempts to register same email again
        - Verifies appropriate error response
        """
        # Clear any existing users
        clear_users_db()

        user_data = {
            "email": "duplicate@example.com",
            "password": "password12345678"
        }

        # First registration should succeed
        response1 = client.post("/register", json=user_data)
        assert response1.status_code == 200, \
            f"First registration should succeed, got {response1.status_code}"

        # Second registration with same email should fail
        response2 = client.post("/register", json=user_data)
        assert response2.status_code == 400, \
            f"Duplicate registration should return 400, got {response2.status_code}"

        error_data = response2.json()
        assert "detail" in error_data, "Error response should contain detail"
        assert "already exists" in error_data["detail"], \
            f"Error message should indicate email already exists, got {error_data['detail']}"

    def test_register_user_invalid_password(self, client: TestClient):
        """Test user registration with invalid password (too short)."""
        # Clear any existing users
        clear_users_db()

        user_data = {
            "email": "shortpass@example.com",
            "password": "short"  # Too short, min_length is 8
        }

        response = client.post("/register", json=user_data)

        assert response.status_code == 422, \
            f"Registration with short password should return 422, got {response.status_code}"


class TestUserLogin:
    """Tests for user login endpoint."""

    def test_login_success(self, client: TestClient):
        """Test successful user login.

        This test:
        - Registers a user
        - Makes POST request to /login with correct credentials
        - Verifies 200 status code
        - Verifies response contains access_token
        """
        # Clear any existing users
        clear_users_db()

        # Register a user first
        user_data = {
            "email": "loginuser@example.com",
            "password": "correctpassword123"
        }
        client.post("/register", json=user_data)

        # Login with correct credentials
        login_data = {
            "username": "loginuser@example.com",
            "password": "correctpassword123"
        }

        response = client.post("/login", data=login_data)

        assert response.status_code == 200, \
            f"Login should return 200, got {response.status_code}"

        data = response.json()
        assert "access_token" in data, "Response should contain access_token"
        assert "token_type" in data, "Response should contain token_type"
        assert data["token_type"] == "bearer", \
            f"Token type should be 'bearer', got {data.get('token_type')}"

    def test_login_failure(self, client: TestClient):
        """Test login with wrong credentials.

        This test:
        - Makes POST request to /login with wrong credentials
        - Verifies 401 status code
        """
        # Clear any existing users
        clear_users_db()

        # Register a user first
        user_data = {
            "email": "wrongpass@example.com",
            "password": "correctpassword123"
        }
        client.post("/register", json=user_data)

        # Login with wrong password
        login_data = {
            "username": "wrongpass@example.com",
            "password": "wrongpassword123"
        }

        response = client.post("/login", data=login_data)

        assert response.status_code == 401, \
            f"Login with wrong password should return 401, got {response.status_code}"

        error_data = response.json()
        assert "detail" in error_data, "Error response should contain detail"

    def test_login_nonexistent_user(self, client: TestClient):
        """Test login with non-existent user."""
        # Clear any existing users
        clear_users_db()

        login_data = {
            "username": "nonexistent@example.com",
            "password": "anypassword123"
        }

        response = client.post("/login", data=login_data)

        assert response.status_code == 401, \
            f"Login with non-existent user should return 401, got {response.status_code}"


class TestUserRetrieval:
    """Tests for user retrieval endpoints."""

    def test_get_user_by_id(self, client: TestClient):
        """Test retrieving a user by ID.

        This test:
        - Registers a user
        - Makes GET request to /users/{user_id}
        - Verifies 200 status code
        - Verifies response contains user email
        """
        # Clear any existing users
        clear_users_db()

        # Register a user
        user_data = {
            "email": "getbyid@example.com",
            "password": "password12345678"
        }
        register_response = client.post("/register", json=user_data)
        created_user = register_response.json()
        user_id = created_user["id"]

        # Get user by ID
        response = client.get(f"/users/{user_id}")

        assert response.status_code == 200, \
            f"Get user by ID should return 200, got {response.status_code}"

        data = response.json()
        assert "email" in data, "Response should contain email"
        assert data["email"] == "getbyid@example.com", \
            f"Email should be 'getbyid@example.com', got {data.get('email')}"

    def test_get_nonexistent_user(self, client: TestClient):
        """Test retrieving a non-existent user by ID.

        This test:
        - Makes GET request to /users/99999
        - Verifies 404 status code
        """
        # Clear any existing users
        clear_users_db()

        response = client.get("/users/99999")

        assert response.status_code == 404, \
            f"Get non-existent user should return 404, got {response.status_code}"

        error_data = response.json()
        assert "detail" in error_data, "Error response should contain detail"

    def test_get_user_by_email(self, client: TestClient):
        """Test retrieving a user by email.

        This test:
        - Registers a user
        - Makes GET request to /users/email/{email}
        - Verifies 200 status code
        - Verifies response contains user email
        """
        # Clear any existing users
        clear_users_db()

        # Register a user
        user_data = {
            "email": "getbyemail@example.com",
            "password": "password12345678"
        }
        client.post("/register", json=user_data)

        # Get user by email
        response = client.get("/users/email/getbyemail@example.com")

        assert response.status_code == 200, \
            f"Get user by email should return 200, got {response.status_code}"

        data = response.json()
        assert "email" in data, "Response should contain email"
        assert data["email"] == "getbyemail@example.com", \
            f"Email should be 'getbyemail@example.com', got {data.get('email')}"

    def test_get_user_by_nonexistent_email(self, client: TestClient):
        """Test retrieving a user by non-existent email."""
        # Clear any existing users
        clear_users_db()

        response = client.get("/users/email/nonexistent@example.com")

        assert response.status_code == 404, \
            f"Get user by non-existent email should return 404, got {response.status_code}"

        error_data = response.json()
        assert "detail" in error_data, "Error response should contain detail"
