"""Integration tests for parent endpoints.

This module tests all parent API endpoints:
- POST /parent/create-add-device-token - Create add-device token
- POST /parent/remove-device - Remove device
- POST /parent/link-mail-address - Link mail address
- POST /parent/create-identity-token - Create identity token
- POST /parent/delete-account - Delete account
"""

import pytest
import uuid
from fastapi.testclient import TestClient

from app.services.auth_service import AuthService
from app.core.security import hash_password
from app.core.state import state_manager


def create_device_token(email: str = None):
    """Create a valid device auth token for testing."""
    import asyncio

    if email is None:
        email = f"test_device_{uuid.uuid4().hex[:8]}@example.com"

    async def get_token():
        auth = AuthService()
        auth.state = state_manager
        # Mock the code generation to return predictable code
        auth._generate_code = lambda: "123456"
        send_result = await auth.send_mail_login_code(email)
        mail_auth_token = await auth.sign_in_by_mail_code(
            send_result["mailLoginToken"], "123456"
        )
        parent_password = {
            "hash": hash_password("password123"),
            "secondHash": "hash",
            "secondSalt": "salt"
        }
        result = await auth.create_family(
            mail_auth_token["mailAuthToken"],
            parent_password,
            "Device",
            "Pixel"
        )
        return result["deviceAuthToken"]

    return asyncio.run(get_token())


class TestCreateAddDeviceToken:
    """Tests for POST /parent/create-add-device-token endpoint."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        from app.main import app
        return TestClient(app)

    def test_create_add_device_token_invalid_token(self, client):
        """Test create add-device token with invalid device auth token."""
        response = client.post(
            "/api/v1/parent/create-add-device-token",
            json={
                "deviceAuthToken": "invalid_token",
                "parentId": "parent_123",
                "parentPasswordSecondHash": "hash_value"
            }
        )

        assert response.status_code == 401, \
            f"Should return 401 for invalid token, got {response.status_code}"

    def test_create_add_device_token_missing_fields(self, client):
        """Test create add-device token with missing fields."""
        # Create device token in the same test context
        device_token = create_device_token()

        response = client.post(
            "/api/v1/parent/create-add-device-token",
            headers={"Authorization": f"Bearer {device_token}"},
            json={"deviceAuthToken": device_token}
        )

        assert response.status_code == 422, \
            f"Should return 422 for missing fields, got {response.status_code}"


class TestRemoveDevice:
    """Tests for POST /parent/remove-device endpoint."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        from app.main import app
        return TestClient(app)

    def test_remove_device_invalid_token(self, client):
        """Test remove device with invalid token."""
        response = client.post(
            "/api/v1/parent/remove-device",
            json={
                "deviceAuthToken": "invalid_token",
                "deviceId": "device_123"
            }
        )

        assert response.status_code == 401, \
            f"Should return 401 for invalid token, got {response.status_code}"

    def test_remove_device_missing_fields(self, client):
        """Test remove device with missing fields."""
        # Create device token in the same test context
        device_token = create_device_token()

        response = client.post(
            "/api/v1/parent/remove-device",
            headers={"Authorization": f"Bearer {device_token}"},
            json={"deviceAuthToken": device_token}
        )

        assert response.status_code == 422, \
            f"Should return 422 for missing fields, got {response.status_code}"


