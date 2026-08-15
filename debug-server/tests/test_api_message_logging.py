"""Unit tests for API message logging middleware.

This module tests the APIMessageLoggingMiddleware functionality including:
- Immediate logging of incoming requests
- Server response logging with comprehensive metadata
- Timestamp accuracy
- Message content formatting
- Message integrity verification
- Error scenarios
"""

import glob
import json
import logging
import os
import re
import shutil
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


class TestAPIMessageLoggingMiddleware:
    """Tests for APIMessageLoggingMiddleware class."""

    def setup_method(self):
        """Reset the global server message logger before each test."""
        reset_server_message_logger()

    def teardown_method(self):
        """Reset the global server message logger after each test."""
        reset_server_message_logger()

    def test_middleware_logs_post_request_with_json_body(self, tmp_path):
        """Verify POST requests with JSON body are logged correctly."""
        log_file = tmp_path / "test-api.log"
        
        # Create a test app with the middleware
        app = FastAPI()
        app.add_middleware(APIMessageLoggingMiddleware, log_file_path=str(log_file))
        
        @app.post("/test")
        async def test_endpoint(request: Request):
            return {"status": "ok"}
        
        # Make a request
        client = TestClient(app)
        test_data = {"email": "test@example.com", "action": "login"}
        response = client.post("/test", json=test_data)
        
        assert response.status_code == 200
        
        # Verify log file contains the request
        log_content = log_file.read_text()
        
        # Check for timestamp format [YYYY-MM-DD HH:MM:SS.mmm]
        timestamp_pattern = r'\[\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d{3}\]'
        assert re.search(timestamp_pattern, log_content), \
            f"Timestamp not found in log. Content: {log_content}"
        
        # Check for API marker
        assert "[API]" in log_content, f"[API] marker not found in log. Content: {log_content}"
        
        # Check for HTTP method
        assert "POST" in log_content, f"POST method not found in log. Content: {log_content}"
        
        # Check for path
        assert "/test" in log_content, f"Path /test not found in log. Content: {log_content}"
        
        # Check for JSON body content
        assert "test@example.com" in log_content, \
            f"Request body content not found in log. Content: {log_content}"
        assert "login" in log_content, f"Action 'login' not found in log. Content: {log_content}"

    def test_middleware_logs_get_request_without_body(self, tmp_path):
        """Verify GET requests without body are logged correctly."""
        log_file = tmp_path / "test-api.log"
        
        app = FastAPI()
        app.add_middleware(APIMessageLoggingMiddleware, log_file_path=str(log_file))
        
        @app.get("/health")
        async def health_endpoint():
            return {"status": "healthy"}
        
        client = TestClient(app)
        response = client.get("/health")
        
        assert response.status_code == 200
        
        log_content = log_file.read_text()
        
        # Check for timestamp
        timestamp_pattern = r'\[\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d{3}\]'
        assert re.search(timestamp_pattern, log_content), \
            f"Timestamp not found in log. Content: {log_content}"
        
        # Check for GET method
        assert "GET" in log_content, f"GET method not found in log. Content: {log_content}"
        
        # Check for path
        assert "/health" in log_content, f"Path /health not found in log. Content: {log_content}"

    def test_middleware_logs_with_query_parameters(self, tmp_path):
        """Verify requests with query parameters are logged correctly."""
        log_file = tmp_path / "test-api.log"
        
        app = FastAPI()
        app.add_middleware(APIMessageLoggingMiddleware, log_file_path=str(log_file))
        
        @app.get("/search")
        async def search_endpoint():
            return {"results": []}
        
        client = TestClient(app)
        response = client.get("/search?q=test&limit=10")
        
        assert response.status_code == 200
        
        log_content = log_file.read_text()
        
        # Check for query parameters in log
        assert "q=test" in log_content, f"Query parameter 'q=test' not found in log. Content: {log_content}"
        assert "limit=10" in log_content, f"Query parameter 'limit=10' not found in log. Content: {log_content}"

    def test_middleware_logs_timestamp_accuracy(self, tmp_path):
        """Verify timestamps in log entries are accurate."""
        log_file = tmp_path / "test-api.log"
        
        app = FastAPI()
        app.add_middleware(APIMessageLoggingMiddleware, log_file_path=str(log_file))
        
        @app.post("/timestamp-test")
        async def timestamp_endpoint():
            return {"status": "ok"}
        
        client = TestClient(app)
        
        # Record time before request
        before_time = datetime.now()
        response = client.post("/timestamp-test", json={"test": "data"})
        after_time = datetime.now()
        
        assert response.status_code == 200
        
        log_content = log_file.read_text()
        
        # Extract timestamp from log
        timestamp_match = re.search(r'\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d{3})\]', log_content)
        assert timestamp_match, f"Timestamp not found in log. Content: {log_content}"
        
        log_timestamp_str = timestamp_match.group(1)
        log_timestamp = datetime.strptime(log_timestamp_str, "%Y-%m-%d %H:%M:%S.%f")
        
        # Verify timestamp is within the request time window
        assert before_time <= log_timestamp <= after_time, \
            f"Log timestamp {log_timestamp} is not between request time {before_time} and {after_time}"

    def test_middleware_logs_message_integrity(self, tmp_path):
        """Verify message content integrity is maintained in logs."""
        log_file = tmp_path / "test-api.log"
        
        app = FastAPI()
        app.add_middleware(APIMessageLoggingMiddleware, log_file_path=str(log_file))
        
        @app.post("/integrity-test")
        async def integrity_endpoint():
            return {"status": "ok"}
        
        client = TestClient(app)
        
        # Test with complex nested JSON
        test_data = {
            "user": {
                "id": 12345,
                "email": "user@example.com",
                "profile": {
                    "name": "Test User",
                    "preferences": ["email", "sms"]
                }
            },
            "action": "update_profile",
            "timestamp": "2024-01-15T10:30:00Z"
        }
        
        response = client.post("/integrity-test", json=test_data)
        assert response.status_code == 200
        
        log_content = log_file.read_text()
        
        # Verify key data is preserved
        assert "12345" in log_content, f"User ID not found in log. Content: {log_content}"
        assert "user@example.com" in log_content, f"Email not found in log. Content: {log_content}"
        assert "update_profile" in log_content, f"Action not found in log. Content: {log_content}"

    def test_middleware_logs_multiple_requests(self, tmp_path):
        """Verify multiple requests are all logged correctly."""
        log_file = tmp_path / "test-api.log"
        
        app = FastAPI()
        app.add_middleware(APIMessageLoggingMiddleware, log_file_path=str(log_file))
        
        @app.post("/multi-test")
        async def multi_endpoint():
            return {"status": "ok"}
        
        client = TestClient(app)
        
        # Make multiple requests
        for i in range(5):
            response = client.post("/multi-test", json={"request_id": i})
            assert response.status_code == 200
        
        log_content = log_file.read_text()
        
        # Count log entries (should have 10 entries: 5 requests + 5 responses)
        log_entries = log_content.strip().split('\n')
        assert len(log_entries) == 10, f"Expected 10 log entries (5 requests + 5 responses), got {len(log_entries)}. Content: {log_content}"
        
        # Verify request entries have [API] marker
        api_entries = [e for e in log_entries if "[API]" in e]
        assert len(api_entries) == 5, f"Expected 5 [API] entries, got {len(api_entries)}"
        
        # Verify response entries have [SERVER] marker
        server_entries = [e for e in log_entries if "[SERVER]" in e]
        assert len(server_entries) == 5, f"Expected 5 [SERVER] entries, got {len(server_entries)}"
        
        # Verify each API entry has proper format
        for entry in api_entries:
            assert "POST" in entry, f"POST method not found in entry: {entry}"

    def test_middleware_logs_put_request(self, tmp_path):
        """Verify PUT requests are logged correctly."""
        log_file = tmp_path / "test-api.log"
        
        app = FastAPI()
        app.add_middleware(APIMessageLoggingMiddleware, log_file_path=str(log_file))
        
        @app.put("/update-item/{item_id}")
        async def update_item(item_id: int):
            return {"id": item_id, "updated": True}
        
        client = TestClient(app)
        response = client.put("/update-item/42", json={"name": "Updated Item"})
        
        assert response.status_code == 200
        
        log_content = log_file.read_text()
        
        assert "PUT" in log_content, f"PUT method not found in log. Content: {log_content}"
        assert "/update-item/42" in log_content, f"Path not found in log. Content: {log_content}"
        assert "Updated Item" in log_content, f"Body content not found in log. Content: {log_content}"

    def test_middleware_logs_delete_request(self, tmp_path):
        """Verify DELETE requests are logged correctly."""
        log_file = tmp_path / "test-api.log"
        
        app = FastAPI()
        app.add_middleware(APIMessageLoggingMiddleware, log_file_path=str(log_file))
        
        @app.delete("/delete-item/{item_id}")
        async def delete_item(item_id: int):
            return {"id": item_id, "deleted": True}
        
        client = TestClient(app)
        response = client.delete("/delete-item/99")
        
        assert response.status_code == 200
        
        log_content = log_file.read_text()
        
        assert "DELETE" in log_content, f"DELETE method not found in log. Content: {log_content}"
        assert "/delete-item/99" in log_content, f"Path not found in log. Content: {log_content}"

    def test_middleware_logs_patch_request(self, tmp_path):
        """Verify PATCH requests are logged correctly."""
        log_file = tmp_path / "test-api.log"
        
        app = FastAPI()
        app.add_middleware(APIMessageLoggingMiddleware, log_file_path=str(log_file))
        
        @app.patch("/patch-item/{item_id}")
        async def patch_item(item_id: int):
            return {"id": item_id, "patched": True}
        
        client = TestClient(app)
        response = client.patch("/patch-item/55", json={"field": "value"})
        
        assert response.status_code == 200
        
        log_content = log_file.read_text()
        
        assert "PATCH" in log_content, f"PATCH method not found in log. Content: {log_content}"
        assert "/patch-item/55" in log_content, f"Path not found in log. Content: {log_content}"

    def test_middleware_handles_large_json_body(self, tmp_path):
        """Verify large JSON bodies are logged (truncated if necessary)."""
        log_file = tmp_path / "test-api.log"
        
        app = FastAPI()
        app.add_middleware(APIMessageLoggingMiddleware, log_file_path=str(log_file))
        
        @app.post("/large-body")
        async def large_body_endpoint():
            return {"status": "ok"}
        
        client = TestClient(app)
        
        # Create a large JSON body
        large_data = {
            "items": [{"id": i, "data": "x" * 100} for i in range(100)]
        }
        
        response = client.post("/large-body", json=large_data)
        assert response.status_code == 200
        
        log_content = log_file.read_text()
        
        # Verify some content is logged
        assert "[API]" in log_content, f"[API] marker not found in log. Content: {log_content}"
        # The body should be truncated but still contain key elements
        assert "items" in log_content, f"Body content not found in log. Content: {log_content}"

    def test_middleware_logs_non_json_body(self, tmp_path):
        """Verify non-JSON request bodies are logged correctly."""
        log_file = tmp_path / "test-api.log"
        
        app = FastAPI()
        app.add_middleware(APIMessageLoggingMiddleware, log_file_path=str(log_file))
        
        @app.post("/raw-data")
        async def raw_data_endpoint():
            return {"status": "ok"}
        
        client = TestClient(app)
        response = client.post(
            "/raw-data",
            content="raw text data without json",
            headers={"Content-Type": "text/plain"}
        )
        
        assert response.status_code == 200
        
        log_content = log_file.read_text()
        
        # Verify the raw content is logged
        assert "raw text data" in log_content, f"Raw body content not found in log. Content: {log_content}"

    def test_middleware_logs_format_structure(self, tmp_path):
        """Verify log entry format follows the expected structure."""
        log_file = tmp_path / "test-api.log"
        
        app = FastAPI()
        app.add_middleware(APIMessageLoggingMiddleware, log_file_path=str(log_file))
        
        @app.post("/format-test")
        async def format_endpoint():
            return {"status": "ok"}
        
        client = TestClient(app)
        response = client.post("/format-test", json={"test": "data"})
        assert response.status_code == 200
        
        log_content = log_file.read_text().strip()
        
        # Expected format: [timestamp] [API] METHOD path - body
        # Pattern: [YYYY-MM-DD HH:MM:SS.mmm] [API] METHOD path - body_content
        pattern = r'\[\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d{3}\] \[API\] (GET|POST|PUT|PATCH|DELETE) /[^\s]+(?: - .+)?'
        
        assert re.match(pattern, log_content), \
            f"Log entry doesn't match expected format. Content: {log_content}"


