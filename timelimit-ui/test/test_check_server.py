"""Comprehensive unit tests for the check_server module.

This module tests the server connection checking functionality including:
- Successful connections
- Network timeouts
- Invalid server responses
- Unreachable servers
- Retry logic and exponential backoff
"""

import json
import socket
import sys
import time
import urllib.error
from unittest.mock import MagicMock, patch, call
import pytest

# Import the module under test
sys.path.insert(0, 'rootfs/usr/bin')
from check_server import (
    ServerChecker,
    ServerCheckResult,
    check_server_connection,
    ERROR_CODE_TIMEOUT,
    ERROR_CODE_UNREACHABLE,
    ERROR_CODE_INVALID_RESPONSE,
    ERROR_CODE_SERVER_ERROR,
    ERROR_CODE_UNKNOWN,
    USER_MESSAGES
)


class TestServerCheckResult:
    """Tests for the ServerCheckResult dataclass."""

    def test_to_dict_success(self):
        """Test to_dict() returns correct structure for successful result."""
        result = ServerCheckResult(
            success=True,
            server_time=1704067200000,
            attempts=1,
            server_url="http://localhost:8080"
        )
        
        d = result.to_dict()
        
        assert d["success"] is True
        assert d["time"] == 1704067200000
        assert d["attempts"] == 1
        assert d["server_url"] == "http://localhost:8080"
        assert "error_code" not in d
        assert "user_message" not in d

    def test_to_dict_failure(self):
        """Test to_dict() returns correct structure for failed result."""
        result = ServerCheckResult(
            success=False,
            error_code=ERROR_CODE_TIMEOUT,
            user_message="Server did not respond",
            technical_detail="Connection timed out after 10s",
            attempts=3,
            server_url="http://localhost:8080"
        )
        
        d = result.to_dict()
        
        assert d["success"] is False
        assert d["status"] == "error"
        assert d["error_code"] == ERROR_CODE_TIMEOUT
        assert d["user_message"] == "Server did not respond"
        assert d["technical_detail"] == "Connection timed out after 10s"
        assert d["attempts"] == 3
        assert d["server_url"] == "http://localhost:8080"


class TestServerCheckerSuccess:
    """Tests for successful server connections."""

    @patch('check_server.urllib.request.urlopen')
    def test_successful_connection(self, mock_urlopen, sample_server_time):
        """Test successful server connection returns correct result."""
        # Setup mock
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.read.return_value = json.dumps({"time": sample_server_time}).encode('utf-8')
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response
        
        # Execute
        checker = ServerChecker("http://localhost:8080", timeout=5, max_retries=1)
        result = checker.check()
        
        # Assert
        assert result.success is True
        assert result.server_time == sample_server_time
        assert result.attempts == 1
        assert result.server_url == "http://localhost:8080"
        assert result.error_code is None
        assert result.user_message is None

    @patch('check_server.urllib.request.urlopen')
    def test_successful_connection_with_retries(self, mock_urlopen, sample_server_time):
        """Test successful connection after retry."""
        # First call fails, second succeeds
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.read.return_value = json.dumps({"time": sample_server_time}).encode('utf-8')
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)
        
        # First call raises timeout, second succeeds
        mock_urlopen.side_effect = [
            socket.timeout("Connection timed out"),
            mock_response
        ]
        
        # Execute
        checker = ServerChecker("http://localhost:8080", timeout=5, max_retries=3, retry_delay=0.01)
        result = checker.check()
        
        # Assert
        assert result.success is True
        assert result.server_time == sample_server_time
        assert result.attempts == 2  # 1 failed + 1 successful

    @patch('check_server.urllib.request.urlopen')
    def test_server_time_is_integer(self, mock_urlopen):
        """Test that server time is converted to integer."""
        sample_time = 1704067200123  # milliseconds
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.read.return_value = json.dumps({"time": sample_time}).encode('utf-8')
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response
        
        checker = ServerChecker("http://localhost:8080")
        result = checker.check()
        
        assert result.success is True
        assert isinstance(result.server_time, int)


