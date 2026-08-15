"""Unit tests for MessageSentLogger.

This module tests the MessageSentLogger class and related functionality including:
- Logger creation and initialization
- Sensitive data sanitization
- API reply logging
- WebSocket reply logging
- Broadcast logging
- Sync reply logging
- Auth reply logging
- Async mode behavior
- Log buffer functionality
- Edge cases
"""

import json
import logging
import os
import re
import tempfile
import time
from datetime import datetime
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from app.middleware.message_sent_logger import (
    MessageSentLogger,
    get_message_sent_logger,
    reset_message_sent_logger,
    SENSITIVE_KEYS,
)
from app.middleware.server_message_logger import (
    ServerMessageLogger,
    MessageType,
    reset_server_message_logger,
)


class TestMessageSentLoggerInitialization:
    """Tests for MessageSentLogger initialization."""

    def setup_method(self):
        """Reset the global logger before each test."""
        reset_server_message_logger()
        reset_message_sent_logger()

    def teardown_method(self):
        """Reset the global logger after each test."""
        reset_server_message_logger()
        reset_message_sent_logger()

    def test_logger_creation(self):
        """Verify MessageSentLogger creates correctly."""
        server_logger = ServerMessageLogger()
        msg_logger = MessageSentLogger(server_logger)
        assert msg_logger is not None
        assert msg_logger._server_logger is server_logger

    def test_get_message_sent_logger_returns_instance(self):
        """Verify get_message_sent_logger returns a MessageSentLogger instance."""
        server_logger = ServerMessageLogger()
        msg_logger = get_message_sent_logger(server_logger)
        assert isinstance(msg_logger, MessageSentLogger)

    def test_get_message_sent_logger_returns_same_instance(self):
        """Verify get_message_sent_logger returns the same instance."""
        server_logger = ServerMessageLogger()
        msg_logger1 = get_message_sent_logger(server_logger)
        msg_logger2 = get_message_sent_logger(server_logger)
        assert msg_logger1 is msg_logger2

    def test_get_message_sent_logger_uses_server_logger(self):
        """Verify get_message_sent_logger uses the provided server logger."""
        server_logger = ServerMessageLogger()
        msg_logger = get_message_sent_logger(server_logger)
        assert msg_logger._server_logger is server_logger

    def test_reset_message_sent_logger(self):
        """Verify reset_message_sent_logger creates a new instance."""
        server_logger = ServerMessageLogger()
        msg_logger1 = get_message_sent_logger(server_logger)
        reset_message_sent_logger()
        msg_logger2 = get_message_sent_logger(server_logger)
        assert msg_logger1 is not msg_logger2


