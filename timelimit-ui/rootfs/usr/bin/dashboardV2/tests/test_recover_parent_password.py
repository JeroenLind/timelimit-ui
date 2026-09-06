"""Unit tests for recover parent password flow routes.

This module tests the server-side rendered recover parent password flow:
- GET /recover-parent-password - renders appropriate step based on session state
- POST /recover-parent-password - processes form submissions for all 3 steps
"""

import pytest
import re
from unittest.mock import patch, MagicMock


class TestGetRecoverParentPassword:
    """Tests for GET /recover-parent-password route."""

    @pytest.mark.timeout(10)
    def test_get_recover_parent_password_step1_renders_email_form(self, client):
        """Test that GET /recover-parent-password renders step 1 (email form) when no session."""
        response = client.get('/recover-parent-password')
        
        assert response.status_code == 200
        assert b'Recover Parent Password' in response.data
        assert b'Email' in response.data

    @pytest.mark.timeout(10)
    def test_get_recover_parent_password_step1_shows_step_indicator(self, client):
        """Test that step 1 shows correct step indicator."""
        response = client.get('/recover-parent-password')
        
        assert response.status_code == 200
        # Should show step 1 as active
        assert b'step' in response.data.lower() or b'1' in response.data

    @pytest.mark.timeout(10)
    def test_get_recover_parent_password_step2_renders_code_form(self, client):
        """Test that GET /recover-parent-password renders step 2 (code form) when mail_login_token in session."""
        with client.session_transaction() as sess:
            sess['mail_login_token'] = 'test-login-token'
        
        response = client.get('/recover-parent-password')
        
        assert response.status_code == 200
        assert b'Verification Code' in response.data or b'Code' in response.data

    @pytest.mark.timeout(10)
    def test_get_recover_parent_password_step3_renders_password_form(self, client):
        """Test that GET /recover-parent-password renders step 3 (password form) when mail_auth_token in session."""
        with client.session_transaction() as sess:
            sess['mail_login_token'] = 'test-login-token'
            sess['mail_auth_token'] = 'test-auth-token'
        
        response = client.get('/recover-parent-password')
        
        assert response.status_code == 200
        assert b'New Password' in response.data or b'password' in response.data.lower()

    @pytest.mark.timeout(10)
    def test_get_recover_parent_password_shows_error_when_authenticated(self, client):
        """Test that GET /recover-parent-password shows error when device_auth_token in session."""
        with client.session_transaction() as sess:
            sess['device_auth_token'] = 'test-device-token'
        
        response = client.get('/recover-parent-password')
        
        # Should render the page with an error message instead of redirecting
        assert response.status_code == 200
        assert b'already logged in' in response.data.lower() or b'sign out' in response.data.lower()

    @pytest.mark.timeout(10)
    def test_get_recover_parent_password_shows_error_message(self, client):
        """Test that GET /recover-parent-password shows error message from session."""
        with client.session_transaction() as sess:
            sess['recover_parent_password_error'] = 'Test error message'
        
        response = client.get('/recover-parent-password')
        
        assert response.status_code == 200
        assert b'Test error message' in response.data

    @pytest.mark.timeout(10)
    def test_get_recover_parent_password_shows_success_message(self, client):
        """Test that GET /recover-parent-password shows success message from session."""
        with client.session_transaction() as sess:
            sess['mail_login_token'] = 'test-login-token'
            sess['mail_auth_token'] = 'test-auth-token'
            sess['recover_parent_password_success'] = 'Password recovered successfully!'
        
        response = client.get('/recover-parent-password')
        
        assert response.status_code == 200
        assert b'Password recovered successfully!' in response.data