class TestAPIMessageLoggingResponse:
    """Tests for server response logging in APIMessageLoggingMiddleware."""

    def setup_method(self):
        """Reset the global server message logger before each test."""
        reset_server_message_logger()

    def teardown_method(self):
        """Reset the global server message logger after each test."""
        reset_server_message_logger()

    def test_middleware_logs_response(self, tmp_path):
        """Verify server responses are logged with [SERVER] marker."""
        log_file = tmp_path / "test-api.log"
        
        app = FastAPI()
        app.add_middleware(APIMessageLoggingMiddleware, log_file_path=str(log_file))
        
        @app.post("/response-test")
        async def response_test():
            return {"status": "ok", "message": "Success"}
        
        client = TestClient(app)
        response = client.post("/response-test", json={"test": "data"})
        
        assert response.status_code == 200
        
        log_content = log_file.read_text()
        
        # Check for [SERVER] marker in response log
        assert "[SERVER]" in log_content, f"[SERVER] marker not found in log. Content: {log_content}"
        assert "api_response" in log_content, f"api_response type not found in log. Content: {log_content}"

    def test_middleware_logs_response_status_code(self, tmp_path):
        """Verify response status code is logged."""
        log_file = tmp_path / "test-api.log"
        
        app = FastAPI()
        app.add_middleware(APIMessageLoggingMiddleware, log_file_path=str(log_file))
        
        @app.get("/status-test")
        async def status_test():
            return {"status": "ok"}
        
        client = TestClient(app)
        response = client.get("/status-test")
        
        assert response.status_code == 200
        
        log_content = log_file.read_text()
        
        # Check for status code in log
        assert "200" in log_content, f"Status code 200 not found in log. Content: {log_content}"

    def test_middleware_logs_response_with_path(self, tmp_path):
        """Verify response log includes the request path."""
        log_file = tmp_path / "test-api.log"
        
        app = FastAPI()
        app.add_middleware(APIMessageLoggingMiddleware, log_file_path=str(log_file))
        
        @app.post("/users")
        async def users_endpoint():
            return {"users": []}
        
        client = TestClient(app)
        response = client.post("/users", json={"name": "test"})
        
        assert response.status_code == 200
        
        log_content = log_file.read_text()
        
        # Check for path in log
        assert "/users" in log_content, f"Path not found in log. Content: {log_content}"

    def test_middleware_logs_response_with_method(self, tmp_path):
        """Verify response log includes the HTTP method."""
        log_file = tmp_path / "test-api.log"
        
        app = FastAPI()
        app.add_middleware(APIMessageLoggingMiddleware, log_file_path=str(log_file))
        
        @app.put("/update")
        async def update_endpoint():
            return {"updated": True}
        
        client = TestClient(app)
        response = client.put("/update", json={"id": 1})
        
        assert response.status_code == 200
        
        log_content = log_file.read_text()
        
        # Check for method in log
        assert "PUT" in log_content, f"PUT method not found in log. Content: {log_content}"

    def test_middleware_logs_response_content(self, tmp_path):
        """Verify response content is logged."""
        log_file = tmp_path / "test-api.log"
        
        app = FastAPI()
        app.add_middleware(APIMessageLoggingMiddleware, log_file_path=str(log_file))
        
        @app.get("/data")
        async def data_endpoint():
            return {"items": [{"id": 1, "name": "Item 1"}, {"id": 2, "name": "Item 2"}]}
        
        client = TestClient(app)
        response = client.get("/data")
        
        assert response.status_code == 200
        
        log_content = log_file.read_text()
        
        # Check for response content in log (should be in SERVER log entry)
        assert "items" in log_content, f"Response content not found in log. Content: {log_content}"
        # Check for item names in the log
        assert "Item 1" in log_content, f"Response content 'Item 1' not found in log. Content: {log_content}"
        assert "Item 2" in log_content, f"Response content 'Item 2' not found in log. Content: {log_content}"

    def test_middleware_logs_response_timestamp(self, tmp_path):
        """Verify response log includes accurate timestamp."""
        log_file = tmp_path / "test-api.log"
        
        app = FastAPI()
        app.add_middleware(APIMessageLoggingMiddleware, log_file_path=str(log_file))
        
        @app.get("/timestamp")
        async def timestamp_endpoint():
            return {"timestamp": datetime.now().isoformat()}
        
        client = TestClient(app)
        
        before_time = datetime.now()
        response = client.get("/timestamp")
        after_time = datetime.now()
        
        assert response.status_code == 200
        
        log_content = log_file.read_text()
        
        # Extract timestamp from server log entry
        match = re.search(r'\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d{3})\] \[SERVER\]', log_content)
        assert match, f"Server log timestamp not found. Content: {log_content}"
        
        log_timestamp_str = match.group(1)
        log_timestamp = datetime.strptime(log_timestamp_str, "%Y-%m-%d %H:%M:%S.%f")
        
        # Verify timestamp is within the expected window
        assert before_time <= log_timestamp <= after_time, \
            f"Log timestamp {log_timestamp} is not between request time {before_time} and {after_time}"

    def test_middleware_logs_response_with_duration(self, tmp_path):
        """Verify response log includes duration in milliseconds."""
        log_file = tmp_path / "test-api.log"
        
        app = FastAPI()
        app.add_middleware(APIMessageLoggingMiddleware, log_file_path=str(log_file))
        
        @app.get("/slow")
        async def slow_endpoint():
            import asyncio
            await asyncio.sleep(0.01)
            return {"status": "ok"}
        
        client = TestClient(app)
        response = client.get("/slow")
        
        assert response.status_code == 200
        
        log_content = log_file.read_text()
        
        # Check for duration_ms in log
        assert "duration_ms" in log_content, f"duration_ms not found in log. Content: {log_content}"

    def test_middleware_logs_both_request_and_response(self, tmp_path):
        """Verify both request and response are logged for each request."""
        log_file = tmp_path / "test-api.log"
        
        app = FastAPI()
        app.add_middleware(APIMessageLoggingMiddleware, log_file_path=str(log_file))
        
        @app.post("/both-test")
        async def both_test():
            return {"status": "ok"}
        
        client = TestClient(app)
        response = client.post("/both-test", json={"test": "data"})
        
        assert response.status_code == 200
        
        log_content = log_file.read_text()
        
        # Check for both [API] and [SERVER] markers
        assert "[API]" in log_content, f"[API] marker not found in log. Content: {log_content}"
        assert "[SERVER]" in log_content, f"[SERVER] marker not found in log. Content: {log_content}"

    def test_middleware_logs_error_response(self, tmp_path):
        """Verify error responses are logged correctly."""
        log_file = tmp_path / "test-api.log"
        
        app = FastAPI()
        app.add_middleware(APIMessageLoggingMiddleware, log_file_path=str(log_file))
        
        @app.get("/error")
        async def error_endpoint():
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail="Not found")
        
        client = TestClient(app)
        response = client.get("/error")
        
        # Response should be 404
        assert response.status_code == 404
        
        log_content = log_file.read_text()
        
        # Check for error information in log
        assert "[SERVER]" in log_content, f"[SERVER] marker not found in log. Content: {log_content}"