class TestMessageSentLoggerSanitization:
    """Tests for sensitive data sanitization."""

    def setup_method(self):
        """Reset the global logger before each test."""
        reset_server_message_logger()
        reset_message_sent_logger()

    def teardown_method(self):
        """Reset the global logger after each test."""
        reset_server_message_logger()
        reset_message_sent_logger()

    def test_sensitive_key_redaction(self, tmp_path):
        """Verify sensitive keys are redacted in log output."""
        log_file = tmp_path / "test.log"
        server_logger = ServerMessageLogger(log_file_path=str(log_file), async_mode=False, sanitize=True)
        msg_logger = MessageSentLogger(server_logger)
        
        content = {
            "password": "secret123",
            "token": "abc123",
            "normal_field": "visible"
        }
        
        msg_logger.log_outgoing_message(
            message_type=MessageType.API_RESPONSE,
            content=content
        )
        
        log_content = log_file.read_text()
        assert "***REDACTED***" in log_content
        assert "secret123" not in log_content
        assert "abc123" not in log_content
        assert "visible" in log_content

    def test_nested_dict_sanitization(self, tmp_path):
        """Verify nested dicts are sanitized recursively."""
        log_file = tmp_path / "test.log"
        server_logger = ServerMessageLogger(log_file_path=str(log_file), async_mode=False, sanitize=True)
        msg_logger = MessageSentLogger(server_logger)
        
        content = {
            "user": {
                "password": "secret",
                "name": "John"
            },
            "token": "abc123"
        }
        
        msg_logger.log_outgoing_message(
            message_type=MessageType.API_RESPONSE,
            content=content
        )
        
        log_content = log_file.read_text()
        assert "***REDACTED***" in log_content
        assert "secret" not in log_content
        assert "John" in log_content
        assert "abc123" not in log_content

    def test_long_string_truncation(self, tmp_path):
        """Verify long strings are truncated."""
        log_file = tmp_path / "test.log"
        server_logger = ServerMessageLogger(log_file_path=str(log_file), async_mode=False, sanitize=True)
        msg_logger = MessageSentLogger(server_logger)
        
        long_string = "x" * 1000
        content = {"data": long_string}
        
        msg_logger.log_outgoing_message(
            message_type=MessageType.API_RESPONSE,
            content=content
        )
        
        log_content = log_file.read_text()
        assert "...[truncated]" in log_content

    def test_non_sensitive_data_preserved(self, tmp_path):
        """Verify non-sensitive data is preserved."""
        log_file = tmp_path / "test.log"
        server_logger = ServerMessageLogger(log_file_path=str(log_file), async_mode=False, sanitize=True)
        msg_logger = MessageSentLogger(server_logger)
        
        content = {
            "user_id": "user_123",
            "name": "Test User",
            "email": "test@example.com"
        }
        
        msg_logger.log_outgoing_message(
            message_type=MessageType.API_RESPONSE,
            content=content
        )
        
        log_content = log_file.read_text()
        assert "user_123" in log_content
        assert "Test User" in log_content
        assert "test@example.com" in log_content


class TestMessageSentLoggerAPIReply:
    """Tests for API reply logging."""

    def setup_method(self):
        """Reset the global logger before each test."""
        reset_server_message_logger()
        reset_message_sent_logger()

    def teardown_method(self):
        """Reset the global logger after each test."""
        reset_server_message_logger()
        reset_message_sent_logger()

    def test_log_api_reply(self, tmp_path):
        """Verify API reply logging works correctly."""
        log_file = tmp_path / "test.log"
        server_logger = ServerMessageLogger(log_file_path=str(log_file), async_mode=False)
        msg_logger = MessageSentLogger(server_logger)
        
        msg_logger.log_api_reply(
            content={"status": "ok", "data": {"id": 1}},
            status_code=200,
            request_id="req123",
            path="/test",
            method="POST",
            duration_ms=50
        )
        
        content = log_file.read_text()
        assert "[SERVER]" in content
        assert "api_response" in content
        assert "200" in content
        assert "POST" in content
        assert "/test" in content
        assert "req123" in content

    def test_log_api_reply_error_status(self, tmp_path):
        """Verify API error responses are logged correctly."""
        log_file = tmp_path / "test.log"
        server_logger = ServerMessageLogger(log_file_path=str(log_file), async_mode=False)
        msg_logger = MessageSentLogger(server_logger)
        
        msg_logger.log_api_reply(
            content={"error": "Not found"},
            status_code=404,
            request_id="req456",
            path="/notfound",
            method="GET",
            duration_ms=10
        )
        
        content = log_file.read_text()
        assert "404" in content

    def test_log_api_reply_empty_content(self, tmp_path):
        """Verify API reply with empty content is logged."""
        log_file = tmp_path / "test.log"
        server_logger = ServerMessageLogger(log_file_path=str(log_file), async_mode=False)
        msg_logger = MessageSentLogger(server_logger)
        
        msg_logger.log_api_reply(
            content={},
            status_code=204,
            request_id="req789",
            path="/empty",
            method="DELETE",
            duration_ms=5
        )
        
        content = log_file.read_text()
        assert "[SERVER]" in content


