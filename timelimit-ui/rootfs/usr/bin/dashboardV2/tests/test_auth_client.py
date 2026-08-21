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
        
        assert client.base_url == 'http://127.0.0.1:8081'
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
        response = client.send_mail_login_code(mail='test@example.com', locale='en')
        
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
            },
            parent_device={'model': 'Pixel 7'},
            device_name='Parent Device',
            time_zone='Europe/Amsterdam',
            parent_name='Parent User'
        )
        
        assert response.success is True
        assert response.data['deviceAuthToken'] == 'device_token_123'
    
    @pytest.mark.timeout(10)
    @patch('requests.Session')
    def test_create_family_rest_success(self, mock_session_class):
        """Test successful create family REST endpoint request."""
        mock_session = Mock()
        mock_response = Mock()
        mock_response.ok = True
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'status': 'ok',
            'deviceAuthToken': 'device_token_rest',
            'ownDeviceId': 'device_rest456'
        }
        mock_session.post.return_value = mock_response
        mock_session_class.return_value = mock_session
        
        client = AuthClient()
        response = client.create_family_rest(
            mail_auth_token='mail_auth_token_123',
            parent_password={
                'hash': '$2b$12$hash1',
                'secondHash': '$2b$12$hash2',
                'secondSalt': '$2b$12$salt'
            },
            parent_device={'model': 'Pixel 7'},
            device_name='Parent Device',
            time_zone='Europe/Amsterdam',
            parent_name='Parent User',
            locale='en'
        )
        
        assert response.success is True
        assert response.data['deviceAuthToken'] == 'device_token_rest'
        assert response.data['ownDeviceId'] == 'device_rest456'
    
    @pytest.mark.timeout(10)
    @patch('requests.Session')
    def test_create_family_rest_with_minimal_fields(self, mock_session_class):
        """Test create family REST endpoint with minimal required fields."""
        mock_session = Mock()
        mock_response = Mock()
        mock_response.ok = True
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'status': 'ok',
            'deviceAuthToken': 'device_token_minimal',
            'ownDeviceId': 'device_minimal123'
        }
        mock_session.post.return_value = mock_response
        mock_session_class.return_value = mock_session
        
        client = AuthClient()
        response = client.create_family_rest(
            mail_auth_token='mail_auth_token_123',
            parent_password={
                'hash': '$2b$12$hash1',
                'secondHash': '$2b$12$hash2',
                'secondSalt': '$2b$12$salt'
            },
            parent_device={'model': 'Pixel 7'},
            device_name='Parent Device',
            time_zone='Europe/Amsterdam',
            parent_name='Parent User'
        )
        
        assert response.success is True
        assert response.data['deviceAuthToken'] == 'device_token_minimal'

    # ========================================================================
    # Success Cases for create_family_rest
    # ========================================================================

    @pytest.mark.timeout(10)
    @patch('requests.Session')
    def test_create_family_rest_returns_device_auth_token(self, mock_session_class):
        """Test that create_family_rest returns deviceAuthToken in response."""
        mock_session = Mock()
        mock_response = Mock()
        mock_response.ok = True
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'status': 'ok',
            'deviceAuthToken': 'device_token_abc123',
            'ownDeviceId': 'device_xyz789'
        }
        mock_session.post.return_value = mock_response
        mock_session_class.return_value = mock_session
        
        client = AuthClient()
        response = client.create_family_rest(
            mail_auth_token='mail_auth_token_123',
            parent_password={
                'hash': '$2b$12$hash1',
                'secondHash': '$2b$12$hash2',
                'secondSalt': '$2b$12$salt'
            },
            parent_device={'model': 'Pixel 7'},
            device_name='Parent Device',
            time_zone='Europe/Amsterdam',
            parent_name='Parent User'
        )
        
        assert response.success is True
        assert 'deviceAuthToken' in response.data
        assert response.data['deviceAuthToken'] == 'device_token_abc123'

    @pytest.mark.timeout(10)
    @patch('requests.Session')
    def test_create_family_rest_returns_own_device_id(self, mock_session_class):
        """Test that create_family_rest returns ownDeviceId in response."""
        mock_session = Mock()
        mock_response = Mock()
        mock_response.ok = True
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'status': 'ok',
            'deviceAuthToken': 'device_token_abc123',
            'ownDeviceId': 'device_xyz789'
        }
        mock_session.post.return_value = mock_response
        mock_session_class.return_value = mock_session
        
        client = AuthClient()
        response = client.create_family_rest(
            mail_auth_token='mail_auth_token_123',
            parent_password={
                'hash': '$2b$12$hash1',
                'secondHash': '$2b$12$hash2',
                'secondSalt': '$2b$12$salt'
            },
            parent_device={'model': 'Pixel 7'},
            device_name='Parent Device',
            time_zone='Europe/Amsterdam',
            parent_name='Parent User'
        )
        
        assert response.success is True
        assert 'ownDeviceId' in response.data
        assert response.data['ownDeviceId'] == 'device_xyz789'

    @pytest.mark.timeout(10)
    @patch('requests.Session')
    def test_create_family_rest_returns_initial_data(self, mock_session_class):
        """Test that create_family_rest returns initial server data in response."""
        mock_session = Mock()
        mock_response = Mock()
        mock_response.ok = True
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'status': 'ok',
            'deviceAuthToken': 'device_token_abc123',
            'ownDeviceId': 'device_xyz789',
            'initialData': {
                'serverTime': 1704067200000,
                'familyId': 'family_abc123',
                'devices': []
            }
        }
        mock_session.post.return_value = mock_response
        mock_session_class.return_value = mock_session
        
        client = AuthClient()
        response = client.create_family_rest(
            mail_auth_token='mail_auth_token_123',
            parent_password={
                'hash': '$2b$12$hash1',
                'secondHash': '$2b$12$hash2',
                'secondSalt': '$2b$12$salt'
            },
            parent_device={'model': 'Pixel 7'},
            device_name='Parent Device',
            time_zone='Europe/Amsterdam',
            parent_name='Parent User'
        )
        
        assert response.success is True
        assert 'initialData' in response.data
        assert response.data['initialData']['serverTime'] == 1704067200000
        assert response.data['initialData']['familyId'] == 'family_abc123'

    # ========================================================================
    # Validation Error Tests for create_family_rest
    # ========================================================================

    @pytest.mark.timeout(10)
    @patch('requests.Session')
    def test_create_family_rest_missing_mail_auth_token(self, mock_session_class):
        """Test create_family_rest fails when mailAuthToken is missing."""
        mock_session = Mock()
        mock_response = Mock()
        mock_response.ok = False
        mock_response.status_code = 400
        mock_response.json.return_value = {
            'status': 'error',
            'error': 'Missing mailAuthToken'
        }
        mock_session.post.return_value = mock_response
        mock_session_class.return_value = mock_session
        
        client = AuthClient()
        response = client.create_family_rest(
            mail_auth_token=None,
            parent_password={
                'hash': '$2b$12$hash1',
                'secondHash': '$2b$12$hash2',
                'secondSalt': '$2b$12$salt'
            },
            parent_device={'model': 'Pixel 7'},
            device_name='Parent Device',
            time_zone='Europe/Amsterdam',
            parent_name='Parent User'
        )
        
        assert response.success is False
        assert response.status_code == 400

    @pytest.mark.timeout(10)
    @patch('requests.Session')
    def test_create_family_rest_missing_parent_password(self, mock_session_class):
        """Test create_family_rest fails when parentPassword is missing."""
        mock_session = Mock()
        mock_response = Mock()
        mock_response.ok = False
        mock_response.status_code = 400
        mock_response.json.return_value = {
            'status': 'error',
            'error': 'Missing parentPassword'
        }
        mock_session.post.return_value = mock_response
        mock_session_class.return_value = mock_session
        
        client = AuthClient()
        response = client.create_family_rest(
            mail_auth_token='mail_auth_token_123',
            parent_password=None,
            parent_device={'model': 'Pixel 7'},
            device_name='Parent Device',
            time_zone='Europe/Amsterdam',
            parent_name='Parent User'
        )
        
        assert response.success is False
        assert response.status_code == 400

    @pytest.mark.timeout(10)
    @patch('requests.Session')
    def test_create_family_rest_missing_hash(self, mock_session_class):
        """Test create_family_rest fails when hash is missing in parentPassword."""
        mock_session = Mock()
        mock_response = Mock()
        mock_response.ok = False
        mock_response.status_code = 400
        mock_response.json.return_value = {
            'status': 'error',
            'error': 'Missing hash in parentPassword'
        }
        mock_session.post.return_value = mock_response
        mock_session_class.return_value = mock_session
        
        client = AuthClient()
        response = client.create_family_rest(
            mail_auth_token='mail_auth_token_123',
            parent_password={
                'secondHash': '$2b$12$hash2',
                'secondSalt': '$2b$12$salt'
            },
            parent_device={'model': 'Pixel 7'},
            device_name='Parent Device',
            time_zone='Europe/Amsterdam',
            parent_name='Parent User'
        )
        
        assert response.success is False
        assert response.status_code == 400

    @pytest.mark.timeout(10)
    @patch('requests.Session')
    def test_create_family_rest_missing_second_hash(self, mock_session_class):
        """Test create_family_rest fails when secondHash is missing in parentPassword."""
        mock_session = Mock()
        mock_response = Mock()
        mock_response.ok = False
        mock_response.status_code = 400
        mock_response.json.return_value = {
            'status': 'error',
            'error': 'Missing secondHash in parentPassword'
        }
        mock_session.post.return_value = mock_response
        mock_session_class.return_value = mock_session
        
        client = AuthClient()
        response = client.create_family_rest(
            mail_auth_token='mail_auth_token_123',
            parent_password={
                'hash': '$2b$12$hash1',
                'secondSalt': '$2b$12$salt'
            },
            parent_device={'model': 'Pixel 7'},
            device_name='Parent Device',
            time_zone='Europe/Amsterdam',
            parent_name='Parent User'
        )
        
        assert response.success is False
        assert response.status_code == 400

    @pytest.mark.timeout(10)
    @patch('requests.Session')
    def test_create_family_rest_missing_second_salt(self, mock_session_class):
        """Test create_family_rest fails when secondSalt is missing in parentPassword."""
        mock_session = Mock()
        mock_response = Mock()
        mock_response.ok = False
        mock_response.status_code = 400
        mock_response.json.return_value = {
            'status': 'error',
            'error': 'Missing secondSalt in parentPassword'
        }
        mock_session.post.return_value = mock_response
        mock_session_class.return_value = mock_session
        
        client = AuthClient()
        response = client.create_family_rest(
            mail_auth_token='mail_auth_token_123',
            parent_password={
                'hash': '$2b$12$hash1',
                'secondHash': '$2b$12$hash2'
            },
            parent_device={'model': 'Pixel 7'},
            device_name='Parent Device',
            time_zone='Europe/Amsterdam',
            parent_name='Parent User'
        )
        
        assert response.success is False
        assert response.status_code == 400

    @pytest.mark.timeout(10)
    @patch('requests.Session')
    def test_create_family_rest_missing_encrypted(self, mock_session_class):
        """Test create_family_rest succeeds when encrypted is missing (not required by server)."""
        mock_session = Mock()
        mock_response = Mock()
        mock_response.ok = True
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'status': 'ok',
            'deviceAuthToken': 'device_token_no_encrypted',
            'ownDeviceId': 'device_no_encrypted123'
        }
        mock_session.post.return_value = mock_response
        mock_session_class.return_value = mock_session
        
        client = AuthClient()
        response = client.create_family_rest(
            mail_auth_token='mail_auth_token_123',
            parent_password={
                'hash': '$2b$12$hash1',
                'secondHash': '$2b$12$hash2',
                'secondSalt': '$2b$12$salt'
            },
            parent_device={'model': 'Pixel 7'},
            device_name='Parent Device',
            time_zone='Europe/Amsterdam',
            parent_name='Parent User'
        )
        
        assert response.success is True
        assert response.status_code == 200

    # ========================================================================
    # Edge Cases for create_family_rest
    # ========================================================================

    @pytest.mark.timeout(10)
    @patch('requests.Session')
    def test_create_family_rest_invalid_mail_auth_token(self, mock_session_class):
        """Test create_family_rest fails with invalid/expired mailAuthToken."""
        mock_session = Mock()
        mock_response = Mock()
        mock_response.ok = False
        mock_response.status_code = 401
        mock_response.json.return_value = {
            'status': 'error',
            'error_code': 'unauthorized',
            'error_message': 'Invalid or expired token'
        }
        mock_session.post.return_value = mock_response
        mock_session_class.return_value = mock_session
        
        client = AuthClient()
        response = client.create_family_rest(
            mail_auth_token='invalid_token_xyz',
            parent_password={
                'hash': '$2b$12$hash1',
                'secondHash': '$2b$12$hash2',
                'secondSalt': '$2b$12$salt'
            },
            parent_device={'model': 'Pixel 7'},
            device_name='Parent Device',
            time_zone='Europe/Amsterdam',
            parent_name='Parent User'
        )
        
        assert response.success is False
        assert response.status_code == 401
        assert response.error_code == 'unauthorized'

    @pytest.mark.timeout(10)
    @patch('requests.Session')
    def test_create_family_rest_family_already_exists(self, mock_session_class):
        """Test create_family_rest fails when family already exists for email."""
        mock_session = Mock()
        mock_response = Mock()
        mock_response.ok = False
        mock_response.status_code = 401
        mock_response.json.return_value = {
            'status': 'error',
            'error_code': 'family_exists',
            'error_message': 'Family already exists for this email'
        }
        mock_session.post.return_value = mock_response
        mock_session_class.return_value = mock_session
        
        client = AuthClient()
        response = client.create_family_rest(
            mail_auth_token='mail_auth_token_123',
            parent_password={
                'hash': '$2b$12$hash1',
                'secondHash': '$2b$12$hash2',
                'secondSalt': '$2b$12$salt'
            },
            parent_device={'model': 'Pixel 7'},
            device_name='Parent Device',
            time_zone='Europe/Amsterdam',
            parent_name='Parent User'
        )
        
        assert response.success is False
        assert response.status_code == 401
        assert response.error_code == 'family_exists'

    @pytest.mark.timeout(10)
    @patch('requests.Session')
    def test_create_family_rest_with_locale(self, mock_session_class):
        """Test create_family_rest with locale parameter."""
        mock_session = Mock()
        mock_response = Mock()
        mock_response.ok = True
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'status': 'ok',
            'deviceAuthToken': 'device_token_locale',
            'ownDeviceId': 'device_locale123'
        }
        mock_session.post.return_value = mock_response
        mock_session_class.return_value = mock_session
        
        client = AuthClient()
        response = client.create_family_rest(
            mail_auth_token='mail_auth_token_123',
            parent_password={
                'hash': '$2b$12$hash1',
                'secondHash': '$2b$12$hash2',
                'secondSalt': '$2b$12$salt'
            },
            parent_device={'model': 'Pixel 7'},
            device_name='Parent Device',
            time_zone='Europe/Amsterdam',
            parent_name='Parent User',
            locale='nl_NL'
        )
        
        assert response.success is True
        assert response.data['deviceAuthToken'] == 'device_token_locale'

    @pytest.mark.timeout(10)
    @patch('requests.Session')
    def test_create_family_rest_with_device_name(self, mock_session_class):
        """Test create_family_rest with deviceName parameter."""
        mock_session = Mock()
        mock_response = Mock()
        mock_response.ok = True
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'status': 'ok',
            'deviceAuthToken': 'device_token_name',
            'ownDeviceId': 'device_name123'
        }
        mock_session.post.return_value = mock_response
        mock_session_class.return_value = mock_session
        
        client = AuthClient()
        response = client.create_family_rest(
            mail_auth_token='mail_auth_token_123',
            parent_password={
                'hash': '$2b$12$hash1',
                'secondHash': '$2b$12$hash2',
                'secondSalt': '$2b$12$salt'
            },
            parent_device={'model': 'Pixel 7'},
            device_name='Parent Device',
            time_zone='Europe/Amsterdam',
            parent_name='Parent User'
        )
        
        assert response.success is True
        assert response.data['deviceAuthToken'] == 'device_token_name'

    @pytest.mark.timeout(10)
    @patch('requests.Session')
    def test_create_family_rest_with_device_model(self, mock_session_class):
        """Test create_family_rest with deviceModel parameter."""
        mock_session = Mock()
        mock_response = Mock()
        mock_response.ok = True
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'status': 'ok',
            'deviceAuthToken': 'device_token_model',
            'ownDeviceId': 'device_model123'
        }
        mock_session.post.return_value = mock_response
        mock_session_class.return_value = mock_session
        
        client = AuthClient()
        response = client.create_family_rest(
            mail_auth_token='mail_auth_token_123',
            parent_password={
                'hash': '$2b$12$hash1',
                'secondHash': '$2b$12$hash2',
                'secondSalt': '$2b$12$salt'
            },
            parent_device={'model': 'Pixel 7'},
            device_name='Parent Device',
            time_zone='Europe/Amsterdam',
            parent_name='Parent User'
        )
        
        assert response.success is True
        assert response.data['deviceAuthToken'] == 'device_token_model'

    @pytest.mark.timeout(10)
    @patch('requests.Session')
    def test_create_family_rest_empty_parent_password(self, mock_session_class):
        """Test create_family_rest fails with empty parentPassword object."""
        mock_session = Mock()
        mock_response = Mock()
        mock_response.ok = False
        mock_response.status_code = 400
        mock_response.json.return_value = {
            'status': 'error',
            'error': 'Invalid parentPassword: empty object'
        }
        mock_session.post.return_value = mock_response
        mock_session_class.return_value = mock_session
        
        client = AuthClient()
        response = client.create_family_rest(
            mail_auth_token='mail_auth_token_123',
            parent_password={},
            parent_device={'model': 'Pixel 7'},
            device_name='Parent Device',
            time_zone='Europe/Amsterdam',
            parent_name='Parent User'
        )
        
        assert response.success is False
        assert response.status_code == 400

    @pytest.mark.timeout(10)
    @patch('requests.Session')
    def test_create_family_rest_empty_string_mail_auth_token(self, mock_session_class):
        """Test create_family_rest fails with empty string mailAuthToken."""
        mock_session = Mock()
        mock_response = Mock()
        mock_response.ok = False
        mock_response.status_code = 400
        mock_response.json.return_value = {
            'status': 'error',
            'error': 'Invalid mailAuthToken: empty string'
        }
        mock_session.post.return_value = mock_response
        mock_session_class.return_value = mock_session
        
        client = AuthClient()
        response = client.create_family_rest(
            mail_auth_token='',
            parent_password={
                'hash': '$2b$12$hash1',
                'secondHash': '$2b$12$hash2',
                'secondSalt': '$2b$12$salt'
            },
            parent_device={'model': 'Pixel 7'},
            device_name='Parent Device',
            time_zone='Europe/Amsterdam',
            parent_name='Parent User'
        )
        
        assert response.success is False
        assert response.status_code == 400

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
        response1 = client.send_mail_login_code(mail='test@example.com', locale='en')
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
            },
            parent_device={'model': 'Pixel 7'},
            device_name='Parent Device',
            time_zone='Europe/Amsterdam',
            parent_name='Parent User'
        )
        assert response3.success is True
        assert response3.data['deviceAuthToken'] == 'device_token_123'


