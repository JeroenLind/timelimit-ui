"""Pytest fixtures for TimeLimit UI tests.

This module provides shared fixtures for all test modules.
"""

import sys
import os
import pytest
from unittest.mock import MagicMock, patch
import json

# Add the rootfs/usr/bin directory to the path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'rootfs', 'usr', 'bin'))


@pytest.fixture
def sample_server_url():
    """Provide a sample server URL for testing."""
    return "http://192.168.68.30:8080"


@pytest.fixture
def sample_server_time():
    """Provide a sample server time in milliseconds."""
    return 1704067200000  # 2024-01-01 00:00:00 UTC in milliseconds


@pytest.fixture
def mock_successful_response(sample_server_time):
    """Create a mock successful response from the server."""
    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.read.return_value = json.dumps({"time": sample_server_time}).encode('utf-8')
    mock_response.__enter__ = MagicMock(return_value=mock_response)
    mock_response.__exit__ = MagicMock(return_value=False)
    return mock_response


@pytest.fixture
def mock_timeout_error():
    """Create a mock socket timeout error."""
    import socket
    return socket.timeout("Connection timed out")


@pytest.fixture
def mock_connection_refused_error():
    """Create a mock connection refused error."""
    return ConnectionRefusedError("Connection refused")


@pytest.fixture
def mock_url_error():
    """Create a mock URL error."""
    import urllib.error
    return urllib.error.URLError("Connection refused")


@pytest.fixture
def mock_http_error():
    """Create a mock HTTP error response."""
    import urllib.error
    error = urllib.error.HTTPError(
        url="http://192.168.68.30:8080/time",
        code=500,
        msg="Internal Server Error",
        hdrs={},
        fp=None
    )
    return error


@pytest.fixture
def mock_invalid_json_response():
    """Create a mock response with invalid JSON."""
    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.read.return_value = b"not valid json"
    mock_response.__enter__ = MagicMock(return_value=mock_response)
    mock_response.__exit__ = MagicMock(return_value=False)
    return mock_response


@pytest.fixture
def mock_missing_time_field_response():
    """Create a mock response with missing 'time' field."""
    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.read.return_value = json.dumps({"status": "ok"}).encode('utf-8')
    mock_response.__enter__ = MagicMock(return_value=mock_response)
    mock_response.__exit__ = MagicMock(return_value=False)
    return mock_response


@pytest.fixture
def mock_non_numeric_time_response():
    """Create a mock response with non-numeric 'time' field."""
    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.read.return_value = json.dumps({"time": "not a number"}).encode('utf-8')
    mock_response.__enter__ = MagicMock(return_value=mock_response)
    mock_response.__exit__ = MagicMock(return_value=False)
    return mock_response


@pytest.fixture
def mock_server_error_response():
    """Create a mock HTTP 500 error response."""
    import urllib.error
    error = urllib.error.HTTPError(
        url="http://192.168.68.30:8080/time",
        code=500,
        msg="Internal Server Error",
        hdrs={},
        fp=None
    )
    error.read = MagicMock(return_value=b'{"error": "Internal server error"}')
    return error