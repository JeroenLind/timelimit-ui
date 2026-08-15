"""Unit tests for auth client HTTP communication.

This module tests the auth_client module functionality including:
- AuthClient initialization
- API response handling
- HTTP request methods
- Error handling
- Timeout mechanisms
"""

import json
import pytest
from unittest.mock import Mock, patch, MagicMock
from requests.exceptions import Timeout, ConnectionError

from auth_client import AuthClient, APIResponse, create_auth_client, get_auth_client, reset_auth_client


class TestAPIResponse:
    """Tests for APIResponse dataclass."""
    
    def test_successful_response(self):
        """Test creating a successful API response."""
        response = APIResponse(
            success=True,
            status_code=200,
            data={'ms': 1704067200000}
        )
        
        assert response.success is True
        assert response.status_code == 200
        assert response.data == {'ms': 1704067200000}
        assert response.error_code is None
        assert response.error_message is None
    
    def test_failed_response(self):
        """Test creating a failed API response."""
        response = APIResponse(
            success=False,
            status_code=401,
            data={'error': 'Invalid token'},
            error_code='unauthorized',
            error_message='Invalid or expired token',
            technical_detail='Token validation failed'
        )
        
        assert response.success is False
        assert response.status_code == 401
        assert response.error_code == 'unauthorized'
        assert response.error_message == 'Invalid or expired token'
        assert response.technical_detail == 'Token validation failed'


class TestAuthClientInitialization:
    """Tests for AuthClient initialization."""
    
    def test_default_initialization(self):
        """Test AuthClient with default values."""
        client = AuthClient()
        
        assert client.base_url == 'http://localhost:8080'
        assert client.timeout == 10
        assert client.max_retries == 3
        assert client.retry_delay == 1.0
        assert client.verbose is False
    
    def test_custom_initialization(self):
        """Test AuthClient with custom values."""
        client = AuthClient(
            base_url='http://custom:9000',
            timeout=30,
            max_retries=5,
            retry_delay=2.0,
            verbose=True
        )
        
        assert client.base_url == 'http://custom:9000'
        assert client.timeout == 30
        assert client.max_retries == 5
        assert client.retry_delay == 2.0
        assert client.verbose is True
    
    def test_base_url_trailing_slash_removed(self):
        """Test that trailing slash is removed from base URL."""
        client = AuthClient(base_url='http://localhost:8080/')
        
        assert client.base_url == 'http://localhost:8080'


class TestAuthClientHeaders:
    """Tests for AuthClient header generation."""
    
    def test_headers_without_token(self):
        """Test headers without authorization token."""
        client = AuthClient()
        headers = client._get_headers()
        
        assert 'Content-Type' in headers
        assert headers['Content-Type'] == 'application/json'
        assert 'Authorization' not in headers
    
    def test_headers_with_token(self):
        """Test headers with authorization token."""
        client = AuthClient()
        headers = client._get_headers(token='test_token_123')
        
        assert headers['Content-Type'] == 'application/json'
        assert headers['Authorization'] == 'Bearer test_token_123'


class TestAuthClientTimeEndpoint:
    """Tests for the time endpoint."""
    
    @pytest.mark.timeout(10)
    @patch('requests.Session')
    def test_get_server_time_success(self, mock_session_class):
        """Test successful server time request."""
        mock_session = Mock()
        mock_response = Mock()
        mock_response.ok = True
        mock_response.status_code = 200
        mock_response.json.return_value = {'ms': 1704067200000}
        mock_session.get.return_value = mock_response
        mock_session_class.return_value = mock_session
        
        client = AuthClient()
        response = client.get_server_time()
        
        assert response.success is True
        assert response.status_code == 200
        assert response.data == {'ms': 1704067200000}
    
    @pytest.mark.timeout(10)
    @patch('requests.Session')
    def test_get_server_time_failure(self, mock_session_class):
        """Test failed server time request."""
        mock_session = Mock()
        mock_response = Mock()
        mock_response.ok = False
        mock_response.status_code = 500
        mock_response.json.return_value = {
            'status': 'error',
            'error': 'Internal server error'
        }
        mock_session.get.return_value = mock_response
        mock_session_class.return_value = mock_session
        
        client = AuthClient()
        response = client.get_server_time()
        
        assert response.success is False
        assert response.status_code == 500


