"""Unit tests for authentication flows.

This module tests authentication-related functionality including:
- Mail login code generation and validation
- Mail authentication token handling
- Family creation and sign-in
- Password recovery
"""

import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta, timezone

from app.services.auth_service import AuthService
from app.core.state import StateManager
from app.core.security import hash_password


class TestMailLoginToken:
    """Tests for mail login token generation and validation."""

    @pytest.fixture
    def auth_service(self):
        """Create an AuthService instance for testing."""
        service = AuthService()
        # Mock the code generation to return a predictable code
        service._generate_code = lambda: "123456"
        return service

    @pytest.fixture
    def state_manager(self):
        """Create a state manager instance for testing."""
        return StateManager()

    @pytest.mark.asyncio
    @pytest.mark.timeout(10)
    async def test_send_mail_login_code(self, auth_service, state_manager):
        """Test mail login code generation."""
        auth_service.state = state_manager
        mail = "test@example.com"

        result = await auth_service.send_mail_login_code(mail)

        assert result is not None, "Result should be returned"
        assert "mailLoginToken" in result, "Result should contain mailLoginToken"
        assert result["mailLoginToken"] is not None, "Token should not be None"

    @pytest.mark.asyncio
    @pytest.mark.timeout(10)
    async def test_sign_in_by_mail_code_valid(self, auth_service, state_manager):
        """Test sign in with valid mail login token and code."""
        auth_service.state = state_manager
        mail = "test@example.com"

        # First send login code
        send_result = await auth_service.send_mail_login_code(mail)
        mail_login_token = send_result["mailLoginToken"]

        # Then sign in with the code
        result = await auth_service.sign_in_by_mail_code(mail_login_token, "123456")

        assert result is not None, "Result should be returned"
        assert "mailAuthToken" in result, "Result should contain mailAuthToken"

    @pytest.mark.asyncio
    @pytest.mark.timeout(10)
    async def test_sign_in_by_mail_code_invalid_token(self, auth_service, state_manager):
        """Test sign in with invalid mail login token."""
        auth_service.state = state_manager

        with pytest.raises(ValueError, match="Invalid or expired mail login token"):
            await auth_service.sign_in_by_mail_code("invalid_token", "123456")

    @pytest.mark.asyncio
    @pytest.mark.timeout(10)
    async def test_sign_in_by_mail_code_invalid_code(self, auth_service, state_manager):
        """Test sign in with invalid verification code."""
        auth_service.state = state_manager
        mail = "test@example.com"

        # First send login code
        send_result = await auth_service.send_mail_login_code(mail)
        mail_login_token = send_result["mailLoginToken"]

        # Try to sign in with wrong code
        with pytest.raises(ValueError, match="Invalid verification code"):
            await auth_service.sign_in_by_mail_code(mail_login_token, "000000")


class TestMailAuthToken:
    """Tests for mail authentication token handling."""

    @pytest.fixture
    def auth_service(self):
        """Create an AuthService instance for testing."""
        service = AuthService()
        service._generate_code = lambda: "123456"
        return service

    @pytest.fixture
    def state_manager(self):
        """Create a state manager instance for testing."""
        return StateManager()

    @pytest.mark.asyncio
    @pytest.mark.timeout(10)
    async def test_get_status_by_mail_address_new(self, auth_service, state_manager):
        """Test get status for new mail address."""
        auth_service.state = state_manager
        mail = "new@example.com"

        # Send login code to create token
        send_result = await auth_service.send_mail_login_code(mail)
        mail_auth_token = await auth_service.sign_in_by_mail_code(
            send_result["mailLoginToken"], "123456"
        )

        result = await auth_service.get_status_by_mail_address(mail_auth_token["mailAuthToken"])

        assert result is not None, "Result should be returned"
        assert result["mail"] == mail, "Mail should match"
        assert result["status"] == "new", "Status should be 'new'"
        assert result["canCreateFamily"] is True, "Should be able to create family"

    @pytest.mark.asyncio
    @pytest.mark.timeout(10)
    async def test_get_status_by_mail_address_invalid_token(self, auth_service, state_manager):
        """Test get status with invalid mail auth token."""
        auth_service.state = state_manager

        with pytest.raises(ValueError, match="Invalid mail auth token"):
            await auth_service.get_status_by_mail_address("invalid_token")