class TestServerCheckerTimeout:
    """Tests for network timeout scenarios."""

    @patch('check_server.urllib.request.urlopen')
    def test_timeout_error(self, mock_urlopen):
        """Test that timeout errors are handled correctly."""
        mock_urlopen.side_effect = socket.timeout("Connection timed out")
        
        checker = ServerChecker("http://localhost:8080", timeout=5, max_retries=1)
        result = checker.check()
        
        assert result.success is False
        assert result.error_code == ERROR_CODE_TIMEOUT
        assert result.user_message == USER_MESSAGES[ERROR_CODE_TIMEOUT]
        assert "timeout" in result.technical_detail.lower()
        assert result.attempts == 1

    @patch('check_server.urllib.request.urlopen')
    def test_timeout_with_retries(self, mock_urlopen):
        """Test that timeout errors trigger retries."""
        mock_urlopen.side_effect = socket.timeout("Connection timed out")
        
        checker = ServerChecker("http://localhost:8080", timeout=5, max_retries=3, retry_delay=0.01)
        result = checker.check()
        
        assert result.success is False
        assert result.error_code == ERROR_CODE_TIMEOUT
        assert result.attempts == 3  # All retries exhausted


class TestServerCheckerUnreachable:
    """Tests for unreachable server scenarios."""

    @patch('check_server.urllib.request.urlopen')
    def test_connection_refused(self, mock_urlopen):
        """Test that connection refused errors are handled correctly."""
        mock_urlopen.side_effect = ConnectionRefusedError("Connection refused")
        
        checker = ServerChecker("http://localhost:8080", max_retries=3)
        result = checker.check()
        
        assert result.success is False
        assert result.error_code == ERROR_CODE_UNREACHABLE
        assert result.user_message == USER_MESSAGES[ERROR_CODE_UNREACHABLE]
        assert result.attempts == 1  # No retries on connection refused

    @patch('check_server.urllib.request.urlopen')
    def test_url_error_unreachable(self, mock_urlopen):
        """Test that URLError (unreachable) is handled correctly."""
        mock_urlopen.side_effect = urllib.error.URLError("Connection refused")
        
        checker = ServerChecker("http://localhost:8080", max_retries=3)
        result = checker.check()
        
        assert result.success is False
        assert result.error_code == ERROR_CODE_UNREACHABLE
        assert result.attempts == 1  # No retries on connection refused

    @patch('check_server.urllib.request.urlopen')
    def test_host_unreachable(self, mock_urlopen):
        """Test that host unreachable errors are handled correctly."""
        mock_urlopen.side_effect = urllib.error.URLError("[Errno 101] Network is unreachable")
        
        checker = ServerChecker("http://localhost:8080", max_retries=3)
        result = checker.check()
        
        assert result.success is False
        assert result.error_code == ERROR_CODE_UNREACHABLE


class TestServerCheckerInvalidResponse:
    """Tests for invalid server response scenarios."""

    @patch('check_server.urllib.request.urlopen')
    def test_invalid_json_response(self, mock_urlopen):
        """Test that invalid JSON responses are handled correctly."""
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.read.return_value = b"not valid json"
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response
        
        checker = ServerChecker("http://localhost:8080", max_retries=1)
        result = checker.check()
        
        assert result.success is False
        assert result.error_code == ERROR_CODE_INVALID_RESPONSE
        assert "json" in result.technical_detail.lower()

    @patch('check_server.urllib.request.urlopen')
    def test_missing_time_field(self, mock_urlopen):
        """Test that responses missing 'time' field are handled correctly."""
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.read.return_value = json.dumps({"status": "ok"}).encode('utf-8')
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response
        
        checker = ServerChecker("http://localhost:8080", max_retries=1)
        result = checker.check()
        
        assert result.success is False
        assert result.error_code == ERROR_CODE_INVALID_RESPONSE
        assert "time" in result.technical_detail.lower()

    @patch('check_server.urllib.request.urlopen')
    def test_non_numeric_time_field(self, mock_urlopen):
        """Test that responses with non-numeric 'time' field are handled correctly."""
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.read.return_value = json.dumps({"time": "not a number"}).encode('utf-8')
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response
        
        checker = ServerChecker("http://localhost:8080", max_retries=1)
        result = checker.check()
        
        assert result.success is False
        assert result.error_code == ERROR_CODE_INVALID_RESPONSE

    @patch('check_server.urllib.request.urlopen')
    def test_empty_response(self, mock_urlopen):
        """Test that empty responses are handled correctly."""
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.read.return_value = b""
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response
        
        checker = ServerChecker("http://localhost:8080", max_retries=1)
        result = checker.check()
        
        assert result.success is False
        assert result.error_code == ERROR_CODE_INVALID_RESPONSE


