"""Unit tests for server message logging functionality.

This module tests the ServerMessageLogger class and related functionality including:
- Message transmission logging
- Timestamp accuracy
- Message content formatting
- Metadata handling
- Error scenarios
- Log output consistency with expected formats and data integrity
"""

import json
import logging
import os
import re
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from app.middleware.server_message_logger import (
    ServerMessageLogger,
    MessageType,
    get_server_message_logger,
    reset_server_message_logger,
)


class TestServerMessageLogger:
    """Tests for ServerMessageLogger class."""

    def setup_method(self):
        """Reset the global logger before each test."""
        reset_server_message_logger()

    def teardown_method(self):
        """Reset the global logger after each test."""
        reset_server_message_logger()

    def test_logger_initialization(self):
        """Verify ServerMessageLogger initializes correctly."""
        logger = ServerMessageLogger()
        assert logger is not None
        assert logger.log_file_path is None

    def test_logger_initialization_with_path(self):
        """Verify ServerMessageLogger initializes with log file path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = os.path.join(tmpdir, "test.log")
            logger = ServerMessageLogger(log_file_path=log_path)
            assert logger.log_file_path == log_path

    def test_log_message_basic(self, tmp_path):
        """Verify basic message logging works correctly."""
        log_file = tmp_path / "test.log"
        logger = ServerMessageLogger(log_file_path=str(log_file), async_mode=False)
        
        logger.log_message(
            message_type=MessageType.API_RESPONSE,
            content={"status": "ok"},
            metadata={"path": "/test"}
        )
        
        # Verify log file was created and contains the message
        assert log_file.exists()
        content = log_file.read_text()
        assert "[SERVER]" in content
        assert "api_response" in content

    def test_log_message_with_timestamp(self, tmp_path):
        """Verify log messages include accurate timestamps."""
        log_file = tmp_path / "test.log"
        logger = ServerMessageLogger(log_file_path=str(log_file), async_mode=False)
        
        before_time = datetime.now()
        logger.log_message(
            message_type=MessageType.API_RESPONSE,
            content={"status": "ok"}
        )
        after_time = datetime.now()
        
        content = log_file.read_text()
        
        # Extract timestamp from log
        timestamp_match = re.search(r'\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d{3})\]', content)
        assert timestamp_match, "Timestamp not found in log"
        
        log_timestamp_str = timestamp_match.group(1)
        # Parse with millisecond precision (3 digits)
        log_timestamp = datetime.strptime(log_timestamp_str, "%Y-%m-%d %H:%M:%S.%f")
        
        # Convert before/after times to millisecond precision for comparison
        before_ms = before_time.replace(microsecond=(before_time.microsecond // 1000) * 1000)
        after_ms = after_time.replace(microsecond=(after_time.microsecond // 1000) * 1000)
        
        # Verify timestamp is within the expected window (at millisecond precision)
        assert before_ms <= log_timestamp <= after_ms

    def test_log_message_with_metadata(self, tmp_path):
        """Verify log messages include metadata correctly."""
        log_file = tmp_path / "test.log"
        logger = ServerMessageLogger(log_file_path=str(log_file), async_mode=False)
        
        metadata = {
            "path": "/test",
            "method": "POST",
            "status_code": 200,
            "duration_ms": 45
        }
        
        logger.log_message(
            message_type=MessageType.API_RESPONSE,
            content={"result": "success"},
            metadata=metadata
        )
        
        content = log_file.read_text()
        
        # Verify metadata is in the log
        assert "path" in content
        assert "/test" in content
        assert "status_code" in content
        assert "200" in content

    def test_log_message_with_request_id(self, tmp_path):
        """Verify log messages include request ID for correlation."""
        log_file = tmp_path / "test.log"
        logger = ServerMessageLogger(log_file_path=str(log_file), async_mode=False)
        
        request_id = "abc12345"
        
        logger.log_message(
            message_type=MessageType.API_RESPONSE,
            content={"status": "ok"},
            request_id=request_id
        )
        
        content = log_file.read_text()
        assert request_id in content

    def test_log_message_with_connection_id(self, tmp_path):
        """Verify log messages include connection ID for WebSocket messages."""
        log_file = tmp_path / "test.log"
        logger = ServerMessageLogger(log_file_path=str(log_file), async_mode=False)
        
        connection_id = "conn_1234567890abcdef"
        
        logger.log_message(
            message_type=MessageType.WEBSOCKET_EVENT,
            content={"status": "ok"},
            connection_id=connection_id
        )
        
        content = log_file.read_text()
        # Connection ID should be truncated in the log (JSON format)
        # The truncation happens in metadata, then JSON serialization
        assert "conn_123" in content

    def test_log_message_with_error(self, tmp_path):
        """Verify log messages include error information when present."""
        log_file = tmp_path / "test.log"
        logger = ServerMessageLogger(log_file_path=str(log_file), async_mode=False)
        
        error = ValueError("Test error")
        
        logger.log_message(
            message_type=MessageType.API_RESPONSE,
            content={"error": "failed"},
            error=error
        )
        
        content = log_file.read_text()
        assert "ValueError" in content
        assert "Test error" in content

    def test_log_message_content_serialization(self, tmp_path):
        """Verify message content is serialized correctly."""
        log_file = tmp_path / "test.log"
        logger = ServerMessageLogger(log_file_path=str(log_file), async_mode=False)
        
        content = {
            "user": {
                "id": 12345,
                "email": "test@example.com"
            },
            "action": "update_profile"
        }
        
        logger.log_message(
            message_type=MessageType.API_RESPONSE,
            content=content
        )
        
        log_content = log_file.read_text()
        assert "12345" in log_content
        assert "test@example.com" in log_content
        assert "update_profile" in log_content


class TestServerMessageLoggerAPIResponse:
    """Tests for API response logging."""

    def setup_method(self):
        """Reset the global logger before each test."""
        reset_server_message_logger()

    def teardown_method(self):
        """Reset the global logger after each test."""
        reset_server_message_logger()

    def test_log_api_response(self, tmp_path):
        """Verify API response logging works correctly."""
        log_file = tmp_path / "test.log"
        logger = ServerMessageLogger(log_file_path=str(log_file), async_mode=False)
        
        logger.log_api_response(
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

    def test_log_api_response_with_json_content(self, tmp_path):
        """Verify API response with JSON content is logged correctly."""
        log_file = tmp_path / "test.log"
        logger = ServerMessageLogger(log_file_path=str(log_file), async_mode=False)
        
        response_data = {
            "users": [
                {"id": 1, "name": "User 1"},
                {"id": 2, "name": "User 2"}
            ],
            "total": 2
        }
        
        logger.log_api_response(
            content=response_data,
            status_code=200
        )
        
        content = log_file.read_text()
        assert "users" in content
        assert "User 1" in content

    def test_log_api_response_error_status(self, tmp_path):
        """Verify API error responses are logged correctly."""
        log_file = tmp_path / "test.log"
        logger = ServerMessageLogger(log_file_path=str(log_file), async_mode=False)
        
        logger.log_api_response(
            content={"error": "Not found"},
            status_code=404,
            path="/notfound"
        )
        
        content = log_file.read_text()
        assert "404" in content


class TestServerMessageLoggerWebSocket:
    """Tests for WebSocket message logging."""

    def setup_method(self):
        """Reset the global logger before each test."""
        reset_server_message_logger()

    def teardown_method(self):
        """Reset the global logger after each test."""
        reset_server_message_logger()

    def test_log_websocket_event(self, tmp_path):
        """Verify WebSocket event logging works correctly."""
        log_file = tmp_path / "test.log"
        logger = ServerMessageLogger(log_file_path=str(log_file), async_mode=False)
        
        logger.log_websocket_event(
            event="devicelogin",
            data={"status": "ok", "message": "Device logged in"},
            sid="socket_12345678"
        )
        
        content = log_file.read_text()
        assert "[SERVER]" in content
        assert "websocket_event" in content
        assert "devicelogin" in content

    def test_log_websocket_broadcast(self, tmp_path):
        """Verify WebSocket broadcast logging works correctly."""
        log_file = tmp_path / "test.log"
        logger = ServerMessageLogger(log_file_path=str(log_file), async_mode=False)
        
        logger.log_websocket_broadcast(
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

    def test_log_websocket_event_with_connection_id(self, tmp_path):
        """Verify WebSocket event logging includes connection ID."""
        log_file = tmp_path / "test.log"
        logger = ServerMessageLogger(log_file_path=str(log_file), async_mode=False)
        
        logger.log_websocket_event(
            event="ping",
            data={"status": "ok"},
            connection_id="conn_abcdef123456"
        )
        
        content = log_file.read_text()
        # Connection ID should be truncated in the log (JSON format)
        # The truncation happens in metadata, then JSON serialization
        assert "conn_abc" in content


class TestServerMessageLoggerSync:
    """Tests for sync action logging."""

    def setup_method(self):
        """Reset the global logger before each test."""
        reset_server_message_logger()

    def teardown_method(self):
        """Reset the global logger after each test."""
        reset_server_message_logger()

    def test_log_sync_action(self, tmp_path):
        """Verify sync action logging works correctly."""
        log_file = tmp_path / "test.log"
        logger = ServerMessageLogger(log_file_path=str(log_file), async_mode=False)
        
        logger.log_sync_action(
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

    def test_log_sync_action_minimal(self, tmp_path):
        """Verify sync action logging with minimal data."""
        log_file = tmp_path / "test.log"
        logger = ServerMessageLogger(log_file_path=str(log_file), async_mode=False)
        
        logger.log_sync_action(
            action_type="DeleteUserAction",
            action_data={"userId": "user_123"}
        )
        
        content = log_file.read_text()
        assert "DeleteUserAction" in content


class TestServerMessageLoggerAuth:
    """Tests for auth event logging."""

    def setup_method(self):
        """Reset the global logger before each test."""
        reset_server_message_logger()

    def teardown_method(self):
        """Reset the global logger after each test."""
        reset_server_message_logger()

    def test_log_auth_event(self, tmp_path):
        """Verify auth event logging works correctly."""
        log_file = tmp_path / "test.log"
        logger = ServerMessageLogger(log_file_path=str(log_file), async_mode=False)
        
        logger.log_auth_event(
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
        # JSON serializes boolean as lowercase
        assert "true" in content

    def test_log_auth_event_failure(self, tmp_path):
        """Verify auth failure event logging works correctly."""
        log_file = tmp_path / "test.log"
        logger = ServerMessageLogger(log_file_path=str(log_file), async_mode=False)
        
        logger.log_auth_event(
            event_type="login_failed",
            user_id="user_123",
            success=False
        )
        
        content = log_file.read_text()
        assert "login_failed" in content
        # JSON serializes boolean as lowercase
        assert "false" in content


class TestServerMessageLoggerSystem:
    """Tests for system event logging."""

    def setup_method(self):
        """Reset the global logger before each test."""
        reset_server_message_logger()

    def teardown_method(self):
        """Reset the global logger after each test."""
        reset_server_message_logger()

    def test_log_system_event(self, tmp_path):
        """Verify system event logging works correctly."""
        log_file = tmp_path / "test.log"
        logger = ServerMessageLogger(log_file_path=str(log_file), async_mode=False)
        
        logger.log_system_event(
            event="server_startup",
            details={"version": "1.0.0", "port": 8080}
        )
        
        content = log_file.read_text()
        assert "[SERVER]" in content
        assert "system_event" in content
        assert "server_startup" in content

    def test_log_system_event_no_details(self, tmp_path):
        """Verify system event logging without details."""
        log_file = tmp_path / "test.log"
        logger = ServerMessageLogger(log_file_path=str(log_file), async_mode=False)
        
        logger.log_system_event(event="health_check")
        
        content = log_file.read_text()
        assert "health_check" in content


class TestServerMessageLoggerFormat:
    """Tests for log format verification."""

    def setup_method(self):
        """Reset the global logger before each test."""
        reset_server_message_logger()

    def teardown_method(self):
        """Reset the global logger after each test."""
        reset_server_message_logger()

    def test_log_format_structure(self, tmp_path):
        """Verify log entry follows the expected format structure."""
        log_file = tmp_path / "test.log"
        logger = ServerMessageLogger(log_file_path=str(log_file), async_mode=False)
        
        logger.log_message(
            message_type=MessageType.API_RESPONSE,
            content={"status": "ok"},
            metadata={"path": "/test"}
        )
        
        content = log_file.read_text().strip()
        
        # Expected format: [timestamp] [SERVER] message_type - metadata - content
        pattern = r'\[\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d{3}\] \[SERVER\] \w+ - .+ - .+'
        assert re.match(pattern, content), f"Log entry doesn't match expected format: {content}"

    def test_timestamp_format_is_iso_like(self, tmp_path):
        """Verify timestamp follows ISO-like format with milliseconds."""
        log_file = tmp_path / "test.log"
        logger = ServerMessageLogger(log_file_path=str(log_file), async_mode=False)
        
        logger.log_message(
            message_type=MessageType.API_RESPONSE,
            content={"status": "ok"}
        )
        
        content = log_file.read_text()
        
        # Extract timestamp
        match = re.search(r'\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d{3})\]', content)
        assert match, f"Timestamp not found in log. Content: {content}"
        
        timestamp_str = match.group(1)
        
        # Verify format: YYYY-MM-DD HH:MM:SS.mmm
        assert len(timestamp_str) == 23, f"Timestamp length incorrect: {timestamp_str}"
        assert timestamp_str[4] == '-', f"Date separator missing: {timestamp_str}"
        assert timestamp_str[7] == '-', f"Date separator missing: {timestamp_str}"
        assert timestamp_str[10] == ' ', f"Date/time separator missing: {timestamp_str}"
        assert timestamp_str[13] == ':', f"Time separator missing: {timestamp_str}"
        assert timestamp_str[16] == ':', f"Time separator missing: {timestamp_str}"
        assert timestamp_str[19] == '.', f"Millisecond separator missing: {timestamp_str}"

    def test_timestamps_are_sequential(self, tmp_path):
        """Verify timestamps are sequential for multiple messages."""
        log_file = tmp_path / "test.log"
        logger = ServerMessageLogger(log_file_path=str(log_file), async_mode=False)
        
        for i in range(3):
            logger.log_message(
                message_type=MessageType.API_RESPONSE,
                content={"id": i}
            )
        
        content = log_file.read_text()
        
        # Extract all timestamps
        matches = re.findall(r'\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d{3})\]', content)
        
        assert len(matches) == 3, f"Expected 3 timestamps, got {len(matches)}"
        
        # Verify timestamps are in ascending order
        for i in range(len(matches) - 1):
            assert matches[i] <= matches[i + 1], \
                f"Timestamps not sequential: {matches[i]} > {matches[i + 1]}"


class TestServerMessageLoggerEdgeCases:
    """Tests for edge cases in server message logging."""

    def setup_method(self):
        """Reset the global logger before each test."""
        reset_server_message_logger()

    def teardown_method(self):
        """Reset the global logger after each test."""
        reset_server_message_logger()

    def test_log_empty_content(self, tmp_path):
        """Verify empty content is handled correctly."""
        log_file = tmp_path / "test.log"
        logger = ServerMessageLogger(log_file_path=str(log_file), async_mode=False)
        
        logger.log_message(
            message_type=MessageType.API_RESPONSE,
            content=None
        )
        
        content = log_file.read_text()
        assert "[SERVER]" in content

    def test_log_empty_dict_content(self, tmp_path):
        """Verify empty dict content is handled correctly."""
        log_file = tmp_path / "test.log"
        logger = ServerMessageLogger(log_file_path=str(log_file), async_mode=False)
        
        logger.log_message(
            message_type=MessageType.API_RESPONSE,
            content={}
        )
        
        content = log_file.read_text()
        assert "[SERVER]" in content

    def test_log_special_characters_in_content(self, tmp_path):
        """Verify special characters in content are logged correctly."""
        log_file = tmp_path / "test.log"
        logger = ServerMessageLogger(log_file_path=str(log_file), async_mode=False)
        
        content = {
            "message": "Hello! @#$%^&*()_+-=[]{}|;':\",./<>?",
            "unicode": "你好世界 🌍"
        }
        
        logger.log_message(
            message_type=MessageType.API_RESPONSE,
            content=content
        )
        
        log_content = log_file.read_text(encoding="utf-8")
        assert "Hello!" in log_content or "你好世界" in log_content

    def test_log_large_content(self, tmp_path):
        """Verify large content is logged (truncated if necessary)."""
        log_file = tmp_path / "test.log"
        logger = ServerMessageLogger(log_file_path=str(log_file), async_mode=False)
        
        # Create a large content
        large_content = {
            "items": [{"id": i, "data": "x" * 100} for i in range(100)]
        }
        
        logger.log_message(
            message_type=MessageType.API_RESPONSE,
            content=large_content
        )
        
        content = log_file.read_text()
        assert "[SERVER]" in content
        assert "items" in content

    def test_log_nested_dict_content(self, tmp_path):
        """Verify nested dict content is logged correctly."""
        log_file = tmp_path / "test.log"
        logger = ServerMessageLogger(log_file_path=str(log_file), async_mode=False)
        
        content = {
            "level1": {
                "level2": {
                    "level3": {
                        "value": "deep"
                    }
                }
            }
        }
        
        logger.log_message(
            message_type=MessageType.API_RESPONSE,
            content=content
        )
        
        log_content = log_file.read_text()
        assert "deep" in log_content

    def test_log_list_content(self, tmp_path):
        """Verify list content is logged correctly."""
        log_file = tmp_path / "test.log"
        logger = ServerMessageLogger(log_file_path=str(log_file), async_mode=False)
        
        content = ["item1", "item2", "item3"]
        
        logger.log_message(
            message_type=MessageType.API_RESPONSE,
            content=content
        )
        
        log_content = log_file.read_text()
        assert "item1" in log_content
        assert "item2" in log_content


class TestServerMessageLoggerGlobalInstance:
    """Tests for global server message logger instance."""

    def setup_method(self):
        """Reset the global logger before each test."""
        reset_server_message_logger()

    def teardown_method(self):
        """Reset the global logger after each test."""
        reset_server_message_logger()

    def test_get_server_message_logger_returns_instance(self):
        """Verify get_server_message_logger returns a ServerMessageLogger instance."""
        logger = get_server_message_logger()
        assert isinstance(logger, ServerMessageLogger)

    def test_get_server_message_logger_returns_same_instance(self):
        """Verify get_server_message_logger returns the same instance."""
        logger1 = get_server_message_logger()
        logger2 = get_server_message_logger()
        assert logger1 is logger2

    def test_reset_server_message_logger(self):
        """Verify reset_server_message_logger creates a new instance."""
        logger1 = get_server_message_logger()
        reset_server_message_logger()
        logger2 = get_server_message_logger()
        assert logger1 is not logger2


class TestMessageType:
    """Tests for MessageType enum."""

    def test_message_type_values(self):
        """Verify MessageType enum has expected values."""
        assert MessageType.API_RESPONSE.value == "api_response"
        assert MessageType.WEBSOCKET_EVENT.value == "websocket_event"
        assert MessageType.WEBSOCKET_BROADCAST.value == "websocket_broadcast"
        assert MessageType.SYNC_ACTION.value == "sync_action"
        assert MessageType.AUTH_EVENT.value == "auth_event"
        assert MessageType.SYSTEM_EVENT.value == "system_event"

    def test_message_type_iteration(self):
        """Verify MessageType enum can be iterated."""
        types = list(MessageType)
        assert len(types) == 6


class TestServerMessageLoggerSanitization:
    """Tests for sensitive data sanitization in ServerMessageLogger."""

    def setup_method(self):
        """Reset the global logger before each test."""
        reset_server_message_logger()

    def teardown_method(self):
        """Reset the global logger after each test."""
        reset_server_message_logger()

    def test_sensitive_password_sanitized(self, tmp_path):
        """Verify password field is sanitized in log output."""
        log_file = tmp_path / "test.log"
        logger = ServerMessageLogger(log_file_path=str(log_file), async_mode=False, sanitize=True)
        
        logger.log_message(
            message_type=MessageType.API_RESPONSE,
            content={"password": "secret123", "email": "test@example.com"}
        )
        
        content = log_file.read_text()
        assert "***REDACTED***" in content
        assert "secret123" not in content
        assert "test@example.com" in content

    def test_sensitive_token_sanitized(self, tmp_path):
        """Verify token fields are sanitized in log output."""
        log_file = tmp_path / "test.log"
        logger = ServerMessageLogger(log_file_path=str(log_file), async_mode=False, sanitize=True)
        
        logger.log_message(
            message_type=MessageType.WEBSOCKET_EVENT,
            content={"token": "my_token_123", "data": "visible"}
        )
        
        content = log_file.read_text()
        assert "***REDACTED***" in content
        assert "my_token_123" not in content
        assert "visible" in content

    def test_nested_sensitive_data_sanitized(self, tmp_path):
        """Verify nested sensitive data is sanitized."""
        log_file = tmp_path / "test.log"
        logger = ServerMessageLogger(log_file_path=str(log_file), async_mode=False, sanitize=True)
        
        logger.log_message(
            message_type=MessageType.SYNC_ACTION,
            content={
                "user": {
                    "password": "nested_secret",
                    "name": "John"
                },
                "device": {
                    "token": "device_token",
                    "id": "device_123"
                }
            }
        )
        
        content = log_file.read_text()
        assert "***REDACTED***" in content
        assert "nested_secret" not in content
        assert "device_token" not in content
        assert "John" in content
        assert "device_123" in content

    def test_sanitization_disabled(self, tmp_path):
        """Verify sanitization can be disabled."""
        log_file = tmp_path / "test.log"
        logger = ServerMessageLogger(log_file_path=str(log_file), async_mode=False, sanitize=False)
        
        logger.log_message(
            message_type=MessageType.API_RESPONSE,
            content={"password": "secret123"}
        )
        
        content = log_file.read_text()
        assert "secret123" in content
        assert "***REDACTED***" not in content

    def test_all_sensitive_keys_sanitized(self, tmp_path):
        """Verify all defined sensitive keys are sanitized."""
        log_file = tmp_path / "test.log"
        logger = ServerMessageLogger(log_file_path=str(log_file), async_mode=False, sanitize=True)
        
        logger.log_message(
            message_type=MessageType.API_RESPONSE,
            content={
                "password": "secret123",
                "password_hash": "hash123",
                "second_hash": "second123",
                "token": "token123",
                "access_token": "access123",
                "refresh_token": "refresh123",
                "device_auth_token": "device123",
                "mail_auth_token": "mail123",
                "mail_login_token": "login123",
                "secret_key": "secret123",
                "jwt_secret": "jwt123",
                "api_key": "api123",
                "private_key": "private123",
                "signature": "sig123",
                "encrypted": "enc123",
                "parentPassword": "parent123",
                "identityToken": "identity123"
            }
        )
        
        content = log_file.read_text()
        # All sensitive values should be redacted
        assert "secret123" not in content
        assert "hash123" not in content
        assert "token123" not in content
        assert "access123" not in content
        assert "refresh123" not in content
        assert "device123" not in content
        assert "mail123" not in content
        assert "login123" not in content
        assert "secret123" not in content
        assert "jwt123" not in content
        assert "api123" not in content
        assert "private123" not in content
        assert "sig123" not in content
        assert "enc123" not in content
        assert "parent123" not in content
        assert "identity123" not in content


class TestServerMessageLoggerAsyncMode:
    """Tests for async logging mode in ServerMessageLogger."""

    def setup_method(self):
        """Reset the global logger before each test."""
        reset_server_message_logger()

    def teardown_method(self):
        """Reset the global logger after each test."""
        reset_server_message_logger()

    def test_async_mode_initialization(self, tmp_path):
        """Verify async mode initializes correctly."""
        log_file = tmp_path / "test.log"
        logger = ServerMessageLogger(log_file_path=str(log_file), async_mode=True)
        
        assert logger.async_mode is True
        assert logger._log_queue is not None
        assert logger._log_thread is not None
        assert logger._log_thread.is_alive()

    def test_sync_mode_initialization(self, tmp_path):
        """Verify sync mode initializes correctly."""
        log_file = tmp_path / "test.log"
        logger = ServerMessageLogger(log_file_path=str(log_file), async_mode=False)
        
        assert logger.async_mode is False
        assert logger._log_queue is None
        assert logger._log_thread is None

    def test_async_mode_writes_to_file(self, tmp_path):
        """Verify async mode writes messages to file."""
        log_file = tmp_path / "test.log"
        logger = ServerMessageLogger(log_file_path=str(log_file), async_mode=True)
        
        logger.log_message(
            message_type=MessageType.API_RESPONSE,
            content={"status": "ok"}
        )
        
        # Flush to ensure message is written
        logger.flush()
        
        content = log_file.read_text()
        assert "[SERVER]" in content
        assert "api_response" in content

    def test_flush_waits_for_queue(self, tmp_path):
        """Verify flush waits for all queued messages."""
        log_file = tmp_path / "test.log"
        logger = ServerMessageLogger(log_file_path=str(log_file), async_mode=True)
        
        # Log multiple messages
        for i in range(5):
            logger.log_message(
                message_type=MessageType.API_RESPONSE,
                content={"id": i}
            )
        
        # Flush should wait for all messages
        logger.flush()
        
        content = log_file.read_text()
        lines = [l for l in content.strip().split('\n') if l.strip()]
        assert len(lines) == 5

    def test_stop_async_logging(self, tmp_path):
        """Verify stop_async_logging stops the background thread."""
        log_file = tmp_path / "test.log"
        logger = ServerMessageLogger(log_file_path=str(log_file), async_mode=True)
        
        assert logger._log_thread is not None
        assert logger._log_thread.is_alive()
        
        logger.stop_async_logging()
        
        assert logger._log_thread is None


class TestServerMessageLoggerBuffer:
    """Tests for log buffer functionality in ServerMessageLogger."""

    def setup_method(self):
        """Reset the global logger before each test."""
        reset_server_message_logger()

    def teardown_method(self):
        """Reset the global logger after each test."""
        reset_server_message_logger()

    def test_log_buffer_populated(self, tmp_path):
        """Verify log buffer is populated with entries."""
        log_file = tmp_path / "test.log"
        logger = ServerMessageLogger(log_file_path=str(log_file), async_mode=False)
        
        logger.log_message(
            message_type=MessageType.API_RESPONSE,
            content={"status": "ok"},
            metadata={"path": "/test"}
        )
        
        buffer = logger.get_log_buffer()
        assert len(buffer) == 1
        assert buffer[0]["message_type"] == "api_response"
        assert buffer[0]["content"]["status"] == "ok"

    def test_log_buffer_multiple_entries(self, tmp_path):
        """Verify log buffer handles multiple entries."""
        log_file = tmp_path / "test.log"
        logger = ServerMessageLogger(log_file_path=str(log_file), async_mode=False)
        
        for i in range(10):
            logger.log_message(
                message_type=MessageType.API_RESPONSE,
                content={"id": i}
            )
        
        buffer = logger.get_log_buffer()
        assert len(buffer) == 10

    def test_log_buffer_max_size(self, tmp_path):
        """Verify log buffer respects max size limit."""
        log_file = tmp_path / "test.log"
        max_size = 5
        logger = ServerMessageLogger(
            log_file_path=str(log_file),
            async_mode=False,
            max_buffer_size=max_size
        )
        
        # Log more than max_size entries
        for i in range(10):
            logger.log_message(
                message_type=MessageType.API_RESPONSE,
                content={"id": i}
            )
        
        buffer = logger.get_log_buffer()
        assert len(buffer) == max_size
        # Should keep the most recent entries
        assert buffer[0]["content"]["id"] == 5
        assert buffer[-1]["content"]["id"] == 9

    def test_log_buffer_clear(self, tmp_path):
        """Verify log buffer can be cleared."""
        log_file = tmp_path / "test.log"
        logger = ServerMessageLogger(log_file_path=str(log_file), async_mode=False)
        
        logger.log_message(
            message_type=MessageType.API_RESPONSE,
            content={"status": "ok"}
        )
        
        assert len(logger.get_log_buffer()) == 1
        
        logger.clear_log_buffer()
        
        assert len(logger.get_log_buffer()) == 0

    def test_log_buffer_structured_entry(self, tmp_path):
        """Verify log buffer entries have correct structure."""
        log_file = tmp_path / "test.log"
        logger = ServerMessageLogger(log_file_path=str(log_file), async_mode=False)
        
        logger.log_message(
            message_type=MessageType.SYNC_ACTION,
            content={"action": "test"},
            metadata={"path": "/test"},
            request_id="req_123",
            duration_ms=50
        )
        
        buffer = logger.get_log_buffer()
        entry = buffer[0]
        
        assert "timestamp" in entry
        assert "message_type" in entry
        assert "metadata" in entry
        assert "content" in entry
        assert "log_message" in entry
        assert entry["message_type"] == "sync_action"
        assert entry["metadata"]["path"] == "/test"
        assert entry["metadata"]["request_id"] == "req_123"
        assert entry["metadata"]["duration_ms"] == 50


class TestServerMessageLoggerLogLevel:
    """Tests for log level configuration in ServerMessageLogger."""

    def setup_method(self):
        """Reset the global logger before each test."""
        reset_server_message_logger()

    def teardown_method(self):
        """Reset the global logger after each test."""
        reset_server_message_logger()

    def test_default_log_level(self, tmp_path):
        """Verify default log level is INFO."""
        log_file = tmp_path / "test.log"
        logger = ServerMessageLogger(log_file_path=str(log_file), async_mode=False)
        
        assert logger.log_level == 20  # logging.INFO = 20

    def test_custom_log_level(self, tmp_path):
        """Verify custom log level is set correctly."""
        log_file = tmp_path / "test.log"
        logger = ServerMessageLogger(
            log_file_path=str(log_file),
            log_level=logging.DEBUG
        )
        
        assert logger.log_level == 10  # logging.DEBUG = 10

    def test_log_level_warning(self, tmp_path):
        """Verify WARNING log level works correctly."""
        log_file = tmp_path / "test.log"
        logger = ServerMessageLogger(
            log_file_path=str(log_file),
            log_level=logging.WARNING,
            async_mode=False
        )
        
        logger.log_message(
            message_type=MessageType.API_RESPONSE,
            content={"status": "ok"}
        )
        
        content = log_file.read_text()
        assert "[SERVER]" in content

    def test_log_level_error(self, tmp_path):
        """Verify ERROR log level works correctly."""
        log_file = tmp_path / "test.log"
        logger = ServerMessageLogger(
            log_file_path=str(log_file),
            log_level=logging.ERROR,
            async_mode=False
        )
        
        logger.log_message(
            message_type=MessageType.API_RESPONSE,
            content={"status": "ok"}
        )
        
        content = log_file.read_text()
        assert "[SERVER]" in content