class TestAuthClientMailLoginCode:
    """Tests for mail login code endpoints."""
    
    @pytest.mark.timeout(10)
    @patch('requests.Session')
    def test_send_mail_login_code_success(self, mock_session_class):
        """Test successful send mail login code request."""
        mock_session = Mock()
        mock_response = Mock()
        mock_response.ok = True
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'status': 'ok',
            'mailLoginToken': 'test_token_123'
        }
        mock_session.post.return_value = mock_response
        mock_session_class.return_value = mock_session
        
        client = AuthClient()
        response = client.send_mail_login_code(mail='test@example.com')
        
        assert response.success is True
        assert response.data['mailLoginToken'] == 'test_token_123'
    
    @pytest.mark.timeout(10)
    @patch('requests.Session')
    def test_send_mail_login_code_with_locale(self, mock_session_class):
        """Test send mail login code with locale."""
        mock_session = Mock()
        mock_response = Mock()
        mock_response.ok = True
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'status': 'ok',
            'mailLoginToken': 'test_token_123'
        }
        mock_session.post.return_value = mock_response
        mock_session_class.return_value = mock_session
        
        client = AuthClient()
        response = client.send_mail_login_code(
            mail='test@example.com',
            locale='en'
        )
        
        assert response.success is True
    
    @pytest.mark.timeout(10)
    @patch('requests.Session')
    def test_sign_in_by_mail_code_success(self, mock_session_class):
        """Test successful sign in by mail code request."""
        mock_session = Mock()
        mock_response = Mock()
        mock_response.ok = True
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'status': 'ok',
            'mailAuthToken': 'mail_auth_token_123'
        }
        mock_session.post.return_value = mock_response
        mock_session_class.return_value = mock_session
        
        client = AuthClient()
        response = client.sign_in_by_mail_code(
            mail_login_token='login_token_123',
            received_code='123456'
        )
        
        assert response.success is True
        assert response.data['mailAuthToken'] == 'mail_auth_token_123'


class TestAuthClientFamilyCreation:
    """Tests for family creation endpoints."""
    
    @pytest.mark.timeout(10)
    @patch('requests.Session')
    def test_create_family_success(self, mock_session_class):
        """Test successful create family request."""
        mock_session = Mock()
        mock_response = Mock()
        mock_response.ok = True
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'status': 'ok',
            'deviceAuthToken': 'device_token_123',
            'ownDeviceId': 'device_abc123'
        }
        mock_session.post.return_value = mock_response
        mock_session_class.return_value = mock_session
        
        client = AuthClient()
        response = client.create_family(
            mail_auth_token='mail_auth_token_123',
            parent_password={
                'hash': '$2b$12$hash1',
                'secondHash': '$2b$12$hash2',
                'secondSalt': '$2b$12$salt'
            }
        )
        
        assert response.success is True
        assert response.data['deviceAuthToken'] == 'device_token_123'
    
    @pytest.mark.timeout(10)
    @patch('requests.Session')
    def test_sign_in_into_family_success(self, mock_session_class):
        """Test successful sign in into family request."""
        mock_session = Mock()
        mock_response = Mock()
        mock_response.ok = True
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'status': 'ok',
            'deviceAuthToken': 'device_token_456',
            'ownDeviceId': 'device_xyz789'
        }
        mock_session.post.return_value = mock_response
        mock_session_class.return_value = mock_session
        
        client = AuthClient()
        response = client.sign_in_into_family(
            mail_auth_token='mail_auth_token_123',
            parent_password_second_hash='$2b$12$hash2'
        )
        
        assert response.success is True
        assert response.data['deviceAuthToken'] == 'device_token_456'


class TestAuthClientChildDevice:
    """Tests for child device endpoints."""
    
    @pytest.mark.timeout(10)
    @patch('requests.Session')
    def test_create_add_device_token_success(self, mock_session_class):
        """Test successful create add device token request."""
        mock_session = Mock()
        mock_response = Mock()
        mock_response.ok = True
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'status': 'ok',
            'token': 'register_token_123',
            'deviceId': 'device_child123'
        }
        mock_session.post.return_value = mock_response
        mock_session_class.return_value = mock_session
        
        client = AuthClient()
        response = client.create_add_device_token(
            device_auth_token='device_token_123',
            parent_password_second_hash='$2b$12$hash2'
        )
        
        assert response.success is True
        assert response.data['token'] == 'register_token_123'
    
    @pytest.mark.timeout(10)
    @patch('requests.Session')
    def test_add_device_success(self, mock_session_class):
        """Test successful add device request."""
        mock_session = Mock()
        mock_response = Mock()
        mock_response.ok = True
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'status': 'ok',
            'deviceAuthToken': 'child_device_token',
            'ownDeviceId': 'device_child456'
        }
        mock_session.post.return_value = mock_response
        mock_session_class.return_value = mock_session
        
        client = AuthClient()
        response = client.add_device(
            register_token='register_token_123',
            device_name='Child Device',
            device_model='Pixel 7'
        )
        
        assert response.success is True
        assert response.data['deviceAuthToken'] == 'child_device_token'


