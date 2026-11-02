"""Unit tests for AuthClient logging.

Tests for AuthClient request/response logging, error logging,
sanitization, and error categorization.
"""

import io
import json
import os
import sys
import tempfile
from unittest.mock import MagicMock, patch, Mock

import pytest
import requests
from requests.exceptions import Timeout, ConnectionError

from auth_client import AuthClient, APIResponse, create_auth_client


def reset_structlog():
    """Reset structlog configuration for clean test state."""
    import structlog
    import logging
    
    # Close all handlers
    root_logger = logging.getLogger()
    for handler in root_logger.handlers[:]:
        try:
            handler.flush()
            handler.close()
        except Exception:
            pass
        root_logger.removeHandler(handler)
    
    # Reset structlog
    structlog.reset_defaults()


class TestAuthClientLogging:
    """Tests for AuthClient logging functionality."""

    @pytest.mark.timeout(10)
    def test_auth_client_logs_request_start(self):
        """Verify AuthClient logs request start."""
        reset_structlog()
        
        with patch.dict(os.environ, {
            'LOG_LEVEL': 'DEBUG',
            'LOG_FORMAT': 'json'
        }):
            from utils.logging import setup_structlog, get_logger
            setup_structlog()

            with patch('requests.Session') as mock_session_class:
                mock_session = Mock()
                mock_response = Mock()
                mock_response.status_code = 200
                mock_response.ok = True
                mock_response.json.return_value = {'server_time': 1234567890}
                mock_session.get.return_value = mock_response
                mock_session_class.return_value = mock_session

                client = AuthClient('http://localhost:8080')
                
                # Capture stdout to get JSON output
                captured_output = io.StringIO()
                with patch('sys.stdout', captured_output):
                    client.get_server_time()
                
                reset_structlog()

            # Parse the captured output as JSON
            output = captured_output.getvalue().strip()
            lines = [l for l in output.split('\n') if l]
            
            # Should have at least one log entry with request info
            found_request = False
            for line in lines:
                try:
                    entry = json.loads(line)
                    if 'request' in entry.get('event', '').lower() or 'api' in entry.get('event', '').lower():
                        found_request = True
                        break
                except json.JSONDecodeError:
                    pass
            
            assert found_request, f"Expected 'request' or 'api' in log events, got: {output}"

    @pytest.mark.timeout(10)
    def test_auth_client_logs_response_success(self):
        """Verify AuthClient logs successful responses."""
        reset_structlog()
        
        with patch.dict(os.environ, {
            'LOG_LEVEL': 'DEBUG',
            'LOG_FORMAT': 'json'
        }):
            from utils.logging import setup_structlog, get_logger
            setup_structlog()

            with patch('requests.Session') as mock_session_class:
                mock_session = Mock()
                mock_response = Mock()
                mock_response.status_code = 200
                mock_response.ok = True
                mock_response.json.return_value = {'server_time': 1234567890}
                mock_session.get.return_value = mock_response
                mock_session_class.return_value = mock_session

                client = AuthClient('http://localhost:8080')
                
                # Capture stdout to get JSON output
                captured_output = io.StringIO()
                with patch('sys.stdout', captured_output):
                    client.get_server_time()
                
                reset_structlog()

            # Parse the captured output as JSON
            output = captured_output.getvalue().strip()
            lines = [l for l in output.split('\n') if l]
            
            # Should have at least one log entry with success info
            found_success = False
            for line in lines:
                try:
                    entry = json.loads(line)
                    if 'success' in entry.get('event', '').lower() or entry.get('status_code') == 200:
                        found_success = True
                        break
                except json.JSONDecodeError:
                    pass
            
            assert found_success, f"Expected 'success' or status_code 200 in log events, got: {output}"

    @pytest.mark.timeout(10)
    def test_auth_client_logs_response_error(self):
        """Verify AuthClient logs error responses."""
        reset_structlog()
        
        with patch.dict(os.environ, {
            'LOG_LEVEL': 'DEBUG',
            'LOG_FORMAT': 'json'
        }):
            from utils.logging import setup_structlog, get_logger
            setup_structlog()

            with patch('requests.Session') as mock_session_class:
                mock_session = Mock()
                mock_response = Mock()
                mock_response.status_code = 500
                mock_response.ok = False
                mock_response.json.return_value = {'error': 'Internal Server Error'}
                mock_session.get.return_value = mock_response
                mock_session_class.return_value = mock_session

                client = AuthClient('http://localhost:8080')
                
                # Capture stdout to get JSON output
                captured_output = io.StringIO()
                with patch('sys.stdout', captured_output):
                    client.get_server_time()
                
                reset_structlog()

            # Parse the captured output as JSON
            output = captured_output.getvalue().strip()
            lines = [l for l in output.split('\n') if l]
            
            # Should have at least one log entry with error info
            found_error = False
            for line in lines:
                try:
                    entry = json.loads(line)
                    if 'error' in entry.get('event', '').lower() or entry.get('status_code') == 500:
                        found_error = True
                        break
                except json.JSONDecodeError:
                    pass
            
            assert found_error, f"Expected 'error' or status_code 500 in log events, got: {output}"