class TestPostRecoverParentPasswordStep1:
    """Tests for POST /recover-parent-password step 1 (email submission)."""

    @pytest.mark.timeout(10)
    def test_post_recover_parent_password_step1_missing_email(self, client):
        """Test that step 1 fails with missing email."""
        response = client.post('/recover-parent-password', data={
            'step': '1',
            'mail': ''
        }, follow_redirects=True)
        
        assert b'Email is required' in response.data or b'required' in response.data.lower()

    @pytest.mark.timeout(10)
    def test_post_recover_parent_password_step1_invalid_email(self, client):
        """Test that step 1 fails with invalid email format."""
        response = client.post('/recover-parent-password', data={
            'step': '1',
            'mail': 'invalid-email'
        }, follow_redirects=True)
        
        assert b'Invalid email format' in response.data or b'invalid' in response.data.lower()

    @pytest.mark.timeout(10)
    def test_post_recover_parent_password_step1_valid_email(self, client):
        """Test that step 1 processes valid email."""
        with patch('app.AuthClient') as mock_auth_client_class:
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.success = True
            mock_response.data = {'mailLoginToken': 'test-login-token'}
            mock_client.send_mail_login_code.return_value = mock_response
            mock_auth_client_class.return_value = mock_client
            
            response = client.post('/recover-parent-password', data={
                'step': '1',
                'mail': 'test@example.com'
            }, follow_redirects=True)
            
            # Should redirect to step 2
            assert response.status_code == 200

    @pytest.mark.timeout(10)
    def test_post_recover_parent_password_step1_api_failure(self, client):
        """Test that step 1 handles API failure."""
        with patch('app.AuthClient') as mock_auth_client_class:
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.success = False
            mock_response.error_message = 'API error'
            mock_client.send_mail_login_code.return_value = mock_response
            mock_auth_client_class.return_value = mock_client
            
            response = client.post('/recover-parent-password', data={
                'step': '1',
                'mail': 'test@example.com'
            }, follow_redirects=True)
            
            assert b'API error' in response.data or b'Failed' in response.data


class TestPostRecoverParentPasswordStep2:
    """Tests for POST /recover-parent-password step 2 (verification code)."""

    @pytest.mark.timeout(10)
    def test_post_recover_parent_password_step2_missing_token(self, client):
        """Test that step 2 fails without mail_login_token in session."""
        response = client.post('/recover-parent-password', data={
            'step': '2',
            'receivedCode': 'Pferd Miete abwenden'
        }, follow_redirects=True)
        
        assert b'Session expired' in response.data or b'start again' in response.data.lower()

    @pytest.mark.timeout(10)
    def test_post_recover_parent_password_step2_missing_code(self, client):
        """Test that step 2 fails with missing verification code."""
        with client.session_transaction() as sess:
            sess['mail_login_token'] = 'test-login-token'
        
        response = client.post('/recover-parent-password', data={
            'step': '2',
            'receivedCode': ''
        }, follow_redirects=True)
        
        assert b'Verification code is required' in response.data or b'required' in response.data.lower()

    @pytest.mark.timeout(10)
    def test_post_recover_parent_password_step2_invalid_code_format(self, client):
        """Test that step 2 fails with invalid verification code format."""
        with client.session_transaction() as sess:
            sess['mail_login_token'] = 'test-login-token'
        
        response = client.post('/recover-parent-password', data={
            'step': '2',
            'receivedCode': 'abc123'
        }, follow_redirects=True)
        
        assert b'Invalid verification code format' in response.data or b'Invalid' in response.data

    @pytest.mark.timeout(10)
    def test_post_recover_parent_password_step2_valid_code(self, client):
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
            
            response = client.post('/recover-parent-password', data={
                'step': '2',
                'receivedCode': 'Pferd Miete abwenden'
            }, follow_redirects=True)
            
            # Should redirect to step 3
            assert response.status_code == 200


