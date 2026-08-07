"""Integration tests for authentication endpoints.

This module tests all authentication API endpoints:
- POST /time - Get server time
- POST /auth/send-mail-login-code-v2 - Send mail login code
- POST /auth/sign-in-by-mail-code - Sign in by mail code
- POST /parent/get-status-by-mail-address - Get status by mail
- POST /parent/create-family - Create family
- POST /parent/sign-in-into-family - Sign in to family
- POST /parent/recover-parent-password - Recover password
"""

import pytest
from fastapi.testclient import TestClient

from app.services.user import clear_users_db
from app.services.auth_service import AuthService
from app.core.security import hash_password


class TestTimeEndpoint:
    """Tests for POST /time endpoint."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        from app.main import app
        return TestClient(app)

    def test_time_endpoint_returns_milliseconds(self, client):
        """Test that /time returns time in milliseconds."""
        response = client.post("/api/v1/time")

        assert response.status_code == 200, \
            f"Time endpoint should return 200, got {response.status_code}"

        data = response.json()
        assert "time" in data, "Response should contain time"
        assert isinstance(data["time"], int), "Time should be an integer"

        # Time should be in milliseconds (13 digits for current time)
        assert len(str(data["time"])) >= 10, "Time should be in milliseconds"

    def test_time_endpoint_consistency(self, client):
        """Test that time endpoint returns consistent format."""
        response1 = client.post("/api/v1/time")
        response2 = client.post("/api/v1/time")

        data1 = response1.json()
        data2 = response2.json()

        # Times should be different (not the same millisecond)
        # But both should be valid timestamps
        assert isinstance(data1["time"], int)
        assert isinstance(data2["time"], int)


class TestSendMailLoginCode:
    """Tests for POST /auth/send-mail-login-code-v2 endpoint."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        from app.main import app
        return TestClient(app)

    def test_send_mail_login_code_success(self, client):
        """Test successful mail login code request."""
        response = client.post(
            "/api/v1/auth/send-mail-login-code-v2",
            json={"mail": "test@example.com", "locale": "en"}
        )

        assert response.status_code == 200, \
            f"Should return 200, got {response.status_code}"

        data = response.json()
        assert "mailLoginToken" in data, "Response should contain mailLoginToken"

    def test_send_mail_login_code_invalid_email(self, client):
        """Test mail login code with invalid email."""
        response = client.post(
            "/api/v1/auth/send-mail-login-code-v2",
            json={"mail": "invalid-email", "locale": "en"}
        )

        assert response.status_code == 422, \
            f"Should return 422 for invalid email, got {response.status_code}"

    def test_send_mail_login_code_missing_mail(self, client):
        """Test mail login code with missing mail field."""
        response = client.post(
            "/api/v1/auth/send-mail-login-code-v2",
            json={"locale": "en"}
        )

        assert response.status_code == 422, \
            f"Should return 422 for missing mail, got {response.status_code}"


class TestSignInByMailCode:
    """Tests for POST /auth/sign-in-by-mail-code endpoint."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        from app.main import app
        return TestClient(app)

    def test_sign_in_by_mail_code_invalid_token(self, client):
        """Test sign in with invalid mail login token."""
        response = client.post(
            "/api/v1/auth/sign-in-by-mail-code",
            json={"mailLoginToken": "invalid_token", "receivedCode": "123456"}
        )

        assert response.status_code == 401, \
            f"Should return 401 for invalid token, got {response.status_code}"


class TestGetStatusByMailAddress:
    """Tests for POST /parent/get-status-by-mail-address endpoint."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        from app.main import app
        return TestClient(app)

    def test_get_status_by_mail_invalid_token(self, client):
        """Test get status with invalid mail auth token."""
        response = client.post(
            "/api/v1/parent/get-status-by-mail-address",
            json={"mailAuthToken": "invalid_token"}
        )

        assert response.status_code == 401, \
            f"Should return 401 for invalid token, got {response.status_code}"

    def test_get_status_by_mail_missing_token(self, client):
        """Test get status with missing mail auth token."""
        response = client.post(
            "/api/v1/parent/get-status-by-mail-address",
            json={}
        )

        assert response.status_code == 422, \
            f"Should return 422 for missing token, got {response.status_code}"


