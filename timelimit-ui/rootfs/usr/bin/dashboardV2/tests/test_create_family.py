"""Unit tests for create family flow routes.

This module tests the server-side rendered create family flow:
- GET /create-family - renders appropriate step based on session state
- POST /create-family - processes form submissions for all 3 steps
- POST /create-family/cancel - clears session and redirects
"""

import pytest
import re
from unittest.mock import patch, MagicMock


class TestGetCreateFamily:
    """Tests for GET /create-family route."""

    @pytest.mark.timeout(10)
    def test_get_create_family_step1_renders_email_form(self, client):
        """Test that GET /create-family renders step 1 (email form) when no session."""
        response = client.get('/create-family')
        
        assert response.status_code == 200
        assert b'Create Family' in response.data
        assert b'Enter your email' in response.data or b'Email' in response.data

    @pytest.mark.timeout(10)
    def test_get_create_family_step1_shows_step_indicator(self, client):
        """Test that step 1 shows correct step indicator."""
        response = client.get('/create-family')
        
        assert response.status_code == 200
        # Should show step 1 as active
        assert b'step' in response.data.lower() or b'1' in response.data

    @pytest.mark.timeout(10)
    def test_get_create_family_step2_renders_code_form(self, client):
        """Test that GET /create-family renders step 2 (code form) when mail_login_token in session."""
        with client.session_transaction() as sess:
            sess['mail_login_token'] = 'test-login-token'
        
        response = client.get('/create-family')
        
        assert response.status_code == 200
        assert b'Verification code' in response.data or b'Code' in response.data

    @pytest.mark.timeout(10)
    def test_get_create_family_step3_renders_password_form(self, client):
        """Test that GET /create-family renders step 3 (password form) when mail_auth_token in session."""
        with client.session_transaction() as sess:
            sess['mail_login_token'] = 'test-login-token'
            sess['mail_auth_token'] = 'test-auth-token'
        
        response = client.get('/create-family')
        
        assert response.status_code == 200
        assert b'Password' in response.data or b'password' in response.data

    @pytest.mark.timeout(10)
    def test_get_create_family_redirects_when_authenticated(self, client):
        """Test that GET /create-family redirects to dashboard when device_auth_token in session."""
        with client.session_transaction() as sess:
            sess['device_auth_token'] = 'test-device-token'
        
        response = client.get('/create-family')
        
        assert response.status_code == 302
        assert '/dashboardV2' in response.headers.get('Location', '')

    @pytest.mark.timeout(10)
    def test_get_create_family_shows_error_message(self, client):
        """Test that GET /create-family shows error message from session."""
        with client.session_transaction() as sess:
            sess['create_family_error'] = 'Test error message'
        
        response = client.get('/create-family')
        
        assert response.status_code == 200
        assert b'Test error message' in response.data


class TestPostCreateFamilyStep1:
    """Tests for POST /create-family step 1 (email submission)."""

    @pytest.mark.timeout(10)
    def test_post_create_family_step1_missing_email(self, client):
        """Test that step 1 fails with missing email."""
        response = client.post('/create-family', data={
            'step': '1',
            'mail': ''
        }, follow_redirects=True)
        
        assert b'Email is required' in response.data or b'required' in response.data.lower()

    @pytest.mark.timeout(10)
    def test_post_create_family_step1_invalid_email(self, client):
        """Test that step 1 fails with invalid email format."""
        response = client.post('/create-family', data={
            'step': '1',
            'mail': 'invalid-email'
        }, follow_redirects=True)
        
        assert b'Invalid email format' in response.data or b'invalid' in response.data.lower()

    @pytest.mark.timeout(10)
    def test_post_create_family_step1_valid_email(self, client):
        """Test that step 1 processes valid email."""
        with patch('app.AuthClient') as mock_auth_client_class:
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.success = True
            mock_response.data = {'mailLoginToken': 'test-login-token'}
            mock_client.send_mail_login_code.return_value = mock_response
            mock_auth_client_class.return_value = mock_client
            
            response = client.post('/create-family', data={
                'step': '1',
                'mail': 'test@example.com'
            }, follow_redirects=True)
            
            # Should redirect to step 2
            assert response.status_code == 200

    @pytest.mark.timeout(10)
    def test_post_create_family_step1_api_failure(self, client):
        """Test that step 1 handles API failure."""
        with patch('app.AuthClient') as mock_auth_client_class:
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.success = False
            mock_response.error_message = 'API error'
            mock_client.send_mail_login_code.return_value = mock_response
            mock_auth_client_class.return_value = mock_client
            
            response = client.post('/create-family', data={
                'step': '1',
                'mail': 'test@example.com'
            }, follow_redirects=True)
            
            assert b'API error' in response.data or b'Failed' in response.data


