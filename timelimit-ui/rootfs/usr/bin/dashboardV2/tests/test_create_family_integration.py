"""Integration tests for the complete create family flow.

This module tests the end-to-end create family flow:
1. User visits /create-family (step 1 - email)
2. User submits email, receives verification code
3. User submits verification code (step 2)
4. User submits password (step 3)
5. Family is created, user redirected to dashboard
"""

import pytest
from unittest.mock import patch, MagicMock, call
import time


class TestCreateFamilyIntegration:
    """Integration tests for the complete create family flow."""

    @pytest.mark.timeout(30)
    def test_full_flow_step1_to_step2(self, client):
        """Test complete flow from step 1 to step 2."""
        # Step 1: Get create family page
        response = client.get('/create-family')
        assert response.status_code == 200
        
        # Step 1: Submit email
        with patch('app.AuthClient') as mock_auth_client_class:
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.success = True
            mock_response.data = {'mailLoginToken': 'test-login-token-123'}
            mock_client.send_mail_login_code.return_value = mock_response
            mock_auth_client_class.return_value = mock_client
            
            response = client.post('/create-family', data={
                'step': '1',
                'mail': 'test@example.com'
            }, follow_redirects=True)
            
            assert response.status_code == 200
            
            # Verify AuthClient was called with correct parameters
            mock_client.send_mail_login_code.assert_called_once_with(mail='test@example.com', locale='en')
        
        # Step 2: Get create family page (should show code form)
        response = client.get('/create-family')
        assert response.status_code == 200
        
        # Step 2: Submit verification code (3-word passphrase)
        with patch('app.AuthClient') as mock_auth_client_class:
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.success = True
            mock_response.data = {'mailAuthToken': 'test-auth-token-456'}
            mock_client.sign_in_by_mail_code.return_value = mock_response
            mock_auth_client_class.return_value = mock_client
            
            response = client.post('/create-family', data={
                'step': '2',
                'receivedCode': 'Pferd Miete abwenden'
            }, follow_redirects=True)
            
            assert response.status_code == 200
            
            # Verify AuthClient was called with correct parameters
            mock_client.sign_in_by_mail_code.assert_called_once_with(
                mail_login_token='test-login-token-123',
                received_code='Pferd Miete abwenden'
            )

    @pytest.mark.timeout(30)
    def test_full_flow_step2_to_step3(self, client):
        """Test complete flow from step 2 to step 3."""
        # Set up session with tokens
        with client.session_transaction() as sess:
            sess['mail_login_token'] = 'test-login-token-123'
            sess['mail_auth_token'] = 'test-auth-token-456'
        
        # Step 3: Get create family page (should show password form)
        response = client.get('/create-family')
        assert response.status_code == 200
        
        # Step 3: Submit password with all required fields
        with patch('app.AuthClient') as mock_auth_client_class, \
             patch('app.create_sync_manager') as mock_create_sync_manager:
            mock_client = MagicMock()
            
            # Mock create_family_rest response
            mock_create_response = MagicMock()
            mock_create_response.success = True
            mock_create_response.data = {
                'deviceAuthToken': 'device-token-789',
                'ownDeviceId': 'device-id-abc'
            }
            mock_client.create_family_rest.return_value = mock_create_response
            
            mock_auth_client_class.return_value = mock_client
            
            # Mock sync manager to return success
            mock_sync_manager = MagicMock()
            mock_sync_manager.do_sync.return_value = True
            mock_create_sync_manager.return_value = mock_sync_manager
            
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
            
            assert response.status_code == 200
            
            # Verify session was updated
            with client.session_transaction() as sess:
                assert sess.get('device_auth_token') == 'device-token-789'
                assert sess.get('own_device_id') == 'device-id-abc'
                assert 'mail_login_token' not in sess
                assert 'mail_auth_token' not in sess

    @pytest.mark.timeout(30)
    def test_full_flow_complete(self, client):
        """Test complete flow from start to finish."""
        # Step 1: Get create family page
        response = client.get('/create-family')
        assert response.status_code == 200
        
        # Step 1: Submit email
        with patch('app.AuthClient') as mock_auth_client_class:
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.success = True
            mock_response.data = {'mailLoginToken': 'login-token-xyz'}
            mock_client.send_mail_login_code.return_value = mock_response
            mock_auth_client_class.return_value = mock_client
            
            response = client.post('/create-family', data={
                'step': '1',
                'mail': 'integration@test.com'
            }, follow_redirects=True)
            
            assert response.status_code == 200
        
        # Step 2: Submit verification code (3-word passphrase)
        with patch('app.AuthClient') as mock_auth_client_class:
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.success = True
            mock_response.data = {'mailAuthToken': 'auth-token-xyz'}
            mock_client.sign_in_by_mail_code.return_value = mock_response
            mock_auth_client_class.return_value = mock_client
            
            response = client.post('/create-family', data={
                'step': '2',
                'receivedCode': 'Haus Regen Tisch'
            }, follow_redirects=True)
            
            assert response.status_code == 200
        
        # Step 3: Submit password with all required fields
        with patch('app.AuthClient') as mock_auth_client_class, \
             patch('app.create_sync_manager') as mock_create_sync_manager:
            mock_client = MagicMock()
            
            # Mock create_family_rest response
            mock_create_response = MagicMock()
            mock_create_response.success = True
            mock_create_response.data = {
                'deviceAuthToken': 'final-device-token',
                'ownDeviceId': 'final-device-id'
            }
            mock_client.create_family_rest.return_value = mock_create_response
            
            mock_auth_client_class.return_value = mock_client
            
            # Mock sync manager to return success
            mock_sync_manager = MagicMock()
            mock_sync_manager.do_sync.return_value = True
            mock_create_sync_manager.return_value = mock_sync_manager
            
            response = client.post('/create-family', data={
                'step': '3',
                'password': 'finalpassword123',
                'secondPassword': 'finalpassword123',
                'deviceName': 'Final Device',
                'deviceModel': 'Final Model',
                'locale': 'en',
                'parentName': 'Test Parent',
                'timeZone': 'Europe/Amsterdam'
            }, follow_redirects=True)
            
            assert response.status_code == 200
            
            # Verify final session state
            with client.session_transaction() as sess:
                assert sess.get('device_auth_token') == 'final-device-token'
                assert sess.get('own_device_id') == 'final-device-id'

    @pytest.mark.timeout(30)
    def test_flow_with_password_hashes(self, client):
        """Test that password hashes are correctly generated and passed to API."""
        # Set up session with tokens
        with client.session_transaction() as sess:
            sess['mail_login_token'] = 'test-login-token'
            sess['mail_auth_token'] = 'test-auth-token'
        
        with patch('app.AuthClient') as mock_auth_client_class, \
             patch('app.create_sync_manager') as mock_create_sync_manager:
            mock_client = MagicMock()
            
            # Mock create_family_rest response
            mock_create_response = MagicMock()
            mock_create_response.success = True
            mock_create_response.data = {
                'deviceAuthToken': 'device-token',
                'ownDeviceId': 'device-id'
            }
            mock_client.create_family_rest.return_value = mock_create_response
            
            mock_auth_client_class.return_value = mock_client
            
            # Mock sync manager to return success
            mock_sync_manager = MagicMock()
            mock_sync_manager.do_sync.return_value = True
            mock_create_sync_manager.return_value = mock_sync_manager
            
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
            
            assert response.status_code == 200
            
            # Verify create_family_rest was called with password data
            assert mock_client.create_family_rest.called
            call_args = mock_client.create_family_rest.call_args
            
            # Check that password_data was passed
            assert 'parent_password' in call_args.kwargs
            password_data = call_args.kwargs['parent_password']
            
            # Verify password data structure
            # Note: PlaintextParentPassword does NOT include 'encrypted' field
            # The server's JSON schema has additionalProperties: false for PlaintextParentPassword
            assert 'hash' in password_data
            assert 'secondHash' in password_data
            assert 'secondSalt' in password_data
            # 'encrypted' field should NOT be present - it's only for EncryptableParentPassword
            assert 'encrypted' not in password_data

    @pytest.mark.timeout(30)
    def test_flow_with_locale_and_device_info(self, client):
        """Test that device info is passed to API correctly."""
        # Set up session with tokens
        with client.session_transaction() as sess:
            sess['mail_login_token'] = 'test-login-token'
            sess['mail_auth_token'] = 'test-auth-token'
        
        with patch('app.AuthClient') as mock_auth_client_class, \
             patch('app.create_sync_manager') as mock_create_sync_manager:
            mock_client = MagicMock()
            
            # Mock create_family_rest response
            mock_create_response = MagicMock()
            mock_create_response.success = True
            mock_create_response.data = {
                'deviceAuthToken': 'device-token',
                'ownDeviceId': 'device-id'
            }
            mock_client.create_family_rest.return_value = mock_create_response
            
            mock_auth_client_class.return_value = mock_client
            
            # Mock sync manager to return success
            mock_sync_manager = MagicMock()
            mock_sync_manager.do_sync.return_value = True
            mock_create_sync_manager.return_value = mock_sync_manager
            
            response = client.post('/create-family', data={
                'step': '3',
                'password': 'testpass123',
                'secondPassword': 'testpass123',
                'deviceName': 'My Device',
                'deviceModel': 'My Model',
                'locale': 'nl',
                'parentName': 'Test Parent',
                'timeZone': 'Europe/Amsterdam'
            }, follow_redirects=True)
            
            assert response.status_code == 200
            
            # Verify create_family_rest was called with correct parameters
            call_args = mock_client.create_family_rest.call_args
            # locale is NOT sent to server (not in schema), but is accepted as input
            assert call_args.kwargs.get('device_name') == 'My Device'
            # parent_device is passed as a dict with 'model' key
            parent_device = call_args.kwargs.get('parent_device')
            assert parent_device is not None
            assert parent_device.get('model') == 'My Model'

    @pytest.mark.timeout(30)
    def test_flow_with_optional_fields(self, client):
        """Test that optional fields are handled correctly."""
        # Set up session with tokens
        with client.session_transaction() as sess:
            sess['mail_login_token'] = 'test-login-token'
            sess['mail_auth_token'] = 'test-auth-token'
        
        with patch('app.AuthClient') as mock_auth_client_class, \
             patch('app.create_sync_manager') as mock_create_sync_manager:
            mock_client = MagicMock()
            
            # Mock create_family_rest response
            mock_create_response = MagicMock()
            mock_create_response.success = True
            mock_create_response.data = {
                'deviceAuthToken': 'device-token',
                'ownDeviceId': 'device-id'
            }
            mock_client.create_family_rest.return_value = mock_create_response
            
            mock_auth_client_class.return_value = mock_client
            
            # Mock sync manager to return success
            mock_sync_manager = MagicMock()
            mock_sync_manager.do_sync.return_value = True
            mock_create_sync_manager.return_value = mock_sync_manager
            
            # Test with default locale (en)
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
            
            assert response.status_code == 200
            
            # Verify create_family_rest was called
            assert mock_client.create_family_rest.called
            call_args = mock_client.create_family_rest.call_args
            # locale is NOT sent to server (not in schema)