class TestCreateFamily:
    """Tests for POST /parent/create-family endpoint."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        from app.main import app
        return TestClient(app)

    def test_create_family_invalid_token(self, client):
        """Test create family with invalid token."""
        response = client.post(
            "/api/v1/parent/create-family",
            json={
                "mailAuthToken": "invalid_token",
                "parentPassword": {
                    "hash": hash_password("password123"),
                    "secondHash": "hash",
                    "secondSalt": "salt"
                },
                "deviceName": "Test Device",
                "deviceModel": "Pixel 7"
            }
        )

        assert response.status_code == 401, \
            f"Should return 401 for invalid token, got {response.status_code}"

    def test_create_family_missing_fields(self, client):
        """Test create family with missing required fields."""
        response = client.post(
            "/api/v1/parent/create-family",
            json={"mailAuthToken": "token"}
        )

        assert response.status_code == 422, \
            f"Should return 422 for missing fields, got {response.status_code}"


class TestSignInIntoFamily:
    """Tests for POST /parent/sign-in-into-family endpoint."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        from app.main import app
        return TestClient(app)

    def test_sign_in_into_family_invalid_token(self, client):
        """Test sign in with invalid token."""
        response = client.post(
            "/api/v1/parent/sign-in-into-family",
            json={
                "mailAuthToken": "invalid_token",
                "parentPasswordSecondHash": "hash"
            }
        )

        assert response.status_code == 401, \
            f"Should return 401 for invalid token, got {response.status_code}"

    def test_sign_in_into_family_missing_fields(self, client):
        """Test sign in with missing required fields."""
        response = client.post(
            "/api/v1/parent/sign-in-into-family",
            json={"mailAuthToken": "token"}
        )

        assert response.status_code == 422, \
            f"Should return 422 for missing fields, got {response.status_code}"


class TestRecoverParentPassword:
    """Tests for POST /parent/recover-parent-password endpoint."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        from app.main import app
        return TestClient(app)

    def test_recover_password_invalid_token(self, client):
        """Test password recovery with invalid token."""
        response = client.post(
            "/api/v1/parent/recover-parent-password",
            json={
                "mailAuthToken": "invalid_token",
                "newPassword": {
                    "hash": hash_password("newpassword"),
                    "secondHash": "hash",
                    "secondSalt": "salt"
                }
            }
        )

        assert response.status_code == 401, \
            f"Should return 401 for invalid token, got {response.status_code}"

    def test_recover_password_missing_fields(self, client):
        """Test password recovery with missing fields."""
        response = client.post(
            "/api/v1/parent/recover-parent-password",
            json={"mailAuthToken": "token"}
        )

        assert response.status_code == 422, \
            f"Should return 422 for missing fields, got {response.status_code}"


class TestLegacyAuthEndpoints:
    """Tests for legacy authentication endpoints."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        from app.main import app
        return TestClient(app)

    def test_register_endpoint(self, client):
        """Test POST /register endpoint."""
        clear_users_db()

        response = client.post(
            "/api/v1/register",
            json={"email": "legacy@example.com", "password": "password12345678"}
        )

        assert response.status_code == 200, \
            f"Register should return 200, got {response.status_code}"

        data = response.json()
        assert "email" in data, "Response should contain email"

    def test_login_endpoint(self, client):
        """Test POST /login endpoint."""
        clear_users_db()

        # Register user first
        client.post(
            "/api/v1/register",
            json={"email": "login_legacy@example.com", "password": "password12345678"}
        )

        # Login
        response = client.post(
            "/api/v1/login",
            data={"username": "login_legacy@example.com", "password": "password12345678"}
        )

        assert response.status_code == 200, \
            f"Login should return 200, got {response.status_code}"

        data = response.json()
        assert "access_token" in data, "Response should contain access_token"


class TestAuthEndpointSecurity:
    """Security tests for authentication endpoints."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        from app.main import app
        return TestClient(app)

    def test_password_not_returned_in_response(self, client):
        """Test that password is never returned in responses."""
        clear_users_db()

        response = client.post(
            "/api/v1/register",
            json={"email": "secure@example.com", "password": "password12345678"}
        )

        data = response.json()
        assert "password" not in data, "Password should not be in response"
        assert "passwordHash" not in data, "Password hash should not be in response"

    def test_token_not_leaked_in_error(self, client):
        """Test that tokens are not leaked in error responses."""
        response = client.post(
            "/api/v1/auth/sign-in-by-mail-code",
            json={"mailLoginToken": "invalid", "receivedCode": "123456"}
        )

        data = response.json()
        assert "mailAuthToken" not in data or data.get("mailAuthToken") is None, \
            "Token should not be in error response"


class TestAuthEndpointValidation:
    """Validation tests for authentication endpoints."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        from app.main import app
        return TestClient(app)

    def test_email_validation(self, client):
        """Test email format validation."""
        invalid_emails = [
            "not-an-email",
            "@example.com",
            "test@",
            "test@.com",
            "test@example",
        ]

        for email in invalid_emails:
            response = client.post(
                "/api/v1/auth/send-mail-login-code-v2",
                json={"mail": email, "locale": "en"}
            )

            assert response.status_code == 422, \
                f"Invalid email '{email}' should return 422, got {response.status_code}"

    def test_json_validation(self, client):
        """Test JSON request validation."""
        # Send invalid JSON
        response = client.post(
            "/api/v1/auth/send-mail-login-code-v2",
            content="not valid json",
            headers={"Content-Type": "application/json"}
        )

        assert response.status_code in [400, 422], \
            f"Invalid JSON should return 400 or 422, got {response.status_code}"