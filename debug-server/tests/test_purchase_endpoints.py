"""Integration tests for purchase endpoints.

This module tests all purchase API endpoints:
- POST /purchase/can-do-purchase - Check purchase eligibility
- POST /purchase/finish-purchase-by-google-play - Finish Google Play purchase
"""

import pytest
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient

from app.services.auth_service import AuthService
from app.core.security import hash_password
from app.core.state import state_manager


class TestCanDoPurchase:
    """Tests for POST /purchase/can-do-purchase endpoint."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        from app.main import app
        return TestClient(app)

    def test_can_do_purchase_invalid_token(self, client):
        """Test can-do-purchase with invalid device auth token."""
        response = client.post(
            "/api/v1/purchase/can-do-purchase",
            json={
                "deviceAuthToken": "invalid_token",
                "productId": "premium_unlock"
            }
        )

        assert response.status_code == 401, \
            f"Should return 401 for invalid token, got {response.status_code}"

    def test_can_do_purchase_missing_fields(self, client):
        """Test can-do-purchase with missing required fields."""
        response = client.post(
            "/api/v1/purchase/can-do-purchase",
            json={"deviceAuthToken": "token"}
        )

        # Missing productId - but token is invalid, so we get 401
        assert response.status_code == 401, \
            f"Should return 401 for invalid token, got {response.status_code}"

    def test_can_do_purchase_valid(self, client):
        """Test can-do-purchase with valid token."""
        import asyncio

        async def get_token():
            auth = AuthService()
            auth.state = state_manager
            auth._generate_code = lambda: "123456"
            send_result = await auth.send_mail_login_code("purchase_test@example.com")
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
            "/api/v1/purchase/can-do-purchase",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "productId": "premium_unlock"
            }
        )

        assert response.status_code == 200, \
            f"Should return 200, got {response.status_code}"

        data = response.json()
        assert data["status"] == "ok", "Status should be ok"
        assert "canDoPurchase" in data, "Response should contain canDoPurchase"


class TestFinishPurchaseByGooglePlay:
    """Tests for POST /purchase/finish-purchase-by-google-play endpoint."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        from app.main import app
        return TestClient(app)

    def test_finish_purchase_invalid_token(self, client):
        """Test finish purchase with invalid device auth token."""
        response = client.post(
            "/api/v1/purchase/finish-purchase-by-google-play",
            json={
                "deviceAuthToken": "invalid_token",
                "productId": "premium_unlock",
                "purchaseToken": "purchase_123",
                "signature": "signature_123"
            }
        )

        assert response.status_code == 401, \
            f"Should return 401 for invalid token, got {response.status_code}"

    def test_finish_purchase_missing_fields(self, client):
            """Test finish purchase with missing required fields."""
            import asyncio
    
            async def get_token():
                auth = AuthService()
                auth.state = state_manager
                auth._generate_code = lambda: "123456"
                send_result = await auth.send_mail_login_code("missing_fields_test@example.com")
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
    
            # Missing productId, purchaseToken, signature - should return 422
            response = client.post(
                "/api/v1/purchase/finish-purchase-by-google-play",
                headers={"Authorization": f"Bearer {token}"},
                json={}
            )
    
            assert response.status_code == 422, \
                f"Should return 422 for missing fields, got {response.status_code}"

    def test_finish_purchase_valid(self, client):
        """Test finish purchase with valid token and data."""
        import asyncio

        async def get_token():
            auth = AuthService()
            auth.state = state_manager
            auth._generate_code = lambda: "123456"
            send_result = await auth.send_mail_login_code("finish_purchase_test@example.com")
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
            "/api/v1/purchase/finish-purchase-by-google-play",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "productId": "premium_unlock",
                "purchaseToken": "purchase_token_123",
                "signature": "signature_123"
            }
        )

        assert response.status_code == 200, \
            f"Should return 200, got {response.status_code}"

        data = response.json()
        assert data["status"] == "ok", "Status should be ok"
        assert "fullVersionUntil" in data, "Response should contain fullVersionUntil"