class TestCreateFamilyErrorHandling:
    """Tests for error handling in the create family flow."""

    @pytest.mark.timeout(30)
    def test_flow_api_error_at_step1(self, client):
        """Test that API error at step 1 is handled correctly."""
        response = client.get('/create-family')
        assert response.status_code == 200
        
        with patch('app.AuthClient') as mock_auth_client_class:
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.success = False
            mock_response.error_message = 'Rate limit exceeded'
            mock_client.send_mail_login_code.return_value = mock_response
            mock_auth_client_class.return_value = mock_client
            
            response = client.post('/create-family', data={
                'step': '1',
                'mail': 'test@example.com'
            }, follow_redirects=True)
            
            assert response.status_code == 200
            assert b'Rate limit exceeded' in response.data

    @pytest.mark.timeout(30)
    def test_flow_api_error_at_step2(self, client):
        """Test that API error at step 2 is handled correctly."""
        with client.session_transaction() as sess:
            sess['mail_login_token'] = 'test-login-token'
        
        with patch('app.AuthClient') as mock_auth_client_class:
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.success = False
            mock_response.error_message = 'Invalid verification code'
            mock_client.sign_in_by_mail_code.return_value = mock_response
            mock_auth_client_class.return_value = mock_client
            
            response = client.post('/create-family', data={
                'step': '2',
                'receivedCode': 'Haus Regen Tisch'
            }, follow_redirects=True)
            
            assert response.status_code == 200
            assert b'Invalid verification code' in response.data

    @pytest.mark.timeout(30)
    def test_flow_api_error_at_step3(self, client):
        """Test that API error at step 3 is handled correctly."""
        with client.session_transaction() as sess:
            sess['mail_login_token'] = 'test-login-token'
            sess['mail_auth_token'] = 'test-auth-token'
        
        with patch('app.AuthClient') as mock_auth_client_class, \
             patch('app.create_sync_manager') as mock_create_sync_manager:
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.success = False
            mock_response.error_message = 'Failed to create family'
            mock_client.create_family_rest.return_value = mock_response
            mock_auth_client_class.return_value = mock_client
            
            # Mock sync manager to return success (even on error, sync should be called)
            mock_sync_manager = MagicMock()
            mock_sync_manager.do_sync.return_value = True
            mock_create_sync_manager.return_value = mock_sync_manager
            
            response = client.post('/create-family', data={
                'step': '3',
                'password': 'testpass123',
                'secondPassword': 'testpass123',
                'parentName': 'Test Parent',
                'timeZone': 'Europe/Amsterdam',
                'deviceModel': 'Test Model',
                'deviceName': 'Test Device'
            }, follow_redirects=True)
            
            assert response.status_code == 200
            assert b'Failed to create family' in response.data

    @pytest.mark.timeout(30)
    def test_flow_session_expired_at_step2(self, client):
        """Test that expired session at step 2 is handled correctly."""
        # Don't set mail_login_token
        response = client.post('/create-family', data={
            'step': '2',
            'receivedCode': 'Pferd Miete abwenden'
        }, follow_redirects=True)
        
        assert response.status_code == 200
        assert b'Session expired' in response.data

    @pytest.mark.timeout(30)
    def test_flow_session_expired_at_step3(self, client):
        """Test that expired session at step 3 is handled correctly."""
        # Only set mail_login_token, not mail_auth_token
        with client.session_transaction() as sess:
            sess['mail_login_token'] = 'test-login-token'
        
        response = client.post('/create-family', data={
            'step': '3',
            'password': 'testpass123',
            'secondPassword': 'testpass123',
            'parentName': 'Test Parent',
            'timeZone': 'Europe/Amsterdam',
            'deviceModel': 'Test Model',
            'deviceName': 'Test Device'
        }, follow_redirects=True)
        
        assert response.status_code == 200
        assert b'Session expired' in response.data


