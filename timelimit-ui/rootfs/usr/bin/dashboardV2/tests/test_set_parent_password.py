"""Unit tests for set parent password routes.

This module tests the server-side rendered set parent password flow:
- GET /set-parent-password - renders the password form
- POST /set-parent-password - processes form submission and stores hash
"""

import pytest
from unittest.mock import patch, MagicMock


class TestGetSetParentPassword:
    """Tests for GET /set-parent-password route."""

    @pytest.mark.timeout(10)
    def test_get_set_parent_password_renders_form(self, client):
        """Test that GET /set-parent-password renders the form when authenticated."""
        with client.session_transaction() as sess:
            sess['device_auth_token'] = 'test-device-token'
        
        response = client.get('/set-parent-password')
        
        assert response.status_code == 200
        assert b'Set Parent Password Hash' in response.data
        assert b'password' in response.data.lower()

    @pytest.mark.timeout(10)
    def test_get_set_parent_password_redirects_when_not_authenticated(self, client):
        """Test that GET /set-parent-password redirects when not authenticated."""
        response = client.get('/set-parent-password')
        
        assert response.status_code == 302
        assert '/dashboardV2' in response.headers.get('Location', '')


class TestPostSetParentPassword:
    """Tests for POST /set-parent-password route."""

    @pytest.mark.timeout(10)
    def test_post_set_parent_password_missing_auth(self, client):
        """Test that POST /set-parent-password fails without authentication."""
        response = client.post('/set-parent-password', data={
            'password': 'testpassword123'
        }, follow_redirects=True)
        
        # Should redirect to dashboard
        assert response.status_code == 200

    @pytest.mark.timeout(10)
    def test_post_set_parent_password_missing_password_and_hash(self, client):
        """Test that POST /set-parent-password fails with missing password and hash."""
        with client.session_transaction() as sess:
            sess['device_auth_token'] = 'test-device-token'
        
        response = client.post('/set-parent-password', data={}, follow_redirects=False)
        
        # Should redirect back to the form
        assert response.status_code == 302
        assert '/set-parent-password' in response.headers.get('Location', '')

    @pytest.mark.timeout(10)
    def test_post_set_parent_password_with_direct_hash(self, client):
        """Test that POST /set-parent-password accepts a direct hash input."""
        with client.session_transaction() as sess:
            sess['device_auth_token'] = 'test-device-token'
        
        with patch('app.get_database') as mock_get_db:
            mock_db = MagicMock()
            mock_get_db.return_value = mock_db
            
            # Mock upsert_family_password_hash to return True
            with patch('app.upsert_family_password_hash', return_value=True) as mock_upsert:
                response = client.post('/set-parent-password', data={
                    'parentPasswordSecondHash': '$2b$12$testhash123'
                }, follow_redirects=True)
                
                # Should redirect to dashboard with success message
                assert response.status_code == 200
                
                # Verify upsert was called with correct parameters
                mock_upsert.assert_called_once()
                call_kwargs = mock_upsert.call_args.kwargs
                assert call_kwargs['db'] == mock_db
                assert call_kwargs['device_auth_token'] == 'test-device-token'
                assert call_kwargs['parent_password_second_hash'] == '$2b$12$testhash123'
                
                # Verify hash was stored in session
                with client.session_transaction() as sess:
                    assert sess.get('parent_password_second_hash') == '$2b$12$testhash123'

    @pytest.mark.timeout(10)
    def test_post_set_parent_password_with_password_hashes_it(self, client):
        """Test that POST /set-parent-password hashes a password with bcrypt."""
        with client.session_transaction() as sess:
            sess['device_auth_token'] = 'test-device-token'
        
        with patch('app.get_database') as mock_get_db:
            mock_db = MagicMock()
            mock_get_db.return_value = mock_db
            
            with patch('app.upsert_family_password_hash', return_value=True) as mock_upsert:
                response = client.post('/set-parent-password', data={
                    'password': 'testpassword123'
                }, follow_redirects=True)
                
                # Should redirect to dashboard with success message
                assert response.status_code == 200
                
                # Verify upsert was called
                mock_upsert.assert_called_once()
                call_kwargs = mock_upsert.call_args.kwargs
                assert call_kwargs['db'] == mock_db
                assert call_kwargs['device_auth_token'] == 'test-device-token'
                
                # Verify the hash is a valid bcrypt hash (starts with $2a$ to match family creation)
                stored_hash = call_kwargs['parent_password_second_hash']
                assert stored_hash.startswith('$2a$')
                
                # Verify hash was stored in session
                with client.session_transaction() as sess:
                    assert sess.get('parent_password_second_hash') == stored_hash

    @pytest.mark.timeout(10)
    def test_post_set_parent_password_hash_persists_to_database(self, client):
        """Test that POST /set-parent-password persists hash to database."""
        with client.session_transaction() as sess:
            sess['device_auth_token'] = 'test-device-token'
        
        with patch('app.get_database') as mock_get_db:
            mock_db = MagicMock()
            mock_get_db.return_value = mock_db
            
            with patch('app.upsert_family_password_hash', return_value=True):
                response = client.post('/set-parent-password', data={
                    'parentPasswordSecondHash': '$2b$12$testhash123'
                }, follow_redirects=True)
                
                assert response.status_code == 200
                
                # Verify the hash was stored in session
                with client.session_transaction() as sess:
                    assert sess.get('parent_password_second_hash') == '$2b$12$testhash123'

    @pytest.mark.timeout(10)
    def test_post_set_parent_password_hash_in_session(self, client):
        """Test that POST /set-parent-password stores hash in session for immediate use."""
        with client.session_transaction() as sess:
            sess['device_auth_token'] = 'test-device-token'
        
        with patch('app.get_database') as mock_get_db:
            mock_db = MagicMock()
            mock_get_db.return_value = mock_db
            
            with patch('app.upsert_family_password_hash', return_value=True):
                response = client.post('/set-parent-password', data={
                    'parentPasswordSecondHash': '$2b$12$testhash123'
                }, follow_redirects=True)
                
                # Verify hash is in session
                with client.session_transaction() as sess:
                    assert sess.get('parent_password_second_hash') == '$2b$12$testhash123'

    @pytest.mark.timeout(10)
    def test_post_set_parent_password_uses_upsert_not_update(self, client):
        """Test that POST /set-parent-password uses upsert (handles missing family record)."""
        with client.session_transaction() as sess:
            sess['device_auth_token'] = 'test-device-token'
        
        with patch('app.get_database') as mock_get_db:
            mock_db = MagicMock()
            mock_get_db.return_value = mock_db
            
            # Use upsert_family_password_hash which handles both INSERT and UPDATE
            with patch('app.upsert_family_password_hash', return_value=True) as mock_upsert:
                response = client.post('/set-parent-password', data={
                    'parentPasswordSecondHash': '$2b$12$testhash123'
                }, follow_redirects=True)
                
                assert response.status_code == 200
                
                # Verify upsert_family_password_hash was called (not update_family_password_hash)
                mock_upsert.assert_called_once()

    @pytest.mark.timeout(10)
    def test_post_set_parent_password_hash_format(self, client):
        """Test that stored hash has correct bcrypt format."""
        with client.session_transaction() as sess:
            sess['device_auth_token'] = 'test-device-token'
        
        with patch('app.get_database') as mock_get_db:
            mock_db = MagicMock()
            mock_get_db.return_value = mock_db
            
            with patch('app.upsert_family_password_hash', return_value=True):
                response = client.post('/set-parent-password', data={
                    'parentPasswordSecondHash': '$2b$12$testhash123'
                }, follow_redirects=True)
                
                assert response.status_code == 200
                
                # Verify hash format
                with client.session_transaction() as sess:
                    stored_hash = sess.get('parent_password_second_hash')
                    assert stored_hash is not None
                    assert stored_hash.startswith('$2b$')


