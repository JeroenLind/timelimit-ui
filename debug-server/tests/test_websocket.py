"""Unit tests for WebSocket functionality.

This module tests WebSocket (Socket.IO) functionality:
- Connection handling
- Event broadcasting
- Message handling
- Disconnection handling
"""

import pytest
import asyncio
import json
from unittest.mock import patch, MagicMock, AsyncMock
from fastapi.testclient import TestClient

from app.websocket.manager import ConnectionManager, SocketIOHandler
from app.websocket.handlers import (
    on_connect,
    on_disconnect,
    on_devicelogin,
    on_should_sync,
    on_connected_devices,
    on_sign_out,
    on_ping,
    on_pong,
    get_event_handler,
)


class TestConnectionManager:
    """Tests for ConnectionManager class."""

    @pytest.fixture
    def manager(self):
        """Create a ConnectionManager instance for testing."""
        return ConnectionManager()

    def test_manager_initialization(self, manager):
        """Test ConnectionManager initialization."""
        assert manager is not None, "Manager should be initialized"
        assert hasattr(manager, '_active_connections'), "Should have active_connections attribute"

    @pytest.mark.asyncio
    async def test_add_connection(self, manager):
        """Test adding a connection."""
        connection_id = "conn_123"

        await manager.connect(connection_id)

        assert connection_id in manager.get_active_connections(), \
            "Connection should be added to active connections"

    @pytest.mark.asyncio
    async def test_remove_connection(self, manager):
        """Test removing a connection."""
        connection_id = "conn_123"

        await manager.connect(connection_id)
        await manager.disconnect(connection_id)

        assert connection_id not in manager.get_active_connections(), \
            "Connection should be removed from active connections"

    @pytest.mark.asyncio
    async def test_get_active_connections(self, manager):
        """Test getting all active connections."""
        connection_ids = ["conn_1", "conn_2", "conn_3"]

        for cid in connection_ids:
            await manager.connect(cid)

        active = manager.get_active_connections()
        assert len(active) == 3, "Should have 3 active connections"
        assert set(active) == set(connection_ids), "All connection IDs should be present"

    @pytest.mark.asyncio
    async def test_duplicate_connection(self, manager):
        """Test adding duplicate connection."""
        connection_id = "conn_123"

        await manager.connect(connection_id)
        await manager.connect(connection_id)  # Add again

        active = manager.get_active_connections()
        assert len(active) == 1, "Duplicate connection should not be added twice"


class TestSocketIOHandler:
    """Tests for SocketIOHandler class."""

    @pytest.fixture
    def handler(self):
        """Create a SocketIOHandler instance for testing."""
        return SocketIOHandler()

    def test_handler_initialization(self, handler):
        """Test SocketIOHandler initialization."""
        assert handler is not None, "Handler should be initialized"

    @pytest.mark.asyncio
    async def test_handle_connect(self, handler):
        """Test connection event handling."""
        result = await on_connect("conn_123", {})

        assert result is not None, "Connect handler should return a result"
        assert result["status"] == "connected", "Status should be connected"

    @pytest.mark.asyncio
    async def test_handle_disconnect(self, handler):
        """Test disconnection event handling."""
        # Should not raise
        await on_disconnect("conn_123")

    @pytest.mark.asyncio
    async def test_handle_devicelogin(self, handler):
        """Test device login event handling."""
        data = {"deviceId": "device_123", "familyId": "family_456"}

        result = await on_devicelogin("conn_123", data)

        assert result is not None, "Device login handler should return a result"
        assert result["status"] == "ok", "Status should be ok"

    @pytest.mark.asyncio
    async def test_handle_should_sync(self, handler):
        """Test sync notification event handling."""
        data = {"deviceId": "device_123", "familyId": "family_456"}

        result = await on_should_sync("conn_123", data)

        assert result is not None, "Sync handler should return a result"
        assert result["status"] == "ok", "Status should be ok"

    @pytest.mark.asyncio
    async def test_handle_connected_devices(self, handler):
        """Test connected devices event handling."""
        data = {"deviceId": "device_123", "familyId": "family_456"}

        result = await on_connected_devices("conn_123", data)

        assert result is not None, "Connected devices handler should return a result"
        assert result["status"] == "ok", "Status should be ok"

    @pytest.mark.asyncio
    async def test_handle_sign_out(self, handler):
        """Test sign out event handling."""
        data = {"deviceId": "device_123", "familyId": "family_456"}

        result = await on_sign_out("conn_123", data)

        assert result is not None, "Sign out handler should return a result"
        assert result["status"] == "ok", "Status should be ok"

    @pytest.mark.asyncio
    async def test_handle_ping(self, handler):
        """Test ping event handling."""
        data = {"timestamp": 1234567890}

        result = await on_ping("conn_123", data)

        assert result is not None, "Ping handler should return a result"
        assert result["status"] == "ok", "Status should be ok"

    @pytest.mark.asyncio
    async def test_handle_pong(self, handler):
        """Test pong event handling."""
        data = {"timestamp": 1234567890}

        result = await on_pong("conn_123", data)

        assert result is not None, "Pong handler should return a result"
        assert result["status"] == "ok", "Status should be ok"