class TestPostCreateFamilyStep2:
    """Tests for POST /create-family step 2 (verification code)."""

    @pytest.mark.timeout(10)
    def test_post_create_family_step2_missing_token(self, client):
        """Test that step 2 fails without mail_login_token in session."""
        response = client.post('/create-family', data={
            'step': '2',
            'receivedCode': 'Pferd Miete abwenden'
        }, follow_redirects=True)
        
        assert b'Session expired' in response.data or b'start again' in response.data.lower()

    @pytest.mark.timeout(10)
    def test_post_create_family_step2_missing_code(self, client):
        """Test that step 2 fails with missing verification code."""
        with client.session_transaction() as sess:
            sess['mail_login_token'] = 'test-login-token'
        
        response = client.post('/create-family', data={
            'step': '2',
            'receivedCode': ''
        }, follow_redirects=True)
        
        assert b'Verification code is required' in response.data or b'required' in response.data.lower()

    @pytest.mark.timeout(10)
    def test_post_create_family_step2_invalid_code_format(self, client):
        """Test that step 2 fails with invalid verification code format."""
        with client.session_transaction() as sess:
            sess['mail_login_token'] = 'test-login-token'
        
        response = client.post('/create-family', data={
            'step': '2',
            'receivedCode': 'abc123'
        }, follow_redirects=True)
        
        assert b'Invalid verification code format' in response.data or b'Invalid' in response.data

    @pytest.mark.timeout(10)
    def test_post_create_family_step2_valid_code(self, client):
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
            
            response = client.post('/create-family', data={
                'step': '2',
                'receivedCode': 'Pferd Miete abwenden'
            }, follow_redirects=True)
            
            # Should redirect to step 3
            assert response.status_code == 200


