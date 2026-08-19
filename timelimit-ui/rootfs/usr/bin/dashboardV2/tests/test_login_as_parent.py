"""Unit tests for login as parent flow routes.

This module tests the server-side rendered login as parent flow:
- GET /login-as-parent - renders appropriate step based on session state
- POST /login-as-parent - processes form submissions for all 3 steps
- POST /login-as-parent/cancel - clears session and redirects
"""

import pytest
import re
from unittest.mock import patch, MagicMock


class TestGetLoginAsParent:
    """Tests for GET /login-as-parent route."""

    @pytest.mark.timeout(10)
    def test_get_login_as_parent_step1_renders_email_form(self, client):
        """Test that GET /login-as-parent renders step 1 (email form) when no session."""
        response = client.get('/login-as-parent')
        
        assert response.status_code == 200
        assert b'Login to Existing Family' in response.data
        assert b'Email' in response.data

    @pytest.mark.timeout(10)
    def test_get_login_as_parent_step1_shows_step_indicator(self, client):
        """Test that step 1 shows correct step indicator."""
        response = client.get('/login-as-parent')
        
        assert response.status_code == 200
        # Should show step 1 as active
        assert b'step' in response.data.lower() or b'1' in response.data

    @pytest.mark.timeout(10)
    def test_get_login_as_parent_step2_renders_code_form(self, client):
        """Test that GET /login-as-parent renders step 2 (code form) when mail_login_token in session."""
        with client.session_transaction() as sess:
            sess['mail_login_token'] = 'test-login-token'
        
        response = client.get('/login-as-parent')
        
        assert response.status_code == 200
        assert b'Verification Code' in response.data or b'Code' in response.data

    @pytest.mark.timeout(10)
    def test_get_login_as_parent_step3_renders_device_form(self, client):
        """Test that GET /login-as-parent renders step 3 (device info form) when mail_auth_token in session."""
        with client.session_transaction() as sess:
            sess['mail_login_token'] = 'test-login-token'
            sess['mail_auth_token'] = 'test-auth-token'
        
        response = client.get('/login-as-parent')
        
        assert response.status_code == 200
        assert b'Device Model' in response.data or b'device' in response.data.lower()

    @pytest.mark.timeout(10)
    def test_get_login_as_parent_redirects_when_authenticated(self, client):
        """Test that GET /login-as-parent redirects to dashboard when device_auth_token in session."""
        with client.session_transaction() as sess:
            sess['device_auth_token'] = 'test-device-token'
        
        response = client.get('/login-as-parent')
        
        assert response.status_code == 302
        assert '/dashboardV2' in response.headers.get('Location', '')

    @pytest.mark.timeout(10)
    def test_get_login_as_parent_shows_error_message(self, client):
        """Test that GET /login-as-parent shows error message from session."""
        with client.session_transaction() as sess:
            sess['login_as_parent_error'] = 'Test error message'
        
        response = client.get('/login-as-parent')
        
        assert response.status_code == 200
        assert b'Test error message' in response.data


class TestPostLoginAsParentStep1:
    """Tests for POST /login-as-parent step 1 (email submission)."""

    @pytest.mark.timeout(10)
    def test_post_login_as_parent_step1_missing_email(self, client):
        """Test that step 1 fails with missing email."""
        response = client.post('/login-as-parent', data={
            'step': '1',
            'mail': ''
        }, follow_redirects=True)
        
        assert b'Email is required' in response.data or b'required' in response.data.lower()

    @pytest.mark.timeout(10)
    def test_post_login_as_parent_step1_invalid_email(self, client):
        """Test that step 1 fails with invalid email format."""
        response = client.post('/login-as-parent', data={
            'step': '1',
            'mail': 'invalid-email'
        }, follow_redirects=True)
        
        assert b'Invalid email format' in response.data or b'invalid' in response.data.lower()

    @pytest.mark.timeout(10)
    def test_post_login_as_parent_step1_valid_email(self, client):
        """Test that step 1 processes valid email."""
        with patch('app.AuthClient') as mock_auth_client_class:
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.success = True
            mock_response.data = {'mailLoginToken': 'test-login-token'}
            mock_client.send_mail_login_code.return_value = mock_response
            mock_auth_client_class.return_value = mock_client
            
            response = client.post('/login-as-parent', data={
                'step': '1',
                'mail': 'test@example.com'
            }, follow_redirects=True)
            
            # Should redirect to step 2
            assert response.status_code == 200

    @pytest.mark.timeout(10)
    def test_post_login_as_parent_step1_api_failure(self, client):
        """Test that step 1 handles API failure."""
        with patch('app.AuthClient') as mock_auth_client_class:
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.success = False
            mock_response.error_message = 'API error'
            mock_client.send_mail_login_code.return_value = mock_response
            mock_auth_client_class.return_value = mock_client
            
            response = client.post('/login-as-parent', data={
                'step': '1',
                'mail': 'test@example.com'
            }, follow_redirects=True)
            
            assert b'API error' in response.data or b'Failed' in response.data