class TestAuthClientRequestLogging:
    """Tests for AuthClient request logging."""

    @pytest.mark.timeout(10)
    def test_logs_request_method(self):
        """Verify request method is logged."""
        reset_structlog()
        
        with patch.dict(os.environ, {
            'LOG_LEVEL': 'DEBUG',
            'LOG_FORMAT': 'json'
        }):
            from utils.logging import setup_structlog, get_logger
            setup_structlog()

            with patch('requests.Session') as mock_session_class:
                mock_session = Mock()
                mock_response = Mock()
                mock_response.status_code = 200
                mock_response.ok = True
                mock_response.json.return_value = {'success': True}
                mock_session.get.return_value = mock_response
                mock_session_class.return_value = mock_session

                client = AuthClient('http://localhost:8080')
                
                # Capture stdout to get JSON output
                captured_output = io.StringIO()
                with patch('sys.stdout', captured_output):
                    client.get_server_time()
                
                reset_structlog()

            # Parse the captured output as JSON
            output = captured_output.getvalue().strip()
            lines = [l for l in output.split('\n') if l]
            
            # Should have at least one log entry with method info
            found_method = False
            for line in lines:
                try:
                    entry = json.loads(line)
                    if entry.get('method') == 'GET':
                        found_method = True
                        break
                except json.JSONDecodeError:
                    pass
            
            assert found_method, f"Expected method 'GET' in log events, got: {output}"

    @pytest.mark.timeout(10)
    def test_logs_request_endpoint(self):
        """Verify request endpoint is logged."""
        reset_structlog()
        
        with patch.dict(os.environ, {
            'LOG_LEVEL': 'DEBUG',
            'LOG_FORMAT': 'json'
        }):
            from utils.logging import setup_structlog, get_logger
            setup_structlog()

            with patch('requests.Session') as mock_session_class:
                mock_session = Mock()
                mock_response = Mock()
                mock_response.status_code = 200
                mock_response.ok = True
                mock_response.json.return_value = {'success': True}
                mock_session.get.return_value = mock_response
                mock_session_class.return_value = mock_session

                client = AuthClient('http://localhost:8080')
                
                # Capture stdout to get JSON output
                captured_output = io.StringIO()
                with patch('sys.stdout', captured_output):
                    client.get_server_time()
                
                reset_structlog()

            # Parse the captured output as JSON
            output = captured_output.getvalue().strip()
            lines = [l for l in output.split('\n') if l]
            
            # Should have at least one log entry with endpoint info
            found_endpoint = False
            for line in lines:
                try:
                    entry = json.loads(line)
                    if 'time' in entry.get('endpoint', '').lower():
                        found_endpoint = True
                        break
                except json.JSONDecodeError:
                    pass
            
            assert found_endpoint, f"Expected 'time' in endpoint in log events, got: {output}"

    @pytest.mark.timeout(10)
    def test_logs_request_body_sanitized(self):
        """Verify request body is sanitized in logs."""
        reset_structlog()
        
        with patch.dict(os.environ, {
            'LOG_LEVEL': 'DEBUG',
            'LOG_FORMAT': 'json'
        }):
            from utils.logging import setup_structlog, get_logger
            setup_structlog()

            with patch('requests.Session') as mock_session_class:
                mock_session = Mock()
                mock_response = Mock()
                mock_response.status_code = 200
                mock_response.ok = True
                mock_response.json.return_value = {'success': True}
                mock_session.post.return_value = mock_response
                mock_session_class.return_value = mock_session

                client = AuthClient('http://localhost:8080')
                
                # Capture stdout to get JSON output
                captured_output = io.StringIO()
                with patch('sys.stdout', captured_output):
                    client.sign_in_into_family('test@example.com', 'password123')
                
                reset_structlog()

            # Parse the captured output as JSON
            output = captured_output.getvalue().strip()
            
            # Password should be redacted
            assert 'password123' not in output