class TestPostRecoverParentPasswordStep3:
    """Tests for POST /recover-parent-password step 3 (password submission)."""

    @pytest.mark.timeout(10)
    def test_post_recover_parent_password_step3_missing_token(self, client):
        """Test that step 3 fails without mail_auth_token in session."""
        response = client.post('/recover-parent-password', data={
            'step': '3',
            'newPassword': 'newpassword123',
            'confirmPassword': 'newpassword123'
        }, follow_redirects=True)
        
        assert b'Session expired' in response.data or b'start again' in response.data.lower()

    @pytest.mark.timeout(10)
    def test_post_recover_parent_password_step3_missing_password(self, client):
        """Test that step 3 fails with missing new password."""
        with client.session_transaction() as sess:
            sess['mail_login_token'] = 'test-login-token'
            sess['mail_auth_token'] = 'test-auth-token'
        
        response = client.post('/recover-parent-password', data={
            'step': '3',
            'newPassword': '',
            'confirmPassword': ''
        }, follow_redirects=True)
        
        assert b'New password is required' in response.data or b'required' in response.data.lower()

    @pytest.mark.timeout(10)
    def test_post_recover_parent_password_step3_password_mismatch(self, client):
        """Test that step 3 fails with password mismatch."""
        with client.session_transaction() as sess:
            sess['mail_login_token'] = 'test-login-token'
            sess['mail_auth_token'] = 'test-auth-token'
        
        response = client.post('/recover-parent-password', data={
            'step': '3',
            'newPassword': 'newpassword123',
            'confirmPassword': 'differentpassword'
        }, follow_redirects=True)
        
        assert b'Passwords do not match' in response.data or b'mismatch' in response.data.lower()

    @pytest.mark.timeout(10)
    def test_post_recover_parent_password_step3_valid_password(self, client):
        """Test that step 3 processes valid password and recovers password."""
        with client.session_transaction() as sess:
            sess['mail_login_token'] = 'test-login-token'
            sess['mail_auth_token'] = 'test-auth-token'
            sess['device_auth_token'] = 'test-device-token'
        
        with patch('app.AuthClient') as mock_auth_client_class, \
             patch('app.upsert_family_password_hash', return_value=True):
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.success = True
            mock_response.data = {'ok': True}
            mock_client.recover_parent_password.return_value = mock_response
            mock_auth_client_class.return_value = mock_client
            
            response = client.post('/recover-parent-password', data={
                'step': '3',
                'newPassword': 'testpassword123',
                'confirmPassword': 'testpassword123'
            }, follow_redirects=True)
            
            # Should redirect to step 3 with success message
            assert response.status_code == 200
            
            # Verify password hash was stored in session
            with client.session_transaction() as sess:
                assert 'parent_password_second_hash' in sess
                stored_hash = sess.get('parent_password_second_hash')
                assert stored_hash is not None
                assert stored_hash.startswith('$2a$')

    @pytest.mark.timeout(10)
    def test_post_recover_parent_password_step3_api_failure(self, client):
        """Test that step 3 handles API failure."""
        with client.session_transaction() as sess:
            sess['mail_login_token'] = 'test-login-token'
            sess['mail_auth_token'] = 'test-auth-token'
        
        with patch('app.AuthClient') as mock_auth_client_class:
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.success = False
            mock_response.error_message = 'Failed to recover password'
            mock_client.recover_parent_password.return_value = mock_response
            mock_auth_client_class.return_value = mock_client
            
            response = client.post('/recover-parent-password', data={
                'step': '3',
                'newPassword': 'newpassword123',
                'confirmPassword': 'newpassword123'
            }, follow_redirects=True)
            
            assert b'Failed to recover password' in response.data or b'Failed' in response.data


class TestRecoverParentPasswordValidation:
    """Tests for validation helpers used in recover parent password flow."""

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