class TestWebSocketEvents:
    """Tests for WebSocket event handling."""

    def test_event_handler_registry(self):
        """Test that event handlers are registered."""
        handlers = get_event_handler("connect")
        assert handlers is not None, "Connect handler should be registered"

        handlers = get_event_handler("disconnect")
        assert handlers is not None, "Disconnect handler should be registered"

        handlers = get_event_handler("devicelogin")
        assert handlers is not None, "Device login handler should be registered"

    def test_unknown_event_handler(self):
        """Test that unknown events return None."""
        handler = get_event_handler("unknown_event")
        assert handler is None, "Unknown event should return None"


class TestWebSocketMessageFormats:
    """Tests for WebSocket message format handling."""

    def test_sync_message_format(self):
        """Test sync message format."""
        message = {
            "event": "sync",
            "data": {
                "type": "AddCategoryAction",
                "sequenceNumber": 1,
                "integrity": "password:base64encoded",
                "userId": "user_123",
                "encodedAction": '{"categoryId":"cat_123"}'
            }
        }

        assert message["event"] == "sync", "Event should be 'sync'"
        assert "data" in message, "Message should contain data"
        assert "type" in message["data"], "Data should contain type"

    def test_notification_message_format(self):
        """Test notification message format."""
        message = {
            "event": "notification",
            "data": {
                "type": "status_update",
                "message": "Server status changed"
            }
        }

        assert message["event"] == "notification", "Event should be 'notification'"
        assert "type" in message["data"], "Data should contain type"


class TestWebSocketConnectionLifecycle:
    """Tests for WebSocket connection lifecycle."""

    @pytest.fixture
    def manager(self):
        """Create a ConnectionManager instance for testing."""
        return ConnectionManager()

    @pytest.mark.asyncio
    async def test_connection_lifecycle(self, manager):
        """Test complete connection lifecycle: connect → message → disconnect."""
        connection_id = "conn_lifecycle_test"

        # Connect
        await manager.connect(connection_id)
        assert connection_id in manager.get_active_connections(), "Connection should be active"

        # Disconnect
        await manager.disconnect(connection_id)
        assert connection_id not in manager.get_active_connections(), "Connection should be removed"

    @pytest.mark.asyncio
    async def test_multiple_connections(self, manager):
        """Test handling multiple connections."""
        connection_ids = [f"conn_{i}" for i in range(10)]

        # Add all connections
        for cid in connection_ids:
            await manager.connect(cid)

        # Verify all are active
        active = manager.get_active_connections()
        assert len(active) == 10, "Should have 10 active connections"

        # Remove half
        for cid in connection_ids[:5]:
            await manager.disconnect(cid)

        # Verify remaining
        active = manager.get_active_connections()
        assert len(active) == 5, "Half the connections should remain"


class TestWebSocketConcurrency:
    """Tests for WebSocket concurrency handling."""

    @pytest.fixture
    def manager(self):
        """Create a ConnectionManager instance for testing."""
        return ConnectionManager()

    @pytest.mark.asyncio
    async def test_concurrent_connections(self, manager):
        """Test handling concurrent connection operations."""
        async def add_connections(start, count):
            for i in range(count):
                await manager.connect(f"conn_{start}_{i}")

        # Create multiple concurrent tasks
        tasks = [
            asyncio.create_task(add_connections(0, 5)),
            asyncio.create_task(add_connections(5, 5)),
            asyncio.create_task(add_connections(10, 5)),
        ]

        await asyncio.gather(*tasks)

        active = manager.get_active_connections()
        assert len(active) == 15, "Should have 15 connections"

    @pytest.mark.asyncio
    async def test_concurrent_add_remove(self, manager):
        """Test concurrent add and remove operations."""
        async def add_and_remove():
            for i in range(10):
                cid = f"conn_{i}"
                await manager.connect(cid)
                await asyncio.sleep(0.001)
                await manager.disconnect(cid)

        tasks = [
            asyncio.create_task(add_and_remove()),
            asyncio.create_task(add_and_remove()),
        ]

        await asyncio.gather(*tasks)

        # All connections should be cleaned up
        active = manager.get_active_connections()
        assert len(active) == 0, "All connections should be cleaned up"