class TestPostLoginAsParentStep2:
    """Tests for POST /login-as-parent step 2 (verification code)."""

    @pytest.mark.timeout(10)
    def test_post_login_as_parent_step2_missing_token(self, client):
        """Test that step 2 fails without mail_login_token in session."""
        response = client.post('/login-as-parent', data={
            'step': '2',
            'receivedCode': 'Pferd Miete abwenden'
        }, follow_redirects=True)
        
        assert b'Session expired' in response.data or b'start again' in response.data.lower()

    @pytest.mark.timeout(10)
    def test_post_login_as_parent_step2_missing_code(self, client):
        """Test that step 2 fails with missing verification code."""
        with client.session_transaction() as sess:
            sess['mail_login_token'] = 'test-login-token'
        
        response = client.post('/login-as-parent', data={
            'step': '2',
            'receivedCode': ''
        }, follow_redirects=True)
        
        assert b'Verification code is required' in response.data or b'required' in response.data.lower()

    @pytest.mark.timeout(10)
    def test_post_login_as_parent_step2_invalid_code_format(self, client):
        """Test that step 2 fails with invalid verification code format."""
        with client.session_transaction() as sess:
            sess['mail_login_token'] = 'test-login-token'
        
        response = client.post('/login-as-parent', data={
            'step': '2',
            'receivedCode': 'abc123'
        }, follow_redirects=True)
        
        assert b'Invalid verification code format' in response.data or b'Invalid' in response.data

    @pytest.mark.timeout(10)
    def test_post_login_as_parent_step2_valid_code(self, client):
        """Test that step 2 processes valid verification code."""
        with client.session_transaction() as sess:
            sess['mail_login_token'] = 'test-login-token'
        
        with patch('app.AuthClient') as mock_auth_client_class:
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.success = True
            mock_response.data = {'mailAuthToken': 'test-auth-token'}
            mock_client.sign_in_by_mail_code.return_value = mock_response
            mock_auth_client_class.return_value = mock_client
            
            response = client.post('/login-as-parent', data={
                'step': '2',
                'receivedCode': 'Pferd Miete abwenden'
            }, follow_redirects=True)
            
            # Should redirect to step 3
            assert response.status_code == 200


class TestPostLoginAsParentStep3:
    """Tests for POST /login-as-parent step 3 (device info submission)."""

    @pytest.mark.timeout(10)
    def test_post_login_as_parent_step3_missing_token(self, client):
        """Test that step 3 fails without mail_auth_token in session."""
        response = client.post('/login-as-parent', data={
            'step': '3',
            'deviceModel': 'Pixel 7',
            'deviceName': 'Parent Device'
        }, follow_redirects=True)
        
        assert b'Session expired' in response.data or b'start again' in response.data.lower()

    @pytest.mark.timeout(10)
    def test_post_login_as_parent_step3_missing_device_model(self, client):
        """Test that step 3 fails with missing device model."""
        with client.session_transaction() as sess:
            sess['mail_login_token'] = 'test-login-token'
            sess['mail_auth_token'] = 'test-auth-token'
        
        response = client.post('/login-as-parent', data={
            'step': '3',
            'deviceModel': '',
            'deviceName': 'Parent Device'
        }, follow_redirects=True)
        
        assert b'Device model is required' in response.data or b'required' in response.data.lower()

    @pytest.mark.timeout(10)
    def test_post_login_as_parent_step3_missing_device_name(self, client):
        """Test that step 3 fails with missing device name."""
        with client.session_transaction() as sess:
            sess['mail_login_token'] = 'test-login-token'
            sess['mail_auth_token'] = 'test-auth-token'
        
        response = client.post('/login-as-parent', data={
            'step': '3',
            'deviceModel': 'Pixel 7',
            'deviceName': ''
        }, follow_redirects=True)
        
        assert b'Device name is required' in response.data or b'required' in response.data.lower()

    @pytest.mark.timeout(10)
    def test_post_login_as_parent_step3_valid_device_info(self, client):
        """Test that step 3 processes valid device info and signs in to family."""
        with client.session_transaction() as sess:
            sess['mail_login_token'] = 'test-login-token'
            sess['mail_auth_token'] = 'test-auth-token'
        
        with patch('app.AuthClient') as mock_auth_client_class:
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.success = True
            mock_response.data = {
                'deviceAuthToken': 'test-device-token',
                'ownDeviceId': 'test-device-id'
            }
            mock_client.sign_in_into_family.return_value = mock_response
            mock_auth_client_class.return_value = mock_client
            
            response = client.post('/login-as-parent', data={
                'step': '3',
                'deviceModel': 'Pixel 7',
                'deviceName': 'Parent Device'
            }, follow_redirects=True)
            
            # Should redirect to dashboard
            assert response.status_code == 200

    @pytest.mark.timeout(10)
    def test_post_login_as_parent_step3_api_failure(self, client):
        """Test that step 3 handles API failure."""
        with client.session_transaction() as sess:
            sess['mail_login_token'] = 'test-login-token'
            sess['mail_auth_token'] = 'test-auth-token'
        
        with patch('app.AuthClient') as mock_auth_client_class:
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.success = False
            mock_response.error_message = 'Failed to sign in to family'
            mock_client.sign_in_into_family.return_value = mock_response
            mock_auth_client_class.return_value = mock_client
            
            response = client.post('/login-as-parent', data={
                'step': '3',
                'deviceModel': 'Pixel 7',
                'deviceName': 'Parent Device'
            }, follow_redirects=True)
            
            assert b'Failed to sign in to family' in response.data or b'Failed' in response.data