class TestServerCheckerServerError:
    """Tests for server error scenarios."""

    @patch('check_server.urllib.request.urlopen')
    def test_http_500_error(self, mock_urlopen):
        """Test that HTTP 500 errors are handled correctly."""
        error = urllib.error.HTTPError(
            url="http://localhost:8080/api/v1/time",
            code=500,
            msg="Internal Server Error",
            hdrs={},
            fp=None
        )
        error.read = MagicMock(return_value=b'{"error": "Internal server error"}')
        mock_urlopen.side_effect = error
        
        checker = ServerChecker("http://localhost:8080", max_retries=1)
        result = checker.check()
        
        assert result.success is False
        assert result.error_code == ERROR_CODE_SERVER_ERROR

    @patch('check_server.urllib.request.urlopen')
    def test_http_503_error(self, mock_urlopen):
        """Test that HTTP 503 errors are handled correctly."""
        error = urllib.error.HTTPError(
            url="http://localhost:8080/api/v1/time",
            code=503,
            msg="Service Unavailable",
            hdrs={},
            fp=None
        )
        error.read = MagicMock(return_value=b'{"error": "Service unavailable"}')
        mock_urlopen.side_effect = error
        
        checker = ServerChecker("http://localhost:8080", max_retries=1)
        result = checker.check()
        
        assert result.success is False
        assert result.error_code == ERROR_CODE_SERVER_ERROR

    @patch('check_server.urllib.request.urlopen')
    def test_http_404_error(self, mock_urlopen):
        """Test that HTTP 404 errors are handled correctly."""
        error = urllib.error.HTTPError(
            url="http://localhost:8080/api/v1/time",
            code=404,
            msg="Not Found",
            hdrs={},
            fp=None
        )
        error.read = MagicMock(return_value=b'{"error": "Not found"}')
        mock_urlopen.side_effect = error
        
        checker = ServerChecker("http://localhost:8080", max_retries=1)
        result = checker.check()
        
        assert result.success is False
        assert result.error_code == ERROR_CODE_SERVER_ERROR


class TestServerCheckerRetryLogic:
    """Tests for retry logic and exponential backoff."""

    @patch('check_server.urllib.request.urlopen')
    @patch('check_server.time.sleep')
    def test_exponential_backoff(self, mock_sleep, mock_urlopen, sample_server_time):
        """Test that retry delays increase exponentially."""
        # First two calls fail, third succeeds
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.read.return_value = json.dumps({"time": sample_server_time}).encode('utf-8')
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)
        
        mock_urlopen.side_effect = [
            socket.timeout("Connection timed out"),
            socket.timeout("Connection timed out"),
            mock_response
        ]
        
        checker = ServerChecker("http://localhost:8080", timeout=5, max_retries=3, retry_delay=1.0)
        result = checker.check()
        
        assert result.success is True
        assert result.attempts == 3
        
        # Verify exponential backoff: 1.0, 2.0
        assert mock_sleep.call_count == 2
        assert mock_sleep.call_args_list[0] == call(1.0)
        assert mock_sleep.call_args_list[1] == call(2.0)

    @patch('check_server.urllib.request.urlopen')
    def test_all_retries_fail(self, mock_urlopen):
        """Test that all retries are exhausted before returning failure."""
        mock_urlopen.side_effect = socket.timeout("Connection timed out")
        
        checker = ServerChecker("http://localhost:8080", timeout=5, max_retries=3, retry_delay=0.01)
        result = checker.check()
        
        assert result.success is False
        assert result.attempts == 3
        assert mock_urlopen.call_count == 3


class TestServerCheckerConfiguration:
    """Tests for ServerChecker configuration."""

    def test_default_configuration(self):
        """Test default configuration values."""
        checker = ServerChecker("http://localhost:8080")
        
        assert checker.timeout == 10.0
        assert checker.max_retries == 3
        assert checker.retry_delay == 1.0
        assert checker.verbose is False

    def test_custom_configuration(self):
        """Test custom configuration values."""
        checker = ServerChecker(
            "http://localhost:8080",
            timeout=5.0,
            max_retries=5,
            retry_delay=2.0,
            verbose=True
        )
        
        assert checker.timeout == 5.0
        assert checker.max_retries == 5
        assert checker.retry_delay == 2.0
        assert checker.verbose is True

    def test_server_url_normalization(self):
        """Test that server URL is normalized (trailing slash removed)."""
        checker = ServerChecker("http://localhost:8080/")
        assert checker.server_url == "http://localhost:8080"
        
        checker = ServerChecker("http://localhost:8080/api/")
        assert checker.server_url == "http://localhost:8080/api"