class TestCreateFamilyCancel:
    """Tests for cancel functionality in the create family flow."""

    @pytest.mark.timeout(10)
    def test_cancel_clears_all_session_data(self, client):
        """Test that cancel clears all create family session data."""
        # Set up session with all tokens
        with client.session_transaction() as sess:
            sess['mail_login_token'] = 'test-login-token'
            sess['mail_auth_token'] = 'test-auth-token'
            sess['device_auth_token'] = 'test-device-token'
            sess['own_device_id'] = 'test-device-id'
            sess['create_family_error'] = 'Test error'
        
        response = client.post('/create-family/cancel', follow_redirects=True)
        
        assert response.status_code == 200
        
        # Verify all session data is cleared
        with client.session_transaction() as sess:
            assert 'mail_login_token' not in sess
            assert 'mail_auth_token' not in sess
            assert 'device_auth_token' not in sess
            assert 'own_device_id' not in sess
            assert 'create_family_error' not in sess

    @pytest.mark.timeout(10)
    def test_cancel_redirects_to_dashboard(self, client):
        """Test that cancel redirects to dashboard."""
        response = client.post('/create-family/cancel', follow_redirects=False)
        
        assert response.status_code == 302
        assert '/dashboardV2' in response.headers.get('Location', '')


class TestCreateFamilySessionManagement:
    """Tests for session management in the create family flow."""

    @pytest.mark.timeout(10)
    def test_session_persists_across_steps(self, client):
        """Test that session data persists correctly across steps."""
        # Step 1: Submit email
        with patch('app.AuthClient') as mock_auth_client_class:
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.success = True
            mock_response.data = {'mailLoginToken': 'persistent-token'}
            mock_client.send_mail_login_code.return_value = mock_response
            mock_auth_client_class.return_value = mock_client
            
            client.post('/create-family', data={
                'step': '1',
                'mail': 'test@example.com'
            })
        
        # Verify token is in session
        with client.session_transaction() as sess:
            assert sess.get('mail_login_token') == 'persistent-token'
        
        # Step 2: Submit verification code (3-word passphrase)
        with patch('app.AuthClient') as mock_auth_client_class:
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.success = True
            mock_response.data = {'mailAuthToken': 'auth-token'}
            mock_client.sign_in_by_mail_code.return_value = mock_response
            mock_auth_client_class.return_value = mock_client
            
            client.post('/create-family', data={
                'step': '2',
                'receivedCode': 'Pferd Miete abwenden'
            })
        
        # Verify auth token is in session
        with client.session_transaction() as sess:
            assert sess.get('mail_auth_token') == 'auth-token'
            # mail_login_token should still be there
            assert sess.get('mail_login_token') == 'persistent-token'

    @pytest.mark.timeout(10)
    def test_error_message_displayed_once(self, client):
        """Test that error message is displayed once and then cleared."""
        # Set an error in session
        with client.session_transaction() as sess:
            sess['create_family_error'] = 'Test error message'
        
        # Get the page - error should be displayed
        response = client.get('/create-family')
        assert b'Test error message' in response.data
        
        # Get the page again - error should be cleared (popped)
        response = client.get('/create-family')
        assert b'Test error message' not in response.data