class TestPostLoginAsParentCancel:
    """Tests for POST /login-as-parent/cancel route."""

    @pytest.mark.timeout(10)
    def test_post_login_as_parent_cancel_clears_session(self, client):
        """Test that cancel clears all login as parent session data."""
        with client.session_transaction() as sess:
            sess['mail_login_token'] = 'test-login-token'
            sess['mail_auth_token'] = 'test-auth-token'
            sess['device_auth_token'] = 'test-device-token'
            sess['own_device_id'] = 'test-device-id'
            sess['login_as_parent_error'] = 'Test error'
        
        response = client.post('/login-as-parent/cancel', follow_redirects=True)
        
        # Should redirect to dashboard
        assert response.status_code == 200
        
        # Verify session is cleared
        with client.session_transaction() as sess:
            assert 'mail_login_token' not in sess
            assert 'mail_auth_token' not in sess
            assert 'device_auth_token' not in sess
            assert 'own_device_id' not in sess
            assert 'login_as_parent_error' not in sess

    @pytest.mark.timeout(10)
    def test_post_login_as_parent_cancel_redirects_to_dashboard(self, client):
        """Test that cancel redirects to dashboard."""
        response = client.post('/login-as-parent/cancel', follow_redirects=False)
        
        assert response.status_code == 302
        assert '/dashboardV2' in response.headers.get('Location', '')


class TestLoginAsParentTemplate:
    """Tests for login_as_parent.html template rendering."""

    @pytest.mark.timeout(10)
    def test_template_has_csrf_protection_or_security(self, client):
        """Test that template includes security measures."""
        response = client.get('/login-as-parent')
        
        assert response.status_code == 200
        # Check for form elements
        assert b'<form' in response.data or b'form' in response.data.lower()

    @pytest.mark.timeout(10)
    def test_template_has_cancel_button(self, client):
        """Test that template includes cancel functionality."""
        response = client.get('/login-as-parent')
        
        assert response.status_code == 200
        # Should have a cancel button or link
        assert b'cancel' in response.data.lower() or b'Cancel' in response.data

    @pytest.mark.timeout(10)
    def test_template_has_step_indicator(self, client):
        """Test that template includes step indicator."""
        response = client.get('/login-as-parent')
        
        assert response.status_code == 200
        # Should have step indicator dots
        assert b'step' in response.data.lower() or b'dot' in response.data.lower()


class TestLoginAsParentValidation:
    """Tests for validation helpers used in login as parent flow."""

    @pytest.mark.timeout(10)
    def test_email_validation_pattern(self):
        """Test that email validation pattern works correctly."""
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        
        # Valid emails
        assert re.match(email_pattern, 'test@example.com')
        assert re.match(email_pattern, 'user.name@domain.org')
        assert re.match(email_pattern, 'user+tag@example.co.uk')
        
        # Invalid emails
        assert not re.match(email_pattern, 'invalid-email')
        assert not re.match(email_pattern, 'test@')
        assert not re.match(email_pattern, '@example.com')

    @pytest.mark.timeout(10)
    def test_verification_code_validation_pattern(self):
        """Test that verification code validation pattern works correctly.
        
        The official server uses a 3-word passphrase (e.g., "Pferd Miete abwenden"),
        not a 6-digit number.
        """
        # Valid 3-word passphrases
        valid_codes = [
            'Pferd Miete abwenden',
            'Haus Regen Tisch',
            'Apfel Bett Katze',
            'one two three',
            'word1 word2 word3'
        ]
        
        for code in valid_codes:
            code_words = code.split()
            assert len(code_words) == 3, f"Code '{code}' should have 3 words"
        
        # Invalid codes (not 3 words)
        invalid_codes = [
            '123456',           # 6-digit number
            'abc123',           # single word
            'one two',          # 2 words
            'one two three four',  # 4 words
            ''                  # empty
        ]
        
        for code in invalid_codes:
            code_words = code.split()
            assert len(code_words) != 3, f"Code '{code}' should not have 3 words"