class TestSetParentPasswordIntegration:
    """Integration tests for set parent password flow."""

    @pytest.mark.timeout(10)
    def test_set_parent_password_flow_complete(self, client):
        """Test the complete set parent password flow."""
        # Step 1: Authenticate
        with client.session_transaction() as sess:
            sess['device_auth_token'] = 'test-device-token'
        
        # Step 2: Set password hash
        with patch('app.get_database') as mock_get_db:
            mock_db = MagicMock()
            mock_get_db.return_value = mock_db
            
            with patch('app.upsert_family_password_hash', return_value=True):
                response = client.post('/set-parent-password', data={
                    'parentPasswordSecondHash': '$2b$12$testhash123'
                }, follow_redirects=True)
                
                assert response.status_code == 200
                
                # Verify session has the hash
                with client.session_transaction() as sess:
                    assert sess.get('parent_password_second_hash') == '$2b$12$testhash123'

    @pytest.mark.timeout(10)
    def test_set_parent_password_with_special_characters(self, client):
        """Test that set parent password handles special characters in hash."""
        with client.session_transaction() as sess:
            sess['device_auth_token'] = 'test-device-token'
        
        with patch('app.get_database') as mock_get_db:
            mock_db = MagicMock()
            mock_get_db.return_value = mock_db
            
            with patch('app.upsert_family_password_hash', return_value=True):
                # Hash with special characters
                special_hash = '$2b$12$test_hash-with.special:chars@123'
                response = client.post('/set-parent-password', data={
                    'parentPasswordSecondHash': special_hash
                }, follow_redirects=True)
                
                assert response.status_code == 200
                
                with client.session_transaction() as sess:
                    assert sess.get('parent_password_second_hash') == special_hash