class TestAuthClientErrorHandling:
    """Tests for error handling."""
    
    @pytest.mark.timeout(10)
    @patch('requests.Session')
    def test_timeout_error(self, mock_session_class):
        """Test handling of timeout error."""
        mock_session = Mock()
        mock_session.get.side_effect = Timeout('Connection timed out')
        mock_session_class.return_value = mock_session
        
        client = AuthClient()
        response = client.get_server_time()
        
        assert response.success is False
        assert response.error_code == 'timeout'
        assert 'timed out' in response.error_message.lower()
    
    @pytest.mark.timeout(10)
    @patch('requests.Session')
    def test_connection_error(self, mock_session_class):
        """Test handling of connection error."""
        mock_session = Mock()
        mock_session.get.side_effect = ConnectionError('Connection refused')
        mock_session_class.return_value = mock_session
        
        client = AuthClient()
        response = client.get_server_time()
        
        assert response.success is False
        assert response.error_code == 'unreachable'
    
    @pytest.mark.timeout(10)
    @patch('requests.Session')
    def test_invalid_json_response(self, mock_session_class):
        """Test handling of invalid JSON response."""
        mock_session = Mock()
        mock_response = Mock()
        mock_response.ok = True
        mock_response.status_code = 200
        mock_response.json.side_effect = json.JSONDecodeError('Invalid JSON', '', 0)
        mock_response.content = b'Not JSON'
        mock_session.get.return_value = mock_response
        mock_session_class.return_value = mock_session
        
        client = AuthClient()
        response = client.get_server_time()
        
        assert response.success is True
        assert response.data == b'Not JSON'


class TestAuthClientRetry:
    """Tests for retry logic."""
    
    @pytest.mark.timeout(10)
    @patch('requests.Session')
    def test_retry_on_timeout(self, mock_session_class):
        """Test retry on timeout."""
        # First call times out, second succeeds
        mock_session = Mock()
        mock_response = Mock()
        mock_response.ok = True
        mock_response.status_code = 200
        mock_response.json.return_value = {'ms': 1704067200000}
        
        mock_session.get.side_effect = [
            Timeout('Connection timed out'),
            mock_response
        ]
        mock_session_class.return_value = mock_session
        
        client = AuthClient(max_retries=3, retry_delay=0.1)
        response = client.get_server_time()
        
        assert response.success is True
        assert mock_session.get.call_count == 2
    
    @pytest.mark.timeout(10)
    @patch('requests.Session')
    def test_no_retry_on_server_error(self, mock_session_class):
        """Test no retry on server error (500)."""
        mock_session = Mock()
        mock_response = Mock()
        mock_response.ok = False
        mock_response.status_code = 500
        mock_response.json.return_value = {'error': 'Internal server error'}
        mock_session.get.return_value = mock_response
        mock_session_class.return_value = mock_session
        
        client = AuthClient(max_retries=3)
        response = client.get_server_time()
        
        assert response.success is False
        assert mock_session.get.call_count == 1


class TestAuthClientConvenienceFunctions:
    """Tests for convenience functions."""
    
    def test_create_auth_client(self):
        """Test create_auth_client function."""
        client = create_auth_client(
            base_url='http://test:8080',
            timeout=5
        )
        
        assert client.base_url == 'http://test:8080'
        assert client.timeout == 5
    
    def test_get_auth_client_returns_same_instance(self):
        """Test that get_auth_client returns the same instance."""
        reset_auth_client()
        
        client1 = get_auth_client()
        client2 = get_auth_client()
        
        assert client1 is client2
        
        reset_auth_client()
    
    def test_reset_auth_client(self):
        """Test reset_auth_client function."""
        client1 = get_auth_client()
        reset_auth_client()
        client2 = get_auth_client()
        
        assert client1 is not client2