class TestMessageSentLoggerWebSocketReply:
    """Tests for WebSocket reply logging."""

    def setup_method(self):
        """Reset the global logger before each test."""
        reset_server_message_logger()
        reset_message_sent_logger()

    def teardown_method(self):
        """Reset the global logger after each test."""
        reset_server_message_logger()
        reset_message_sent_logger()

    def test_log_websocket_reply(self, tmp_path):
        """Verify WebSocket reply logging works correctly."""
        log_file = tmp_path / "test.log"
        server_logger = ServerMessageLogger(log_file_path=str(log_file), async_mode=False)
        msg_logger = MessageSentLogger(server_logger)
        
        msg_logger.log_websocket_reply(
            event="devicelogin",
            data={"status": "ok", "message": "Device logged in"},
            sid="socket_12345678",
            connection_id="conn_456"
        )
        
        content = log_file.read_text()
        assert "[SERVER]" in content
        assert "websocket_event" in content
        assert "devicelogin" in content

    def test_log_websocket_reply_ping_pong(self, tmp_path):
        """Verify ping/pong events are logged."""
        log_file = tmp_path / "test.log"
        server_logger = ServerMessageLogger(log_file_path=str(log_file), async_mode=False)
        msg_logger = MessageSentLogger(server_logger)
        
        msg_logger.log_websocket_reply(
            event="ping",
            data={"status": "ok", "timestamp": 1234567890},
            sid="socket_123"
        )
        
        content = log_file.read_text()
        assert "ping" in content

    def test_log_websocket_reply_connect_disconnect(self, tmp_path):
        """Verify connect/disconnect events are logged."""
        log_file = tmp_path / "test.log"
        server_logger = ServerMessageLogger(log_file_path=str(log_file), async_mode=False)
        msg_logger = MessageSentLogger(server_logger)
        
        msg_logger.log_websocket_reply(
            event="connect",
            data={"status": "connected"},
            sid="socket_456"
        )
        
        content = log_file.read_text()
        assert "connect" in content


class TestMessageSentLoggerBroadcast:
    """Tests for broadcast logging."""

    def setup_method(self):
        """Reset the global logger before each test."""
        reset_server_message_logger()
        reset_message_sent_logger()

    def teardown_method(self):
        """Reset the global logger after each test."""
        reset_server_message_logger()
        reset_message_sent_logger()

    def test_log_broadcast(self, tmp_path):
        """Verify broadcast logging works correctly."""
        log_file = tmp_path / "test.log"
        server_logger = ServerMessageLogger(log_file_path=str(log_file), async_mode=False)
        msg_logger = MessageSentLogger(server_logger)
        
        msg_logger.log_broadcast(
            event="sync_update",
            data={"type": "AddCategoryAction", "data": {"categoryId": "cat_123"}},
            family_id="family_456",
            notified_count=3
        )
        
        content = log_file.read_text()
        assert "[SERVER]" in content
        assert "websocket_broadcast" in content
        assert "sync_update" in content
        assert "broadcast" in content
        assert "family_456" in content
        assert "3" in content

    def test_log_broadcast_empty(self, tmp_path):
        """Verify empty broadcast is logged."""
        log_file = tmp_path / "test.log"
        server_logger = ServerMessageLogger(log_file_path=str(log_file), async_mode=False)
        msg_logger = MessageSentLogger(server_logger)
        
        msg_logger.log_broadcast(
            event="notification",
            data={},
            family_id="family_789",
            notified_count=0
        )
        
        content = log_file.read_text()
        assert "notification" in content