class TestPurchaseEndpointSecurity:
    """Security tests for purchase endpoints."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        from app.main import app
        return TestClient(app)

    def test_purchase_endpoints_require_auth(self, client):
        """Test that all purchase endpoints require authentication."""
        endpoints = [
            ("/api/v1/purchase/can-do-purchase", {"productId": "premium"}),
            ("/api/v1/purchase/finish-purchase-by-google-play", {
                "productId": "premium",
                "purchaseToken": "token",
                "signature": "sig"
            }),
        ]

        for endpoint, data in endpoints:
            response = client.post(endpoint, json=data)
            assert response.status_code == 401, \
                f"{endpoint} should require authentication, got {response.status_code}"


class TestPurchaseEndpointValidation:
    """Validation tests for purchase endpoints."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        from app.main import app
        return TestClient(app)

    def test_product_id_validation(self, client):
        """Test product ID validation."""
        import asyncio

        async def get_token():
            auth = AuthService()
            auth.state = state_manager
            auth._generate_code = lambda: "123456"
            send_result = await auth.send_mail_login_code("product_id_test@example.com")
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

        # Missing productId
        response = client.post(
            "/api/v1/purchase/can-do-purchase",
            headers={"Authorization": f"Bearer {token}"},
            json={}
        )

        assert response.status_code == 422, \
            f"Missing productId should return 422, got {response.status_code}"

    def test_purchase_token_validation(self, client):
        """Test purchase token validation."""
        import asyncio

        async def get_token():
            auth = AuthService()
            auth.state = state_manager
            auth._generate_code = lambda: "123456"
            send_result = await auth.send_mail_login_code("purchase_token_test@example.com")
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

        # Missing purchaseToken
        response = client.post(
            "/api/v1/purchase/finish-purchase-by-google-play",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "productId": "premium",
                "signature": "sig"
                # Missing purchaseToken
            }
        )

        assert response.status_code == 422, \
            f"Missing purchaseToken should return 422, got {response.status_code}"

    def test_signature_validation(self, client):
        """Test signature validation."""
        import asyncio

        async def get_token():
            auth = AuthService()
            auth.state = state_manager
            auth._generate_code = lambda: "123456"
            send_result = await auth.send_mail_login_code("signature_test@example.com")
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

        # Missing signature
        response = client.post(
            "/api/v1/purchase/finish-purchase-by-google-play",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "productId": "premium",
                "purchaseToken": "token"
                # Missing signature
            }
        )

        assert response.status_code == 422, \
            f"Missing signature should return 422, got {response.status_code}"


class TestPurchaseIntegration:
    """Integration tests for purchase workflows."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        from app.main import app
        return TestClient(app)

    def test_purchase_workflow(self, client):
        """Test complete purchase workflow: check → purchase → verify."""
        import asyncio

        async def get_token():
            auth = AuthService()
            auth.state = state_manager
            auth._generate_code = lambda: "123456"
            send_result = await auth.send_mail_login_code("workflow_purchase@example.com")
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

        # Step 1: Check if can purchase
        check_response = client.post(
            "/api/v1/purchase/can-do-purchase",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "productId": "premium_unlock"
            }
        )

        assert check_response.status_code == 200, "Check purchase should succeed"

        # Step 2: Finish purchase
        finish_response = client.post(
            "/api/v1/purchase/finish-purchase-by-google-play",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "productId": "premium_unlock",
                "purchaseToken": "purchase_token_123",
                "signature": "signature_123"
            }
        )

        assert finish_response.status_code == 200, "Finish purchase should succeed"

        # Step 3: Verify purchase (check again)
        verify_response = client.post(
            "/api/v1/purchase/can-do-purchase",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "productId": "premium_unlock"
            }
        )

        assert verify_response.status_code == 200, "Verify purchase should succeed"
        verify_data = verify_response.json()
        assert verify_data["status"] == "ok", "Status should be ok"