class TestRecoverParentPasswordHashing:
    """Tests for password hashing in recover parent password flow."""

    @pytest.mark.timeout(10)
    def test_password_hash_uses_2a_prefix(self, client):
        """Test that password hash uses $2a$ prefix (not $2b$)."""
        with client.session_transaction() as sess:
            sess['mail_login_token'] = 'test-login-token'
            sess['mail_auth_token'] = 'test-auth-token'
            sess['device_auth_token'] = 'test-device-token'
        
        with patch('app.AuthClient') as mock_auth_client_class, \
             patch('app.upsert_family_password_hash', return_value=True):
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.success = True
            mock_response.data = {'ok': True}
            mock_client.recover_parent_password.return_value = mock_response
            mock_auth_client_class.return_value = mock_client
            
            response = client.post('/recover-parent-password', data={
                'step': '3',
                'newPassword': 'testpassword123',
                'confirmPassword': 'testpassword123'
            }, follow_redirects=True)
            
            # Verify the hash uses $2a$ prefix
            with client.session_transaction() as sess:
                stored_hash = sess.get('parent_password_second_hash')
                assert stored_hash is not None
                assert stored_hash.startswith('$2a$'), f"Hash should start with $2a$, got: {stored_hash[:10]}"

    @pytest.mark.timeout(10)
    def test_password_hash_has_correct_rounds(self, client):
        """Test that password hash has 12 rounds."""
        with client.session_transaction() as sess:
            sess['mail_login_token'] = 'test-login-token'
            sess['mail_auth_token'] = 'test-auth-token'
            sess['device_auth_token'] = 'test-device-token'
        
        with patch('app.AuthClient') as mock_auth_client_class, \
             patch('app.upsert_family_password_hash', return_value=True):
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.success = True
            mock_response.data = {'ok': True}
            mock_client.recover_parent_password.return_value = mock_response
            mock_auth_client_class.return_value = mock_client
            
            response = client.post('/recover-parent-password', data={
                'step': '3',
                'newPassword': 'testpassword123',
                'confirmPassword': 'testpassword123'
            }, follow_redirects=True)
            
            # Verify the hash has 12 rounds
            with client.session_transaction() as sess:
                stored_hash = sess.get('parent_password_second_hash')
                assert stored_hash is not None
                # $2a$12$... format
                assert '$12$' in stored_hash, f"Hash should have 12 rounds, got: {stored_hash}"


class TestRecoverParentPasswordDatabase:
    """Tests for database operations in recover parent password flow."""

    @pytest.mark.timeout(10)
    def test_password_hash_stored_in_database(self, client):
        """Test that password hash is stored in database after recovery."""
        with client.session_transaction() as sess:
            sess['mail_login_token'] = 'test-login-token'
            sess['mail_auth_token'] = 'test-auth-token'
            sess['device_auth_token'] = 'test-device-token'
        
        with patch('app.AuthClient') as mock_auth_client_class, \
             patch('app.upsert_family_password_hash', return_value=True) as mock_upsert:
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.success = True
            mock_response.data = {'ok': True}
            mock_client.recover_parent_password.return_value = mock_response
            mock_auth_client_class.return_value = mock_client
            
            response = client.post('/recover-parent-password', data={
                'step': '3',
                'newPassword': 'testpassword123',
                'confirmPassword': 'testpassword123'
            }, follow_redirects=True)
            
            # Verify upsert was called with all three hash components
            mock_upsert.assert_called_once()
            call_kwargs = mock_upsert.call_args.kwargs
            assert call_kwargs['device_auth_token'] == 'test-device-token'
            assert call_kwargs['parent_password_hash'].startswith('$2a$')
            assert call_kwargs['parent_password_second_hash'].startswith('$2a$')
            assert call_kwargs['parent_password_second_salt'].startswith('$2a$')

    @pytest.mark.timeout(10)
    def test_password_hash_stored_in_session(self, client):
        """Test that password hash is stored in session after recovery."""
        with client.session_transaction() as sess:
            sess['mail_login_token'] = 'test-login-token'
            sess['mail_auth_token'] = 'test-auth-token'
            sess['device_auth_token'] = 'test-device-token'
        
        with patch('app.AuthClient') as mock_auth_client_class, \
             patch('app.upsert_family_password_hash', return_value=True):
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.success = True
            mock_response.data = {'ok': True}
            mock_client.recover_parent_password.return_value = mock_response
            mock_auth_client_class.return_value = mock_client
            
            response = client.post('/recover-parent-password', data={
                'step': '3',
                'newPassword': 'testpassword123',
                'confirmPassword': 'testpassword123'
            }, follow_redirects=True)
            
            # Verify hash is in session
            with client.session_transaction() as sess:
                stored_hash = sess.get('parent_password_second_hash')
                assert stored_hash is not None
                assert stored_hash.startswith('$2a$')