class TestMessageSentLoggerSyncReply:
    """Tests for sync reply logging."""

    def setup_method(self):
        """Reset the global logger before each test."""
        reset_server_message_logger()
        reset_message_sent_logger()

    def teardown_method(self):
        """Reset the global logger after each test."""
        reset_server_message_logger()
        reset_message_sent_logger()

    def test_log_sync_reply(self, tmp_path):
        """Verify sync reply logging works correctly."""
        log_file = tmp_path / "test.log"
        server_logger = ServerMessageLogger(log_file_path=str(log_file), async_mode=False)
        msg_logger = MessageSentLogger(server_logger)
        
        msg_logger.log_sync_reply(
            action_type="AddCategoryAction",
            action_data={"categoryId": "cat_123", "name": "Test Category"},
            sequence_number=1,
            user_id="user_456",
            family_id="family_789"
        )
        
        content = log_file.read_text()
        assert "[SERVER]" in content
        assert "sync_action" in content
        assert "AddCategoryAction" in content
        assert "1" in content

    def test_log_sync_reply_minimal(self, tmp_path):
        """Verify sync reply with minimal data is logged."""
        log_file = tmp_path / "test.log"
        server_logger = ServerMessageLogger(log_file_path=str(log_file), async_mode=False)
        msg_logger = MessageSentLogger(server_logger)
        
        msg_logger.log_sync_reply(
            action_type="DeleteUserAction",
            action_data={"userId": "user_123"}
        )
        
        content = log_file.read_text()
        assert "DeleteUserAction" in content


class TestMessageSentLoggerAuthReply:
    """Tests for auth reply logging."""

    def setup_method(self):
        """Reset the global logger before each test."""
        reset_server_message_logger()
        reset_message_sent_logger()

    def teardown_method(self):
        """Reset the global logger after each test."""
        reset_server_message_logger()
        reset_message_sent_logger()

    def test_log_auth_reply(self, tmp_path):
        """Verify auth reply logging works correctly."""
        log_file = tmp_path / "test.log"
        server_logger = ServerMessageLogger(log_file_path=str(log_file), async_mode=False)
        msg_logger = MessageSentLogger(server_logger)
        
        msg_logger.log_auth_reply(
            event_type="login_success",
            user_id="user_123",
            device_id="device_456",
            family_id="family_789",
            success=True
        )
        
        content = log_file.read_text()
        assert "[SERVER]" in content
        assert "auth_event" in content
        assert "login_success" in content
        assert "user_123" in content
        assert "true" in content

    def test_log_auth_reply_failure(self, tmp_path):
        """Verify auth failure reply is logged correctly."""
        log_file = tmp_path / "test.log"
        server_logger = ServerMessageLogger(log_file_path=str(log_file), async_mode=False)
        msg_logger = MessageSentLogger(server_logger)
        
        msg_logger.log_auth_reply(
            event_type="login_failed",
            user_id="user_123",
            success=False
        )
        
        content = log_file.read_text()
        assert "login_failed" in content
        assert "false" in content


class TestMessageSentLoggerAsyncMode:
    """Tests for async logging mode."""

    def setup_method(self):
        """Reset the global logger before each test."""
        reset_server_message_logger()
        reset_message_sent_logger()

    def teardown_method(self):
        """Reset the global logger after each test."""
        reset_server_message_logger()
        reset_message_sent_logger()

    def test_async_mode_initialization(self, tmp_path):
        """Verify async mode initializes correctly."""
        log_file = tmp_path / "test.log"
        server_logger = ServerMessageLogger(
            log_file_path=str(log_file),
            async_mode=True
        )
        msg_logger = MessageSentLogger(server_logger)
        
        assert server_logger._log_queue is not None
        assert server_logger._log_thread is not None

    def test_sync_mode_initialization(self, tmp_path):
        """Verify sync mode initializes correctly."""
        log_file = tmp_path / "test.log"
        server_logger = ServerMessageLogger(
            log_file_path=str(log_file),
            async_mode=False
        )
        msg_logger = MessageSentLogger(server_logger)
        
        assert server_logger._log_queue is None
        assert server_logger._log_thread is None

    def test_flush_behavior(self, tmp_path):
        """Verify flush method works correctly."""
        log_file = tmp_path / "test.log"
        server_logger = ServerMessageLogger(
            log_file_path=str(log_file),
            async_mode=True
        )
        msg_logger = MessageSentLogger(server_logger)
        
        msg_logger.log_api_reply(
            content={"status": "ok"},
            status_code=200,
            request_id="req1",
            path="/test",
            method="GET",
            duration_ms=10
        )
        
        # Flush should not raise
        msg_logger.flush()
        
        # Wait a bit for async write
        time.sleep(0.2)
        
        content = log_file.read_text()
        assert "[SERVER]" in content


