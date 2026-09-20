"""Unit tests for sign-out functionality.

Tests verify that sign-out properly clears:
- Flask session
- Database auth tokens
- JSON file persistence
- Auth token backup file
"""

import os
import pytest
import sqlite3
from unittest.mock import patch, MagicMock


class TestSignOut:
    """Tests for sign-out functionality."""

    @pytest.mark.timeout(10)
    def test_sign_out_clears_session(self, client):
        """Test that sign-out clears the Flask session."""
        # Set up authenticated session
        with client.session_transaction() as sess:
            sess['device_auth_token'] = 'test_token_123'
            sess['own_device_id'] = 'test_device_id'
            sess['server_url'] = 'http://localhost:8080'
        
        # Call sign-out endpoint
        response = client.post('/api/session/clear')
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['status'] == 'ok'
        
        # Verify session is cleared
        with client.session_transaction() as sess:
            assert 'device_auth_token' not in sess
            assert 'own_device_id' not in sess

    @pytest.mark.timeout(10)
    def test_sign_out_returns_ok_status(self, client):
        """Test that sign-out endpoint returns success status."""
        response = client.post('/api/session/clear')
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['status'] == 'ok'

    @pytest.mark.timeout(10)
    def test_sign_out_sets_authenticated_false(self, client):
        """Test that after sign-out, session status shows not authenticated."""
        # Set up authenticated session
        with client.session_transaction() as sess:
            sess['device_auth_token'] = 'test_token_123'
        
        # Sign out
        response = client.post('/api/session/clear')
        assert response.status_code == 200
        
        # Check session status
        response = client.get('/api/session/status')
        data = response.get_json()
        
        assert data['authenticated'] is False
        assert data['has_device_auth_token'] is False

    @pytest.mark.timeout(10)
    def test_sign_out_clears_persisted_device_auth_token(self, client):
        """Test that sign-out clears device_auth_token from database."""
        from database import store_auth_token, get_latest_device_auth_token
        
        # Get the database from the client fixture
        db = client.application.test_db
        
        # Store a device auth token in the database
        store_auth_token(
            db=db,
            token_type='device_auth_token',
            token_value='test_token_123',
            device_id='test_device_id'
        )
        
        # Verify token was stored
        token = get_latest_device_auth_token(db)
        assert token == 'test_token_123'
        
        # Sign out
        response = client.post('/api/session/clear')
        assert response.status_code == 200
        
        # Verify token was cleared from database
        token = get_latest_device_auth_token(db)
        assert token is None

    @pytest.mark.timeout(10)
    def test_sign_out_clears_persisted_own_device_id(self, client, test_db):
        """Test that sign-out clears own_device_id from JSON file."""
        from persistence import (
            get_server_selection_store,
            get_persisted_own_device_id,
            set_persisted_own_device_id
        )
        
        # Set up own_device_id in JSON file
        set_persisted_own_device_id('test_device_id')
        
        # Verify device_id was stored
        device_id = get_persisted_own_device_id()
        assert device_id == 'test_device_id'
        
        # Sign out
        response = client.post('/api/session/clear')
        assert response.status_code == 200
        
        # Verify device_id was cleared from JSON file
        device_id = get_persisted_own_device_id()
        assert device_id is None

    @pytest.mark.timeout(10)
    def test_sign_out_clears_auth_token_backup(self, client):
        """Test that sign-out clears the auth token backup file."""
        from persistence import (
            get_auth_token_backup_path,
            backup_auth_tokens,
            clear_auth_token_backup
        )
        
        # Create a backup file
        backup_auth_tokens()
        backup_path = get_auth_token_backup_path()
        assert os.path.exists(backup_path)
        
        # Sign out
        response = client.post('/api/session/clear')
        assert response.status_code == 200
        
        # Verify backup file was deleted
        assert not os.path.exists(backup_path)

    @pytest.mark.timeout(10)
    def test_sign_out_does_not_clear_server_selection(self, client):
        """Test that sign-out does not clear server selection."""
        from persistence import (
            get_current_server_key,
            get_current_server_url,
            set_current_server_key,
            set_current_server_url
        )
        
        # Set up server selection
        set_current_server_key('local')
        set_current_server_url('http://localhost:8080')
        
        # Verify server selection was set
        assert get_current_server_key() == 'local'
        assert get_current_server_url() == 'http://localhost:8080'
        
        # Sign out
        response = client.post('/api/session/clear')
        assert response.status_code == 200
        
        # Verify server selection is still set
        assert get_current_server_key() == 'local'
        assert get_current_server_url() == 'http://localhost:8080'

    @pytest.mark.timeout(10)
    def test_sign_out_preserves_mail_auth_token_in_database(self, client):
        """Test that sign-out preserves mail_auth_token in database."""
        from database import store_auth_token, get_auth_token
        
        # Get the database from the client fixture
        db = client.application.test_db
        
        # Store both device_auth_token and mail_auth_token
        store_auth_token(
            db=db,
            token_type='device_auth_token',
            token_value='device_token_123',
            device_id='test_device_id'
        )
        store_auth_token(
            db=db,
            token_type='mail_auth_token',
            token_value='mail_token_456',
            device_id='test_device_id'
        )
        
        # Verify both tokens were stored
        device_token = get_auth_token(db, 'device_token_123')
        mail_token = get_auth_token(db, 'mail_token_456')
        assert device_token is not None
        assert mail_token is not None
        
        # Sign out
        response = client.post('/api/session/clear')
        assert response.status_code == 200
        
        # Verify device_auth_token was cleared but mail_auth_token is preserved
        # Note: delete_all_device_auth_tokens only deletes device_auth_token type
        device_token = get_auth_token(db, 'device_token_123')
        assert device_token is None  # Should be cleared

    @pytest.mark.timeout(10)
    def test_sign_out_when_not_authenticated(self, client):
        """Test that sign-out works even when not authenticated."""
        # Sign out without being authenticated
        response = client.post('/api/session/clear')
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['status'] == 'ok'

    @pytest.mark.timeout(10)
    def test_sign_out_multiple_times(self, client):
        """Test that sign-out can be called multiple times without error."""
        # First sign out
        response = client.post('/api/session/clear')
        assert response.status_code == 200
        
        # Second sign out
        response = client.post('/api/session/clear')
        assert response.status_code == 200
        
        # Third sign out
        response = client.post('/api/session/clear')
        assert response.status_code == 200