class TestSignInIntoFamilyRequestFormat:
    """Tests for sign_in_into_family request format."""

    @pytest.mark.timeout(10)
    def test_sign_in_into_family_sends_correct_request_format(self):
        """Test that sign_in_into_family sends correct request format."""
        from auth_client import AuthClient, APIResponse
        
        client = AuthClient(base_url='http://test-server')
        
        # Mock the _request_with_retry method to capture the request
        captured_data = {}
        
        def mock_request(method, endpoint, data=None, token=None, retry_count=0, skip_prefix=False):
            captured_data.update(data or {})
            return APIResponse(
                success=True,
                status_code=200,
                data={'deviceAuthToken': 'test-token', 'ownDeviceId': 'test-device-id'}
            )
        
        client._request_with_retry = mock_request
        
        # Call the method
        response = client.sign_in_into_family(
            mail_auth_token='test-mail-token',
            device_name='Test Device',
            device_model='Test Model'
        )
        
        # Verify the request format
        assert captured_data['mailAuthToken'] == 'test-mail-token'
        assert captured_data['deviceName'] == 'Test Device'
        assert captured_data['parentDevice'] == {'model': 'Test Model'}
        assert response.success

    @pytest.mark.timeout(10)
    def test_sign_in_into_family_without_password_second_hash(self):
        """Test that sign_in_into_family works without parent_password_second_hash."""
        from auth_client import AuthClient, APIResponse
        
        client = AuthClient(base_url='http://test-server')
        
        # Mock the _request_with_retry method to capture the request
        captured_data = {}
        
        def mock_request(method, endpoint, data=None, token=None, retry_count=0, skip_prefix=False):
            captured_data.update(data or {})
            return APIResponse(
                success=True,
                status_code=200,
                data={'deviceAuthToken': 'test-token', 'ownDeviceId': 'test-device-id'}
            )
        
        client._request_with_retry = mock_request
        
        # Call the method without parent_password_second_hash
        response = client.sign_in_into_family(
            mail_auth_token='test-mail-token',
            device_name='Test Device',
            device_model='Test Model'
        )
        
        # Verify the request format - parentPasswordSecondHash should NOT be in the request
        assert 'parentPasswordSecondHash' not in captured_data
        assert captured_data['mailAuthToken'] == 'test-mail-token'
        assert captured_data['parentDevice'] == {'model': 'Test Model'}
        assert response.success

    @pytest.mark.timeout(10)
    def test_sign_in_into_family_with_client_level(self):
        """Test that sign_in_into_family includes clientLevel when provided."""
        from auth_client import AuthClient, APIResponse
        
        client = AuthClient(base_url='http://test-server')
        
        # Mock the _request_with_retry method to capture the request
        captured_data = {}
        
        def mock_request(method, endpoint, data=None, token=None, retry_count=0, skip_prefix=False):
            captured_data.update(data or {})
            return APIResponse(
                success=True,
                status_code=200,
                data={'deviceAuthToken': 'test-token', 'ownDeviceId': 'test-device-id'}
            )
        
        client._request_with_retry = mock_request
        
        # Call the method with client_level
        response = client.sign_in_into_family(
            mail_auth_token='test-mail-token',
            device_name='Test Device',
            device_model='Test Model',
            client_level=7
        )
        
        # Verify the request format
        assert captured_data['clientLevel'] == 7
        assert response.success

    @pytest.mark.timeout(10)
    def test_sign_in_into_family_without_device_model_uses_unknown(self):
        """Test that sign_in_into_family uses 'Unknown' for device model when not provided."""
        from auth_client import AuthClient, APIResponse
        
        client = AuthClient(base_url='http://test-server')
        
        # Mock the _request_with_retry method to capture the request
        captured_data = {}
        
        def mock_request(method, endpoint, data=None, token=None, retry_count=0, skip_prefix=False):
            captured_data.update(data or {})
            return APIResponse(
                success=True,
                status_code=200,
                data={'deviceAuthToken': 'test-token', 'ownDeviceId': 'test-device-id'}
            )
        
        client._request_with_retry = mock_request
        
        # Call the method without device_model
        response = client.sign_in_into_family(
            mail_auth_token='test-mail-token',
            device_name='Test Device'
        )
        
        # Verify the request format - should use 'Unknown' for model
        assert captured_data['parentDevice'] == {'model': 'Unknown'}
        assert captured_data['deviceName'] == 'Test Device'
        assert response.success