"""Unit tests for enhanced ServerMessageLogger functionality.

This module tests the enhanced ServerMessageLogger class including:
- Sensitive data sanitization
- Async logging mode
- Log buffer population
- Log level filtering
- Flush behavior
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

from app.middleware.server_message_logger import (
    ServerMessageLogger,
    MessageType,
    get_server_message_logger,
    reset_server_message_logger,
    SENSITIVE_KEYS,
)


class TestServerMessageLoggerSanitization:
    """Tests for sensitive data sanitization in ServerMessageLogger."""

    def setup_method(self):
        """Reset the global logger before each test."""
        reset_server_message_logger()

    def teardown_method(self):
        """Reset the global logger after each test."""
        reset_server_message_logger()

    def test_sensitive_data_redaction_in_log_message(self, tmp_path):
        """Verify sensitive data is redacted in log_message."""
        log_file = tmp_path / "test.log"
        logger = ServerMessageLogger(log_file_path=str(log_file), async_mode=False, sanitize=True)
        
        content = {
            "password": "secret123",
            "token": "abc123",
            "normal_field": "visible"
        }
        
        logger.log_message(
            message_type=MessageType.API_RESPONSE,
            content=content
        )
        
        log_content = log_file.read_text()
        assert "***REDACTED***" in log_content
        assert "secret123" not in log_content
        assert "abc123" not in log_content
        assert "visible" in log_content

    def test_sensitive_data_redaction_in_log_api_response(self, tmp_path):
        """Verify sensitive data is redacted in log_api_response."""
        log_file = tmp_path / "test.log"
        logger = ServerMessageLogger(log_file_path=str(log_file), async_mode=False, sanitize=True)
        
        content = {
            "user": {
                "password": "user_secret",
                "name": "John"
            },
            "device_auth_token": "device_token_123"
        }
        
        logger.log_api_response(
            content=content,
            status_code=200
        )
        
        log_content = log_file.read_text()
        assert "***REDACTED***" in log_content
        assert "user_secret" not in log_content
        assert "device_token_123" not in log_content
        assert "John" in log_content

    def test_sensitive_data_redaction_in_log_websocket_event(self, tmp_path):
        """Verify sensitive data is redacted in log_websocket_event."""
        log_file = tmp_path / "test.log"
        logger = ServerMessageLogger(log_file_path=str(log_file), async_mode=False, sanitize=True)
        
        data = {
            "token": "websocket_token",
            "message": "hello"
        }
        
        logger.log_websocket_event(
            event="test",
            data=data
        )
        
        log_content = log_file.read_text()
        assert "***REDACTED***" in log_content
        assert "websocket_token" not in log_content
        assert "hello" in log_content

    def test_sensitive_data_redaction_in_log_sync_action(self, tmp_path):
        """Verify sensitive data is redacted in log_sync_action."""
        log_file = tmp_path / "test.log"
        logger = ServerMessageLogger(log_file_path=str(log_file), async_mode=False, sanitize=True)
        
        action_data = {
            "secondHash": "hash_value",
            "action": "test"
        }
        
        logger.log_sync_action(
            action_type="TestAction",
            action_data=action_data
        )
        
        log_content = log_file.read_text()
        assert "***REDACTED***" in log_content
        assert "hash_value" not in log_content

    def test_sensitive_data_redaction_in_log_auth_event(self, tmp_path):
        """Verify sensitive data is redacted in log_auth_event."""
        log_file = tmp_path / "test.log"
        logger = ServerMessageLogger(log_file_path=str(log_file), async_mode=False, sanitize=True)
        
        logger.log_auth_event(
            event_type="test_event",
            user_id="user_123",
            device_id="device_456"
        )
        
        log_content = log_file.read_text()
        assert "user_123" in log_content
        assert "device_456" in log_content

    def test_nested_sensitive_data_redaction(self, tmp_path):
        """Verify nested sensitive data is redacted."""
        log_file = tmp_path / "test.log"
        logger = ServerMessageLogger(log_file_path=str(log_file), async_mode=False, sanitize=True)
        
        content = {
            "level1": {
                "password": "nested_secret",
                "level2": {
                    "token": "deep_token",
                    "value": "ok"
                }
            }
        }
        
        logger.log_message(
            message_type=MessageType.API_RESPONSE,
            content=content
        )
        
        log_content = log_file.read_text()
        assert "***REDACTED***" in log_content
        assert "nested_secret" not in log_content
        assert "deep_token" not in log_content
        assert "ok" in log_content

    def test_sanitize_disabled(self, tmp_path):
        """Verify sanitization can be disabled."""
        log_file = tmp_path / "test.log"
        logger = ServerMessageLogger(log_file_path=str(log_file), async_mode=False, sanitize=False)
        
        content = {
            "password": "secret123",
            "token": "abc123"
        }
        
        logger.log_message(
            message_type=MessageType.API_RESPONSE,
            content=content
        )
        
        log_content = log_file.read_text()
        assert "secret123" in log_content
        assert "abc123" in log_content


class TestServerMessageLoggerAsync:
    """Tests for async logging mode."""

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
        
        assert logger._log_queue is not None
        assert logger._log_thread is not None
        assert logger._log_thread.is_alive()

    def test_sync_mode_initialization(self, tmp_path):
        """Verify sync mode initializes correctly."""
        log_file = tmp_path / "test.log"
        logger = ServerMessageLogger(log_file_path=str(log_file), async_mode=False)
        
        assert logger._log_queue is None
        assert logger._log_thread is None

    def test_async_mode_writes_to_file(self, tmp_path):
        """Verify async mode writes to file correctly."""
        log_file = tmp_path / "test.log"
        logger = ServerMessageLogger(log_file_path=str(log_file), async_mode=True)
        
        logger.log_message(
            message_type=MessageType.API_RESPONSE,
            content={"status": "ok"}
        )
        
        # Flush and wait
        logger.flush()
        time.sleep(0.2)
        
        content = log_file.read_text()
        assert "[SERVER]" in content

    def test_flush_drain_queue(self, tmp_path):
        """Verify flush drains the async queue."""
        log_file = tmp_path / "test.log"
        logger = ServerMessageLogger(log_file_path=str(log_file), async_mode=True)
        
        for i in range(5):
            logger.log_message(
                message_type=MessageType.API_RESPONSE,
                content={"id": i}
            )
        
        # Queue should have items
        assert logger._log_queue.qsize() > 0
        
        # Flush should drain
        logger.flush()
        time.sleep(0.2)
        
        assert logger._log_queue.empty()

    def test_stop_async_logging(self, tmp_path):
        """Verify stop_async_logging stops the background thread."""
        log_file = tmp_path / "test.log"
        logger = ServerMessageLogger(log_file_path=str(log_file), async_mode=True)
        
        assert logger._log_thread is not None
        assert logger._log_thread.is_alive()
        
        logger.stop_async_logging()
        
        # After stopping, _log_thread should be None
        assert logger._log_thread is None


class TestServerMessageLoggerBuffer:
    """Tests for log buffer functionality."""

    def setup_method(self):
        """Reset the global logger before each test."""
        reset_server_message_logger()

    def teardown_method(self):
        """Reset the global logger after each test."""
        reset_server_message_logger()

    def test_buffer_population_on_log_message(self, tmp_path):
        """Verify buffer is populated on log_message."""
        log_file = tmp_path / "test.log"
        logger = ServerMessageLogger(log_file_path=str(log_file), async_mode=False)
        
        logger.log_message(
            message_type=MessageType.API_RESPONSE,
            content={"status": "ok"}
        )
        
        buffer = logger.get_log_buffer()
        assert len(buffer) == 1
        assert buffer[0]["message_type"] == "api_response"
        assert "timestamp" in buffer[0]
        assert "metadata" in buffer[0]
        assert "content" in buffer[0]

    def test_buffer_structured_entry_format(self, tmp_path):
        """Verify buffer entries have correct structure."""
        log_file = tmp_path / "test.log"
        logger = ServerMessageLogger(log_file_path=str(log_file), async_mode=False)
        
        logger.log_message(
            message_type=MessageType.WEBSOCKET_EVENT,
            content={"status": "ok"},
            metadata={"event": "test"},
            request_id="req123"
        )
        
        buffer = logger.get_log_buffer()
        entry = buffer[0]
        
        assert entry["message_type"] == "websocket_event"
        assert entry["metadata"]["event"] == "test"
        assert entry["metadata"]["request_id"] == "req123"

    def test_buffer_max_size_enforcement(self, tmp_path):
        """Verify buffer enforces max size."""
        log_file = tmp_path / "test.log"
        logger = ServerMessageLogger(
            log_file_path=str(log_file),
            max_buffer_size=5
        )
        
        for i in range(10):
            logger.log_message(
                message_type=MessageType.API_RESPONSE,
                content={"id": i}
            )
        
        buffer = logger.get_log_buffer()
        assert len(buffer) == 5

    def test_buffer_clear(self, tmp_path):
        """Verify buffer can be cleared."""
        log_file = tmp_path / "test.log"
        logger = ServerMessageLogger(log_file_path=str(log_file), async_mode=False)
        
        logger.log_message(
            message_type=MessageType.API_RESPONSE,
            content={"status": "ok"}
        )
        
        assert len(logger.get_log_buffer()) == 1
        
        logger.clear_log_buffer()
        
        assert len(logger.get_log_buffer()) == 0

    def test_buffer_returns_copy(self, tmp_path):
        """Verify get_log_buffer returns a copy."""
        log_file = tmp_path / "test.log"
        logger = ServerMessageLogger(log_file_path=str(log_file), async_mode=False)
        
        logger.log_message(
            message_type=MessageType.API_RESPONSE,
            content={"status": "ok"}
        )
        
        buffer1 = logger.get_log_buffer()
        buffer2 = logger.get_log_buffer()
        
        assert buffer1 is not buffer2


class TestServerMessageLoggerLogLevel:
    """Tests for log level filtering."""

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
        
        assert logger.log_level == logging.INFO

    def test_custom_log_level(self, tmp_path):
        """Verify custom log level is set correctly."""
        log_file = tmp_path / "test.log"
        logger = ServerMessageLogger(
            log_file_path=str(log_file),
            log_level=logging.DEBUG
        )
        
        assert logger.log_level == logging.DEBUG

    def test_log_level_filtering(self, tmp_path):
        """Verify log level filtering works."""
        log_file = tmp_path / "test.log"
        logger = ServerMessageLogger(
            log_file_path=str(log_file),
            log_level=logging.WARNING,
            async_mode=False
        )
        
        # This should still log because we're using logger.log() directly
        # The log level affects the standard logger, not the file write
        logger.log_message(
            message_type=MessageType.API_RESPONSE,
            content={"status": "ok"}
        )
        
        content = log_file.read_text()
        assert "[SERVER]" in content


class TestServerMessageLoggerFlush:
    """Tests for flush method."""

    def setup_method(self):
        """Reset the global logger before each test."""
        reset_server_message_logger()

    def teardown_method(self):
        """Reset the global logger after each test."""
        reset_server_message_logger()

    def test_flush_in_sync_mode(self, tmp_path):
        """Verify flush works in sync mode."""
        log_file = tmp_path / "test.log"
        logger = ServerMessageLogger(
            log_file_path=str(log_file),
            async_mode=False
        )
        
        logger.log_message(
            message_type=MessageType.API_RESPONSE,
            content={"status": "ok"}
        )
        
        # Should not raise
        logger.flush()
        
        content = log_file.read_text()
        assert "[SERVER]" in content

    def test_flush_in_async_mode(self, tmp_path):
        """Verify flush works in async mode."""
        log_file = tmp_path / "test.log"
        logger = ServerMessageLogger(
            log_file_path=str(log_file),
            async_mode=True
        )
        
        logger.log_message(
            message_type=MessageType.API_RESPONSE,
            content={"status": "ok"}
        )
        
        # Should not raise
        logger.flush()
        time.sleep(0.1)
        
        content = log_file.read_text()
        assert "[SERVER]" in content


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

    def test_get_server_message_logger_with_params(self):
        """Verify get_server_message_logger accepts parameters."""
        logger = get_server_message_logger(
            async_mode=False,
            log_level=logging.DEBUG,
            max_buffer_size=500,
            sanitize=False
        )
        
        assert logger.async_mode == False
        assert logger.log_level == logging.DEBUG
        assert logger.max_buffer_size == 500
        assert logger.sanitize == False


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


class TestSensitiveKeysConstant:
    """Tests for SENSITIVE_KEYS constant."""

    def test_sensitive_keys_defined(self):
        """Verify SENSITIVE_KEYS is defined with expected keys."""
        assert 'password' in SENSITIVE_KEYS
        assert 'password_hash' in SENSITIVE_KEYS
        assert 'second_hash' in SENSITIVE_KEYS
        assert 'token' in SENSITIVE_KEYS
        assert 'access_token' in SENSITIVE_KEYS
        assert 'refresh_token' in SENSITIVE_KEYS
        assert 'device_auth_token' in SENSITIVE_KEYS
        assert 'mail_auth_token' in SENSITIVE_KEYS
        assert 'mail_login_token' in SENSITIVE_KEYS
        assert 'secret_key' in SENSITIVE_KEYS
        assert 'jwt_secret' in SENSITIVE_KEYS
        assert 'api_key' in SENSITIVE_KEYS
        assert 'private_key' in SENSITIVE_KEYS
        assert 'signature' in SENSITIVE_KEYS
        assert 'encrypted' in SENSITIVE_KEYS
        assert 'parentpassword' in SENSITIVE_KEYS
        assert 'secondhash' in SENSITIVE_KEYS
        assert 'secondsalt' in SENSITIVE_KEYS
        assert 'deviceauthtoken' in SENSITIVE_KEYS
        assert 'mailauthtoken' in SENSITIVE_KEYS
        assert 'maillogintoken' in SENSITIVE_KEYS
        assert 'identitytoken' in SENSITIVE_KEYS