class TestLinkMailAddress:
    """Tests for POST /parent/link-mail-address endpoint."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        from app.main import app
        return TestClient(app)

    def test_link_mail_address_invalid_token(self, client):
        """Test link mail address with invalid token."""
        response = client.post(
            "/api/v1/parent/link-mail-address",
            json={
                "deviceAuthToken": "invalid_token",
                "mailAuthToken": "mail_token"
            }
        )

        assert response.status_code == 401, \
            f"Should return 401 for invalid token, got {response.status_code}"

    def test_link_mail_address_missing_fields(self, client):
        """Test link mail address with missing fields."""
        # Create device token in the same test context
        device_token = create_device_token()

        response = client.post(
            "/api/v1/parent/link-mail-address",
            headers={"Authorization": f"Bearer {device_token}"},
            json={"deviceAuthToken": device_token}
        )

        assert response.status_code == 422, \
            f"Should return 422 for missing fields, got {response.status_code}"


class TestCreateIdentityToken:
    """Tests for POST /parent/create-identity-token endpoint."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        from app.main import app
        return TestClient(app)

    def test_create_identity_token_invalid_token(self, client):
        """Test create identity token with invalid token."""
        response = client.post(
            "/api/v1/parent/create-identity-token",
            json={"deviceAuthToken": "invalid_token"}
        )

        assert response.status_code == 401, \
            f"Should return 401 for invalid token, got {response.status_code}"

    def test_create_identity_token_valid(self, client):
        """Test create identity token with valid token."""
        # Create device token in the same test context
        device_token = create_device_token()

        response = client.post(
            "/api/v1/parent/create-identity-token",
            headers={"Authorization": f"Bearer {device_token}"},
            json={"deviceAuthToken": device_token}
        )

        assert response.status_code == 200, \
            f"Should return 200, got {response.status_code}"

        data = response.json()
        assert "identityToken" in data, "Response should contain identityToken"


class TestDeleteAccount:
    """Tests for POST /parent/delete-account endpoint."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        from app.main import app
        return TestClient(app)

    def test_delete_account_invalid_token(self, client):
        """Test delete account with invalid token."""
        response = client.post(
            "/api/v1/parent/delete-account",
            json={"deviceAuthToken": "invalid_token"}
        )

        assert response.status_code == 401, \
            f"Should return 401 for invalid token, got {response.status_code}"

    def test_delete_account_valid(self, client):
        """Test delete account with valid token."""
        # Create device token in the same test context
        device_token = create_device_token()

        response = client.post(
            "/api/v1/parent/delete-account",
            headers={"Authorization": f"Bearer {device_token}"},
            json={"deviceAuthToken": device_token}
        )

        assert response.status_code == 200, \
            f"Should return 200, got {response.status_code}"

        data = response.json()
        assert data["status"] == "ok", "Status should be ok"


class TestParentEndpointSecurity:
    """Security tests for parent endpoints."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        from app.main import app
        return TestClient(app)

    def test_parent_endpoints_require_auth(self, client):
        """Test that all parent endpoints require authentication."""
        endpoints = [
            ("/api/v1/parent/create-add-device-token", {"parentId": "p1", "parentPasswordSecondHash": "h"}),
            ("/api/v1/parent/remove-device", {"deviceId": "d1"}),
            ("/api/v1/parent/link-mail-address", {"mailAuthToken": "m"}),
            ("/api/v1/parent/create-identity-token", {}),
            ("/api/v1/parent/delete-account", {}),
        ]

        for endpoint, data in endpoints:
            response = client.post(endpoint, json=data)
            assert response.status_code == 401, \
                f"{endpoint} should require authentication, got {response.status_code}"


class TestParentEndpointValidation:
    """Validation tests for parent endpoints."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        from app.main import app
        return TestClient(app)

    def test_parent_id_validation(self, client):
        """Test parent ID validation."""
        # Create device token in the same test context with unique email
        device_token = create_device_token("parent_id_test@example.com")

        # Missing parentId - should succeed since parentId is optional
        response = client.post(
            "/api/v1/parent/create-add-device-token",
            headers={"Authorization": f"Bearer {device_token}"},
            json={
                "deviceAuthToken": device_token,
                "parentPasswordSecondHash": "hash"
            }
        )

        assert response.status_code == 200, \
            f"Missing parentId should return 200 (optional field), got {response.status_code}"

    def test_device_id_validation(self, client):
        """Test device ID validation."""
        # Create device token in the same test context with unique email
        device_token = create_device_token("device_id_test@example.com")

        # Missing deviceId
        response = client.post(
            "/api/v1/parent/remove-device",
            headers={"Authorization": f"Bearer {device_token}"},
            json={"deviceAuthToken": device_token}
        )

        assert response.status_code == 422, \
            f"Missing deviceId should return 422, got {response.status_code}"