class TestDeviceAuthToken:
    """Tests for device authentication token handling."""

    @pytest.fixture
    def auth_service(self):
        """Create an AuthService instance for testing."""
        service = AuthService()
        service._generate_code = lambda: "123456"
        return service

    @pytest.fixture
    def state_manager(self):
        """Create a state manager instance for testing."""
        return StateManager()

    @pytest.mark.asyncio
    @pytest.mark.timeout(10)
    async def test_create_family(self, auth_service, state_manager):
        """Test family creation."""
        auth_service.state = state_manager
        mail = "parent@example.com"

        # Create mail auth token
        send_result = await auth_service.send_mail_login_code(mail)
        mail_auth_token = await auth_service.sign_in_by_mail_code(
            send_result["mailLoginToken"], "123456"
        )

        # Create family
        parent_password = {
            "hash": hash_password("password123"),
            "secondHash": "second_hash_value",
            "secondSalt": "salt_value"
        }

        result = await auth_service.create_family(
            mail_auth_token["mailAuthToken"],
            parent_password,
            "Test Device",
            "Pixel 7"
        )

        assert result is not None, "Result should be returned"
        assert "deviceAuthToken" in result, "Result should contain deviceAuthToken"
        assert "ownDeviceId" in result, "Result should contain ownDeviceId"

    @pytest.mark.asyncio
    @pytest.mark.timeout(10)
    async def test_sign_in_into_family(self, auth_service, state_manager):
        """Test sign in to existing family."""
        auth_service.state = state_manager
        mail = "existing@example.com"

        # Create family first
        send_result = await auth_service.send_mail_login_code(mail)
        mail_auth_token = await auth_service.sign_in_by_mail_code(
            send_result["mailLoginToken"], "123456"
        )

        # Store the password hash to use in both places
        password_hash = hash_password("password123")
        parent_password = {
            "hash": password_hash,
            "secondHash": "second_hash",
            "secondSalt": "salt"
        }

        family_result = await auth_service.create_family(
            mail_auth_token["mailAuthToken"],
            parent_password,
            "Device 1",
            "Pixel 7"
        )

        # Now sign in again using the same mail auth token
        # Note: sign_in_into_family checks the password field (not secondPasswordSalt)
        result = await auth_service.sign_in_into_family(
            mail_auth_token["mailAuthToken"],
            password_hash,  # Must match the password hash stored in user
            "Device 2",
            "Pixel 8"
        )

        assert result is not None, "Result should be returned"
        assert "deviceAuthToken" in result, "Result should contain deviceAuthToken"


class TestPasswordRecovery:
    """Tests for password recovery flow."""

    @pytest.fixture
    def auth_service(self):
        """Create an AuthService instance for testing."""
        service = AuthService()
        service._generate_code = lambda: "123456"
        return service

    @pytest.fixture
    def state_manager(self):
        """Create a state manager instance for testing."""
        return StateManager()

    @pytest.mark.asyncio
    @pytest.mark.timeout(10)
    async def test_recover_parent_password(self, auth_service, state_manager):
        """Test parent password recovery."""
        auth_service.state = state_manager
        mail = "recover@example.com"

        # Create family first
        send_result = await auth_service.send_mail_login_code(mail)
        mail_auth_token = await auth_service.sign_in_by_mail_code(
            send_result["mailLoginToken"], "123456"
        )

        parent_password = {
            "hash": hash_password("password123"),
            "secondHash": "hash",
            "secondSalt": "salt"
        }

        await auth_service.create_family(
            mail_auth_token["mailAuthToken"],
            parent_password,
            "Device",
            "Pixel"
        )

        # Recover password
        new_password = {
            "hash": hash_password("newpassword"),
            "secondHash": "new_hash",
            "secondSalt": "new_salt"
        }

        result = await auth_service.recover_parent_password(
            mail_auth_token["mailAuthToken"],
            new_password
        )

        assert result is not None, "Result should be returned"
        assert result["status"] == "ok", "Status should be ok"


class TestAuthenticationIntegration:
    """Integration tests for authentication flows."""

    @pytest.fixture
    def auth_service(self):
        """Create an AuthService instance for testing."""
        service = AuthService()
        service._generate_code = lambda: "123456"
        return service

    @pytest.fixture
    def state_manager(self):
        """Create a state manager instance for testing."""
        return StateManager()

    @pytest.mark.asyncio
    @pytest.mark.timeout(10)
    async def test_complete_auth_flow(self, auth_service, state_manager):
        """Test complete authentication flow: mail → code → token → family."""
        auth_service.state = state_manager
        mail = "complete@example.com"

        # Step 1: Generate mail login token
        send_result = await auth_service.send_mail_login_code(mail)
        mail_login_token = send_result["mailLoginToken"]
        assert mail_login_token is not None, "Mail login token should be generated"

        # Step 2: Generate mail auth token
        mail_auth_result = await auth_service.sign_in_by_mail_code(
            mail_login_token, "123456"
        )
        mail_auth_token = mail_auth_result["mailAuthToken"]
        assert mail_auth_token is not None, "Mail auth token should be generated"

        # Step 3: Create family
        parent_password = {
            "hash": hash_password("password123"),
            "secondHash": "hash",
            "secondSalt": "salt"
        }

        family_result = await auth_service.create_family(
            mail_auth_token,
            parent_password,
            "Test Device",
            "Pixel 7"
        )
        assert family_result is not None, "Family creation should succeed"

        # Step 4: Validate device auth token
        device_auth_token = family_result.get("deviceAuthToken")
        assert device_auth_token is not None, "Device auth token should be present"

    @pytest.mark.asyncio
    @pytest.mark.timeout(10)
    async def test_auth_flow_with_wrong_code(self, auth_service, state_manager):
        """Test authentication flow with wrong verification code."""
        auth_service.state = state_manager
        mail = "wrong_code@example.com"

        # Generate mail login token
        send_result = await auth_service.send_mail_login_code(mail)
        mail_login_token = send_result["mailLoginToken"]

        # Try to sign in with wrong code
        with pytest.raises(ValueError, match="Invalid verification code"):
            await auth_service.sign_in_by_mail_code(mail_login_token, "000000")