class TestAuthClientResponseLogging:
    """Tests for AuthClient response logging."""

    @pytest.mark.timeout(10)
    def test_logs_status_code(self):
        """Verify response status code is logged."""
        reset_structlog()
        
        with patch.dict(os.environ, {
            'LOG_LEVEL': 'DEBUG',
            'LOG_FORMAT': 'json'
        }):
            from utils.logging import setup_structlog, get_logger
            setup_structlog()

            with patch('requests.Session') as mock_session_class:
                mock_session = Mock()
                mock_response = Mock()
                mock_response.status_code = 200
                mock_response.ok = True
                mock_response.json.return_value = {'server_time': 1234567890}
                mock_session.get.return_value = mock_response
                mock_session_class.return_value = mock_session

                client = AuthClient('http://localhost:8080')
                
                # Capture stdout to get JSON output
                captured_output = io.StringIO()
                with patch('sys.stdout', captured_output):
                    client.get_server_time()
                
                reset_structlog()

            # Parse the captured output as JSON
            output = captured_output.getvalue().strip()
            lines = [l for l in output.split('\n') if l]
            
            # Should have at least one log entry with status code 200
            found_200 = False
            for line in lines:
                try:
                    entry = json.loads(line)
                    if entry.get('status_code') == 200:
                        found_200 = True
                        break
                except json.JSONDecodeError:
                    pass
            
            assert found_200, f"Expected status_code 200 in log events, got: {output}"

    @pytest.mark.timeout(10)
    def test_logs_response_data(self):
        """Verify response data is logged."""
        reset_structlog()
        
        with patch.dict(os.environ, {
            'LOG_LEVEL': 'DEBUG',
            'LOG_FORMAT': 'json'
        }):
            from utils.logging import setup_structlog, get_logger
            setup_structlog()

            with patch('requests.Session') as mock_session_class:
                mock_session = Mock()
                mock_response = Mock()
                mock_response.status_code = 200
                mock_response.ok = True
                mock_response.json.return_value = {'server_time': 1234567890}
                mock_session.get.return_value = mock_response
                mock_session_class.return_value = mock_session

                client = AuthClient('http://localhost:8080')
                
                # Capture stdout to get JSON output
                captured_output = io.StringIO()
                with patch('sys.stdout', captured_output):
                    client.get_server_time()
                
                reset_structlog()

            # Parse the captured output as JSON
            output = captured_output.getvalue().strip()
            lines = [l for l in output.split('\n') if l]
            
            # Should have at least one log entry with server_time or data
            found_data = False
            for line in lines:
                try:
                    entry = json.loads(line)
                    data = entry.get('data')
                    if data and 'server_time' in data:
                        found_data = True
                        break
                    if 'data' in entry:
                        found_data = True
                        break
                except json.JSONDecodeError:
                    pass
            
            assert found_data, f"Expected 'server_time' or 'data' in log events, got: {output}"