class TestApiRecoverParentPassword:
    """Tests for /api/auth/recover-parent-password endpoint."""

    @pytest.mark.timeout(10)
    def test_api_recover_parent_password_missing_fields(self, client):
        """Test that API endpoint fails with missing required fields."""
        response = client.post('/api/auth/recover-parent-password', 
            json={},
            content_type='application/json')
        
        assert response.status_code == 400
        data = response.get_json()
        assert data['status'] == 'error'
        assert 'Missing required fields' in data.get('error', '')

    @pytest.mark.timeout(10)
    def test_api_recover_parent_password_missing_mail_auth_token(self, client):
        """Test that API endpoint fails with missing mailAuthToken."""
        response = client.post('/api/auth/recover-parent-password',
            json={'newPassword': {'hash': '$2a$12$test', 'secondHash': '$2a$12$test', 'secondSalt': '$2a$12$salt'}},
            content_type='application/json')
        
        assert response.status_code == 400
        data = response.get_json()
        assert data['status'] == 'error'

    @pytest.mark.timeout(10)
    def test_api_recover_parent_password_missing_new_password(self, client):
        """Test that API endpoint fails with missing newPassword."""
        response = client.post('/api/auth/recover-parent-password',
            json={'mailAuthToken': 'test-token'},
            content_type='application/json')
        
        assert response.status_code == 400
        data = response.get_json()
        assert data['status'] == 'error'

    @pytest.mark.timeout(10)
    def test_api_recover_parent_password_success(self, client):
        """Test that API endpoint succeeds with valid data."""
        with client.session_transaction() as sess:
            sess['device_auth_token'] = 'test-device-token'
        
        with patch('app.AuthClient') as mock_auth_client_class, \
             patch('app.upsert_family_password_hash', return_value=True):
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.success = True
            mock_response.data = {'ok': True}
            mock_client.recover_parent_password.return_value = mock_response
            mock_auth_client_class.return_value = mock_client
            
            response = client.post('/api/auth/recover-parent-password',
                json={
                    'mailAuthToken': 'test-auth-token',
                    'password': {
                        'hash': '$2a$12$testhash',
                        'secondHash': '$2a$12$testhash',
                        'secondSalt': '$2a$12$salt'
                    }
                },
                content_type='application/json')
            
            assert response.status_code == 200
            data = response.get_json()
            assert data['ok'] is True

    @pytest.mark.timeout(10)
    def test_api_recover_parent_password_updates_database(self, client):
        """Test that API endpoint updates database after successful recovery."""
        with client.session_transaction() as sess:
            sess['device_auth_token'] = 'test-device-token'
        
        with patch('app.AuthClient') as mock_auth_client_class, \
             patch('app.upsert_family_password_hash', return_value=True) as mock_upsert:
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.success = True
            mock_response.data = {'ok': True}
            mock_client.recover_parent_password.return_value = mock_response
            mock_auth_client_class.return_value = mock_client
            
            response = client.post('/api/auth/recover-parent-password',
                json={
                    'mailAuthToken': 'test-auth-token',
                    'password': {
                        'hash': '$2a$12$testhash',
                        'secondHash': '$2a$12$testhash',
                        'secondSalt': '$2a$12$salt'
                    }
                },
                content_type='application/json')
            
            assert response.status_code == 200
            
            # Verify upsert was called with all three hash components
            mock_upsert.assert_called_once()
            call_kwargs = mock_upsert.call_args.kwargs
            assert call_kwargs['device_auth_token'] == 'test-device-token'
            assert call_kwargs['parent_password_hash'].startswith('$2a$')
            assert call_kwargs['parent_password_second_hash'].startswith('$2a$')
            assert call_kwargs['parent_password_second_salt'].startswith('$2a$')

    @pytest.mark.timeout(10)
    def test_api_recover_parent_password_failure(self, client):
        """Test that API endpoint handles server failure."""
        with patch('app.AuthClient') as mock_auth_client_class:
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.success = False
            mock_response.error_code = 'unauthorized'
            mock_response.error_message = 'Invalid or expired token'
            mock_client.recover_parent_password.return_value = mock_response
            mock_auth_client_class.return_value = mock_client
            
            response = client.post('/api/auth/recover-parent-password',
                json={
                    'mailAuthToken': 'invalid-token',
                    'password': {
                        'hash': '$2a$12$testhash',
                        'secondHash': '$2a$12$testhash',
                        'secondSalt': '$2a$12$salt'
                    }
                },
                content_type='application/json')
            
            assert response.status_code == 401
            data = response.get_json()
            assert data['status'] == 'error'
            assert data['error_code'] == 'unauthorized'