class TestAPIMessageLoggingIntegration:
    """Integration tests for API message logging with real API endpoints."""

    def setup_method(self):
        """Reset the global server message logger before each test."""
        reset_server_message_logger()

    def teardown_method(self):
        """Reset the global server message logger after each test."""
        reset_server_message_logger()

    def test_logs_health_endpoint(self, tmp_path):
        """Verify health endpoint requests are logged."""
        log_file = tmp_path / "test-api.log"
        
        app = FastAPI()
        app.add_middleware(APIMessageLoggingMiddleware, log_file_path=str(log_file))
        
        @app.get("/health")
        async def health():
            return {"status": "healthy"}
        
        client = TestClient(app)
        response = client.get("/health")
        
        assert response.status_code == 200
        
        log_content = log_file.read_text()
        assert "GET" in log_content
        assert "/health" in log_content
        assert "[SERVER]" in log_content

    def test_logs_auth_flow_endpoints(self, tmp_path):
        """Verify authentication flow endpoints are logged."""
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

    def test_logs_with_actual_api_router(self, tmp_path):
        """Verify logging works with the actual API router."""
        log_file = tmp_path / "test-api.log"
        
        # Import the actual API router
        from app.api import api_router
        
        app = FastAPI()
        app.add_middleware(APIMessageLoggingMiddleware, log_file_path=str(log_file))
        app.include_router(api_router, prefix="")
        
        client = TestClient(app)
        
        # Test health endpoint
        response = client.get("/health")
        assert response.status_code == 200
        
        log_content = log_file.read_text()
        assert "[API]" in log_content
        assert "GET" in log_content
        assert "/health" in log_content
        assert "[SERVER]" in log_content


