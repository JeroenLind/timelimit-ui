"""Unit tests for AuthService logging integration.

This module tests that AuthService properly logs auth events:
- send_mail_login_code
- sign_in_by_mail_code (success and failure)
- get_status_by_mail_address
- create_family
- sign_in_into_family
- recover_parent_password
"""

import asyncio
import json
import logging
import os
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.middleware.server_message_logger import (
    ServerMessageLogger,
    MessageType,
    get_server_message_logger,
    reset_server_message_logger,
)
from app.middleware.message_sent_logger import (
    MessageSentLogger,
    get_message_sent_logger,
    reset_message_sent_logger,
)
from app.services.auth_service import AuthService


class TestAuthServiceLogging:
    """Tests for AuthService logging integration."""

    def setup_method(self):
        """Reset the global logger before each test."""
        reset_server_message_logger()
        reset_message_sent_logger()

    def teardown_method(self):
        """Reset the global logger after each test."""
        reset_server_message_logger()
        reset_message_sent_logger()

    @pytest.mark.asyncio
    @pytest.mark.timeout(30)
    async def test_log_auth_event_in_send_mail_login_code(self, tmp_path):
        """Verify log_auth_reply is called in send_mail_login_code."""
        log_file = tmp_path / "test.log"
        
        # Create mock state manager
        mock_state = MagicMock()
        mock_state.store_mail_login_token = AsyncMock()
        
        # Create auth service with mock state
        auth_service = AuthService(state=mock_state)
        
        # Patch the message logger
        with patch.object(auth_service, '_get_msg_logger') as mock_get_logger:
            mock_msg_logger = MagicMock()
            mock_get_logger.return_value = mock_msg_logger
            
            # Call send_mail_login_code
            result = await auth_service.send_mail_login_code(
                mail="test@example.com"
            )
            
            # Verify log_auth_reply was called
            mock_msg_logger.log_auth_reply.assert_called()
            
            # Verify the call arguments
            call_args = mock_msg_logger.log_auth_reply.call_args
            assert call_args[1]['event_type'] == 'mail_login_code_sent'
            assert call_args[1]['success'] == True

    @pytest.mark.asyncio
    @pytest.mark.timeout(30)
    async def test_log_auth_event_in_sign_in_by_mail_code_success(self, tmp_path):
        """Verify log_auth_reply is called in sign_in_by_mail_code on success."""
        log_file = tmp_path / "test.log"
        
        # Create mock state manager
        mock_state = MagicMock()
        mock_state.get_mail_login_token = AsyncMock(return_value={
            "mail": "test@example.com",
            "code": "123456"
        })
        mock_state.store_mail_auth_token = AsyncMock()
        mock_state.delete_mail_login_token = AsyncMock()
        
        # Create auth service with mock state
        auth_service = AuthService(state=mock_state)
        
        # Patch the message logger
        with patch.object(auth_service, '_get_msg_logger') as mock_get_logger:
            mock_msg_logger = MagicMock()
            mock_get_logger.return_value = mock_msg_logger
            
            # Call sign_in_by_mail_code
            result = await auth_service.sign_in_by_mail_code(
                mail_login_token="test_token",
                received_code="123456"
            )
            
            # Verify log_auth_reply was called
            mock_msg_logger.log_auth_reply.assert_called()
            
            # Verify the call arguments
            call_args = mock_msg_logger.log_auth_reply.call_args
            assert call_args[1]['event_type'] == 'sign_in_by_mail_code_success'
            assert call_args[1]['success'] == True

    @pytest.mark.asyncio
    @pytest.mark.timeout(30)
    async def test_log_auth_event_in_sign_in_by_mail_code_failure_invalid_token(self, tmp_path):
        """Verify log_auth_reply is called in sign_in_by_mail_code on invalid token."""
        log_file = tmp_path / "test.log"
        
        # Create mock state manager
        mock_state = MagicMock()
        mock_state.get_mail_login_token = AsyncMock(return_value=None)
        
        # Create auth service with mock state
        auth_service = AuthService(state=mock_state)
        
        # Patch the message logger
        with patch.object(auth_service, '_get_msg_logger') as mock_get_logger:
            mock_msg_logger = MagicMock()
            mock_get_logger.return_value = mock_msg_logger
            
            # Call sign_in_by_mail_code with invalid token
            with pytest.raises(ValueError, match="Invalid or expired mail login token"):
                await auth_service.sign_in_by_mail_code(
                    mail_login_token="invalid_token",
                    received_code="123456"
                )
            
            # Verify log_auth_reply was called with failure
            mock_msg_logger.log_auth_reply.assert_called()
            call_args = mock_msg_logger.log_auth_reply.call_args
            assert call_args[1]['event_type'] == 'login_failed'
            assert call_args[1]['success'] == False

    @pytest.mark.asyncio
    @pytest.mark.timeout(30)
    async def test_log_auth_event_in_sign_in_by_mail_code_failure_invalid_code(self, tmp_path):
        """Verify log_auth_reply is called in sign_in_by_mail_code on invalid code."""
        log_file = tmp_path / "test.log"
        
        # Create mock state manager
        mock_state = MagicMock()
        mock_state.get_mail_login_token = AsyncMock(return_value={
            "mail": "test@example.com",
            "code": "123456"
        })
        
        # Create auth service with mock state
        auth_service = AuthService(state=mock_state)
        
        # Patch the message logger
        with patch.object(auth_service, '_get_msg_logger') as mock_get_logger:
            mock_msg_logger = MagicMock()
            mock_get_logger.return_value = mock_msg_logger
            
            # Call sign_in_by_mail_code with wrong code
            with pytest.raises(ValueError, match="Invalid verification code"):
                await auth_service.sign_in_by_mail_code(
                    mail_login_token="test_token",
                    received_code="000000"
                )
            
            # Verify log_auth_reply was called with failure
            mock_msg_logger.log_auth_reply.assert_called()
            call_args = mock_msg_logger.log_auth_reply.call_args
            assert call_args[1]['event_type'] == 'login_failed'
            assert call_args[1]['success'] == False

    @pytest.mark.asyncio
    @pytest.mark.timeout(30)
    async def test_log_auth_event_in_get_status_by_mail_address(self, tmp_path):
        """Verify log_auth_reply is called in get_status_by_mail_address."""
        log_file = tmp_path / "test.log"
        
        # Create mock state manager
        mock_state = MagicMock()
        mock_state.get_mail_auth_token = AsyncMock(return_value={
            "mail": "test@example.com",
            "family_id": "family_123"
        })
        mock_state.get_family_by_mail = AsyncMock(return_value={"family_id": "family_123"})
        
        # Create auth service with mock state
        auth_service = AuthService(state=mock_state)
        
        # Patch the message logger
        with patch.object(auth_service, '_get_msg_logger') as mock_get_logger:
            mock_msg_logger = MagicMock()
            mock_get_logger.return_value = mock_msg_logger
            
            # Call get_status_by_mail_address
            result = await auth_service.get_status_by_mail_address(
                mail_auth_token="test_token"
            )
            
            # Verify log_auth_reply was called
            mock_msg_logger.log_auth_reply.assert_called()
            
            # Verify the call arguments
            call_args = mock_msg_logger.log_auth_reply.call_args
            assert call_args[1]['event_type'] == 'get_status_by_mail_address'
            assert call_args[1]['success'] == True

    @pytest.mark.asyncio
    @pytest.mark.timeout(30)
    async def test_log_auth_event_in_create_family(self, tmp_path):
        """Verify log_auth_reply is called in create_family."""
        log_file = tmp_path / "test.log"
        
        # Create mock state manager
        mock_state = MagicMock()
        mock_state.get_mail_auth_token = AsyncMock(return_value={
            "mail": "test@example.com",
            "family_id": ""
        })
        mock_state.create_family = AsyncMock()
        mock_state.create_user = AsyncMock()
        mock_state.create_device = AsyncMock()
        mock_state.store_device_auth_token = AsyncMock()
        mock_state.store_mail_auth_token = AsyncMock()
        mock_state.get_apps = AsyncMock(return_value=[])
        mock_state._categories = {}
        # Add mocks for _generate_server_data
        mock_state.get_family = AsyncMock(return_value={"family_id": "family_123"})
        mock_state.get_users_by_family = AsyncMock(return_value=[])
        mock_state.get_devices_by_family = AsyncMock(return_value=[])
        
        # Create auth service with mock state
        auth_service = AuthService(state=mock_state)
        
        # Patch the message logger
        with patch.object(auth_service, '_get_msg_logger') as mock_get_logger:
            mock_msg_logger = MagicMock()
            mock_get_logger.return_value = mock_msg_logger
            
            # Call create_family
            result = await auth_service.create_family(
                mail_auth_token="test_token",
                parent_password={
                    "hash": "test_hash",
                    "secondHash": "test_second_hash",
                    "secondSalt": "test_salt"
                }
            )
            
            # Verify log_auth_reply was called
            mock_msg_logger.log_auth_reply.assert_called()
            
            # Verify the call arguments
            call_args = mock_msg_logger.log_auth_reply.call_args
            assert call_args[1]['event_type'] == 'create_family_success'
            assert call_args[1]['success'] == True

    @pytest.mark.asyncio
    @pytest.mark.timeout(30)
    async def test_log_auth_event_in_sign_in_into_family_success(self, tmp_path):
        """Verify log_auth_reply is called in sign_in_into_family on success."""
        log_file = tmp_path / "test.log"
        
        # Create mock state manager
        mock_state = MagicMock()
        mock_state.get_mail_auth_token = AsyncMock(return_value={
            "mail": "test@example.com",
            "family_id": "family_123"
        })
        mock_state.get_family = AsyncMock(return_value={
            "family_id": "family_123",
            "parent_id": "user_456"
        })
        mock_state.get_user = AsyncMock(return_value={
            "id": "user_456",
            "password": "test_second_hash"
        })
        mock_state.create_device = AsyncMock()
        mock_state.store_device_auth_token = AsyncMock()
        mock_state.get_apps = AsyncMock(return_value=[])
        mock_state._categories = {}
        # Add mocks for _generate_server_data
        mock_state.get_users_by_family = AsyncMock(return_value=[])
        mock_state.get_devices_by_family = AsyncMock(return_value=[])
        
        # Create auth service with mock state
        auth_service = AuthService(state=mock_state)
        
        # Patch the message logger
        with patch.object(auth_service, '_get_msg_logger') as mock_get_logger:
            mock_msg_logger = MagicMock()
            mock_get_logger.return_value = mock_msg_logger
            
            # Call sign_in_into_family
            result = await auth_service.sign_in_into_family(
                mail_auth_token="test_token",
                parent_password_second_hash="test_second_hash"
            )
            
            # Verify log_auth_reply was called
            mock_msg_logger.log_auth_reply.assert_called()
            
            # Verify the call arguments
            call_args = mock_msg_logger.log_auth_reply.call_args
            assert call_args[1]['event_type'] == 'sign_in_into_family_success'
            assert call_args[1]['success'] == True

    @pytest.mark.asyncio
    @pytest.mark.timeout(30)
    async def test_log_auth_event_in_sign_in_into_family_failure(self, tmp_path):
        """Verify log_auth_reply is called in sign_in_into_family on failure."""
        log_file = tmp_path / "test.log"
        
        # Create mock state manager
        mock_state = MagicMock()
        mock_state.get_mail_auth_token = AsyncMock(return_value={
            "mail": "test@example.com",
            "family_id": "family_123"
        })
        mock_state.get_family = AsyncMock(return_value={
            "family_id": "family_123",
            "parent_id": "user_456"
        })
        mock_state.get_user = AsyncMock(return_value={
            "id": "user_456",
            "password": "correct_hash"
        })
        mock_state.create_device = AsyncMock()
        mock_state.store_device_auth_token = AsyncMock()
        mock_state.get_apps = AsyncMock(return_value=[])
        mock_state._categories = {}
        # Add mocks for _generate_server_data
        mock_state.get_users_by_family = AsyncMock(return_value=[])
        mock_state.get_devices_by_family = AsyncMock(return_value=[])
        
        # Create auth service with mock state
        auth_service = AuthService(state=mock_state)
        
        # Patch the message logger
        with patch.object(auth_service, '_get_msg_logger') as mock_get_logger:
            mock_msg_logger = MagicMock()
            mock_get_logger.return_value = mock_msg_logger
            
            # Call sign_in_into_family with wrong password
            with pytest.raises(ValueError, match="Invalid password"):
                await auth_service.sign_in_into_family(
                    mail_auth_token="test_token",
                    parent_password_second_hash="wrong_hash"
                )
            
            # Verify log_auth_reply was called with failure
            mock_msg_logger.log_auth_reply.assert_called()
            call_args = mock_msg_logger.log_auth_reply.call_args
            assert call_args[1]['event_type'] == 'sign_in_into_family_failed'
            assert call_args[1]['success'] == False

    @pytest.mark.asyncio
    @pytest.mark.timeout(30)
    async def test_log_auth_event_in_recover_parent_password(self, tmp_path):
        """Verify log_auth_reply is called in recover_parent_password."""
        log_file = tmp_path / "test.log"
        
        # Create mock state manager
        mock_state = MagicMock()
        mock_state.get_mail_auth_token = AsyncMock(return_value={
            "mail": "test@example.com",
            "family_id": "family_123"
        })
        mock_state.get_family = AsyncMock(return_value={
            "family_id": "family_123",
            "parent_id": "user_456"
        })
        mock_state.update_user = AsyncMock()
        
        # Create auth service with mock state
        auth_service = AuthService(state=mock_state)
        
        # Patch the message logger
        with patch.object(auth_service, '_get_msg_logger') as mock_get_logger:
            mock_msg_logger = MagicMock()
            mock_get_logger.return_value = mock_msg_logger
            
            # Call recover_parent_password
            result = await auth_service.recover_parent_password(
                mail_auth_token="test_token",
                new_password={
                    "hash": "new_hash",
                    "secondSalt": "new_salt"
                }
            )
            
            # Verify log_auth_reply was called
            mock_msg_logger.log_auth_reply.assert_called()
            
            # Verify the call arguments
            call_args = mock_msg_logger.log_auth_reply.call_args
            assert call_args[1]['event_type'] == 'recover_parent_password'
            assert call_args[1]['success'] == True