class TestMessageSentLoggerBuffer:
    """Tests for log buffer functionality."""

    def setup_method(self):
        """Reset the global logger before each test."""
        reset_server_message_logger()
        reset_message_sent_logger()

    def teardown_method(self):
        """Reset the global logger after each test."""
        reset_server_message_logger()
        reset_message_sent_logger()

    def test_buffer_population(self, tmp_path):
        """Verify buffer is populated with log entries."""
        log_file = tmp_path / "test.log"
        server_logger = ServerMessageLogger(
            log_file_path=str(log_file),
            max_buffer_size=100
        )
        msg_logger = MessageSentLogger(server_logger)
        
        msg_logger.log_api_reply(
            content={"status": "ok"},
            status_code=200,
            request_id="req1",
            path="/test",
            method="GET",
            duration_ms=10
        )
        
        buffer = msg_logger.get_log_buffer()
        assert len(buffer) == 1
        assert buffer[0]["message_type"] == "api_response"

    def test_buffer_max_size_enforcement(self, tmp_path):
        """Verify buffer enforces max size."""
        log_file = tmp_path / "test.log"
        server_logger = ServerMessageLogger(
            log_file_path=str(log_file),
            max_buffer_size=5
        )
        msg_logger = MessageSentLogger(server_logger)
        
        for i in range(10):
            msg_logger.log_api_reply(
                content={"status": "ok", "id": i},
                status_code=200,
                request_id=f"req{i}",
                path="/test",
                method="GET",
                duration_ms=10
            )
        
        buffer = msg_logger.get_log_buffer()
        assert len(buffer) <= 5

    def test_buffer_clear(self, tmp_path):
        """Verify buffer can be cleared."""
        log_file = tmp_path / "test.log"
        server_logger = ServerMessageLogger(log_file_path=str(log_file), async_mode=False)
        msg_logger = MessageSentLogger(server_logger)
        
        msg_logger.log_api_reply(
            content={"status": "ok"},
            status_code=200,
            request_id="req1",
            path="/test",
            method="GET",
            duration_ms=10
        )
        
        assert len(msg_logger.get_log_buffer()) == 1
        
        msg_logger.clear_log_buffer()
        
        assert len(msg_logger.get_log_buffer()) == 0