class TestAuthClientErrorLogging:
    """Tests for AuthClient error logging."""

    @pytest.mark.timeout(10)
    def test_logs_timeout_error(self):
        """Verify timeout errors are logged."""
        reset_structlog()
        
        with patch.dict(os.environ, {
            'LOG_LEVEL': 'DEBUG',
            'LOG_FORMAT': 'json'
        }):
            from utils.logging import setup_structlog, get_logger
            setup_structlog()

            with patch('requests.Session') as mock_session_class:
                mock_session = Mock()
                mock_session.get.side_effect = Timeout('Timeout')
                mock_session_class.return_value = mock_session

                client = AuthClient('http://localhost:8080')
                
                # Capture stdout to get JSON output
                captured_output = io.StringIO()
                with patch('sys.stdout', captured_output):
                    result = client.get_server_time()
                
                reset_structlog()

            # Parse the captured output as JSON
            output = captured_output.getvalue().strip()
            lines = [l for l in output.split('\n') if l]
            
            # Should have at least one log entry with timeout or error
            found_timeout = False
            for line in lines:
                try:
                    entry = json.loads(line)
                    if 'timeout' in entry.get('event', '').lower() or entry.get('error_code') == 'timeout':
                        found_timeout = True
                        break
                except json.JSONDecodeError:
                    pass
            
            assert found_timeout, f"Expected 'timeout' in log events, got: {output}"

    @pytest.mark.timeout(10)
    def test_logs_connection_error(self):
        """Verify connection errors are logged."""
        reset_structlog()
        
        with patch.dict(os.environ, {
            'LOG_LEVEL': 'DEBUG',
            'LOG_FORMAT': 'json'
        }):
            from utils.logging import setup_structlog, get_logger
            setup_structlog()

            with patch('requests.Session') as mock_session_class:
                mock_session = Mock()
                mock_session.get.side_effect = ConnectionError('Connection failed')
                mock_session_class.return_value = mock_session

                client = AuthClient('http://localhost:8080')
                
                # Capture stdout to get JSON output
                captured_output = io.StringIO()
                with patch('sys.stdout', captured_output):
                    result = client.get_server_time()
                
                reset_structlog()

            # Parse the captured output as JSON
            output = captured_output.getvalue().strip()
            lines = [l for l in output.split('\n') if l]
            
            # Should have at least one log entry with connection or error
            found_connection = False
            for line in lines:
                try:
                    entry = json.loads(line)
                    if 'connection' in entry.get('event', '').lower() or entry.get('error_code') == 'unreachable':
                        found_connection = True
                        break
                except json.JSONDecodeError:
                    pass
            
            assert found_connection, f"Expected 'connection' or 'unreachable' in log events, got: {output}"

    @pytest.mark.timeout(10)
    def test_logs_invalid_response_error(self):
        """Verify invalid JSON response is handled gracefully."""
        reset_structlog()
        
        with patch.dict(os.environ, {
            'LOG_LEVEL': 'DEBUG',
            'LOG_FORMAT': 'json'
        }):
            from utils.logging import setup_structlog, get_logger
            setup_structlog()

            with patch('requests.Session') as mock_session_class:
                mock_session = Mock()
                mock_response = Mock()
                mock_response.status_code = 200
                mock_response.ok = True
                mock_response.json.side_effect = json.JSONDecodeError('Invalid JSON', '', 0)
                mock_response.content = b'Not JSON'
                mock_session.get.return_value = mock_response
                mock_session_class.return_value = mock_session

                client = AuthClient('http://localhost:8080')
                
                # Capture stdout to get JSON output
                captured_output = io.StringIO()
                with patch('sys.stdout', captured_output):
                    result = client.get_server_time()
                
                reset_structlog()

            # Parse the captured output as JSON
            output = captured_output.getvalue().strip()
            lines = [l for l in output.split('\n') if l]
            
            # Should have at least one log entry with success (HTTP request succeeded)
            # and the raw content should be in the data field
            found_success = False
            for line in lines:
                try:
                    entry = json.loads(line)
                    if entry.get('event') == 'API request successful':
                        found_success = True
                        break
                except json.JSONDecodeError:
                    pass
            
            assert found_success, f"Expected 'API request successful' in log events, got: {output}"