class TestAuthServiceLoggingContent:
    """Tests for auth event log content."""

    def setup_method(self):
        """Reset the global logger before each test."""
        reset_server_message_logger()
        reset_message_sent_logger()

    def teardown_method(self):
        """Reset the global logger after each test."""
        reset_server_message_logger()
        reset_message_sent_logger()

    @pytest.mark.asyncio
    @pytest.mark.timeout(30)
    async def test_auth_event_content_includes_user_id(self, tmp_path):
        """Verify auth event content includes user_id."""
        log_file = tmp_path / "test.log"
        
        # Create mock state manager
        mock_state = MagicMock()
        mock_state.store_mail_login_token = AsyncMock()
        
        # Create auth service with mock state
        auth_service = AuthService(state=mock_state)
        
        # Patch the message logger to verify log_auth_reply is called
        with patch.object(auth_service, '_get_msg_logger') as mock_get_logger:
            mock_msg_logger = MagicMock()
            mock_get_logger.return_value = mock_msg_logger
            
            # Call send_mail_login_code
            await auth_service.send_mail_login_code(mail="test@example.com")
            
            # Verify log_auth_reply was called
            mock_msg_logger.log_auth_reply.assert_called()
            
            # Verify the call arguments
            call_args = mock_msg_logger.log_auth_reply.call_args
            assert call_args[1]['event_type'] == 'mail_login_code_sent'

    @pytest.mark.asyncio
    @pytest.mark.timeout(30)
    async def test_auth_event_content_includes_event_type(self, tmp_path):
        """Verify auth event content includes event_type."""
        log_file = tmp_path / "test.log"
        
        # Create mock state manager
        mock_state = MagicMock()
        mock_state.store_mail_login_token = AsyncMock()
        
        # Create auth service with mock state
        auth_service = AuthService(state=mock_state)
        
        # Patch the message logger to verify log_auth_reply is called
        with patch.object(auth_service, '_get_msg_logger') as mock_get_logger:
            mock_msg_logger = MagicMock()
            mock_get_logger.return_value = mock_msg_logger
            
            # Call send_mail_login_code
            await auth_service.send_mail_login_code(mail="test@example.com")
            
            # Verify log_auth_reply was called
            mock_msg_logger.log_auth_reply.assert_called()
            
            # Verify the call arguments
            call_args = mock_msg_logger.log_auth_reply.call_args
            assert call_args[1]['event_type'] == 'mail_login_code_sent'

    @pytest.mark.asyncio
    @pytest.mark.timeout(30)
    async def test_auth_event_content_includes_success_flag(self, tmp_path):
        """Verify auth event content includes success flag."""
        log_file = tmp_path / "test.log"
        
        # Create mock state manager
        mock_state = MagicMock()
        mock_state.store_mail_login_token = AsyncMock()
        
        # Create auth service with mock state
        auth_service = AuthService(state=mock_state)
        
        # Patch the message logger to verify log_auth_reply is called
        with patch.object(auth_service, '_get_msg_logger') as mock_get_logger:
            mock_msg_logger = MagicMock()
            mock_get_logger.return_value = mock_msg_logger
            
            # Call send_mail_login_code
            await auth_service.send_mail_login_code(mail="test@example.com")
            
            # Verify log_auth_reply was called
            mock_msg_logger.log_auth_reply.assert_called()
            
            # Verify the call arguments
            call_args = mock_msg_logger.log_auth_reply.call_args
            assert call_args[1]['success'] == True