class TestCheckServerConnection:
    """Tests for the convenience function check_server_connection()."""

    @patch('check_server.urllib.request.urlopen')
    def test_convenience_function_success(self, mock_urlopen, sample_server_time):
        """Test that check_server_connection() works correctly for success case."""
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.read.return_value = json.dumps({"time": sample_server_time}).encode('utf-8')
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response
        
        result = check_server_connection("http://localhost:8080", timeout=5, max_retries=1)
        
        assert result.success is True
        assert result.server_time == sample_server_time

    @patch('check_server.urllib.request.urlopen')
    def test_convenience_function_failure(self, mock_urlopen):
        """Test that check_server_connection() works correctly for failure case."""
        mock_urlopen.side_effect = socket.timeout("Connection timed out")
        
        result = check_server_connection("http://localhost:8080", timeout=5, max_retries=1)
        
        assert result.success is False
        assert result.error_code == ERROR_CODE_TIMEOUT


class TestUserMessages:
    """Tests for user message mapping."""

    def test_all_error_codes_have_messages(self):
        """Test that all error codes have corresponding user messages."""
        error_codes = [
            ERROR_CODE_TIMEOUT,
            ERROR_CODE_UNREACHABLE,
            ERROR_CODE_INVALID_RESPONSE,
            ERROR_CODE_SERVER_ERROR,
            ERROR_CODE_UNKNOWN
        ]
        
        for code in error_codes:
            assert code in USER_MESSAGES, f"Missing user message for {code}"
            assert isinstance(USER_MESSAGES[code], str), f"User message for {code} is not a string"
            assert len(USER_MESSAGES[code]) > 0, f"User message for {code} is empty"

    def test_get_user_message(self):
        """Test the get_user_message function."""
        from check_server import get_user_message
        
        assert get_user_message(ERROR_CODE_TIMEOUT) == USER_MESSAGES[ERROR_CODE_TIMEOUT]
        assert get_user_message(ERROR_CODE_UNREACHABLE) == USER_MESSAGES[ERROR_CODE_UNREACHABLE]
        assert get_user_message("unknown_code") == USER_MESSAGES[ERROR_CODE_UNKNOWN]


class TestErrorCodeValidation:
    """Tests for error code validation."""

    def test_is_error_code_valid_codes(self):
        """Test that is_error_code returns True for valid codes."""
        from check_server import is_error_code
        
        assert is_error_code(ERROR_CODE_TIMEOUT) is True
        assert is_error_code(ERROR_CODE_UNREACHABLE) is True
        assert is_error_code(ERROR_CODE_INVALID_RESPONSE) is True
        assert is_error_code(ERROR_CODE_SERVER_ERROR) is True
        assert is_error_code(ERROR_CODE_UNKNOWN) is True

    def test_is_error_code_invalid_codes(self):
        """Test that is_error_code returns False for invalid codes."""
        from check_server import is_error_code
        
        assert is_error_code("invalid") is False
        assert is_error_code("") is False
        assert is_error_code(None) is False


class TestIntegration:
    """Integration tests for the complete check flow."""

    @patch('check_server.urllib.request.urlopen')
    def test_complete_success_flow(self, mock_urlopen, sample_server_time):
        """Test complete successful flow from check to result."""
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.read.return_value = json.dumps({"time": sample_server_time}).encode('utf-8')
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response
        
        result = check_server_connection("http://localhost:8080")
        
        # Verify result structure
        result_dict = result.to_dict()
        assert "success" in result_dict
        assert "time" in result_dict
        assert "attempts" in result_dict
        assert "server_url" in result_dict
        assert "error_code" not in result_dict
        assert "user_message" not in result_dict

    @patch('check_server.urllib.request.urlopen')
    def test_complete_error_flow(self, mock_urlopen):
        """Test complete error flow from check to result."""
        mock_urlopen.side_effect = socket.timeout("Connection timed out")
        
        result = check_server_connection("http://localhost:8080")
        
        # Verify result structure
        result_dict = result.to_dict()
        assert result_dict["success"] is False
        assert result_dict["status"] == "error"
        assert "error_code" in result_dict
        assert "user_message" in result_dict
        assert "technical_detail" in result_dict
        assert "time" not in result_dict


if __name__ == "__main__":
    pytest.main([__file__, "-v"])