class TestMessageSentLoggerEdgeCases:
    """Tests for edge cases."""

    def setup_method(self):
        """Reset the global logger before each test."""
        reset_server_message_logger()
        reset_message_sent_logger()

    def teardown_method(self):
        """Reset the global logger after each test."""
        reset_server_message_logger()
        reset_message_sent_logger()

    def test_none_content(self, tmp_path):
        """Verify None content is handled correctly."""
        log_file = tmp_path / "test.log"
        server_logger = ServerMessageLogger(log_file_path=str(log_file), async_mode=False)
        msg_logger = MessageSentLogger(server_logger)
        
        msg_logger.log_outgoing_message(
            message_type=MessageType.API_RESPONSE,
            content=None
        )
        
        content = log_file.read_text()
        assert "[SERVER]" in content

    def test_empty_dict_content(self, tmp_path):
        """Verify empty dict content is handled correctly."""
        log_file = tmp_path / "test.log"
        server_logger = ServerMessageLogger(log_file_path=str(log_file), async_mode=False)
        msg_logger = MessageSentLogger(server_logger)
        
        msg_logger.log_outgoing_message(
            message_type=MessageType.API_RESPONSE,
            content={}
        )
        
        content = log_file.read_text()
        assert "[SERVER]" in content

    def test_special_characters_in_content(self, tmp_path):
        """Verify special characters in content are logged correctly."""
        log_file = tmp_path / "test.log"
        server_logger = ServerMessageLogger(log_file_path=str(log_file), async_mode=False)
        msg_logger = MessageSentLogger(server_logger)
        
        content = {
            "message": "Hello! @#$%^&*()_+-=[]{}|;':\",./<>?",
            "unicode": "你好世界 🌍"
        }
        
        msg_logger.log_outgoing_message(
            message_type=MessageType.API_RESPONSE,
            content=content
        )
        
        log_content = log_file.read_text(encoding="utf-8")
        assert "Hello!" in log_content or "你好世界" in log_content

    def test_large_content(self, tmp_path):
        """Verify large content is logged (truncated if necessary)."""
        log_file = tmp_path / "test.log"
        server_logger = ServerMessageLogger(log_file_path=str(log_file), async_mode=False)
        msg_logger = MessageSentLogger(server_logger)
        
        large_content = {
            "items": [{"id": i, "data": "x" * 100} for i in range(100)]
        }
        
        msg_logger.log_outgoing_message(
            message_type=MessageType.API_RESPONSE,
            content=large_content
        )
        
        content = log_file.read_text()
        assert "[SERVER]" in content
        assert "items" in content

    def test_nested_structures(self, tmp_path):
        """Verify nested structures are logged correctly."""
        log_file = tmp_path / "test.log"
        server_logger = ServerMessageLogger(log_file_path=str(log_file), async_mode=False)
        msg_logger = MessageSentLogger(server_logger)
        
        content = {
            "level1": {
                "level2": {
                    "level3": {
                        "value": "deep"
                    }
                }
            }
        }
        
        msg_logger.log_outgoing_message(
            message_type=MessageType.API_RESPONSE,
            content=content
        )
        
        log_content = log_file.read_text()
        assert "deep" in log_content

    def test_list_content(self, tmp_path):
        """Verify list content is logged correctly."""
        log_file = tmp_path / "test.log"
        server_logger = ServerMessageLogger(log_file_path=str(log_file), async_mode=False)
        msg_logger = MessageSentLogger(server_logger)
        
        content = ["item1", "item2", "item3"]
        
        msg_logger.log_outgoing_message(
            message_type=MessageType.API_RESPONSE,
            content=content
        )
        
        log_content = log_file.read_text()
        assert "item1" in log_content
        assert "item2" in log_content


class TestSensitiveKeysConstant:
    """Tests for SENSITIVE_KEYS constant."""

    def test_sensitive_keys_defined(self):
        """Verify SENSITIVE_KEYS is defined with expected keys."""
        assert 'password' in SENSITIVE_KEYS
        assert 'token' in SENSITIVE_KEYS
        assert 'device_auth_token' in SENSITIVE_KEYS
        assert 'mail_auth_token' in SENSITIVE_KEYS
        assert 'secondHash' in SENSITIVE_KEYS

    def test_sensitive_keys_case_insensitive(self, tmp_path):
        """Verify sensitive keys are matched case-insensitively."""
        log_file = tmp_path / "test.log"
        server_logger = ServerMessageLogger(log_file_path=str(log_file), async_mode=False, sanitize=True)
        msg_logger = MessageSentLogger(server_logger)
        
        content = {
            "PASSWORD": "secret1",  # uppercase
            "Token": "secret2",       # mixed case
            "NORMAL": "visible"
        }
        
        msg_logger.log_outgoing_message(
            message_type=MessageType.API_RESPONSE,
            content=content
        )
        
        log_content = log_file.read_text()
        assert "***REDACTED***" in log_content
        assert "visible" in log_content