class TestRecoverParentPasswordIntegration:
    """Integration tests for recover parent password flow."""

    @pytest.mark.timeout(10)
    def test_recover_parent_password_flow_complete(self, client):
        """Test the complete recover parent password flow."""
        # Step 1: Enter email
        with patch('app.AuthClient') as mock_auth_client_class:
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.success = True
            mock_response.data = {'mailLoginToken': 'test-login-token'}
            mock_client.send_mail_login_code.return_value = mock_response
            mock_auth_client_class.return_value = mock_client
            
            response = client.post('/recover-parent-password', data={
                'step': '1',
                'mail': 'test@example.com'
            }, follow_redirects=True)
            
            assert response.status_code == 200
        
        # Step 2: Enter verification code
        with patch('app.AuthClient') as mock_auth_client_class:
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.success = True
            mock_response.data = {'mailAuthToken': 'test-auth-token'}
            mock_client.sign_in_by_mail_code.return_value = mock_response
            mock_auth_client_class.return_value = mock_client
            
            response = client.post('/recover-parent-password', data={
                'step': '2',
                'receivedCode': 'Pferd Miete abwenden'
            }, follow_redirects=True)
            
            assert response.status_code == 200
        
        # Step 3: Enter new password
        with client.session_transaction() as sess:
            sess['device_auth_token'] = 'test-device-token'
        
        with patch('app.AuthClient') as mock_auth_client_class, \
             patch('app.upsert_family_password_hash', return_value=True):
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.success = True
            mock_response.data = {'ok': True}
            mock_client.recover_parent_password.return_value = mock_response
            mock_auth_client_class.return_value = mock_client
            
            response = client.post('/recover-parent-password', data={
                'step': '3',
                'newPassword': 'newpassword123',
                'confirmPassword': 'newpassword123'
            }, follow_redirects=True)
            
            assert response.status_code == 200
            
            # Verify success message
            assert b'Password recovered successfully' in response.data or b'success' in response.data.lower()

    @pytest.mark.timeout(10)
    def test_recover_parent_password_with_special_characters(self, client):
        """Test that recover parent password handles special characters in password."""
        with client.session_transaction() as sess:
            sess['mail_login_token'] = 'test-login-token'
            sess['mail_auth_token'] = 'test-auth-token'
            sess['device_auth_token'] = 'test-device-token'
        
        with patch('app.AuthClient') as mock_auth_client_class, \
             patch('app.upsert_family_password_hash', return_value=True):
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.success = True
            mock_response.data = {'ok': True}
            mock_client.recover_parent_password.return_value = mock_response
            mock_auth_client_class.return_value = mock_client
            
            # Password with special characters
            special_password = 'P@ssw0rd!#$%^&*()_+-=[]{}|;:,.<>?'
            
            response = client.post('/recover-parent-password', data={
                'step': '3',
                'newPassword': special_password,
                'confirmPassword': special_password
            }, follow_redirects=True)
            
            assert response.status_code == 200
            
            # Verify hash was stored
            with client.session_transaction() as sess:
                stored_hash = sess.get('parent_password_second_hash')
                assert stored_hash is not None
                assert stored_hash.startswith('$2a$')