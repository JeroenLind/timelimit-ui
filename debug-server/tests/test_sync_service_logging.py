"""Unit tests for SyncService logging integration.

This module tests that SyncService properly logs sync actions:
- push_actions
- pull_status
- report_removed
- is_device_removed
- get_pending_actions
- clear_pending_actions
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
from app.services.sync_service import SyncService


class TestSyncServiceLogging:
    """Tests for SyncService logging integration."""

    def setup_method(self):
        """Reset the global logger before each test."""
        reset_server_message_logger()
        reset_message_sent_logger()

    def teardown_method(self):
        """Reset the global logger after each test."""
        reset_server_message_logger()
        reset_message_sent_logger()

    @pytest.mark.asyncio
    async def test_log_sync_action_in_push_actions(self, tmp_path):
        """Verify log_sync_action is called in push_actions."""
        log_file = tmp_path / "test.log"
        
        # Create mock state manager
        mock_state = MagicMock()
        mock_state.get_device_auth_token = AsyncMock(return_value={
            "device_id": "device_123",
            "family_id": "family_456"
        })
        mock_state.add_pending_action = AsyncMock()
        
        # Create sync service with mock state
        sync_service = SyncService(state=mock_state)
        
        # Patch the message logger
        with patch.object(sync_service, '_get_msg_logger') as mock_get_logger:
            mock_msg_logger = MagicMock()
            mock_get_logger.return_value = mock_msg_logger
            
            # Call push_actions
            result = await sync_service.push_actions(
                device_auth_token="test_token",
                actions=[{"sequenceNumber": 1, "encodedAction": "test", "integrity": "abc"}]
            )
            
            # Verify log_sync_action was called
            mock_msg_logger.log_sync_action.assert_called()
            
            # Verify the call arguments
            call_args = mock_msg_logger.log_sync_action.call_args
            assert call_args[1]['action_type'] == 'PushActionsResponse'
            assert 'shouldDoFullSync' in call_args[1]['action_data']

    @pytest.mark.asyncio
    async def test_log_sync_action_in_pull_status(self, tmp_path):
        """Verify log_sync_action is called in pull_status."""
        log_file = tmp_path / "test.log"
        
        # Create mock state manager
        mock_state = MagicMock()
        mock_state.get_device_auth_token = AsyncMock(return_value={
            "device_id": "device_123",
            "family_id": "family_456"
        })
        mock_state.get_family = AsyncMock(return_value={"family_id": "family_456"})
        mock_state.get_users_by_family = AsyncMock(return_value=[])
        mock_state.get_devices_by_family = AsyncMock(return_value=[])
        mock_state.get_sync_version = AsyncMock(return_value="1")
        mock_state._categories = {}
        mock_state.get_apps = AsyncMock(return_value=[])
        
        # Create sync service with mock state
        sync_service = SyncService(state=mock_state)
        
        # Patch the message logger
        with patch.object(sync_service, '_get_msg_logger') as mock_get_logger:
            mock_msg_logger = MagicMock()
            mock_get_logger.return_value = mock_msg_logger
            
            # Call pull_status
            result = await sync_service.pull_status(
                device_auth_token="test_token",
                client_status={}
            )
            
            # Verify log_sync_action was called
            mock_msg_logger.log_sync_action.assert_called()
            
            # Verify the call arguments
            call_args = mock_msg_logger.log_sync_action.call_args
            assert call_args[1]['action_type'] == 'PullStatusResponse'
            assert 'devices' in call_args[1]['action_data']

    @pytest.mark.asyncio
    async def test_log_sync_action_in_report_removed(self, tmp_path):
        """Verify log_sync_action is called in report_removed."""
        log_file = tmp_path / "test.log"
        
        # Create mock state manager
        mock_state = MagicMock()
        mock_state.get_device_auth_token = AsyncMock(return_value={
            "device_id": "device_123",
            "family_id": "family_456"
        })
        mock_state.delete_device = AsyncMock()
        mock_state.delete_device_auth_token = AsyncMock()
        
        # Create sync service with mock state
        sync_service = SyncService(state=mock_state)
        
        # Patch the message logger
        with patch.object(sync_service, '_get_msg_logger') as mock_get_logger:
            mock_msg_logger = MagicMock()
            mock_get_logger.return_value = mock_msg_logger
            
            # Call report_removed
            result = await sync_service.report_removed(device_auth_token="test_token")
            
            # Verify log_sync_action was called
            mock_msg_logger.log_sync_action.assert_called()
            
            # Verify the call arguments
            call_args = mock_msg_logger.log_sync_action.call_args
            assert call_args[1]['action_type'] == 'ReportRemovedResponse'

    @pytest.mark.asyncio
    async def test_log_sync_action_in_is_device_removed(self, tmp_path):
        """Verify log_sync_action is called in is_device_removed."""
        log_file = tmp_path / "test.log"
        
        # Create mock state manager
        mock_state = MagicMock()
        mock_state.get_device_auth_token = AsyncMock(return_value={
            "device_id": "device_123",
            "family_id": "family_456"
        })
        mock_state.get_device = AsyncMock(return_value={"deviceId": "device_123"})
        
        # Create sync service with mock state
        sync_service = SyncService(state=mock_state)
        
        # Patch the message logger
        with patch.object(sync_service, '_get_msg_logger') as mock_get_logger:
            mock_msg_logger = MagicMock()
            mock_get_logger.return_value = mock_msg_logger
            
            # Call is_device_removed
            result = await sync_service.is_device_removed(device_auth_token="test_token")
            
            # Verify log_sync_action was called
            mock_msg_logger.log_sync_action.assert_called()
            
            # Verify the call arguments
            call_args = mock_msg_logger.log_sync_action.call_args
            assert call_args[1]['action_type'] == 'IsDeviceRemovedResponse'

    @pytest.mark.asyncio
    async def test_log_sync_action_in_get_pending_actions(self, tmp_path):
        """Verify log_sync_action is called in get_pending_actions."""
        log_file = tmp_path / "test.log"
        
        # Create mock state manager
        mock_state = MagicMock()
        mock_state.get_device_auth_token = AsyncMock(return_value={
            "device_id": "device_123",
            "family_id": "family_456"
        })
        mock_state.get_pending_actions = AsyncMock(return_value=[])
        
        # Create sync service with mock state
        sync_service = SyncService(state=mock_state)
        
        # Patch the message logger
        with patch.object(sync_service, '_get_msg_logger') as mock_get_logger:
            mock_msg_logger = MagicMock()
            mock_get_logger.return_value = mock_msg_logger
            
            # Call get_pending_actions
            result = await sync_service.get_pending_actions(
                device_auth_token="test_token",
                limit=25
            )
            
            # Verify log_sync_action was called
            mock_msg_logger.log_sync_action.assert_called()
            
            # Verify the call arguments
            call_args = mock_msg_logger.log_sync_action.call_args
            assert call_args[1]['action_type'] == 'GetPendingActionsResponse'

    @pytest.mark.asyncio
    async def test_log_sync_action_in_clear_pending_actions(self, tmp_path):
        """Verify log_sync_action is called in clear_pending_actions."""
        log_file = tmp_path / "test.log"
        
        # Create mock state manager
        mock_state = MagicMock()
        mock_state.get_device_auth_token = AsyncMock(return_value={
            "device_id": "device_123",
            "family_id": "family_456"
        })
        mock_state.clear_pending_actions = AsyncMock()
        
        # Create sync service with mock state
        sync_service = SyncService(state=mock_state)
        
        # Patch the message logger
        with patch.object(sync_service, '_get_msg_logger') as mock_get_logger:
            mock_msg_logger = MagicMock()
            mock_get_logger.return_value = mock_msg_logger
            
            # Call clear_pending_actions
            await sync_service.clear_pending_actions(device_auth_token="test_token")
            
            # Verify log_sync_action was called
            mock_msg_logger.log_sync_action.assert_called()
            
            # Verify the call arguments
            call_args = mock_msg_logger.log_sync_action.call_args
            assert call_args[1]['action_type'] == 'ClearPendingActionsResponse'

    @pytest.mark.asyncio
    async def test_log_sync_action_on_invalid_token_push_actions(self, tmp_path):
        """Verify log_sync_action is called even on invalid token in push_actions."""
        log_file = tmp_path / "test.log"
        
        # Create mock state manager that returns None for invalid token
        mock_state = MagicMock()
        mock_state.get_device_auth_token = AsyncMock(return_value=None)
        
        # Create sync service with mock state
        sync_service = SyncService(state=mock_state)
        
        # Patch the message logger
        with patch.object(sync_service, '_get_msg_logger') as mock_get_logger:
            mock_msg_logger = MagicMock()
            mock_get_logger.return_value = mock_msg_logger
            
            # Call push_actions with invalid token
            with pytest.raises(ValueError, match="Invalid device auth token"):
                await sync_service.push_actions(
                    device_auth_token="invalid_token",
                    actions=[]
                )
            
            # Verify log_sync_action was NOT called (exception raised before logging)
            mock_msg_logger.log_sync_action.assert_not_called()

    @pytest.mark.asyncio
    async def test_log_sync_action_on_invalid_token_pull_status(self, tmp_path):
        """Verify log_sync_action is called even on invalid token in pull_status."""
        log_file = tmp_path / "test.log"
        
        # Create mock state manager that returns None for invalid token
        mock_state = MagicMock()
        mock_state.get_device_auth_token = AsyncMock(return_value=None)
        
        # Create sync service with mock state
        sync_service = SyncService(state=mock_state)
        
        # Patch the message logger
        with patch.object(sync_service, '_get_msg_logger') as mock_get_logger:
            mock_msg_logger = MagicMock()
            mock_get_logger.return_value = mock_msg_logger
            
            # Call pull_status with invalid token
            with pytest.raises(ValueError, match="Invalid device auth token"):
                await sync_service.pull_status(
                    device_auth_token="invalid_token",
                    client_status={}
                )
            
            # Verify log_sync_action was NOT called (exception raised before logging)
            mock_msg_logger.log_sync_action.assert_not_called()


class TestSyncServiceLoggingContent:
    """Tests for sync action log content."""

    def setup_method(self):
        """Reset the global logger before each test."""
        reset_server_message_logger()
        reset_message_sent_logger()

    def teardown_method(self):
        """Reset the global logger after each test."""
        reset_server_message_logger()
        reset_message_sent_logger()

    @pytest.mark.asyncio
    async def test_sync_action_content_includes_action_type(self, tmp_path):
        """Verify sync action content includes action_type."""
        log_file = tmp_path / "test.log"
        
        # Create mock state manager
        mock_state = MagicMock()
        mock_state.get_device_auth_token = AsyncMock(return_value={
            "device_id": "device_123",
            "family_id": "family_456"
        })
        mock_state.add_pending_action = AsyncMock()
        
        # Create sync service with mock state
        sync_service = SyncService(state=mock_state)
        
        # Patch the message logger
        with patch.object(sync_service, '_get_msg_logger') as mock_get_logger:
            mock_msg_logger = MagicMock()
            mock_get_logger.return_value = mock_msg_logger
            
            # Call push_actions
            await sync_service.push_actions(
                device_auth_token="test_token",
                actions=[{"sequenceNumber": 1, "encodedAction": "test", "integrity": "abc"}]
            )
            
            # Verify log_sync_action was called
            mock_msg_logger.log_sync_action.assert_called()
            
            # Verify the call arguments
            call_args = mock_msg_logger.log_sync_action.call_args
            assert call_args[1]['action_type'] == 'PushActionsResponse'

    @pytest.mark.asyncio
    async def test_sync_action_content_includes_family_id(self, tmp_path):
        """Verify sync action content includes family_id."""
        log_file = tmp_path / "test.log"
        
        # Create mock state manager
        mock_state = MagicMock()
        mock_state.get_device_auth_token = AsyncMock(return_value={
            "device_id": "device_123",
            "family_id": "family_abc123"
        })
        mock_state.add_pending_action = AsyncMock()
        
        # Create sync service with mock state
        sync_service = SyncService(state=mock_state)
        
        # Patch the message logger
        with patch.object(sync_service, '_get_msg_logger') as mock_get_logger:
            mock_msg_logger = MagicMock()
            mock_get_logger.return_value = mock_msg_logger
            
            # Call push_actions
            await sync_service.push_actions(
                device_auth_token="test_token",
                actions=[{"sequenceNumber": 1, "encodedAction": "test", "integrity": "abc"}]
            )
            
            # Verify log_sync_action was called
            mock_msg_logger.log_sync_action.assert_called()
            
            # Verify the call arguments
            call_args = mock_msg_logger.log_sync_action.call_args
            assert call_args[1]['family_id'] == 'family_abc123'

    @pytest.mark.asyncio
    async def test_sync_action_content_includes_sequence_number(self, tmp_path):
        """Verify sync action content includes sequence_number when provided."""
        log_file = tmp_path / "test.log"
        
        # Create mock state manager
        mock_state = MagicMock()
        mock_state.get_device_auth_token = AsyncMock(return_value={
            "device_id": "device_123",
            "family_id": "family_456"
        })
        mock_state.add_pending_action = AsyncMock()
        
        # Create sync service with mock state
        sync_service = SyncService(state=mock_state)
        
        # Patch the message logger
        with patch.object(sync_service, '_get_msg_logger') as mock_get_logger:
            mock_msg_logger = MagicMock()
            mock_get_logger.return_value = mock_msg_logger
            
            # Call push_actions
            await sync_service.push_actions(
                device_auth_token="test_token",
                actions=[{"sequenceNumber": 42, "encodedAction": "test", "integrity": "abc"}]
            )
            
            # Verify log_sync_action was called
            mock_msg_logger.log_sync_action.assert_called()
            
            # Verify the call arguments
            call_args = mock_msg_logger.log_sync_action.call_args
            assert call_args[1]['action_type'] == 'PushActionsResponse'


class TestSyncServiceLoggingErrors:
    """Tests for error scenarios in SyncService logging."""

    def setup_method(self):
        """Reset the global logger before each test."""
        reset_server_message_logger()
        reset_message_sent_logger()

    def teardown_method(self):
        """Reset the global logger after each test."""
        reset_server_message_logger()
        reset_message_sent_logger()

    @pytest.mark.asyncio
    async def test_invalid_token_raises_error(self, tmp_path):
        """Verify invalid token raises error in push_actions."""
        log_file = tmp_path / "test.log"
        
        # Create mock state manager
        mock_state = MagicMock()
        mock_state.get_device_auth_token = AsyncMock(return_value=None)
        
        # Create sync service with mock state
        sync_service = SyncService(state=mock_state)
        
        # Call push_actions with invalid token
        with pytest.raises(ValueError, match="Invalid device auth token"):
            await sync_service.push_actions(
                device_auth_token="invalid_token",
                actions=[]
            )

    @pytest.mark.asyncio
    async def test_invalid_token_raises_error_in_pull_status(self, tmp_path):
        """Verify invalid token raises error in pull_status."""
        log_file = tmp_path / "test.log"
        
        # Create mock state manager
        mock_state = MagicMock()
        mock_state.get_device_auth_token = AsyncMock(return_value=None)
        
        # Create sync service with mock state
        sync_service = SyncService(state=mock_state)
        
        # Call pull_status with invalid token
        with pytest.raises(ValueError, match="Invalid device auth token"):
            await sync_service.pull_status(
                device_auth_token="invalid_token",
                client_status={}
            )

    @pytest.mark.asyncio
    async def test_family_not_found_raises_error(self, tmp_path):
        """Verify family not found raises error in pull_status."""
        log_file = tmp_path / "test.log"
        
        # Create mock state manager
        mock_state = MagicMock()
        mock_state.get_device_auth_token = AsyncMock(return_value={
            "device_id": "device_123",
            "family_id": "family_456"
        })
        mock_state.get_family = AsyncMock(return_value=None)
        
        # Create sync service with mock state
        sync_service = SyncService(state=mock_state)
        
        # Call pull_status
        with pytest.raises(ValueError, match="Family not found"):
            await sync_service.pull_status(
                device_auth_token="test_token",
                client_status={}
            )

    @pytest.mark.asyncio
    async def test_invalid_token_raises_error_in_report_removed(self, tmp_path):
        """Verify invalid token raises error in report_removed."""
        log_file = tmp_path / "test.log"
        
        # Create mock state manager
        mock_state = MagicMock()
        mock_state.get_device_auth_token = AsyncMock(return_value=None)
        
        # Create sync service with mock state
        sync_service = SyncService(state=mock_state)
        
        # Call report_removed with invalid token
        with pytest.raises(ValueError, match="Invalid device auth token"):
            await sync_service.report_removed(device_auth_token="invalid_token")

    @pytest.mark.asyncio
    async def test_invalid_token_raises_error_in_is_device_removed(self, tmp_path):
        """Verify invalid token returns isDeviceRemoved=True in is_device_removed."""
        log_file = tmp_path / "test.log"
        
        # Create mock state manager
        mock_state = MagicMock()
        mock_state.get_device_auth_token = AsyncMock(return_value=None)
        
        # Create sync service with mock state
        sync_service = SyncService(state=mock_state)
        
        # Call is_device_removed with invalid token
        result = await sync_service.is_device_removed(device_auth_token="invalid_token")
        
        # Should return isDeviceRemoved=True
        assert result["isDeviceRemoved"] == True

    @pytest.mark.asyncio
    async def test_invalid_token_raises_error_in_get_pending_actions(self, tmp_path):
        """Verify invalid token raises error in get_pending_actions."""
        log_file = tmp_path / "test.log"
        
        # Create mock state manager
        mock_state = MagicMock()
        mock_state.get_device_auth_token = AsyncMock(return_value=None)
        
        # Create sync service with mock state
        sync_service = SyncService(state=mock_state)
        
        # Call get_pending_actions with invalid token
        with pytest.raises(ValueError, match="Invalid device auth token"):
            await sync_service.get_pending_actions(device_auth_token="invalid_token")

    @pytest.mark.asyncio
    async def test_invalid_token_raises_error_in_clear_pending_actions(self, tmp_path):
        """Verify invalid token raises error in clear_pending_actions."""
        log_file = tmp_path / "test.log"
        
        # Create mock state manager
        mock_state = MagicMock()
        mock_state.get_device_auth_token = AsyncMock(return_value=None)
        
        # Create sync service with mock state
        sync_service = SyncService(state=mock_state)
        
        # Call clear_pending_actions with invalid token
        with pytest.raises(ValueError, match="Invalid device auth token"):
            await sync_service.clear_pending_actions(device_auth_token="invalid_token")