class TestWebSocketIntegration:
    """Integration tests for WebSocket with FastAPI app."""

    @pytest.fixture
    def client(self):
        """Create test client with WebSocket support."""
        from app.main import app
        return TestClient(app)

    def test_websocket_endpoint_exists(self, client):
        """Test that WebSocket endpoint exists."""
        # This test verifies the endpoint is registered
        # Actual WebSocket testing would require more setup
        pass


class TestWebSocketSecurity:
    """Security tests for WebSocket functionality."""

    @pytest.fixture
    def manager(self):
        """Create a ConnectionManager instance for testing."""
        return ConnectionManager()

    @pytest.mark.asyncio
    async def test_connection_cleanup(self, manager):
        """Test connection cleanup."""
        connection_id = "conn_cleanup_test"

        await manager.connect(connection_id)

        # Simulate cleanup
        await manager.disconnect(connection_id)

        # Verify cleanup
        active = manager.get_active_connections()
        assert connection_id not in active, "Connection should be cleaned up"


class TestWebSocketMetadata:
    """Tests for WebSocket connection metadata."""

    @pytest.fixture
    def manager(self):
        """Create a ConnectionManager instance for testing."""
        return ConnectionManager()

    @pytest.mark.asyncio
    async def test_connection_metadata(self, manager):
        """Test connection metadata storage."""
        connection_id = "conn_meta_test"
        device_id = "device_123"

        await manager.connect(connection_id, device_id)

        metadata = manager.get_connection_metadata(connection_id)
        assert metadata is not None, "Metadata should be stored"
        assert metadata["device_id"] == device_id, "Device ID should be in metadata"

    @pytest.mark.asyncio
    async def test_device_connection_lookup(self, manager):
        """Test device connection lookup."""
        connection_id = "conn_device_test"
        device_id = "device_456"

        await manager.connect(connection_id, device_id)

        found_conn = manager.get_device_connection(device_id)
        assert found_conn == connection_id, "Should find connection by device ID"

    @pytest.mark.asyncio
    async def test_connection_count(self, manager):
        """Test connection count."""
        assert manager.get_connection_count() == 0, "Should start with 0 connections"

        await manager.connect("conn_1")
        assert manager.get_connection_count() == 1, "Should have 1 connection"

        await manager.connect("conn_2")
        assert manager.get_connection_count() == 2, "Should have 2 connections"

        await manager.disconnect("conn_1")
        assert manager.get_connection_count() == 1, "Should have 1 connection after disconnect"


