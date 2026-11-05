"""Integration tests for the complete create family flow.

This module tests the end-to-end create family flow:
1. User visits /create-family (step 1 - email)
2. User submits email, receives verification code
3. User submits verification code (step 2)
4. User submits password (step 3)
5. Family is created, user redirected to dashboard
"""

import json
import pytest
from unittest.mock import patch, MagicMock, call, Mock
import time

from database import update_family_parent_user_id, get_users_by_device_auth_token


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


# ============================================================================
# Add User to Family Integration Tests
# ============================================================================

class TestAddUserToFamilyIntegration:
    """Integration tests for the complete add user to family flow.
    
    This module tests the end-to-end add user flow:
    1. Parent is authenticated with device_auth_token and parent_password_second_hash
    2. Parent calls POST /api/dashboard/users/add with user name
    3. Server creates add-device token via create_add_device_token
    4. Server registers child device via add_device
    5. Server syncs users via pull_status
    6. Server saves users to database via save_users
    7. Response includes userId, deviceAuthToken, and ownDeviceId
    """

    @pytest.fixture(autouse=True)
    def _server_confirms_pushes(self):
        """The server confirms every pushed parent action (the push itself is tested in
        test_action_pusher.py and test_action_builder.py)."""
        with patch('app._push_parent_actions_safely',
                   return_value={'synced': True, 'syncMessage': None}) as push:
            self.push_mock = push
            yield push

    @pytest.mark.timeout(30)
    def test_add_user_complete_flow(self, auth_session):
        """Test complete flow from API to database.
        
        This test verifies:
        1. API call is made with correct parameters
        2. AuthClient.create_add_device_token is called
        3. AuthClient.add_device is called
        4. AuthClient.pull_status is called
        5. Users are saved to database
        6. Response contains correct data
        """
        # Get device_auth_token from session
        with auth_session.session_transaction() as sess:
            device_auth_token = sess['device_auth_token']
            sess['parent_password_second_hash'] = '$2b$12$test_hash'
        
        # Set parent_user_id in database (required for the endpoint)
        db = auth_session.application.test_db
        parent_user_id = 'user_parent_123'
        update_family_parent_user_id(db, device_auth_token, parent_user_id)
        
        # Mock the AuthClient and its methods
        with patch('app.AuthClient') as mock_auth_client_class:
            mock_client = MagicMock()
            
            # Mock create_add_device_token response
            token_response = MagicMock()
            token_response.success = True
            token_response.data = {
                'token': 'test_register_token',
                'deviceId': 'device_test_123'
            }
            mock_client.create_add_device_token.return_value = token_response
            
            # Mock add_device response
            add_device_response = MagicMock()
            add_device_response.success = True
            add_device_response.data = {
                'deviceAuthToken': 'child_device_auth_token',
                'ownDeviceId': 'child_device_id'
            }
            mock_client.add_device.return_value = add_device_response
            
            # Mock pull_status response
            pull_status_response = MagicMock()
            pull_status_response.success = True
            pull_status_response.data = {
                'users': {
                    'data': [
                        {
                            'id': 'user_child_456',
                            'name': 'Test Child',
                            'type': 'child',
                            'mail': 'child@test.com',
                            'timeZone': 'Europe/Amsterdam'
                        }
                    ]
                }
            }
            mock_client.pull_status.return_value = pull_status_response
            
            mock_auth_client_class.return_value = mock_client
            
            # Make the API call
            response = auth_session.post('/api/dashboard/users/add',
                                         json={'name': 'Test Child', 'timeZone': 'Europe/Amsterdam'})
            
            assert response.status_code == 200
            data = json.loads(response.data)
            assert data['status'] == 'ok'
            assert data['userId'] == 'user_child_456'
            assert data['deviceAuthToken'] == 'child_device_auth_token'
            assert data['ownDeviceId'] == 'child_device_id'
            
            # Verify the client was called with correct parameters
            mock_client.create_add_device_token.assert_called_once()
            call_kwargs = mock_client.create_add_device_token.call_args[1]
            assert call_kwargs['device_auth_token'] == device_auth_token
            assert call_kwargs['parent_id'] == parent_user_id
            assert call_kwargs['parent_password_second_hash'] == 'device'  # device integrity, no password needed
            
            mock_client.add_device.assert_called_once()
            add_device_kwargs = mock_client.add_device.call_args[1]
            assert add_device_kwargs['register_token'] == 'test_register_token'
            assert add_device_kwargs['device_name'] is None
            assert add_device_kwargs['device_model'] is None
            assert add_device_kwargs['client_level'] == 7
            
            mock_client.pull_status.assert_called_once()
            pull_status_kwargs = mock_client.pull_status.call_args[1]
            # After fix: pull_status should be called with parent's device_auth_token
            # so users are saved with the correct key for the dashboard to retrieve
            assert pull_status_kwargs['device_auth_token'] == device_auth_token
            
            # Verify users were saved to database with parent's device_auth_token
            users = get_users_by_device_auth_token(db, device_auth_token)
            assert len(users) == 1
            assert users[0]['name'] == 'Test Child'
            assert users[0]['type'] == 'child'

    @pytest.mark.timeout(30)
    def test_add_user_with_device_info(self, auth_session):
        """Test adding user with device name and model.
        
        This test verifies that device info is correctly passed through
        the add-device flow.
        """
        # Get device_auth_token from session
        with auth_session.session_transaction() as sess:
            device_auth_token = sess['device_auth_token']
            sess['parent_password_second_hash'] = '$2b$12$test_hash'
        
        # Set parent_user_id in database
        db = auth_session.application.test_db
        parent_user_id = 'user_parent_456'
        update_family_parent_user_id(db, device_auth_token, parent_user_id)
        
        # Mock the AuthClient
        with patch('app.AuthClient') as mock_auth_client_class:
            mock_client = MagicMock()
            
            # Mock create_add_device_token response
            token_response = MagicMock()
            token_response.success = True
            token_response.data = {
                'token': 'test_register_token_with_device',
                'deviceId': 'device_test_456'
            }
            mock_client.create_add_device_token.return_value = token_response
            
            # Mock add_device response
            add_device_response = MagicMock()
            add_device_response.success = True
            add_device_response.data = {
                'deviceAuthToken': 'child_device_auth_token_with_device',
                'ownDeviceId': 'child_device_id_with_device'
            }
            mock_client.add_device.return_value = add_device_response
            
            # Mock pull_status response
            pull_status_response = MagicMock()
            pull_status_response.success = True
            pull_status_response.data = {
                'users': {
                    'data': [
                        {
                            'id': 'user_child_789',
                            'name': 'Child With Device',
                            'type': 'child',
                            'mail': 'child_with_device@test.com',
                            'timeZone': 'Europe/Amsterdam'
                        }
                    ]
                }
            }
            mock_client.pull_status.return_value = pull_status_response
            
            mock_auth_client_class.return_value = mock_client
            
            # Make the API call with device info
            response = auth_session.post('/api/dashboard/users/add',
                                         json={
                                             'timeZone': 'Europe/Amsterdam',
                                             'name': 'Child With Device',
                                             'deviceName': 'My Child Device',
                                             'deviceModel': 'Pixel 7'
                                         })
            
            assert response.status_code == 200
            data = json.loads(response.data)
            assert data['status'] == 'ok'
            
            # Verify add_device was called with device info
            add_device_kwargs = mock_client.add_device.call_args[1]
            assert add_device_kwargs['device_name'] == 'My Child Device'
            assert add_device_kwargs['device_model'] == 'Pixel 7'

    @pytest.mark.timeout(30)
    def test_add_user_error_handling(self, auth_session):
        """Test error handling in complete flow.
        
        This test verifies that errors at each step are properly handled
        and appropriate error responses are returned.
        """
        # Get device_auth_token from session
        with auth_session.session_transaction() as sess:
            device_auth_token = sess['device_auth_token']
            sess['parent_password_second_hash'] = '$2b$12$test_hash'
        
        # Set parent_user_id in database
        db = auth_session.application.test_db
        parent_user_id = 'user_parent_789'
        update_family_parent_user_id(db, device_auth_token, parent_user_id)
        
        # Mock the AuthClient with token creation failure
        with patch('app.AuthClient') as mock_auth_client_class:
            mock_client = MagicMock()
            
            # Mock create_add_device_token to return failure
            token_response = MagicMock()
            token_response.success = False
            token_response.error_code = 'unauthorized'
            token_response.error_message = 'Unauthorized'
            token_response.status_code = 401
            mock_client.create_add_device_token.return_value = token_response
            
            mock_auth_client_class.return_value = mock_client
            
            # Make the API call
            response = auth_session.post('/api/dashboard/users/add',
                                         json={'name': 'Test Child', 'timeZone': 'Europe/Amsterdam'})
            
            assert response.status_code == 500
            data = json.loads(response.data)
            assert data['status'] == 'error'
            assert data['error_code'] == 'unauthorized'
            assert data['error'] == 'Unauthorized'

    @pytest.mark.timeout(30)
    def test_add_user_edge_cases(self, auth_session):
        """Test edge cases in add user flow.
        
        This test verifies:
        1. User name with special characters
        2. Empty device name and model (should be None)
        3. User name with spaces
        """
        # Get device_auth_token from session
        with auth_session.session_transaction() as sess:
            device_auth_token = sess['device_auth_token']
            sess['parent_password_second_hash'] = '$2b$12$test_hash'
        
        # Set parent_user_id in database
        db = auth_session.application.test_db
        parent_user_id = 'user_parent_edge'
        update_family_parent_user_id(db, device_auth_token, parent_user_id)
        
        # Mock the AuthClient
        with patch('app.AuthClient') as mock_auth_client_class:
            mock_client = MagicMock()
            
            # Mock create_add_device_token response
            token_response = MagicMock()
            token_response.success = True
            token_response.data = {
                'token': 'test_register_token_edge',
                'deviceId': 'device_test_edge'
            }
            mock_client.create_add_device_token.return_value = token_response
            
            # Mock add_device response
            add_device_response = MagicMock()
            add_device_response.success = True
            add_device_response.data = {
                'deviceAuthToken': 'child_device_auth_token_edge',
                'ownDeviceId': 'child_device_id_edge'
            }
            mock_client.add_device.return_value = add_device_response
            
            # Mock pull_status response
            pull_status_response = MagicMock()
            pull_status_response.success = True
            pull_status_response.data = {
                'users': {
                    'data': [
                        {
                            'id': 'user_child_edge',
                            'name': 'Child with Special Chars! @#',
                            'type': 'child',
                            'mail': 'child_edge@test.com',
                            'timeZone': 'Europe/Amsterdam'
                        }
                    ]
                }
            }
            mock_client.pull_status.return_value = pull_status_response
            
            mock_auth_client_class.return_value = mock_client
            
            # Test with user name containing special characters and spaces
            response = auth_session.post('/api/dashboard/users/add',
                                         json={
                                             'timeZone': 'Europe/Amsterdam',
                                             'name': 'Child with Special Chars! @#',
                                             'deviceName': '',  # Empty string
                                             'deviceModel': ''  # Empty string
                                         })
            
            assert response.status_code == 200
            data = json.loads(response.data)
            assert data['status'] == 'ok'
            
            # Verify add_device was called with None for empty device info
            add_device_kwargs = mock_client.add_device.call_args[1]
            assert add_device_kwargs['device_name'] is None
            assert add_device_kwargs['device_model'] is None

    @pytest.mark.timeout(30)
    def test_add_user_sync_failure(self, auth_session):
        """Test adding user when sync fails.
        
        This test verifies that when pull_status fails,
        the error is properly returned.
        """
        # Get device_auth_token from session
        with auth_session.session_transaction() as sess:
            device_auth_token = sess['device_auth_token']
            sess['parent_password_second_hash'] = '$2b$12$test_hash'
        
        # Set parent_user_id in database
        db = auth_session.application.test_db
        parent_user_id = 'user_parent_sync_fail'
        update_family_parent_user_id(db, device_auth_token, parent_user_id)
        
        # Mock the AuthClient
        with patch('app.AuthClient') as mock_auth_client_class:
            mock_client = MagicMock()
            
            # Mock create_add_device_token response
            token_response = MagicMock()
            token_response.success = True
            token_response.data = {
                'token': 'test_register_token_sync',
                'deviceId': 'device_test_sync'
            }
            mock_client.create_add_device_token.return_value = token_response
            
            # Mock add_device response
            add_device_response = MagicMock()
            add_device_response.success = True
            add_device_response.data = {
                'deviceAuthToken': 'child_device_auth_token_sync',
                'ownDeviceId': 'child_device_id_sync'
            }
            mock_client.add_device.return_value = add_device_response
            
            # Mock pull_status to return failure
            pull_status_response = MagicMock()
            pull_status_response.success = False
            pull_status_response.error_code = 'sync_failed'
            pull_status_response.error_message = 'Sync failed'
            pull_status_response.status_code = 500
            mock_client.pull_status.return_value = pull_status_response
            
            mock_auth_client_class.return_value = mock_client
            
            # Make the API call
            response = auth_session.post('/api/dashboard/users/add',
                                         json={'name': 'Test Child', 'timeZone': 'Europe/Amsterdam'})
            
            assert response.status_code == 500
            data = json.loads(response.data)
            assert data['status'] == 'error'
            assert data['error_code'] == 'sync_failed'
            assert data['error'] == 'Sync failed'

    @pytest.mark.timeout(30)
    def test_add_user_device_addition_failure(self, auth_session):
        """Test adding user when device addition fails.
        
        This test verifies that when add_device fails,
        the error is properly returned.
        """
        # Get device_auth_token from session
        with auth_session.session_transaction() as sess:
            device_auth_token = sess['device_auth_token']
            sess['parent_password_second_hash'] = '$2b$12$test_hash'
        
        # Set parent_user_id in database
        db = auth_session.application.test_db
        parent_user_id = 'user_parent_device_fail'
        update_family_parent_user_id(db, device_auth_token, parent_user_id)
        
        # Mock the AuthClient
        with patch('app.AuthClient') as mock_auth_client_class:
            mock_client = MagicMock()
            
            # Mock create_add_device_token response
            token_response = MagicMock()
            token_response.success = True
            token_response.data = {
                'token': 'test_register_token_device',
                'deviceId': 'device_test_device'
            }
            mock_client.create_add_device_token.return_value = token_response
            
            # Mock add_device to return failure
            add_device_response = MagicMock()
            add_device_response.success = False
            add_device_response.error_code = 'device_registration_failed'
            add_device_response.error_message = 'Device registration failed'
            add_device_response.status_code = 400
            mock_client.add_device.return_value = add_device_response
            
            mock_auth_client_class.return_value = mock_client
            
            # Make the API call
            response = auth_session.post('/api/dashboard/users/add',
                                         json={'name': 'Test Child', 'timeZone': 'Europe/Amsterdam'})
            
            assert response.status_code == 500
            data = json.loads(response.data)
            assert data['status'] == 'error'
            assert data['error_code'] == 'device_registration_failed'
            assert data['error'] == 'Device registration failed'

    @pytest.mark.timeout(30)
    def test_add_user_parent_user_id_not_found(self, auth_session):
        """Test adding user when parent user ID is not found.
        
        This test verifies that when the parent user ID cannot be
        retrieved from the database, an appropriate error is returned.
        """
        # Get device_auth_token from session
        with auth_session.session_transaction() as sess:
            device_auth_token = sess['device_auth_token']
            sess['parent_password_second_hash'] = '$2b$12$test_hash'
        
        # Do NOT set parent_user_id in database - this should cause the error
        
        # Make the API call
        response = auth_session.post('/api/dashboard/users/add',
                                     json={'name': 'Test Child', 'timeZone': 'Europe/Amsterdam'})
        
        assert response.status_code == 500
        data = json.loads(response.data)
        assert data['status'] == 'error'
        assert data['error_code'] == 'server_error'
        assert data['error'] == 'Parent user ID not found'

    @pytest.mark.timeout(30)
    def test_add_user_user_not_in_sync_response(self, auth_session):
        """Test adding user when the user is not in the sync response.
        
        This test verifies that when the newly added user is not found
        in the pull_status response, a local user record is created
        and the operation still succeeds with a valid userId.
        """
        # Get device_auth_token from session
        with auth_session.session_transaction() as sess:
            device_auth_token = sess['device_auth_token']
            sess['parent_password_second_hash'] = '$2b$12$test_hash'
        
        # Set parent_user_id in database
        db = auth_session.application.test_db
        parent_user_id = 'user_parent_not_found'
        update_family_parent_user_id(db, device_auth_token, parent_user_id)
        
        # Mock the AuthClient
        with patch('app.AuthClient') as mock_auth_client_class:
            mock_client = MagicMock()
            
            # Mock create_add_device_token response
            token_response = MagicMock()
            token_response.success = True
            token_response.data = {
                'token': 'test_register_token_not_found',
                'deviceId': 'device_test_not_found'
            }
            mock_client.create_add_device_token.return_value = token_response
            
            # Mock add_device response
            add_device_response = MagicMock()
            add_device_response.success = True
            add_device_response.data = {
                'deviceAuthToken': 'child_device_auth_token_not_found',
                'ownDeviceId': 'child_device_id_not_found'
            }
            mock_client.add_device.return_value = add_device_response
            
            # Mock pull_status response with different user
            pull_status_response = MagicMock()
            pull_status_response.success = True
            pull_status_response.data = {
                'users': {
                    'data': [
                        {
                            'id': 'user_other',
                            'name': 'Other User',
                            'type': 'child',
                            'mail': 'other@test.com',
                            'timeZone': 'Europe/Amsterdam'
                        }
                    ]
                }
            }
            mock_client.pull_status.return_value = pull_status_response
            
            mock_auth_client_class.return_value = mock_client
            
            # Make the API call
            response = auth_session.post('/api/dashboard/users/add',
                                         json={'name': 'Test Child', 'timeZone': 'Europe/Amsterdam'})
            
            assert response.status_code == 200
            data = json.loads(response.data)
            assert data['status'] == 'ok'
            # The user is not in the sync response, so the id of the ADD_USER action that the
            # server confirmed is used and a local user record is created under it
            pushed_actions = self.push_mock.call_args[0][1]
            assert [a['type'] for a in pushed_actions] == ['ADD_USER']
            assert data['userId'] == pushed_actions[0]['userId']
            assert data['deviceAuthToken'] == 'child_device_auth_token_not_found'
            
            # Verify the user was created locally in the database
            users = get_users_by_device_auth_token(db, device_auth_token)
            assert len(users) == 2  # Other User + Test Child
            user_names = [u['name'] for u in users]
            assert 'Other User' in user_names
            assert 'Test Child' in user_names