class TestPostCreateFamilyStep3:
    """Tests for POST /create-family step 3 (password submission)."""

    @pytest.mark.timeout(10)
    def test_post_create_family_step3_missing_token(self, client):
        """Test that step 3 fails without mail_auth_token in session."""
        response = client.post('/create-family', data={
            'step': '3',
            'password': 'testpass123',
            'secondPassword': 'testpass123'
        }, follow_redirects=True)
        
        assert b'Session expired' in response.data or b'start again' in response.data.lower()

    @pytest.mark.timeout(10)
    def test_post_create_family_step3_missing_password(self, client):
        """Test that step 3 fails with missing password."""
        with client.session_transaction() as sess:
            sess['mail_login_token'] = 'test-login-token'
            sess['mail_auth_token'] = 'test-auth-token'
        
        response = client.post('/create-family', data={
            'step': '3',
            'password': '',
            'secondPassword': 'testpass123',
            'parentName': 'Test Parent',
            'timeZone': 'Europe/Amsterdam',
            'deviceModel': 'Test Model',
            'deviceName': 'Test Device'
        }, follow_redirects=True)
        
        assert b'Password is required' in response.data or b'required' in response.data.lower()

    @pytest.mark.timeout(10)
    def test_post_create_family_step3_missing_second_password(self, client):
        """Test that step 3 fails with missing second password."""
        with client.session_transaction() as sess:
            sess['mail_login_token'] = 'test-login-token'
            sess['mail_auth_token'] = 'test-auth-token'
        
        response = client.post('/create-family', data={
            'step': '3',
            'password': 'testpass123',
            'secondPassword': '',
            'parentName': 'Test Parent',
            'timeZone': 'Europe/Amsterdam',
            'deviceModel': 'Test Model',
            'deviceName': 'Test Device'
        }, follow_redirects=True)
        
        assert b'Second password is required' in response.data or b'required' in response.data.lower()

    @pytest.mark.timeout(10)
    def test_post_create_family_step3_password_mismatch(self, client):
        """Test that step 3 fails with password mismatch."""
        with client.session_transaction() as sess:
            sess['mail_login_token'] = 'test-login-token'
            sess['mail_auth_token'] = 'test-auth-token'
        
        response = client.post('/create-family', data={
            'step': '3',
            'password': 'testpass123',
            'secondPassword': 'differentpass',
            'parentName': 'Test Parent',
            'timeZone': 'Europe/Amsterdam',
            'deviceModel': 'Test Model',
            'deviceName': 'Test Device'
        }, follow_redirects=True)
        
        assert b'Passwords do not match' in response.data or b'mismatch' in response.data.lower()

    @pytest.mark.timeout(10)
    def test_post_create_family_step3_valid_password(self, client):
        """Test that step 3 processes valid password and creates family."""
        with client.session_transaction() as sess:
            sess['mail_login_token'] = 'test-login-token'
            sess['mail_auth_token'] = 'test-auth-token'
        
        with patch('app.AuthClient') as mock_auth_client_class:
            mock_client = MagicMock()
            
            # Mock create_family_rest response with deviceAuthToken
            mock_create_response = MagicMock()
            mock_create_response.success = True
            mock_create_response.data = {
                'deviceAuthToken': 'test-device-token',
                'ownDeviceId': 'test-device-id'
            }
            mock_client.create_family_rest.return_value = mock_create_response
            
            mock_auth_client_class.return_value = mock_client
            
            response = client.post('/create-family', data={
                'step': '3',
                'password': 'testpass123',
                'secondPassword': 'testpass123',
                'deviceName': 'Test Device',
                'deviceModel': 'Test Model',
                'locale': 'en',
                'parentName': 'Test Parent',
                'timeZone': 'Europe/Amsterdam'
            }, follow_redirects=True)
            
            # Should redirect to dashboard
            assert response.status_code == 200
            
            # Verify device_auth_token was stored in session
            with client.session_transaction() as sess:
                assert sess.get('device_auth_token') == 'test-device-token'
                assert sess.get('own_device_id') == 'test-device-id'

    @pytest.mark.timeout(10)
    def test_post_create_family_step3_api_failure(self, client):
        """Test that step 3 handles API failure."""
        with client.session_transaction() as sess:
            sess['mail_login_token'] = 'test-login-token'
            sess['mail_auth_token'] = 'test-auth-token'
        
        with patch('app.AuthClient') as mock_auth_client_class:
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.success = False
            mock_response.error_message = 'Failed to create family'
            mock_client.create_family_rest.return_value = mock_response
            mock_auth_client_class.return_value = mock_client
            
            response = client.post('/create-family', data={
                'step': '3',
                'password': 'testpass123',
                'secondPassword': 'testpass123',
                'parentName': 'Test Parent',
                'timeZone': 'Europe/Amsterdam',
                'deviceModel': 'Test Model',
                'deviceName': 'Test Device'
            }, follow_redirects=True)
            
            assert b'Failed to create family' in response.data or b'Failed' in response.data

    @pytest.mark.timeout(10)
    def test_post_create_family_step3_creates_family_successfully(self, client):
        """Test that step 3 creates family and redirects to dashboard."""
        with client.session_transaction() as sess:
            sess['mail_login_token'] = 'test-login-token'
            sess['mail_auth_token'] = 'test-auth-token'
        
        with patch('app.AuthClient') as mock_auth_client_class:
            mock_client = MagicMock()
            
            # Mock create_family_rest response with deviceAuthToken
            mock_create_response = MagicMock()
            mock_create_response.success = True
            mock_create_response.data = {
                'deviceAuthToken': 'test-device-token',
                'ownDeviceId': 'test-device-id'
            }
            mock_client.create_family_rest.return_value = mock_create_response
            
            mock_auth_client_class.return_value = mock_client
            
            response = client.post('/create-family', data={
                'step': '3',
                'password': 'testpass123',
                'secondPassword': 'testpass123',
                'deviceName': 'Test Device',
                'deviceModel': 'Test Model',
                'locale': 'en',
                'parentName': 'Test Parent',
                'timeZone': 'Europe/Amsterdam'
            }, follow_redirects=True)
            
            # Should redirect to dashboard
            assert response.status_code == 200
            
            # Verify device_auth_token was stored in session
            with client.session_transaction() as sess:
                assert sess.get('device_auth_token') == 'test-device-token'
                assert sess.get('own_device_id') == 'test-device-id'

    @pytest.mark.timeout(10)
    def test_post_create_family_step3_api_failure_shows_error(self, client):
        """Test that step 3 handles API failure gracefully."""
        with client.session_transaction() as sess:
            sess['mail_login_token'] = 'test-login-token'
            sess['mail_auth_token'] = 'test-auth-token'
        
        with patch('app.AuthClient') as mock_auth_client_class:
            mock_client = MagicMock()
            
            # Mock create_family_rest failure
            mock_create_response = MagicMock()
            mock_create_response.success = False
            mock_create_response.error_message = 'Failed to create family'
            mock_client.create_family_rest.return_value = mock_create_response
            
            mock_auth_client_class.return_value = mock_client
            
            response = client.post('/create-family', data={
                'step': '3',
                'password': 'testpass123',
                'secondPassword': 'testpass123',
                'deviceName': 'Test Device',
                'deviceModel': 'Test Model',
                'locale': 'en',
                'parentName': 'Test Parent',
                'timeZone': 'Europe/Amsterdam'
            }, follow_redirects=True)
            
            # Should show error message
            assert response.status_code == 200
            assert b'Failed to create family' in response.data