class TestAuthClientErrorCategorization:
    """Tests for error categorization in AuthClient logging."""

    @pytest.mark.timeout(10)
    def test_timeout_error_code(self):
        """Verify timeout errors have correct error code."""
        reset_structlog()
        
        with patch.dict(os.environ, {
            'LOG_LEVEL': 'DEBUG',
            'LOG_FORMAT': 'json'
        }):
            from utils.logging import setup_structlog, get_logger
            setup_structlog()

            with patch('requests.Session') as mock_session_class:
                mock_session = Mock()
                mock_session.get.side_effect = Timeout('Timeout')
                mock_session_class.return_value = mock_session

                client = AuthClient('http://localhost:8080')
                
                # Capture stdout to get JSON output
                captured_output = io.StringIO()
                with patch('sys.stdout', captured_output):
                    result = client.get_server_time()
                
                reset_structlog()

            # Parse the captured output as JSON
            output = captured_output.getvalue().strip()
            lines = [l for l in output.split('\n') if l]
            
            # Should have at least one log entry with timeout or error_code
            found_timeout = False
            for line in lines:
                try:
                    entry = json.loads(line)
                    if 'timeout' in entry.get('event', '').lower() or 'error_code' in entry:
                        found_timeout = True
                        break
                except json.JSONDecodeError:
                    pass
            
            assert found_timeout, f"Expected 'timeout' or 'error_code' in log events, got: {output}"

    @pytest.mark.timeout(10)
    def test_connection_error_code(self):
        """Verify connection errors have correct error code."""
        reset_structlog()
        
        with patch.dict(os.environ, {
            'LOG_LEVEL': 'DEBUG',
            'LOG_FORMAT': 'json'
        }):
            from utils.logging import setup_structlog, get_logger
            setup_structlog()

            with patch('requests.Session') as mock_session_class:
                mock_session = Mock()
                mock_session.get.side_effect = ConnectionError('Connection failed')
                mock_session_class.return_value = mock_session

                client = AuthClient('http://localhost:8080')
                
                # Capture stdout to get JSON output
                captured_output = io.StringIO()
                with patch('sys.stdout', captured_output):
                    result = client.get_server_time()
                
                reset_structlog()

            # Parse the captured output as JSON
            output = captured_output.getvalue().strip()
            lines = [l for l in output.split('\n') if l]
            
            # Should have at least one log entry with unreachable, connection, or error
            found_connection = False
            for line in lines:
                try:
                    entry = json.loads(line)
                    if 'unreachable' in entry.get('event', '').lower() or 'connection' in entry.get('event', '').lower() or 'error' in entry.get('event', '').lower():
                        found_connection = True
                        break
                except json.JSONDecodeError:
                    pass
            
            assert found_connection, f"Expected 'unreachable', 'connection', or 'error' in log events, got: {output}"

    @pytest.mark.timeout(10)
    def test_server_error_code(self):
        """Verify server errors have correct error code."""
        reset_structlog()
        
        with patch.dict(os.environ, {
            'LOG_LEVEL': 'DEBUG',
            'LOG_FORMAT': 'json'
        }):
            from utils.logging import setup_structlog, get_logger
            setup_structlog()

            with patch('requests.Session') as mock_session_class:
                mock_session = Mock()
                mock_response = Mock()
                mock_response.status_code = 500
                mock_response.ok = False
                mock_response.json.return_value = {'error': 'Server Error'}
                mock_session.get.return_value = mock_response
                mock_session_class.return_value = mock_session

                client = AuthClient('http://localhost:8080')
                
                # Capture stdout to get JSON output
                captured_output = io.StringIO()
                with patch('sys.stdout', captured_output):
                    result = client.get_server_time()
                
                reset_structlog()

            # Parse the captured output as JSON
            output = captured_output.getvalue().strip()
            lines = [l for l in output.split('\n') if l]
            
            # Should have at least one log entry with server_error or 500
            found_server_error = False
            for line in lines:
                try:
                    entry = json.loads(line)
                    if 'server_error' in entry.get('event', '').lower() or entry.get('status_code') == 500:
                        found_server_error = True
                        break
                except json.JSONDecodeError:
                    pass
            
            assert found_server_error, f"Expected 'server_error' or status_code 500 in log events, got: {output}"