class TestAuthClientSession:
    """Tests for session management."""
    
    def test_session_created(self):
        """Test that requests session is created."""
        client = AuthClient()
        
        assert client.session is not None
    
    def test_close_session(self):
        """Test closing the session."""
        client = AuthClient()
        client.close()
        
        # Session should be closed but not raise an error
        assert client.session is not None


class TestAuthClientLogging:
    """Tests for logging functionality."""
    
    def test_verbose_logging(self):
        """Test verbose logging flag."""
        client = AuthClient(verbose=True)
        
        assert client.verbose is True
    
    def test_non_verbose_logging(self):
        """Test non-verbose logging flag."""
        client = AuthClient(verbose=False)
        
        assert client.verbose is False


class TestAuthClientRequestMethods:
    """Tests for HTTP request methods."""
    
    @pytest.mark.timeout(10)
    @patch('requests.Session')
    def test_post_request(self, mock_session_class):
        """Test POST request method."""
        mock_session = Mock()
        mock_response = Mock()
        mock_response.ok = True
        mock_response.status_code = 200
        mock_response.json.return_value = {'status': 'ok'}
        mock_session.post.return_value = mock_response
        mock_session_class.return_value = mock_session
        
        client = AuthClient()
        response = client._make_request('POST', '/test', data={'key': 'value'})
        
        assert response.success is True
        mock_session.post.assert_called_once()
    
    @pytest.mark.timeout(10)
    @patch('requests.Session')
    def test_get_request(self, mock_session_class):
        """Test GET request method."""
        mock_session = Mock()
        mock_response = Mock()
        mock_response.ok = True
        mock_response.status_code = 200
        mock_response.json.return_value = {'status': 'ok'}
        mock_session.get.return_value = mock_response
        mock_session_class.return_value = mock_session
        
        client = AuthClient()
        response = client._make_request('GET', '/test')
        
        assert response.success is True
        mock_session.get.assert_called_once()
    
    @pytest.mark.timeout(10)
    def test_unsupported_method(self):
        """Test unsupported HTTP method."""
        client = AuthClient()
        
        with pytest.raises(ValueError, match='Unsupported HTTP method'):
            client._make_request('DELETE', '/test')


class TestAuthClientIntegration:
    """Integration tests for AuthClient."""
    
    @pytest.mark.timeout(10)
    @patch('requests.Session')
    def test_complete_auth_flow(self, mock_session_class):
        """Test complete authentication flow."""
        # Mock responses for each step
        mock_session = Mock()
        
        mock_send_code = Mock()
        mock_send_code.ok = True
        mock_send_code.status_code = 200
        mock_send_code.json.return_value = {
            'status': 'ok',
            'mailLoginToken': 'login_token_123'
        }
        
        mock_sign_in = Mock()
        mock_sign_in.ok = True
        mock_sign_in.status_code = 200
        mock_sign_in.json.return_value = {
            'status': 'ok',
            'mailAuthToken': 'mail_auth_123'
        }
        
        mock_create_family = Mock()
        mock_create_family.ok = True
        mock_create_family.status_code = 200
        mock_create_family.json.return_value = {
            'status': 'ok',
            'deviceAuthToken': 'device_token_123',
            'ownDeviceId': 'device_abc'
        }
        
        mock_session.post.side_effect = [
            mock_send_code,
            mock_sign_in,
            mock_create_family
        ]
        mock_session_class.return_value = mock_session
        
        client = AuthClient()
        
        # Step 1: Send mail login code
        response1 = client.send_mail_login_code(mail='test@example.com')
        assert response1.success is True
        assert response1.data['mailLoginToken'] == 'login_token_123'
        
        # Step 2: Sign in by mail code
        response2 = client.sign_in_by_mail_code(
            mail_login_token='login_token_123',
            received_code='123456'
        )
        assert response2.success is True
        assert response2.data['mailAuthToken'] == 'mail_auth_123'
        
        # Step 3: Create family
        response3 = client.create_family(
            mail_auth_token='mail_auth_123',
            parent_password={
                'hash': '$2b$12$hash1',
                'secondHash': '$2b$12$hash2',
                'secondSalt': '$2b$12$salt'
            }
        )
        assert response3.success is True
        assert response3.data['deviceAuthToken'] == 'device_token_123'