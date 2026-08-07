"""Integration tests for sync endpoints.

This module tests all sync API endpoints:
- POST /sync/push-actions - Push actions to server
- POST /sync/pull-status - Pull server status
- POST /sync/report-removed - Report device removed
- POST /sync/is-device-removed - Check if device removed
"""

import pytest
import json
from fastapi.testclient import TestClient

from app.services.auth_service import AuthService
from app.core.security import hash_password
from app.core.state import StateManager, state_manager


class TestPushActions:
    """Tests for POST /sync/push-actions endpoint."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        from app.main import app
        return TestClient(app)

    def test_push_actions_invalid_token(self, client):
        """Test push actions with invalid device auth token."""
        response = client.post(
            "/api/v1/sync/push-actions",
            json={
                "deviceAuthToken": "invalid_token",
                "actions": []
            }
        )

        assert response.status_code == 401, \
            f"Should return 401 for invalid token, got {response.status_code}"

    def test_push_actions_missing_token(self, client):
        """Test push actions with missing device auth token."""
        response = client.post(
            "/api/v1/sync/push-actions",
            json={"actions": []}
        )

        assert response.status_code == 401, \
            f"Should return 401 for missing token, got {response.status_code}"

    def test_push_actions_empty_actions(self, client):
        """Test push actions with empty actions list."""
        import asyncio
        
        # Use the global state_manager instance
        auth = AuthService()
        auth.state = state_manager
        # Mock the code generation to return a predictable code
        auth._generate_code = lambda: "123456"
        
        # Clear state for clean test
        asyncio.run(state_manager.reset())
        
        async def get_token():
            send_result = await auth.send_mail_login_code("push_test@example.com")
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

        token = asyncio.run(get_token())

        response = client.post(
            "/api/v1/sync/push-actions",
            json={"deviceAuthToken": token, "actions": []}
        )

        assert response.status_code == 200, \
            f"Should return 200 for empty actions, got {response.status_code}"

        data = response.json()
        assert "shouldDoFullSync" in data, "Response should contain shouldDoFullSync"


class TestPullStatus:
    """Tests for POST /sync/pull-status endpoint."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        from app.main import app
        return TestClient(app)

    def test_pull_status_invalid_token(self, client):
        """Test pull status with invalid device auth token."""
        response = client.post(
            "/api/v1/sync/pull-status",
            json={
                "deviceAuthToken": "invalid_token",
                "status": {
                    "clientLevel": 7,
                    "devices": "",
                    "users": "",
                    "apps": {},
                    "devicesDetail": {},
                    "categories": {},
                    "kri": 0,
                    "kr": 0,
                    "dh": "",
                    "u2f": ""
                }
            }
        )

        assert response.status_code == 401, \
            f"Should return 401 for invalid token, got {response.status_code}"

    def test_pull_status_missing_token(self, client):
        """Test pull status with missing device auth token."""
        response = client.post(
            "/api/v1/sync/pull-status",
            json={"status": {}}
        )

        assert response.status_code == 401, \
            f"Should return 401 for missing token, got {response.status_code}"

    def test_pull_status_with_valid_token(self, client):
        """Test pull status with valid device auth token."""
        import asyncio
        
        # Use the global state_manager instance
        auth = AuthService()
        auth.state = state_manager
        # Mock the code generation to return a predictable code
        auth._generate_code = lambda: "123456"
        
        # Clear state for clean test
        asyncio.run(state_manager.reset())
        
        async def get_token():
            send_result = await auth.send_mail_login_code("pull_test@example.com")
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

        token = asyncio.run(get_token())

        response = client.post(
            "/api/v1/sync/pull-status",
            json={
                "deviceAuthToken": token,
                "status": {
                    "clientLevel": 7,
                    "devices": "",
                    "users": "",
                    "apps": {},
                    "devicesDetail": {},
                    "categories": {},
                    "kri": 0,
                    "kr": 0,
                    "dh": "",
                    "u2f": ""
                }
            }
        )

        assert response.status_code == 200, \
            f"Should return 200, got {response.status_code}"

        data = response.json()
        assert "data" in data, "Response should contain data"