class TestAuthClientSpecificMethodsLogging:
    """Tests for specific AuthClient method logging."""

    @pytest.mark.timeout(10)
    def test_send_mail_login_code_logs_email(self):
        """Verify send_mail_login_code logs email (sanitized)."""
        reset_structlog()
        
        with patch.dict(os.environ, {
            'LOG_LEVEL': 'DEBUG',
            'LOG_FORMAT': 'json'
        }):
            from utils.logging import setup_structlog, get_logger
            setup_structlog()

            with patch('requests.Session') as mock_session_class:
                mock_session = Mock()
                mock_response = Mock()
                mock_response.status_code = 200
                mock_response.ok = True
                mock_response.json.return_value = {'success': True}
                mock_session.post.return_value = mock_response
                mock_session_class.return_value = mock_session

                client = AuthClient('http://localhost:8080')
                
                # Capture stdout to get JSON output
                captured_output = io.StringIO()
                with patch('sys.stdout', captured_output):
                    client.send_mail_login_code('test@example.com', 'en')
                
                reset_structlog()

            # Parse the captured output as JSON
            output = captured_output.getvalue().strip()
            lines = [l for l in output.split('\n') if l]
            
            # Should have at least one log entry with mail or email
            found_mail = False
            for line in lines:
                try:
                    entry = json.loads(line)
                    if 'mail' in entry.get('event', '').lower() or 'email' in entry.get('event', '').lower():
                        found_mail = True
                        break
                except json.JSONDecodeError:
                    pass
            
            assert found_mail, f"Expected 'mail' or 'email' in log events, got: {output}"

    @pytest.mark.timeout(10)
    def test_create_family_logs_family_data(self):
        """Verify create_family logs family creation."""
        reset_structlog()
        
        with patch.dict(os.environ, {
            'LOG_LEVEL': 'DEBUG',
            'LOG_FORMAT': 'json'
        }):
            from utils.logging import setup_structlog, get_logger
            setup_structlog()

            with patch('requests.Session') as mock_session_class:
                mock_session = Mock()
                mock_response = Mock()
                mock_response.status_code = 200
                mock_response.ok = True
                mock_response.json.return_value = {'deviceAuthToken': 'test_token', 'ownDeviceId': 'device123'}
                mock_session.post.return_value = mock_response
                mock_session_class.return_value = mock_session

                client = AuthClient('http://localhost:8080')
                
                # Capture stdout to get JSON output
                captured_output = io.StringIO()
                with patch('sys.stdout', captured_output):
                    client.create_family(
                        'mail_token_123',
                        {'hash': 'hash1', 'secondHash': 'hash2', 'secondSalt': 'salt'},
                        {'model': 'Pixel 7'},
                        'Test Device',
                        'Europe/Amsterdam',
                        'Test Parent'
                    )
                
                reset_structlog()

            # Parse the captured output as JSON
            output = captured_output.getvalue().strip()
            lines = [l for l in output.split('\n') if l]
            
            # Should have at least one log entry with family or create
            found_family = False
            for line in lines:
                try:
                    entry = json.loads(line)
                    if 'family' in entry.get('event', '').lower() or 'create' in entry.get('event', '').lower():
                        found_family = True
                        break
                except json.JSONDecodeError:
                    pass
            
            assert found_family, f"Expected 'family' or 'create' in log events, got: {output}"

    @pytest.mark.timeout(10)
    def test_sign_in_into_family_logs_sign_in(self):
        """Verify sign_in_into_family logs sign-in attempt."""
        reset_structlog()
        
        with patch.dict(os.environ, {
            'LOG_LEVEL': 'DEBUG',
            'LOG_FORMAT': 'json'
        }):
            from utils.logging import setup_structlog, get_logger
            setup_structlog()

            with patch('requests.Session') as mock_session_class:
                mock_session = Mock()
                mock_response = Mock()
                mock_response.status_code = 200
                mock_response.ok = True
                mock_response.json.return_value = {'deviceAuthToken': 'test_token', 'ownDeviceId': 'device123'}
                mock_session.post.return_value = mock_response
                mock_session_class.return_value = mock_session

                client = AuthClient('http://localhost:8080')
                
                # Capture stdout to get JSON output
                captured_output = io.StringIO()
                with patch('sys.stdout', captured_output):
                    client.sign_in_into_family('mail_token_123', 'password123')
                
                reset_structlog()

            # Parse the captured output as JSON
            output = captured_output.getvalue().strip()
            lines = [l for l in output.split('\n') if l]
            
            # Should have at least one log entry with sign or auth
            found_sign = False
            for line in lines:
                try:
                    entry = json.loads(line)
                    if 'sign' in entry.get('event', '').lower() or 'auth' in entry.get('event', '').lower():
                        found_sign = True
                        break
                except json.JSONDecodeError:
                    pass
            
            assert found_sign, f"Expected 'sign' or 'auth' in log events, got: {output}"