class TestAPIMessageLoggingTimestampFormat:
    """Tests for timestamp format verification."""

    def setup_method(self):
        """Reset the global server message logger before each test."""
        reset_server_message_logger()

    def teardown_method(self):
        """Reset the global server message logger after each test."""
        reset_server_message_logger()

    def test_timestamp_format_is_iso_like(self, tmp_path):
        """Verify timestamp follows ISO-like format with milliseconds."""
        log_file = tmp_path / "test-api.log"
        
        app = FastAPI()
        app.add_middleware(APIMessageLoggingMiddleware, log_file_path=str(log_file))
        
        @app.post("/timestamp")
        async def timestamp_endpoint():
            return {"status": "ok"}
        
        client = TestClient(app)
        client.post("/timestamp", json={})
        
        log_content = log_file.read_text()
        
        # Extract timestamp
        match = re.search(r'\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d{3})\]', log_content)
        assert match, f"Timestamp not found in log. Content: {log_content}"
        
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
        """Verify timestamps are sequential for multiple requests."""
        log_file = tmp_path / "test-api.log"
        
        app = FastAPI()
        app.add_middleware(APIMessageLoggingMiddleware, log_file_path=str(log_file))
        
        @app.post("/sequential")
        async def sequential_endpoint():
            return {"status": "ok"}
        
        client = TestClient(app)
        
        for i in range(3):
            client.post("/sequential", json={"id": i})
        
        log_content = log_file.read_text()
        
        # Extract all timestamps (should have 6: 3 requests + 3 responses)
        matches = re.findall(r'\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d{3})\]', log_content)
        
        assert len(matches) == 6, f"Expected 6 timestamps (3 requests + 3 responses), got {len(matches)}"
        
        # Verify timestamps are in ascending order
        for i in range(len(matches) - 1):
            assert matches[i] <= matches[i + 1], \
                f"Timestamps not sequential: {matches[i]} > {matches[i + 1]}"