class TestAuthClientSync:
    """Tests for sync protocol endpoints."""
    
    @pytest.mark.timeout(10)
    @patch('requests.Session')
    def test_pull_status_success(self, mock_session_class):
        """Test successful pull_status request."""
        mock_session = Mock()
        mock_response = Mock()
        mock_response.ok = True
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'status': 'ok',
            'devices': {
                'version': 'v1',
                'data': [
                    {'deviceId': 'device1', 'name': 'Phone', 'model': 'Pixel 7'},
                    {'deviceId': 'device2', 'name': 'Tablet', 'model': 'iPad'}
                ]
            },
            'users': {
                'version': 'v1',
                'data': [
                    {'id': 'user1', 'name': 'Parent', 'type': 'parent', 'mail': 'parent@example.com'},
                    {'id': 'user2', 'name': 'Child', 'type': 'child', 'mail': 'child@example.com'}
                ]
            },
            'categoryBase': [
                {'id': 'cat1', 'title': 'Work', 'childId': 'user2'}
            ],
            'devices2': [
                {'deviceId': 'device1'},
                {'deviceId': 'device2'}
            ]
        }
        mock_session.post.return_value = mock_response
        mock_session_class.return_value = mock_session
        
        client = AuthClient()
        response = client.pull_status(
            device_auth_token='device_token_123'
        )
        
        assert response.success is True
        assert response.status_code == 200
        assert 'devices' in response.data
        assert 'users' in response.data
        assert len(response.data['devices']['data']) == 2
        assert len(response.data['users']['data']) == 2
    
    @pytest.mark.timeout(10)
    @patch('requests.Session')
    def test_pull_status_with_client_status(self, mock_session_class):
        """Test pull_status with existing client status."""
        mock_session = Mock()
        mock_response = Mock()
        mock_response.ok = True
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'status': 'ok',
            'devices': {'version': 'v2', 'data': []},
            'users': {'version': 'v2', 'data': []},
            'categoryBase': []
        }
        mock_session.post.return_value = mock_response
        mock_session_class.return_value = mock_session
        
        client = AuthClient()
        # Use the correct format matching Android app's ClientDataStatus
        client_status = {
            'clientLevel': 7,
            'devices': 'v1',
            'users': 'v1',
            'apps': {},
            'categories': {}
        }
        response = client.pull_status(
            device_auth_token='device_token_123',
            client_data_status=client_status
        )
        
        assert response.success is True
    
    @pytest.mark.timeout(10)
    @patch('requests.Session')
    def test_pull_status_empty_client_data_status_format(self, mock_session_class):
        """Test that pull_status sends correct empty ClientDataStatus format.
        
        The empty status format must match Android app's ClientDataStatus.empty:
        - devices and users are empty strings (not null)
        - Optional fields (devicesDetail, kri, kr, dh, u2f) are omitted
        """
        mock_session = Mock()
        mock_response = Mock()
        mock_response.ok = True
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'status': 'ok',
            'devices': {'version': 'v1', 'data': []},
            'users': {'version': 'v1', 'data': []},
            'categoryBase': []
        }
        mock_session.post.return_value = mock_response
        mock_session_class.return_value = mock_session
        
        client = AuthClient()
        response = client.pull_status(device_auth_token='device_token_123')
        
        assert response.success is True
        
        # Verify the request body contains the correct format
        call_args = mock_session.post.call_args
        import json
        import gzip
        
        # Get the gzipped request body
        request_body = call_args.kwargs['data']
        if 'Content-Encoding' in call_args.kwargs.get('headers', {}):
            # Decompress and parse JSON
            decompressed = gzip.decompress(request_body)
            request_data = json.loads(decompressed.decode('utf-8'))
        else:
            request_data = json.loads(request_body.decode('utf-8') if isinstance(request_body, bytes) else request_body)
        
        # Verify the status field has the correct format
        status = request_data.get('status', {})
        assert status['clientLevel'] == 7
        assert status['devices'] == ""
        assert status['users'] == ""
        assert status['apps'] == {}
        assert status['categories'] == {}
        # Optional fields should be omitted
        assert 'devicesDetail' not in status
        assert 'kri' not in status
        assert 'kr' not in status
        assert 'dh' not in status
        assert 'u2f' not in status
    
    @pytest.mark.timeout(10)
    @patch('requests.Session')
    def test_pull_status_failure(self, mock_session_class):
        """Test failed pull_status request."""
        mock_session = Mock()
        mock_response = Mock()
        mock_response.ok = False
        mock_response.status_code = 401
        mock_response.json.return_value = {
            'status': 'error',
            'error_code': 'unauthorized',
            'error_message': 'Invalid or expired token'
        }
        mock_session.post.return_value = mock_response
        mock_session_class.return_value = mock_session
        
        client = AuthClient()
        response = client.pull_status(
            device_auth_token='invalid_token'
        )
        
        assert response.success is False
        assert response.error_code == 'unauthorized'
    
    @pytest.mark.timeout(10)
    @patch('requests.Session')
    def test_pull_status_uses_gzip(self, mock_session_class):
        """Test that pull_status uses gzip compression."""
        mock_session = Mock()
        mock_response = Mock()
        mock_response.ok = True
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'status': 'ok',
            'devices': {'version': 'v1', 'data': []},
            'users': {'version': 'v1', 'data': []},
            'categoryBase': []
        }
        mock_session.post.return_value = mock_response
        mock_session_class.return_value = mock_session
        
        client = AuthClient()
        response = client.pull_status(device_auth_token='device_token_123')
        
        assert response.success is True
        # Verify POST was called with gzip compression
        call_args = mock_session.post.call_args
        assert 'Content-Encoding' in call_args.kwargs['headers']
        assert call_args.kwargs['headers']['Content-Encoding'] == 'gzip'
    
    @pytest.mark.timeout(10)
    @patch('requests.Session')
    def test_push_actions_success(self, mock_session_class):
        """Test successful push_actions request."""
        mock_session = Mock()
        mock_response = Mock()
        mock_response.ok = True
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'status': 'ok',
            'shouldDoFullSync': False
        }
        mock_session.post.return_value = mock_response
        mock_session_class.return_value = mock_session
        
        client = AuthClient()
        actions = [
            {
                'encodedAction': 'action1',
                'sequenceNumber': 1,
                'integrity': 'hash1',
                'type': 'type1',
                'userId': 'user1'
            }
        ]
        response = client.push_actions(
            device_auth_token='device_token_123',
            actions=actions
        )
        
        assert response.success is True
        assert response.data['shouldDoFullSync'] is False
    
    @pytest.mark.timeout(10)
    @patch('requests.Session')
    def test_push_actions_uses_gzip(self, mock_session_class):
        """Test that push_actions uses gzip compression."""
        mock_session = Mock()
        mock_response = Mock()
        mock_response.ok = True
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'status': 'ok',
            'shouldDoFullSync': False
        }
        mock_session.post.return_value = mock_response
        mock_session_class.return_value = mock_session
        
        client = AuthClient()
        actions = [
            {
                'encodedAction': 'action1',
                'sequenceNumber': 1,
                'integrity': 'hash1',
                'type': 'type1',
                'userId': 'user1'
            }
        ]
        response = client.push_actions(
            device_auth_token='device_token_123',
            actions=actions
        )
        
        assert response.success is True
        # Verify POST was called with gzip compression
        call_args = mock_session.post.call_args
        assert 'Content-Encoding' in call_args.kwargs['headers']
        assert call_args.kwargs['headers']['Content-Encoding'] == 'gzip'
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
        response1 = client.send_mail_login_code(mail='test@example.com', locale='en')
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
            },
            parent_device={'model': 'Pixel 7'},
            device_name='Parent Device',
            time_zone='Europe/Amsterdam',
            parent_name='Parent User'
        )
        assert response3.success is True
        assert response3.data['deviceAuthToken'] == 'device_token_123'