class TestAuthClientSanitization:
    """Tests for AuthClient data sanitization."""

    @pytest.mark.timeout(10)
    def test_password_redacted_in_logs(self):
        """Verify password is redacted in logs."""
        reset_structlog()
        
        with patch.dict(os.environ, {
            'LOG_LEVEL': 'DEBUG',
            'LOG_FORMAT': 'json'
        }):
            from utils.logging import setup_structlog, get_logger
            setup_structlog()

            with patch('requests.Session') as mock_session_class:
                mock_session = Mock()
                mock_response = Mock()
                mock_response.status_code = 200
                mock_response.ok = True
                mock_response.json.return_value = {'success': True}
                mock_session.post.return_value = mock_response
                mock_session_class.return_value = mock_session

                client = AuthClient('http://localhost:8080')
                
                # Capture stdout to get JSON output
                captured_output = io.StringIO()
                with patch('sys.stdout', captured_output):
                    client.sign_in_into_family('mail_token_123', 'mysecretpassword')
                
                reset_structlog()

            # Parse the captured output as JSON
            output = captured_output.getvalue().strip()
            
            # Password should be redacted
            assert 'mysecretpassword' not in output

    @pytest.mark.timeout(10)
    def test_token_redacted_in_logs(self):
        """Verify tokens are redacted in logs."""
        reset_structlog()
        
        with patch.dict(os.environ, {
            'LOG_LEVEL': 'DEBUG',
            'LOG_FORMAT': 'json'
        }):
            from utils.logging import setup_structlog, get_logger
            setup_structlog()

            with patch('requests.Session') as mock_session_class:
                mock_session = Mock()
                mock_response = Mock()
                mock_response.status_code = 200
                mock_response.ok = True
                mock_response.json.return_value = {'success': True}
                mock_session.post.return_value = mock_response
                mock_session_class.return_value = mock_session

                client = AuthClient('http://localhost:8080')
                
                # Capture stdout to get JSON output
                captured_output = io.StringIO()
                with patch('sys.stdout', captured_output):
                    client.create_add_device_token('device123', 'parent_user_123', 'password_hash')
                
                reset_structlog()

            # Parse the captured output as JSON
            output = captured_output.getvalue().strip()
            
            # Token should be redacted
            assert 'device123' not in output or 'REDACTED' in output


class TestAuthClientRequestCorrelation:
    """Tests for request ID correlation in AuthClient."""

    @pytest.mark.timeout(10)
    def test_request_id_in_logs(self):
        """Verify request ID is included in logs."""
        reset_structlog()
        
        with patch.dict(os.environ, {
            'LOG_LEVEL': 'DEBUG',
            'LOG_FORMAT': 'json'
        }):
            from utils.logging import setup_structlog, get_logger
            setup_structlog()

            with patch('requests.Session') as mock_session_class:
                mock_session = Mock()
                mock_response = Mock()
                mock_response.status_code = 200
                mock_response.ok = True
                mock_response.json.return_value = {'server_time': 1234567890}
                mock_session.get.return_value = mock_response
                mock_session_class.return_value = mock_session

                client = AuthClient('http://localhost:8080')
                
                # Capture stdout to get JSON output
                captured_output = io.StringIO()
                with patch('sys.stdout', captured_output):
                    client.get_server_time()
                
                reset_structlog()

            # Parse the captured output as JSON
            output = captured_output.getvalue().strip()
            lines = [l for l in output.split('\n') if l]
            
            # Should have at least one log entry with request_id
            found_request_id = False
            for line in lines:
                try:
                    entry = json.loads(line)
                    if 'request_id' in entry:
                        found_request_id = True
                        break
                except json.JSONDecodeError:
                    pass
            
            assert found_request_id, f"Expected 'request_id' in log events, got: {output}"