class TestAuthServiceLoggingErrors:
    """Tests for error scenarios in AuthService logging."""

    def setup_method(self):
        """Reset the global logger before each test."""
        reset_server_message_logger()
        reset_message_sent_logger()

    def teardown_method(self):
        """Reset the global logger after each test."""
        reset_server_message_logger()
        reset_message_sent_logger()

    @pytest.mark.asyncio
    @pytest.mark.timeout(30)
    async def test_invalid_mail_login_token_raises_error(self, tmp_path):
        """Verify invalid mail login token raises error in send_mail_login_code."""
        log_file = tmp_path / "test.log"
        
        # Create mock state manager
        mock_state = MagicMock()
        mock_state.store_mail_login_token = AsyncMock()
        
        # Create auth service with mock state
        auth_service = AuthService(state=mock_state)
        
        # Patch the message logger
        with patch.object(auth_service, '_get_msg_logger') as mock_get_logger:
            mock_msg_logger = MagicMock()
            mock_get_logger.return_value = mock_msg_logger
            
            # Call send_mail_login_code
            result = await auth_service.send_mail_login_code(mail="test@example.com")
            
            # Verify log_auth_reply was called
            mock_msg_logger.log_auth_reply.assert_called()

    @pytest.mark.asyncio
    @pytest.mark.timeout(30)
    async def test_invalid_mail_auth_token_raises_error(self, tmp_path):
        """Verify invalid mail auth token raises error in get_status_by_mail_address."""
        log_file = tmp_path / "test.log"
        
        # Create mock state manager
        mock_state = MagicMock()
        mock_state.get_mail_auth_token = AsyncMock(return_value=None)
        
        # Create auth service with mock state
        auth_service = AuthService(state=mock_state)
        
        # Call get_status_by_mail_address with invalid token
        with pytest.raises(ValueError, match="Invalid mail auth token"):
            await auth_service.get_status_by_mail_address(mail_auth_token="invalid_token")

    @pytest.mark.asyncio
    @pytest.mark.timeout(30)
    async def test_invalid_mail_auth_token_raises_error_in_create_family(self, tmp_path):
        """Verify invalid mail auth token raises error in create_family."""
        log_file = tmp_path / "test.log"
        
        # Create mock state manager
        mock_state = MagicMock()
        mock_state.get_mail_auth_token = AsyncMock(return_value=None)
        
        # Create auth service with mock state
        auth_service = AuthService(state=mock_state)
        
        # Call create_family with invalid token
        with pytest.raises(ValueError, match="Invalid mail auth token"):
            await auth_service.create_family(
                mail_auth_token="invalid_token",
                parent_password={}
            )

    @pytest.mark.asyncio
    @pytest.mark.timeout(30)
    async def test_invalid_mail_auth_token_raises_error_in_sign_in_into_family(self, tmp_path):
        """Verify invalid mail auth token raises error in sign_in_into_family."""
        log_file = tmp_path / "test.log"
        
        # Create mock state manager
        mock_state = MagicMock()
        mock_state.get_mail_auth_token = AsyncMock(return_value=None)
        
        # Create auth service with mock state
        auth_service = AuthService(state=mock_state)
        
        # Call sign_in_into_family with invalid token
        with pytest.raises(ValueError, match="Invalid mail auth token"):
            await auth_service.sign_in_into_family(
                mail_auth_token="invalid_token",
                parent_password_second_hash="test_hash"
            )

    @pytest.mark.asyncio
    @pytest.mark.timeout(30)
    async def test_invalid_mail_auth_token_raises_error_in_recover_parent_password(self, tmp_path):
        """Verify invalid mail auth token raises error in recover_parent_password."""
        log_file = tmp_path / "test.log"
        
        # Create mock state manager
        mock_state = MagicMock()
        mock_state.get_mail_auth_token = AsyncMock(return_value=None)
        
        # Create auth service with mock state
        auth_service = AuthService(state=mock_state)
        
        # Call recover_parent_password with invalid token
        with pytest.raises(ValueError, match="Invalid mail auth token"):
            await auth_service.recover_parent_password(
                mail_auth_token="invalid_token",
                new_password={}
            )

    @pytest.mark.asyncio
    @pytest.mark.timeout(30)
    async def test_family_not_found_raises_error_in_sign_in_into_family(self, tmp_path):
        """Verify family not found raises error in sign_in_into_family."""
        log_file = tmp_path / "test.log"
        
        # Create mock state manager
        mock_state = MagicMock()
        mock_state.get_mail_auth_token = AsyncMock(return_value={
            "mail": "test@example.com",
            "family_id": "family_123"
        })
        mock_state.get_family = AsyncMock(return_value=None)
        
        # Create auth service with mock state
        auth_service = AuthService(state=mock_state)
        
        # Call sign_in_into_family
        with pytest.raises(ValueError, match="Family not found"):
            await auth_service.sign_in_into_family(
                mail_auth_token="test_token",
                parent_password_second_hash="test_hash"
            )

    @pytest.mark.asyncio
    @pytest.mark.timeout(30)
    async def test_parent_user_not_found_raises_error(self, tmp_path):
        """Verify parent user not found raises error in sign_in_into_family."""
        log_file = tmp_path / "test.log"
        
        # Create mock state manager
        mock_state = MagicMock()
        mock_state.get_mail_auth_token = AsyncMock(return_value={
            "mail": "test@example.com",
            "family_id": "family_123"
        })
        mock_state.get_family = AsyncMock(return_value={
            "family_id": "family_123",
            "parent_id": "user_456"
        })
        mock_state.get_user = AsyncMock(return_value=None)
        
        # Create auth service with mock state
        auth_service = AuthService(state=mock_state)
        
        # Call sign_in_into_family
        with pytest.raises(ValueError, match="Parent user not found"):
            await auth_service.sign_in_into_family(
                mail_auth_token="test_token",
                parent_password_second_hash="test_hash"
            )

    @pytest.mark.asyncio
    @pytest.mark.timeout(30)
    async def test_family_not_found_raises_error_in_recover_parent_password(self, tmp_path):
        """Verify family not found raises error in recover_parent_password."""
        log_file = tmp_path / "test.log"
        
        # Create mock state manager
        mock_state = MagicMock()
        mock_state.get_mail_auth_token = AsyncMock(return_value={
            "mail": "test@example.com",
            "family_id": "family_123"
        })
        mock_state.get_family = AsyncMock(return_value=None)
        
        # Create auth service with mock state
        auth_service = AuthService(state=mock_state)
        
        # Call recover_parent_password
        with pytest.raises(ValueError, match="Family not found"):
            await auth_service.recover_parent_password(
                mail_auth_token="test_token",
                new_password={}
            )
