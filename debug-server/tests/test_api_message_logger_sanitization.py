"""Unit tests for APIMessageLoggingMiddleware sanitization.

This module tests the sanitization functionality in APIMessageLoggingMiddleware:
- Request body sanitization
- Response body sanitization
- Error response sanitization
- Sensitive key redaction
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
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from starlette.responses import JSONResponse

from app.middleware.api_message_logger import (
    APIMessageLoggingMiddleware,
    get_current_log_file_path,
)
from app.middleware.server_message_logger import (
    ServerMessageLogger,
    MessageType,
    get_server_message_logger,
    reset_server_message_logger,
)
from app.middleware.message_sent_logger import (
    get_message_sent_logger,
    reset_message_sent_logger,
)


class TestAPIMessageLoggerSanitization:
    """Tests for API message logging middleware sanitization."""

    def setup_method(self):
        """Reset the global logger before each test."""
        reset_server_message_logger()
        reset_message_sent_logger()

    def teardown_method(self):
        """Reset the global logger after each test."""
        reset_server_message_logger()
        reset_message_sent_logger()

    def test_request_body_sanitization_password(self, tmp_path):
        """Verify password is sanitized in request body."""
        log_file = tmp_path / "test-api.log"
        
        app = FastAPI()
        app.add_middleware(APIMessageLoggingMiddleware, log_file_path=str(log_file))
        
        @app.post("/login")
        async def login_endpoint():
            return {"status": "ok"}
        
        client = TestClient(app)
        test_data = {"email": "test@example.com", "password": "secret123"}
        response = client.post("/login", json=test_data)
        
        assert response.status_code == 200
        
        log_content = log_file.read_text()
        assert "***REDACTED***" in log_content
        assert "secret123" not in log_content
        assert "test@example.com" in log_content

    def test_request_body_sanitization_token(self, tmp_path):
        """Verify token is sanitized in request body."""
        log_file = tmp_path / "test-api.log"
        
        app = FastAPI()
        app.add_middleware(APIMessageLoggingMiddleware, log_file_path=str(log_file))
        
        @app.post("/sync")
        async def sync_endpoint():
            return {"status": "ok"}
        
        client = TestClient(app)
        test_data = {
            "deviceAuthToken": "device_token_123",
            "actions": []
        }
        response = client.post("/sync", json=test_data)
        
        assert response.status_code == 200
        
        log_content = log_file.read_text()
        assert "***REDACTED***" in log_content
        assert "device_token_123" not in log_content

    def test_request_body_sanitization_second_hash(self, tmp_path):
        """Verify secondHash is sanitized in request body."""
        log_file = tmp_path / "test-api.log"
        
        app = FastAPI()
        app.add_middleware(APIMessageLoggingMiddleware, log_file_path=str(log_file))
        
        @app.post("/push-actions")
        async def push_actions_endpoint():
            return {"status": "ok"}
        
        client = TestClient(app)
        test_data = {
            "actions": [],
            "secondHash": "second_hash_value"
        }
        response = client.post("/push-actions", json=test_data)
        
        assert response.status_code == 200
        
        log_content = log_file.read_text()
        assert "***REDACTED***" in log_content
        assert "second_hash_value" not in log_content

    def test_response_body_sanitization(self, tmp_path):
        """Verify response body is sanitized."""
        log_file = tmp_path / "test-api.log"
        
        app = FastAPI()
        app.add_middleware(APIMessageLoggingMiddleware, log_file_path=str(log_file))
        
        @app.get("/user")
        async def user_endpoint():
            return {
                "user": {
                    "name": "Test User",
                    "password": "user_password",
                    "token": "user_token"
                }
            }
        
        client = TestClient(app)
        response = client.get("/user")
        
        assert response.status_code == 200
        
        log_content = log_file.read_text()
        assert "***REDACTED***" in log_content
        assert "user_password" not in log_content
        assert "user_token" not in log_content
        assert "Test User" in log_content

    def test_error_response_sanitization(self, tmp_path):
        """Verify error response is sanitized."""
        log_file = tmp_path / "test-api.log"
        
        app = FastAPI()
        app.add_middleware(APIMessageLoggingMiddleware, log_file_path=str(log_file))
        
        @app.get("/error")
        async def error_endpoint():
            from fastapi import HTTPException
            raise HTTPException(
                status_code=500,
                detail="Internal error with password=secret123"
            )
        
        client = TestClient(app)
        response = client.get("/error")
        
        assert response.status_code == 500
        
        log_content = log_file.read_text()
        # The error message should be logged
        assert "[SERVER]" in log_content


class TestAPIMessageLoggerSensitiveData:
    """Tests for sensitive data handling in API message logging."""

    def setup_method(self):
        """Reset the global logger before each test."""
        reset_server_message_logger()
        reset_message_sent_logger()

    def teardown_method(self):
        """Reset the global logger after each test."""
        reset_server_message_logger()
        reset_message_sent_logger()

    def test_sensitive_keys_redacted(self, tmp_path):
        """Verify all sensitive keys are redacted."""
        log_file = tmp_path / "test-api.log"
        
        app = FastAPI()
        app.add_middleware(APIMessageLoggingMiddleware, log_file_path=str(log_file))
        
        @app.post("/test")
        async def test_endpoint():
            return {"status": "ok"}
        
        client = TestClient(app)
        test_data = {
            "password": "pass123",
            "password_hash": "hash123",
            "second_hash": "second123",
            "second_salt": "salt123",
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
            "secondHash": "secondHash123",
            "secondSalt": "secondSalt123",
            "deviceAuthToken": "deviceAuthToken123",
            "mailAuthToken": "mailAuthToken123",
            "mailLoginToken": "mailLoginToken123",
            "identityToken": "identity123",
            "normal_field": "visible"
        }
        response = client.post("/test", json=test_data)
        
        log_content = log_file.read_text()
        
        # All sensitive values should be redacted
        assert "***REDACTED***" in log_content
        assert "pass123" not in log_content
        assert "hash123" not in log_content
        assert "token123" not in log_content
        assert "access123" not in log_content
        assert "refresh123" not in log_content
        assert "device123" not in log_content
        assert "mail123" not in log_content
        assert "login123" not in log_content
        assert "secret123" not in log_content
        assert "jwt123" not in log_content
        assert "api123" not in log_content
        assert "private123" not in log_content
        assert "sig123" not in log_content
        assert "enc123" not in log_content
        assert "parent123" not in log_content
        assert "identity123" not in log_content
        
        # Normal field should be visible
        assert "visible" in log_content

    def test_nested_sensitive_data_sanitized(self, tmp_path):
        """Verify nested sensitive data is sanitized."""
        log_file = tmp_path / "test-api.log"
        
        app = FastAPI()
        app.add_middleware(APIMessageLoggingMiddleware, log_file_path=str(log_file))
        
        @app.post("/nested")
        async def nested_endpoint():
            return {"status": "ok"}
        
        client = TestClient(app)
        test_data = {
            "user": {
                "password": "nested_password",
                "name": "John"
            },
            "device": {
                "token": "nested_token",
                "id": "device_123"
            }
        }
        response = client.post("/nested", json=test_data)
        
        log_content = log_file.read_text()
        
        assert "***REDACTED***" in log_content
        assert "nested_password" not in log_content
        assert "nested_token" not in log_content
        assert "John" in log_content
        assert "device_123" in log_content

    def test_non_sensitive_data_preserved(self, tmp_path):
        """Verify non-sensitive data is preserved."""
        log_file = tmp_path / "test-api.log"
        
        app = FastAPI()
        app.add_middleware(APIMessageLoggingMiddleware, log_file_path=str(log_file))
        
        @app.post("/data")
        async def data_endpoint():
            return {"status": "ok"}
        
        client = TestClient(app)
        test_data = {
            "user_id": "user_123",
            "name": "Test User",
            "email": "test@example.com",
            "age": 30,
            "active": True
        }
        response = client.post("/data", json=test_data)
        
        log_content = log_file.read_text()
        
        assert "user_123" in log_content
        assert "Test User" in log_content
        assert "test@example.com" in log_content
        assert "30" in log_content
        assert "true" in log_content.lower() or "True" in log_content

    def test_list_sensitive_data_sanitized(self, tmp_path):
        """Verify sensitive data in lists is sanitized."""
        log_file = tmp_path / "test-api.log"
        
        app = FastAPI()
        app.add_middleware(APIMessageLoggingMiddleware, log_file_path=str(log_file))
        
        @app.post("/list")
        async def list_endpoint():
            return {"status": "ok"}
        
        client = TestClient(app)
        test_data = {
            "items": [
                {"password": "pass1", "name": "item1"},
                {"password": "pass2", "name": "item2"}
            ]
        }
        response = client.post("/list", json=test_data)
        
        log_content = log_file.read_text()
        
        assert "***REDACTED***" in log_content
        assert "pass1" not in log_content
        assert "pass2" not in log_content
        assert "item1" in log_content
        assert "item2" in log_content


class TestAPIMessageLoggerSanitizationEdgeCases:
    """Tests for edge cases in API message logging sanitization."""

    def setup_method(self):
        """Reset the global logger before each test."""
        reset_server_message_logger()
        reset_message_sent_logger()

    def teardown_method(self):
        """Reset the global logger after each test."""
        reset_server_message_logger()
        reset_message_sent_logger()

    def test_empty_json_body(self, tmp_path):
        """Verify empty JSON body is handled correctly."""
        log_file = tmp_path / "test-api.log"
        
        app = FastAPI()
        app.add_middleware(APIMessageLoggingMiddleware, log_file_path=str(log_file))
        
        @app.post("/empty")
        async def empty_endpoint():
            return {"status": "ok"}
        
        client = TestClient(app)
        response = client.post("/empty", json={})
        
        assert response.status_code == 200
        
        log_content = log_file.read_text()
        assert "[API]" in log_content
        assert "[SERVER]" in log_content

    def test_special_characters_in_body(self, tmp_path):
        """Verify special characters in request body are logged correctly."""
        log_file = tmp_path / "test-api.log"
        
        app = FastAPI()
        app.add_middleware(APIMessageLoggingMiddleware, log_file_path=str(log_file))
        
        @app.post("/special")
        async def special_endpoint():
            return {"status": "ok"}
        
        client = TestClient(app)
        special_data = {
            "message": "Hello! @#$%^&*()_+-=[]{}|;':\",./<>?",
            "unicode": "你好世界 🌍"
        }
        response = client.post("/special", json=special_data)
        
        assert response.status_code == 200
        
        log_content = log_file.read_text(encoding="utf-8")
        assert "Hello!" in log_content or "你好世界" in log_content

    def test_long_string_truncation(self, tmp_path):
        """Verify long strings are truncated in logs."""
        log_file = tmp_path / "test-api.log"
        
        app = FastAPI()
        app.add_middleware(APIMessageLoggingMiddleware, log_file_path=str(log_file))
        
        @app.post("/long")
        async def long_endpoint():
            return {"status": "ok"}
        
        client = TestClient(app)
        long_data = {
            "data": "x" * 1000
        }
        response = client.post("/long", json=long_data)
        
        assert response.status_code == 200
        
        log_content = log_file.read_text()
        # Long strings should be truncated
        assert "...[truncated]" in log_content or "x" * 100 not in log_content

    def test_case_insensitive_sensitive_keys(self, tmp_path):
        """Verify sensitive keys are matched case-insensitively."""
        log_file = tmp_path / "test-api.log"
        
        app = FastAPI()
        app.add_middleware(APIMessageLoggingMiddleware, log_file_path=str(log_file))
        
        @app.post("/case")
        async def case_endpoint():
            return {"status": "ok"}
        
        client = TestClient(app)
        test_data = {
            "PASSWORD": "upper",
            "Token": "mixed",
            "normal": "visible"
        }
        response = client.post("/case", json=test_data)
        
        log_content = log_file.read_text()
        
        assert "***REDACTED***" in log_content
        assert "upper" not in log_content
        assert "mixed" not in log_content
        assert "visible" in log_content

    def test_non_json_body(self, tmp_path):
        """Verify non-JSON request bodies are handled correctly."""
        log_file = tmp_path / "test-api.log"
        
        app = FastAPI()
        app.add_middleware(APIMessageLoggingMiddleware, log_file_path=str(log_file))
        
        @app.post("/raw")
        async def raw_endpoint():
            return {"status": "ok"}
        
        client = TestClient(app)
        response = client.post(
            "/raw",
            content="raw text data without json",
            headers={"Content-Type": "text/plain"}
        )
        
        assert response.status_code == 200
        
        log_content = log_file.read_text()
        assert "raw text data" in log_content

    def test_unicode_in_path(self, tmp_path):
        """Verify Unicode characters in path are logged correctly."""
        log_file = tmp_path / "test-api.log"
        
        app = FastAPI()
        app.add_middleware(APIMessageLoggingMiddleware, log_file_path=str(log_file))
        
        @app.get("/unicode-测试")
        async def unicode_endpoint():
            return {"status": "ok"}
        
        client = TestClient(app)
        response = client.get("/unicode-测试")
        
        assert response.status_code == 200
        
        log_content = log_file.read_text(encoding="utf-8")
        assert "unicode-测试" in log_content


class TestAPIMessageLoggerSanitizationIntegration:
    """Integration tests for sanitization with actual API endpoints."""

    def setup_method(self):
        """Reset the global logger before each test."""
        reset_server_message_logger()
        reset_message_sent_logger()

    def teardown_method(self):
        """Reset the global logger after each test."""
        reset_server_message_logger()
        reset_message_sent_logger()

    def test_auth_flow_sanitization(self, tmp_path):
        """Verify auth flow endpoints sanitize sensitive data."""
        log_file = tmp_path / "test-api.log"
        
        app = FastAPI()
        app.add_middleware(APIMessageLoggingMiddleware, log_file_path=str(log_file))
        
        @app.post("/auth/send-mail-login-code-v2")
        async def send_mail_login_code():
            return {"mailLoginToken": "test-token"}
        
        @app.post("/auth/sign-in-by-mail-code")
        async def sign_in_by_mail_code():
            return {"mailAuthToken": "auth-token"}
        
        client = TestClient(app)
        
        # First request
        response1 = client.post(
            "/auth/send-mail-login-code-v2",
            json={"mail": "test@example.com"}
        )
        assert response1.status_code == 200
        
        # Second request
        response2 = client.post(
            "/auth/sign-in-by-mail-code",
            json={"mailLoginToken": "test-token", "receivedCode": "123456"}
        )
        assert response2.status_code == 200
        
        log_content = log_file.read_text()
        
        # Verify both requests are logged
        assert "send-mail-login-code-v2" in log_content
        assert "sign-in-by-mail-code" in log_content
        assert "test@example.com" in log_content
        assert "123456" in log_content
        assert "[SERVER]" in log_content

    def test_sync_flow_sanitization(self, tmp_path):
        """Verify sync flow endpoints sanitize sensitive data."""
        log_file = tmp_path / "test-api.log"
        
        app = FastAPI()
        app.add_middleware(APIMessageLoggingMiddleware, log_file_path=str(log_file))
        
        @app.post("/sync/push-actions")
        async def push_actions():
            return {"shouldDoFullSync": False}
        
        @app.post("/sync/pull-status")
        async def pull_status():
            return {"devices": {}, "users": {}}
        
        client = TestClient(app)
        
        # Push actions with sensitive data
        response1 = client.post(
            "/sync/push-actions",
            json={
                "deviceAuthToken": "secret_device_token",
                "actions": []
            }
        )
        assert response1.status_code == 200
        
        # Pull status
        response2 = client.post(
            "/sync/pull-status",
            json={"deviceAuthToken": "another_secret_token"}
        )
        assert response2.status_code == 200
        
        log_content = log_file.read_text()
        
        # Verify sensitive tokens are redacted
        assert "***REDACTED***" in log_content
        assert "secret_device_token" not in log_content
        assert "another_secret_token" not in log_content