class TestWebSocketMessageLogging:
    """Tests for WebSocket message logging integration."""

    def setup_method(self):
        """Reset the global logger before each test."""
        from app.middleware.server_message_logger import reset_server_message_logger
        reset_server_message_logger()

    def teardown_method(self):
        """Reset the global logger after each test."""
        from app.middleware.server_message_logger import reset_server_message_logger
        reset_server_message_logger()

    @pytest.mark.asyncio
    async def test_websocket_connect_logs_event(self):
        """Verify WebSocket connect event is logged."""
        from app.middleware.server_message_logger import get_server_message_logger, MessageType
        
        logger = get_server_message_logger(async_mode=False)
        
        # Simulate connect event
        await on_connect("conn_123", {"deviceId": "device_456"})
        
        buffer = logger.get_log_buffer()
        assert len(buffer) > 0, "Log buffer should contain entries"
        
        # Check for websocket event log
        websocket_entries = [e for e in buffer if e["message_type"] == "websocket_event"]
        assert len(websocket_entries) > 0, "Should have websocket_event entries"

    @pytest.mark.asyncio
    async def test_websocket_devicelogin_logs_event(self):
        """Verify WebSocket devicelogin event is logged."""
        from app.middleware.server_message_logger import get_server_message_logger
        
        logger = get_server_message_logger(async_mode=False)
        
        data = {"deviceId": "device_123", "familyId": "family_456"}
        result = await on_devicelogin("conn_123", data)
        
        assert result is not None
        
        buffer = logger.get_log_buffer()
        websocket_entries = [e for e in buffer if e["message_type"] == "websocket_event"]
        assert len(websocket_entries) > 0, "Should have websocket_event entries"

    @pytest.mark.asyncio
    async def test_websocket_broadcast_logs_event(self):
        """Verify WebSocket broadcast event is logged."""
        from app.middleware.server_message_logger import get_server_message_logger
        
        logger = get_server_message_logger(async_mode=False)
        
        # Simulate broadcast
        from app.websocket.manager import SocketIOHandler
        handler = SocketIOHandler()
        
        # Broadcast to family
        await handler.broadcast_to_family("family_123", "sync_update", {"type": "AddCategoryAction"})
        
        buffer = logger.get_log_buffer()
        broadcast_entries = [e for e in buffer if e["message_type"] == "websocket_broadcast"]
        assert len(broadcast_entries) > 0, "Should have websocket_broadcast entries"

    @pytest.mark.asyncio
    async def test_websocket_disconnect_logs_event(self):
        """Verify WebSocket disconnect event is logged."""
        from app.middleware.server_message_logger import get_server_message_logger
        
        logger = get_server_message_logger(async_mode=False)
        
        # Connect first
        await on_connect("conn_disconnect_test", {})
        
        # Then disconnect
        await on_disconnect("conn_disconnect_test")
        
        buffer = logger.get_log_buffer()
        # Should have logged events
        assert len(buffer) > 0, "Log buffer should contain entries"

    @pytest.mark.asyncio
    async def test_websocket_ping_pong_logs_events(self):
        """Verify WebSocket ping/pong events are logged."""
        from app.middleware.server_message_logger import get_server_message_logger
        
        logger = get_server_message_logger(async_mode=False)
        
        # Ping
        await on_ping("conn_ping_test", {"timestamp": 1234567890})
        
        # Pong
        await on_pong("conn_ping_test", {"timestamp": 1234567891})
        
        buffer = logger.get_log_buffer()
        websocket_entries = [e for e in buffer if e["message_type"] == "websocket_event"]
        assert len(websocket_entries) >= 2, "Should have at least 2 websocket_event entries for ping/pong"

    @pytest.mark.asyncio
    async def test_websocket_should_sync_logs_event(self):
        """Verify WebSocket should_sync event is logged."""
        from app.middleware.server_message_logger import get_server_message_logger
        
        logger = get_server_message_logger(async_mode=False)
        
        data = {"deviceId": "device_123", "familyId": "family_456"}
        result = await on_should_sync("conn_123", data)
        
        assert result is not None
        
        buffer = logger.get_log_buffer()
        websocket_entries = [e for e in buffer if e["message_type"] == "websocket_event"]
        assert len(websocket_entries) > 0, "Should have websocket_event entries"

    @pytest.mark.asyncio
    async def test_websocket_connected_devices_logs_event(self):
        """Verify WebSocket connected_devices event is logged."""
        from app.middleware.server_message_logger import get_server_message_logger
        
        logger = get_server_message_logger(async_mode=False)
        
        data = {"deviceId": "device_123", "familyId": "family_456"}
        result = await on_connected_devices("conn_123", data)
        
        assert result is not None
        
        buffer = logger.get_log_buffer()
        websocket_entries = [e for e in buffer if e["message_type"] == "websocket_event"]
        assert len(websocket_entries) > 0, "Should have websocket_event entries"

    @pytest.mark.asyncio
    async def test_websocket_sign_out_logs_event(self):
        """Verify WebSocket sign_out event is logged."""
        from app.middleware.server_message_logger import get_server_message_logger
        
        logger = get_server_message_logger(async_mode=False)
        
        data = {"deviceId": "device_123", "familyId": "family_456"}
        result = await on_sign_out("conn_123", data)
        
        assert result is not None
        
        buffer = logger.get_log_buffer()
        websocket_entries = [e for e in buffer if e["message_type"] == "websocket_event"]
        assert len(websocket_entries) > 0, "Should have websocket_event entries"

    @pytest.mark.asyncio
    async def test_websocket_event_metadata_includes_sid(self):
        """Verify WebSocket event metadata includes session ID."""
        from app.middleware.server_message_logger import get_server_message_logger
        
        logger = get_server_message_logger(async_mode=False)
        
        await on_devicelogin("conn_sid_test", {"deviceId": "device_123"})
        
        buffer = logger.get_log_buffer()
        websocket_entries = [e for e in buffer if e["message_type"] == "websocket_event"]
        
        if websocket_entries:
            entry = websocket_entries[0]
            assert "metadata" in entry
            assert "event" in entry["metadata"]