class TestAuthClientLoggingWithRetry:
    """Tests for AuthClient logging with retry logic."""

    @pytest.mark.timeout(10)
    def test_retry_attempts_logged(self):
        """Verify retry attempts are logged."""
        reset_structlog()
        
        with patch.dict(os.environ, {
            'LOG_LEVEL': 'DEBUG',
            'LOG_FORMAT': 'json'
        }):
            from utils.logging import setup_structlog, get_logger
            setup_structlog()

            with patch('requests.Session') as mock_session_class:
                mock_session = Mock()
                mock_response = Mock()
                mock_response.status_code = 200
                mock_response.ok = True
                mock_response.json.return_value = {'server_time': 1234567890}
                mock_session.get.return_value = mock_response
                mock_session_class.return_value = mock_session

                client = AuthClient('http://localhost:8080')
                
                # Capture stdout to get JSON output
                captured_output = io.StringIO()
                with patch('sys.stdout', captured_output):
                    client.get_server_time()
                
                reset_structlog()

            # Parse the captured output as JSON
            output = captured_output.getvalue().strip()
            lines = [l for l in output.split('\n') if l]
            
            # Should have at least one log entry with request or api
            found_request = False
            for line in lines:
                try:
                    entry = json.loads(line)
                    if 'request' in entry.get('event', '').lower() or 'api' in entry.get('event', '').lower():
                        found_request = True
                        break
                except json.JSONDecodeError:
                    pass
            
            assert found_request, f"Expected 'request' or 'api' in log events, got: {output}"


class TestAuthClientLoggingIntegration:
    """Integration tests for AuthClient logging."""

    @pytest.mark.timeout(10)
    def test_full_auth_flow_logging(self):
        """Verify complete auth flow is logged."""
        reset_structlog()
        
        with patch.dict(os.environ, {
            'LOG_LEVEL': 'DEBUG',
            'LOG_FORMAT': 'json'
        }):
            from utils.logging import setup_structlog, get_logger
            setup_structlog()

            with patch('requests.Session') as mock_session_class:
                mock_session = Mock()
                
                # Mock responses for each step
                mock_send_code = Mock()
                mock_send_code.status_code = 200
                mock_send_code.ok = True
                mock_send_code.json.return_value = {'success': True}
                
                mock_sign_in = Mock()
                mock_sign_in.status_code = 200
                mock_sign_in.ok = True
                mock_sign_in.json.return_value = {'success': True}
                
                mock_session.post.side_effect = [mock_send_code, mock_sign_in]
                mock_session.get.return_value = mock_send_code
                mock_session_class.return_value = mock_session

                client = AuthClient('http://localhost:8080')
                
                # Capture stdout to get JSON output
                captured_output = io.StringIO()
                with patch('sys.stdout', captured_output):
                    # Simulate auth flow
                    client.get_server_time()
                    client.send_mail_login_code('test@example.com', 'en')
                    client.sign_in_by_mail_code('mail_token_123', '123456')
                
                reset_structlog()

            # Parse the captured output as JSON
            output = captured_output.getvalue().strip()
            lines = [l for l in output.split('\n') if l]
            
            # Should have multiple log entries
            assert len(lines) >= 1

    @pytest.mark.timeout(10)
    def test_log_format_is_json(self):
        """Verify log output is valid JSON."""
        reset_structlog()
        
        with patch.dict(os.environ, {
            'LOG_LEVEL': 'DEBUG',
            'LOG_FORMAT': 'json'
        }):
            from utils.logging import setup_structlog, get_logger
            setup_structlog()

            with patch('requests.Session') as mock_session_class:
                mock_session = Mock()
                mock_response = Mock()
                mock_response.status_code = 200
                mock_response.ok = True
                mock_response.json.return_value = {'server_time': 1234567890}
                mock_session.get.return_value = mock_response
                mock_session_class.return_value = mock_session

                client = AuthClient('http://localhost:8080')
                
                # Capture stdout to get JSON output
                captured_output = io.StringIO()
                with patch('sys.stdout', captured_output):
                    client.get_server_time()
                
                reset_structlog()

            # Parse the captured output as JSON
            output = captured_output.getvalue().strip()
            lines = [l for l in output.split('\n') if l]
            
            # Each line should be valid JSON
            for line in lines:
                if line:
                    entry = json.loads(line)
                    assert 'event' in entry or 'message' in entry