class TestAPIMessageLoggingEdgeCases:
    """Tests for edge cases in API message logging."""

    def setup_method(self):
        """Reset the global server message logger before each test."""
        reset_server_message_logger()

    def teardown_method(self):
        """Reset the global server message logger after each test."""
        reset_server_message_logger()

    def test_logs_empty_json_body(self, tmp_path):
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

    def test_logs_special_characters_in_body(self, tmp_path):
        """Verify special characters in request body are logged correctly."""
        log_file = tmp_path / "test-api.log"
        
        app = FastAPI()
        app.add_middleware(APIMessageLoggingMiddleware, log_file_path=str(log_file))
        
        @app.post("/special-chars")
        async def special_chars_endpoint():
            return {"status": "ok"}
        
        client = TestClient(app)
        special_data = {
            "message": "Hello! @#$%^&*()_+-=[]{}|;':\",./<>?",
            "unicode": "你好世界 🌍"
        }
        response = client.post("/special-chars", json=special_data)
        
        assert response.status_code == 200
        
        log_content = log_file.read_text(encoding="utf-8")
        # Verify special characters are preserved
        assert "Hello!" in log_content or "你好世界" in log_content, \
            f"Special characters not preserved in log. Content: {log_content}"

    def test_logs_unicode_in_path(self, tmp_path):
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
        assert "unicode-测试" in log_content, f"Unicode path not found in log. Content: {log_content}"

    def test_logs_concurrent_requests(self, tmp_path):
        """Verify concurrent requests are all logged."""
        log_file = tmp_path / "test-api.log"
        
        app = FastAPI()
        app.add_middleware(APIMessageLoggingMiddleware, log_file_path=str(log_file))
        
        @app.post("/concurrent")
        async def concurrent_endpoint():
            return {"status": "ok"}
        
        client = TestClient(app)
        
        # Make multiple requests
        for i in range(10):
            response = client.post("/concurrent", json={"id": i})
            assert response.status_code == 200
        
        log_content = log_file.read_text()
        
        # Count log entries (should have 20: 10 requests + 10 responses)
        log_entries = [line for line in log_content.strip().split('\n') if line.strip()]
        assert len(log_entries) == 20, f"Expected 20 log entries (10 requests + 10 responses), got {len(log_entries)}"
        
        # Verify we have both API and SERVER entries
        api_entries = [e for e in log_entries if "[API]" in e]
        server_entries = [e for e in log_entries if "[SERVER]" in e]
        assert len(api_entries) == 10, f"Expected 10 [API] entries, got {len(api_entries)}"
        assert len(server_entries) == 10, f"Expected 10 [SERVER] entries, got {len(server_entries)}"