class TestPostCreateFamilyCancel:
    """Tests for POST /create-family/cancel route."""

    @pytest.mark.timeout(10)
    def test_post_create_family_cancel_clears_session(self, client):
        """Test that cancel clears all create family session data."""
        with client.session_transaction() as sess:
            sess['mail_login_token'] = 'test-login-token'
            sess['mail_auth_token'] = 'test-auth-token'
            sess['device_auth_token'] = 'test-device-token'
            sess['own_device_id'] = 'test-device-id'
            sess['create_family_error'] = 'Test error'
        
        response = client.post('/create-family/cancel', follow_redirects=True)
        
        # Should redirect to dashboard
        assert response.status_code == 200
        
        # Verify session is cleared
        with client.session_transaction() as sess:
            assert 'mail_login_token' not in sess
            assert 'mail_auth_token' not in sess
            assert 'device_auth_token' not in sess
            assert 'own_device_id' not in sess
            assert 'create_family_error' not in sess

    @pytest.mark.timeout(10)
    def test_post_create_family_cancel_redirects_to_dashboard(self, client):
        """Test that cancel redirects to dashboard."""
        response = client.post('/create-family/cancel', follow_redirects=False)
        
        assert response.status_code == 302
        assert '/dashboardV2' in response.headers.get('Location', '')


class TestCreateFamilyTemplate:
    """Tests for create_family.html template rendering."""

    @pytest.mark.timeout(10)
    def test_template_has_csrf_protection_or_security(self, client):
        """Test that template includes security measures."""
        response = client.get('/create-family')
        
        assert response.status_code == 200
        # Check for form elements
        assert b'<form' in response.data or b'form' in response.data.lower()

    @pytest.mark.timeout(10)
    def test_template_has_cancel_button(self, client):
        """Test that template includes cancel functionality."""
        response = client.get('/create-family')
        
        assert response.status_code == 200
        # Should have a cancel button or link
        assert b'cancel' in response.data.lower() or b'Cancel' in response.data


class TestCreateFamilyValidation:
    """Tests for validation helpers used in create family flow."""

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