class TestReportRemoved:
    """Tests for POST /sync/report-removed endpoint."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        from app.main import app
        return TestClient(app)

    def test_report_removed_invalid_token(self, client):
        """Test report removed with invalid token."""
        response = client.post(
            "/api/v1/sync/report-removed",
            json={"deviceAuthToken": "invalid_token"}
        )

        assert response.status_code == 401, \
            f"Should return 401 for invalid token, got {response.status_code}"

    def test_report_removed_valid(self, client):
        """Test report removed with valid token."""
        import asyncio
        
        # Use the global state_manager instance
        auth = AuthService()
        auth.state = state_manager
        # Mock the code generation to return a predictable code
        auth._generate_code = lambda: "123456"
        
        # Clear state for clean test
        asyncio.run(state_manager.reset())
        
        async def get_token():
            send_result = await auth.send_mail_login_code("report_test@example.com")
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

        token = asyncio.run(get_token())

        response = client.post(
            "/api/v1/sync/report-removed",
            json={"deviceAuthToken": token}
        )

        assert response.status_code == 200, \
            f"Should return 200, got {response.status_code}"

        data = response.json()
        assert data["status"] == "ok", "Status should be ok"


class TestIsDeviceRemoved:
    """Tests for POST /sync/is-device-removed endpoint."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        from app.main import app
        return TestClient(app)

    def test_is_device_removed_invalid_token(self, client):
        """Test is device removed with invalid token."""
        response = client.post(
            "/api/v1/sync/is-device-removed",
            json={"deviceAuthToken": "invalid_token"}
        )

        assert response.status_code == 401, \
            f"Should return 401 for invalid token, got {response.status_code}"

    def test_is_device_removed_valid(self, client):
        """Test is device removed with valid token."""
        import asyncio
        
        # Use the global state_manager instance
        auth = AuthService()
        auth.state = state_manager
        # Mock the code generation to return a predictable code
        auth._generate_code = lambda: "123456"
        
        # Clear state for clean test
        asyncio.run(state_manager.reset())
        
        async def get_token():
            send_result = await auth.send_mail_login_code("removed_test@example.com")
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

        token = asyncio.run(get_token())

        response = client.post(
            "/api/v1/sync/is-device-removed",
            json={"deviceAuthToken": token}
        )

        assert response.status_code == 200, \
            f"Should return 200, got {response.status_code}"

        data = response.json()
        assert "isDeviceRemoved" in data, "Response should contain isDeviceRemoved"


class TestSyncProtocolIntegration:
    """Integration tests for sync protocol."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        from app.main import app
        return TestClient(app)

    def test_full_sync_flow(self, client):
        """Test complete sync flow: push → pull."""
        import asyncio
        
        # Use the global state_manager instance
        auth = AuthService()
        auth.state = state_manager
        # Mock the code generation to return a predictable code
        auth._generate_code = lambda: "123456"
        
        # Clear state for clean test
        asyncio.run(state_manager.reset())
        
        async def get_token():
            send_result = await auth.send_mail_login_code("full_sync_test@example.com")
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

        token = asyncio.run(get_token())

        # Push actions
        actions = [{
            "type": "AddCategoryAction",
            "sequenceNumber": 1,
            "integrity": "password:base64",
            "userId": "user_123",
            "encodedAction": '{"categoryId":"cat_123","title":"Games","childId":"user_456"}'
        }]

        push_response = client.post(
            "/api/v1/sync/push-actions",
            json={"deviceAuthToken": token, "actions": actions}
        )

        assert push_response.status_code == 200, "Push should succeed"

        # Pull status
        pull_response = client.post(
            "/api/v1/sync/pull-status",
            json={
                "deviceAuthToken": token,
                "status": {
                    "clientLevel": 7,
                    "devices": "",
                    "users": "",
                    "apps": {},
                    "devicesDetail": {},
                    "categories": {},
                    "kri": 0,
                    "kr": 0,
                    "dh": "",
                    "u2f": ""
                }
            }
        )

        assert pull_response.status_code == 200, "Pull should succeed"