class TestAPIMessageLoggingSanitization:
    """Tests for sanitization in API message logging middleware."""

    def setup_method(self):
        """Reset the global server message logger before each test."""
        reset_server_message_logger()

    def teardown_method(self):
        """Reset the global server message logger after each test."""
        reset_server_message_logger()

    def test_request_body_password_sanitized(self, tmp_path):
        """Verify password in request body is sanitized."""
        log_file = tmp_path / "test-api.log"
        
        app = FastAPI()
        app.add_middleware(APIMessageLoggingMiddleware, log_file_path=str(log_file))
        
        @app.post("/login")
        async def login_endpoint():
            return {"status": "ok"}
        
        client = TestClient(app)
        response = client.post("/login", json={"email": "test@example.com", "password": "secret123"})
        
        assert response.status_code == 200
        
        log_content = log_file.read_text()
        assert "***REDACTED***" in log_content
        assert "secret123" not in log_content
        assert "test@example.com" in log_content

    def test_request_body_token_sanitized(self, tmp_path):
        """Verify token in request body is sanitized."""
        log_file = tmp_path / "test-api.log"
        
        app = FastAPI()
        app.add_middleware(APIMessageLoggingMiddleware, log_file_path=str(log_file))
        
        @app.post("/sync")
        async def sync_endpoint():
            return {"status": "ok"}
        
        client = TestClient(app)
        response = client.post("/sync", json={"deviceAuthToken": "device_token_123", "actions": []})
        
        assert response.status_code == 200
        
        log_content = log_file.read_text()
        assert "***REDACTED***" in log_content
        assert "device_token_123" not in log_content

    def test_response_body_password_sanitized(self, tmp_path):
        """Verify password in response body is sanitized."""
        log_file = tmp_path / "test-api.log"
        
        app = FastAPI()
        app.add_middleware(APIMessageLoggingMiddleware, log_file_path=str(log_file))
        
        @app.get("/user")
        async def user_endpoint():
            return {"user": {"name": "Test User", "password": "user_password", "token": "user_token"}}
        
        client = TestClient(app)
        response = client.get("/user")
        
        assert response.status_code == 200
        
        log_content = log_file.read_text()
        assert "***REDACTED***" in log_content
        assert "user_password" not in log_content
        assert "user_token" not in log_content
        assert "Test User" in log_content

    def test_nested_sensitive_data_sanitized(self, tmp_path):
        """Verify nested sensitive data in request/response is sanitized."""
        log_file = tmp_path / "test-api.log"
        
        app = FastAPI()
        app.add_middleware(APIMessageLoggingMiddleware, log_file_path=str(log_file))
        
        @app.post("/nested")
        async def nested_endpoint():
            return {"status": "ok"}
        
        client = TestClient(app)
        response = client.post("/nested", json={
            "user": {
                "password": "nested_password",
                "name": "John"
            },
            "device": {
                "token": "nested_token",
                "id": "device_123"
            }
        })
        
        assert response.status_code == 200
        
        log_content = log_file.read_text()
        assert "***REDACTED***" in log_content
        assert "nested_password" not in log_content
        assert "nested_token" not in log_content
        assert "John" in log_content
        assert "device_123" in log_content

    def test_all_sensitive_keys_sanitized(self, tmp_path):
        """Verify all sensitive keys are sanitized in request/response."""
        log_file = tmp_path / "test-api.log"
        
        app = FastAPI()
        app.add_middleware(APIMessageLoggingMiddleware, log_file_path=str(log_file))
        
        @app.post("/sensitive")
        async def sensitive_endpoint():
            return {"status": "ok"}
        
        client = TestClient(app)
        response = client.post("/sensitive", json={
            "password": "pass123",
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
            "secondHash": "secondHash123",
            "secondSalt": "secondSalt123",
            "deviceAuthToken": "deviceAuthToken123",
            "mailAuthToken": "mailAuthToken123",
            "mailLoginToken": "mailLoginToken123",
            "identityToken": "identity123",
            "normal_field": "visible"
        })
        
        assert response.status_code == 200
        
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

    def test_sensitive_data_in_response_sanitized(self, tmp_path):
        """Verify sensitive data in response body is sanitized."""
        log_file = tmp_path / "test-api.log"
        
        app = FastAPI()
        app.add_middleware(APIMessageLoggingMiddleware, log_file_path=str(log_file))
        
        @app.get("/response")
        async def response_endpoint():
            return {
                "user": {
                    "id": 1,
                    "password": "response_password",
                    "token": "response_token"
                }
            }
        
        client = TestClient(app)
        response = client.get("/response")
        
        assert response.status_code == 200
        
        log_content = log_file.read_text()
        assert "***REDACTED***" in log_content
        assert "response_password" not in log_content
        assert "response_token" not in log_content
        assert "1" in log_content  # Non-sensitive data preserved