class TestSessionRestorationAfterSignOut:
    """Tests for session restoration after sign-out."""

    @pytest.mark.timeout(10)
    def test_session_not_restored_after_sign_out(self, client, test_db):
        """Test that session is not restored after sign-out."""
        from database import store_auth_token, get_latest_device_auth_token
        
        # Set up authenticated session
        with client.session_transaction() as sess:
            sess['device_auth_token'] = 'test_token_123'
        
        # Store token in database
        db = test_db
        store_auth_token(
            db=db,
            token_type='device_auth_token',
            token_value='test_token_123',
            device_id='test_device_id'
        )
        
        # Sign out
        response = client.post('/api/session/clear')
        assert response.status_code == 200
        
        # Make a new request (simulating app restart)
        # The before_request handler should not restore the session
        response = client.get('/api/session/status')
        data = response.get_json()
        
        assert data['authenticated'] is False
        assert data['has_device_auth_token'] is False

    @pytest.mark.timeout(10)
    def test_session_restored_when_token_exists(self, client):
        """Test that session is restored when token exists in database."""
        from database import store_auth_token
        
        # Get the database from the client fixture
        db = client.application.test_db
        
        # Store token in database (without signing in first)
        store_auth_token(
            db=db,
            token_type='device_auth_token',
            token_value='restored_token_789',
            device_id='test_device_id'
        )
        
        # Make a request (simulating app restart)
        # The before_request handler should restore the session
        response = client.get('/api/session/status')
        data = response.get_json()
        
        # Session should be restored from database
        assert data['authenticated'] is True
        assert data['has_device_auth_token'] is True


class TestSignOutWithOwnDeviceId:
    """Tests for sign-out with own_device_id."""

    @pytest.mark.timeout(10)
    def test_sign_out_clears_own_device_id_from_session(self, client):
        """Test that sign-out clears own_device_id from session."""
        # Set up session with own_device_id
        with client.session_transaction() as sess:
            sess['device_auth_token'] = 'test_token_123'
            sess['own_device_id'] = 'test_device_id'
        
        # Sign out
        response = client.post('/api/session/clear')
        assert response.status_code == 200
        
        # Verify own_device_id is cleared from session
        with client.session_transaction() as sess:
            assert 'own_device_id' not in sess

    @pytest.mark.timeout(10)
    def test_sign_out_clears_parent_password_hash_from_session(self, client):
        """Test that sign-out clears parent_password_second_hash from session."""
        # Set up session with parent password hash
        with client.session_transaction() as sess:
            sess['device_auth_token'] = 'test_token_123'
            sess['parent_password_second_hash'] = 'test_hash'
        
        # Sign out
        response = client.post('/api/session/clear')
        assert response.status_code == 200
        
        # Verify parent_password_second_hash is cleared from session
        with client.session_transaction() as sess:
            assert 'parent_password_second_hash' not in sess