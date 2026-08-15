"""Integration tests for child endpoints.

This module tests all child API endpoints:
- POST /child/add-device - Add device
- POST /child/update-primary-device - Update primary device
- POST /child/logout-at-primary-device - Logout at primary device
"""

import pytest
from fastapi.testclient import TestClient

from app.services.auth_service import AuthService
from app.core.security import hash_password
from app.core.state import state_manager


def get_valid_device_token():
    """Helper function to get a valid device auth token for testing."""
    import asyncio
    import secrets
    from datetime import datetime, timezone, timedelta

    async def get_token():
        auth = AuthService()
        # Use the global state_manager
        auth.state = state_manager
        # Mock the code generation to return predictable code
        auth._generate_code = lambda: "123456"
        send_result = await auth.send_mail_login_code("test_device@example.com")
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


def create_add_device_token():
    """Helper function to create an add-device token for testing."""
    import asyncio
    import secrets
    from datetime import datetime, timezone, timedelta

    async def create_token():
        add_device_token = secrets.token_urlsafe(32)
        child_device_id = f"device_{secrets.token_urlsafe(16)}"

        await state_manager.create_add_device_token(
            token=add_device_token,
            device_id=child_device_id,
            parent_id="parent_test",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=24)
        )
        return add_device_token

    return asyncio.run(create_token())


class TestAddDevice:
    """Tests for POST /child/add-device endpoint."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        from app.main import app
        return TestClient(app)

    def test_add_device_invalid_token(self, client):
        """Test add device with invalid register token - should return 401 for missing auth."""
        response = client.post(
            "/child/add-device",
            json={
                "registerToken": "invalid_token",
                "deviceName": "Test Device",
                "deviceModel": "Pixel 7"
            }
        )

        # Without valid device auth token, should return 401
        assert response.status_code == 401, \
            f"Should return 401 for missing auth, got {response.status_code}"

    def test_add_device_missing_fields(self, client):
        """Test add device with missing required fields."""
        # Get a valid device token for authentication
        device_token = get_valid_device_token()
        add_device_token = create_add_device_token()

        response = client.post(
            "/child/add-device",
            headers={"Authorization": f"Bearer {device_token}"},
            json={"registerToken": add_device_token}
        )

        # Missing deviceName and deviceModel should succeed with defaults (they're optional)
        assert response.status_code == 200, \
            f"Should return 200 (optional fields), got {response.status_code}"


class TestUpdatePrimaryDevice:
    """Tests for POST /child/update-primary-device endpoint."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        from app.main import app
        return TestClient(app)

    def test_update_primary_device_invalid_token(self, client):
        """Test update primary device with invalid token."""
        response = client.post(
            "/child/update-primary-device",
            json={
                "deviceAuthToken": "invalid_token",
                "primaryDeviceId": "device_123"
            }
        )

        assert response.status_code == 401, \
            f"Should return 401 for invalid token, got {response.status_code}"

    def test_update_primary_device_missing_fields(self, client):
        """Test update primary device with missing fields."""
        # Get a valid device token for authentication
        device_token = get_valid_device_token()

        response = client.post(
            "/child/update-primary-device",
            headers={"Authorization": f"Bearer {device_token}"},
            json={"deviceAuthToken": device_token}
        )

        # Missing primaryDeviceId should return 422
        assert response.status_code == 422, \
            f"Should return 422 for missing primaryDeviceId, got {response.status_code}"


class TestLogoutAtPrimaryDevice:
    """Tests for POST /child/logout-at-primary-device endpoint."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        from app.main import app
        return TestClient(app)

    def test_logout_invalid_token(self, client):
        """Test logout with invalid token."""
        response = client.post(
            "/child/logout-at-primary-device",
            json={"deviceAuthToken": "invalid_token"}
        )

        assert response.status_code == 401, \
            f"Should return 401 for invalid token, got {response.status_code}"

    def test_logout_valid(self, client):
        """Test logout with valid token."""
        # Get a valid device token for authentication
        device_token = get_valid_device_token()

        response = client.post(
            "/child/logout-at-primary-device",
            headers={"Authorization": f"Bearer {device_token}"},
            json={"deviceAuthToken": device_token}
        )

        assert response.status_code == 200, \
            f"Should return 200, got {response.status_code}"

        data = response.json()
        assert data["status"] == "ok", "Status should be ok"


class TestChildEndpointSecurity:
    """Security tests for child endpoints."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        from app.main import app
        return TestClient(app)

    def test_child_endpoints_require_auth(self, client):
        """Test that child endpoints require authentication."""
        endpoints = [
            ("/child/update-primary-device", {"primaryDeviceId": "d1"}),
            ("/child/logout-at-primary-device", {}),
        ]

        for endpoint, data in endpoints:
            response = client.post(endpoint, json=data)
            assert response.status_code == 401, \
                f"{endpoint} should require authentication, got {response.status_code}"


class TestChildEndpointValidation:
    """Validation tests for child endpoints."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        from app.main import app
        return TestClient(app)

    def test_device_name_validation(self, client):
        """Test device name validation - deviceName is optional."""
        # Get a valid device token for authentication
        device_token = get_valid_device_token()
        add_device_token = create_add_device_token()

        # Missing deviceName - should succeed with default
        response = client.post(
            "/child/add-device",
            headers={"Authorization": f"Bearer {device_token}"},
            json={
                "registerToken": add_device_token,
                "deviceModel": "Pixel 7"
            }
        )

        # deviceName is optional, so it should succeed
        assert response.status_code == 200, \
            f"Missing deviceName should return 200 (optional field), got {response.status_code}"

    def test_primary_device_id_validation(self, client):
        """Test primary device ID validation."""
        # Get a valid device token for authentication
        device_token = get_valid_device_token()

        # Missing primaryDeviceId
        response = client.post(
            "/child/update-primary-device",
            headers={"Authorization": f"Bearer {device_token}"},
            json={"deviceAuthToken": device_token}
        )

        assert response.status_code == 422, \
            f"Missing primaryDeviceId should return 422, got {response.status_code}"
