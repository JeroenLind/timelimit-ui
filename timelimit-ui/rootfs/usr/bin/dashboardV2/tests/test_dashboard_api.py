"""Unit tests for dashboard API routes.

This module tests the dashboard API endpoints including:
- /api/sync/pull - Manual sync trigger
- /api/dashboard/users - Get users for device auth token
- /api/dashboard/devices - Get devices for device auth token
- /api/dashboard/categories - Get categories for device auth token
- /api/dashboard/connected-devices - Get connected devices
- /api/dashboard/stream - SSE endpoint for real-time updates
"""

import os
import tempfile
import pytest
import json
import queue
import threading
import time
from unittest.mock import Mock, patch, MagicMock
from flask import session

from app import app, get_database, reset_database
from database import (
    Database,
    create_family,
    store_auth_token,
    save_users,
    save_categories,
    save_connected_devices,
    get_users_by_device_auth_token,
    get_categories_by_device_auth_token,
    get_connected_devices,
    get_device_auth_tokens,
    _db_instance
)
from database import get_database as db_get_database


@pytest.fixture
def test_app(request):
    """Create a test Flask application."""
    # Use a unique database path for each test
    test_name = request.node.name
    # Use absolute path to avoid any path resolution issues
    db_path = os.path.abspath(os.path.join(os.path.dirname(__file__), f'test_dashboard_{test_name}.db'))
    
    # Reset the database singleton first
    reset_database()
    
    # Delete any leftover database file from a previous run to ensure clean state
    if os.path.exists(db_path):
        try:
            os.unlink(db_path)
        except PermissionError:
            pass
    
    # Set environment variable to the full absolute path
    os.environ['DATABASE_PATH'] = db_path
    
    # Configure app for testing
    app.config['TESTING'] = True
    app.config['DATABASE_PATH'] = db_path
    
    # Create a new database instance with the unique path
    db = Database(db_path=db_path)
    db.init_db()
    
    # Store the db instance in the app for later use
    app.test_db = db
    
    # Update the global database singleton to use the test database
    import database as db_module
    db_module._db_instance = db
    
    # Create a temporary server selection store for isolation
    import shutil
    temp_dir = tempfile.mkdtemp()
    temp_file = os.path.join(temp_dir, 'server_selection.json')
    from persistence import FileServerSelectionStore
    temp_store = FileServerSelectionStore(temp_file)
    
    # Patch the store in app.py and persistence.py
    import app as app_module
    import persistence as persistence_module
    
    original_app_store = getattr(app_module, 'persistence_store', None)
    original_default_store = getattr(persistence_module, '_default_store', None)
    
    app_module.persistence_store = temp_store
    persistence_module._default_store = temp_store
    
    # Mock persistence functions for non-restoration tests to ensure clean state
    from unittest.mock import patch
    is_restoration_test = request.cls and request.cls.__name__ == 'TestSessionRestoration'
    
    if not is_restoration_test:
        with patch('app.get_persisted_device_auth_token', return_value=None), \
             patch('app.get_persisted_own_device_id', return_value=None):
            yield app
    else:
        yield app
    
    # Restore original stores
    if original_app_store is not None:
        app_module.persistence_store = original_app_store
    if original_default_store is not None:
        persistence_module._default_store = original_default_store
        
    # Cleanup temp directory
    try:
        shutil.rmtree(temp_dir)
    except OSError:
        pass
        
    # Cleanup: close database and remove file
    db.close()
    if os.path.exists(db_path):
        try:
            os.unlink(db_path)
        except PermissionError:
            # File might be locked by background threads, try again later
            pass
    # Restore original environment
    if 'DATABASE_PATH' in os.environ:
        del os.environ['DATABASE_PATH']
    
    # Reset database singleton after test
    reset_database()


@pytest.fixture
def client(test_app, request):
    """Create a test client."""
    from unittest.mock import patch
    
    # Check if this is a session restoration test
    is_restoration_test = request.cls and request.cls.__name__ == 'TestSessionRestoration'
    
    if not is_restoration_test:
        # Patch persistence functions to prevent session restoration from previous tests
        with patch('app.get_persisted_device_auth_token', return_value=None), \
             patch('app.get_persisted_own_device_id', return_value=None):
            test_client = test_app.test_client()
            with test_client.session_transaction() as sess:
                sess.clear()
            yield test_client
    else:
        test_client = test_app.test_client()
        with test_client.session_transaction() as sess:
            sess.clear()
        yield test_client


@pytest.fixture
def auth_session(client, request):
    """Create an authenticated session for testing."""
    # Generate unique values per test to avoid UNIQUE constraint conflicts
    test_name = request.node.name
    unique_suffix = f"_{test_name}"
    
    # Create a test device auth token with unique suffix
    device_auth_token = f'device_token_test123{unique_suffix}'
    
    # Get the database from the app
    db = client.application.test_db
    
    create_family(
        db=db,
        device_auth_token=device_auth_token,
        mail='test@example.com',
        parent_password_hash='$2b$12$hash1',
        parent_password_second_hash='$2b$12$hash2',
        parent_password_second_salt='$2b$12$salt',
        parent_password_encrypted=False
    )
    
    # Store auth token in session
    with client.session_transaction() as sess:
        sess['device_auth_token'] = device_auth_token
        sess['server_url'] = 'http://localhost:8080'
    
    # Store the token in database
    store_auth_token(
        db=db,
        token_type='device_auth_token',
        token_value=device_auth_token,
        device_id='device_test123',
        mail='test@example.com'
    )
    
    return client


class TestApiSyncPull:
    """Tests for /api/sync/pull endpoint."""
    
    @pytest.mark.timeout(10)
    def test_sync_pull_unauthenticated(self, client):
        """Test sync pull without authentication."""
        response = client.post('/api/sync/pull')
        
        # When session is cleared, Flask session may have default values
        # The code checks for device_auth_token before returning 401
        assert response.status_code in [400, 401]
        data = json.loads(response.data)
        assert data['status'] == 'error'
        assert data['error_code'] in ['unauthorized', 'no_device_auth_token']
    
    @pytest.mark.timeout(10)
    def test_sync_pull_no_device_auth_token(self, client):
        """Test sync pull without device auth token in session."""
        with client.session_transaction() as sess:
            sess['device_auth_token'] = None
        
        response = client.post('/api/sync/pull')
        
        assert response.status_code == 400
        data = json.loads(response.data)
        assert data['status'] == 'error'
        assert data['error_code'] == 'no_device_auth_token'
    
    @pytest.mark.timeout(10)
    @patch('app.create_sync_manager')
    def test_sync_pull_success(self, mock_create_manager, auth_session):
        """Test successful sync pull."""
        # Mock the sync manager
        mock_manager = Mock()
        mock_manager.do_sync.return_value = True
        mock_create_manager.return_value = mock_manager
        
        response = auth_session.post('/api/sync/pull')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['status'] == 'ok'
        assert data['synced'] is True
    
    @pytest.mark.timeout(10)
    @patch('app.create_sync_manager')
    def test_sync_pull_failure(self, mock_create_manager, auth_session):
        """Test failed sync pull."""
        # Mock the sync manager to return failure
        mock_manager = Mock()
        mock_manager.do_sync.return_value = False
        mock_create_manager.return_value = mock_manager
        
        response = auth_session.post('/api/sync/pull')
        
        assert response.status_code == 500
        data = json.loads(response.data)
        assert data['status'] == 'error'
        assert data['error_code'] == 'sync_failed'


class TestApiDashboardUsers:
    """Tests for /api/dashboard/users endpoint."""
    
    @pytest.mark.timeout(10)
    def test_users_unauthenticated(self, client):
        """Test getting users without authentication."""
        response = client.get('/api/dashboard/users')
        
        # When session is cleared, Flask session may have default values
        assert response.status_code in [400, 401]
        data = json.loads(response.data)
        assert data['status'] == 'error'
    
    @pytest.mark.timeout(10)
    def test_users_no_device_auth_token(self, client):
        """Test getting users without device auth token in session."""
        with client.session_transaction() as sess:
            sess['device_auth_token'] = None
        
        response = client.get('/api/dashboard/users')
        
        assert response.status_code == 400
        data = json.loads(response.data)
        assert data['status'] == 'error'
        assert data['error'] == 'No device auth token'
    
    @pytest.mark.timeout(10)
    def test_users_success(self, auth_session):
        """Test getting users successfully."""
        # Get device_auth_token from session
        with auth_session.session_transaction() as sess:
            device_auth_token = sess['device_auth_token']
        
        # Add some users
        db = auth_session.application.test_db
        save_users(db, device_auth_token, [
            {
                'id': 'user1',
                'name': 'Parent User',
                'type': 'parent',
                'mail': 'parent@example.com',
                'timeZone': 'Europe/Amsterdam'
            },
            {
                'id': 'user2',
                'name': 'Child User',
                'type': 'child',
                'mail': 'child@example.com',
                'timeZone': 'Europe/Amsterdam'
            }
        ])
        
        response = auth_session.get('/api/dashboard/users')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['status'] == 'ok'
        assert data['count'] == 2
        assert len(data['users']) == 2
    
    @pytest.mark.timeout(10)
    def test_users_empty(self, auth_session):
        """Test getting users when there are none."""
        response = auth_session.get('/api/dashboard/users')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['status'] == 'ok'
        assert data['count'] == 0
        assert len(data['users']) == 0


class TestApiDashboardDevices:
    """Tests for /api/dashboard/devices endpoint."""
    
    @pytest.mark.timeout(10)
    def test_devices_unauthenticated(self, client):
        """Test getting devices without authentication."""
        response = client.get('/api/dashboard/devices')
        
        # When session is cleared, Flask session may have default values
        assert response.status_code in [400, 401]
        data = json.loads(response.data)
        assert data['status'] == 'error'
    
    @pytest.mark.timeout(10)
    def test_devices_no_device_auth_token(self, client):
        """Test getting devices without device auth token in session."""
        with client.session_transaction() as sess:
            sess['device_auth_token'] = None
        
        response = client.get('/api/dashboard/devices')
        
        assert response.status_code == 400
        data = json.loads(response.data)
        assert data['status'] == 'error'
        assert data['error'] == 'No device auth token'
    
    @pytest.mark.timeout(10)
    def test_devices_success(self, auth_session):
        """Test getting devices successfully."""
        # Get device_auth_token from session
        with auth_session.session_transaction() as sess:
            device_auth_token = sess['device_auth_token']
        
        # Add some devices
        db = auth_session.application.test_db
        from database import create_device
        create_device(
            db=db,
            device_id='device1',
            device_auth_token=device_auth_token,
            name='Parent Phone',
            model='Pixel 7'
        )
        create_device(
            db=db,
            device_id='device2',
            device_auth_token=device_auth_token,
            name='Child Tablet',
            model='iPad'
        )
        
        response = auth_session.get('/api/dashboard/devices')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['status'] == 'ok'
        assert data['count'] == 2
        assert len(data['devices']) == 2
        # own_device_id should be None when not set in session
        assert 'own_device_id' in data
    
    @pytest.mark.timeout(10)
    def test_devices_with_own_device_id(self, auth_session):
        """Test getting devices with own_device_id set in session."""
        # Get device_auth_token from session
        with auth_session.session_transaction() as sess:
            device_auth_token = sess['device_auth_token']
            # Set own_device_id in session
            sess['own_device_id'] = 'device1'
        
        # Add some devices
        db = auth_session.application.test_db
        from database import create_device
        create_device(
            db=db,
            device_id='device1',
            device_auth_token=device_auth_token,
            name='Parent Phone',
            model='Pixel 7'
        )
        create_device(
            db=db,
            device_id='device2',
            device_auth_token=device_auth_token,
            name='Child Tablet',
            model='iPad'
        )
        
        response = auth_session.get('/api/dashboard/devices')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['status'] == 'ok'
        assert data['count'] == 2
        assert len(data['devices']) == 2
        # own_device_id should be set in the response
        assert data['own_device_id'] == 'device1'
    
    @pytest.mark.timeout(10)
    def test_devices_includes_public_key(self, auth_session):
        """Test that devices API returns public_key (signing key)."""
        # Get device_auth_token from session
        with auth_session.session_transaction() as sess:
            device_auth_token = sess['device_auth_token']
        
        db = auth_session.application.test_db
        from database import create_device
        
        # Create a device with a public key (signing key)
        test_public_key = 'a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6'
        create_device(
            db=db,
            device_id='device1',
            device_auth_token=device_auth_token,
            name='Parent Phone',
            model='Pixel 7',
            public_key=test_public_key
        )
        
        response = auth_session.get('/api/dashboard/devices')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['status'] == 'ok'
        assert data['count'] == 1
        
        # Verify public_key is included in the device data
        device = data['devices'][0]
        assert 'public_key' in device
        assert device['public_key'] == test_public_key
    
    @pytest.mark.timeout(10)
    def test_devices_public_key_can_be_null(self, auth_session):
        """Test that devices API handles null public_key (device without signing key)."""
        # Get device_auth_token from session
        with auth_session.session_transaction() as sess:
            device_auth_token = sess['device_auth_token']
        
        db = auth_session.application.test_db
        from database import create_device
        
        # Create a device without a public key
        create_device(
            db=db,
            device_id='device1',
            device_auth_token=device_auth_token,
            name='Parent Phone',
            model='Pixel 7'
        )
        
        response = auth_session.get('/api/dashboard/devices')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['status'] == 'ok'
        
        # Verify public_key is present but can be None
        device = data['devices'][0]
        assert 'public_key' in device
        assert device['public_key'] is None
    
    @pytest.mark.timeout(10)
    def test_devices_multiple_with_varying_public_keys(self, auth_session):
        """Test devices API with multiple devices having different public_key values."""
        # Get device_auth_token from session
        with auth_session.session_transaction() as sess:
            device_auth_token = sess['device_auth_token']
        
        db = auth_session.application.test_db
        from database import create_device
        
        # Create multiple devices with different public_key values
        create_device(
            db=db,
            device_id='device1',
            device_auth_token=device_auth_token,
            name='Parent Phone',
            model='Pixel 7',
            public_key='pubkey_parent_12345'
        )
        create_device(
            db=db,
            device_id='device2',
            device_auth_token=device_auth_token,
            name='Child Tablet',
            model='iPad',
            public_key='pubkey_child_67890'
        )
        create_device(
            db=db,
            device_id='device3',
            device_auth_token=device_auth_token,
            name='Dashboard',
            model='Web',
            public_key=None  # Dashboard device without signing key
        )
        
        response = auth_session.get('/api/dashboard/devices')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['status'] == 'ok'
        assert data['count'] == 3
        
        # Verify each device has the correct public_key
        devices_by_id = {d['id']: d for d in data['devices']}
        
        assert devices_by_id['device1']['public_key'] == 'pubkey_parent_12345'
        assert devices_by_id['device2']['public_key'] == 'pubkey_child_67890'
        assert devices_by_id['device3']['public_key'] is None

    @pytest.mark.timeout(10)
    def test_devices_includes_has_parent_password_second_hash(self, auth_session):
        """Test that devices endpoint includes has_parent_password_second_hash field."""
        # Get device_auth_token from session
        with auth_session.session_transaction() as sess:
            device_auth_token = sess['device_auth_token']
        
        # Add a device
        db = auth_session.application.test_db
        from database import create_device
        create_device(
            db=db,
            device_id='device1',
            device_auth_token=device_auth_token,
            name='Parent Phone',
            model='Pixel 7'
        )
        
        response = auth_session.get('/api/dashboard/devices')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['status'] == 'ok'
        # Verify has_parent_password_second_hash field is present
        assert 'has_parent_password_second_hash' in data
        # The auth_session fixture creates a family with a password hash, so should be True
        assert data['has_parent_password_second_hash'] is True

    @pytest.mark.timeout(10)
    def test_devices_has_parent_password_second_hash_false_when_not_set(self, client):
        """Test that has_parent_password_second_hash is False when not set in session or database."""
        # Create a fresh session without password hash
        device_auth_token = 'device_token_no_hash_test'
        own_device_id = 'device_no_hash_test'
        
        db = client.application.test_db
        from database import create_device, store_auth_token
        
        # Store auth token in database
        store_auth_token(
            db=db,
            token_type='device_auth_token',
            token_value=device_auth_token,
            device_id=own_device_id,
            mail='nohash@example.com'
        )
        
        # Create a device
        create_device(
            db=db,
            device_id='device1',
            device_auth_token=device_auth_token,
            name='Parent Phone',
            model='Pixel 7'
        )
        
        # Set up session WITHOUT password hash
        with client.session_transaction() as sess:
            sess['device_auth_token'] = device_auth_token
            sess['own_device_id'] = own_device_id
            # Do NOT set parent_password_second_hash
        
        response = client.get('/api/dashboard/devices')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['status'] == 'ok'
        # Should be False when not set
        assert data['has_parent_password_second_hash'] is False

    @pytest.mark.timeout(10)
    def test_devices_has_parent_password_second_hash_true_when_in_session(self, auth_session):
        """Test that has_parent_password_second_hash is True when set in session."""
        # Get device_auth_token from session
        with auth_session.session_transaction() as sess:
            device_auth_token = sess['device_auth_token']
            # Set parent_password_second_hash in session
            sess['parent_password_second_hash'] = '$2b$12$test_hash_in_session'
        
        # Add a device
        db = auth_session.application.test_db
        from database import create_device
        create_device(
            db=db,
            device_id='device1',
            device_auth_token=device_auth_token,
            name='Parent Phone',
            model='Pixel 7'
        )
        
        response = auth_session.get('/api/dashboard/devices')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['status'] == 'ok'
        # Should be True when set in session
        assert data['has_parent_password_second_hash'] is True

    @pytest.mark.timeout(10)
    def test_devices_has_parent_password_second_hash_true_when_in_database(self, auth_session):
        """Test that has_parent_password_second_hash is True when set in database."""
        # Get device_auth_token from session
        with auth_session.session_transaction() as sess:
            device_auth_token = sess['device_auth_token']
            # Ensure parent_password_second_hash is NOT in session
            sess.pop('parent_password_second_hash', None)
        
        # Add a device
        db = auth_session.application.test_db
        from database import create_device, upsert_family_password_hash
        create_device(
            db=db,
            device_id='device1',
            device_auth_token=device_auth_token,
            name='Parent Phone',
            model='Pixel 7'
        )
        
        # Store password hash in database
        upsert_family_password_hash(
            db=db,
            device_auth_token=device_auth_token,
            parent_password_second_hash='$2b$12$test_hash_in_database'
        )
        
        response = auth_session.get('/api/dashboard/devices')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['status'] == 'ok'
        # Should be True when set in database
        assert data['has_parent_password_second_hash'] is True

    @pytest.mark.timeout(10)
    def test_devices_session_hash_takes_precedence_over_database(self, auth_session):
        """Test that session password hash takes precedence over database for has_parent_password_second_hash."""
        # Get device_auth_token from session
        with auth_session.session_transaction() as sess:
            device_auth_token = sess['device_auth_token']
            # Set a different hash in session
            sess['parent_password_second_hash'] = '$2b$12$hash_in_session'
        
        # Add a device
        db = auth_session.application.test_db
        from database import create_device, upsert_family_password_hash
        create_device(
            db=db,
            device_id='device1',
            device_auth_token=device_auth_token,
            name='Parent Phone',
            model='Pixel 7'
        )
        
        # Store a DIFFERENT hash in database
        upsert_family_password_hash(
            db=db,
            device_auth_token=device_auth_token,
            parent_password_second_hash='$2b$12$hash_in_database'
        )
        
        response = auth_session.get('/api/dashboard/devices')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['status'] == 'ok'
        # Should be True (session hash takes precedence)
        assert data['has_parent_password_second_hash'] is True


class TestApiDashboardCategories:
    """Tests for /api/dashboard/categories endpoint."""
    
    @pytest.mark.timeout(10)
    def test_categories_unauthenticated(self, client):
        """Test getting categories without authentication."""
        response = client.get('/api/dashboard/categories')
        
        # When session is cleared, Flask session may have default values
        assert response.status_code in [400, 401]
        data = json.loads(response.data)
        assert data['status'] == 'error'
    
    @pytest.mark.timeout(10)
    def test_categories_no_device_auth_token(self, client):
        """Test getting categories without device auth token in session."""
        with client.session_transaction() as sess:
            sess['device_auth_token'] = None
        
        response = client.get('/api/dashboard/categories')
        
        assert response.status_code == 400
        data = json.loads(response.data)
        assert data['status'] == 'error'
        assert data['error'] == 'No device auth token'
    
    @pytest.mark.timeout(10)
    def test_categories_success(self, auth_session):
        """Test getting categories successfully."""
        # Get device_auth_token from session
        with auth_session.session_transaction() as sess:
            device_auth_token = sess['device_auth_token']
        
        # Add some categories
        db = auth_session.application.test_db
        save_categories(db, device_auth_token, [
            {
                'id': 'cat1',
                'title': 'Work',
                'childId': 'user2',
                'extraTime': 60
            },
            {
                'id': 'cat2',
                'title': 'Play',
                'childId': 'user2',
                'extraTime': 30
            }
        ])
        
        response = auth_session.get('/api/dashboard/categories')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['status'] == 'ok'
        assert data['count'] == 2
        assert len(data['categories']) == 2


class TestApiDashboardConnectedDevices:
    """Tests for /api/dashboard/connected-devices endpoint."""
    
    @pytest.mark.timeout(10)
    def test_connected_devices_unauthenticated(self, client):
        """Test getting connected devices without authentication."""
        response = client.get('/api/dashboard/connected-devices')
        
        # When session is cleared, Flask session may have default values
        assert response.status_code in [400, 401]
        data = json.loads(response.data)
        assert data['status'] == 'error'
    
    @pytest.mark.timeout(10)
    def test_connected_devices_no_device_auth_token(self, client):
        """Test getting connected devices without device auth token in session."""
        with client.session_transaction() as sess:
            sess['device_auth_token'] = None
        
        response = client.get('/api/dashboard/connected-devices')
        
        assert response.status_code == 400
        data = json.loads(response.data)
        assert data['status'] == 'error'
        assert data['error'] == 'No device auth token'
    
    @pytest.mark.timeout(10)
    def test_connected_devices_success(self, auth_session):
        """Test getting connected devices successfully."""
        # Get device_auth_token from session
        with auth_session.session_transaction() as sess:
            device_auth_token = sess['device_auth_token']
        
        # Add some connected devices
        db = auth_session.application.test_db
        save_connected_devices(db, device_auth_token, ['device1', 'device2', 'device3'])
        
        response = auth_session.get('/api/dashboard/connected-devices')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['status'] == 'ok'
        assert data['count'] == 3
        assert len(data['devices']) == 3
        device_ids = [d['device_id'] for d in data['devices']]
        assert 'device1' in device_ids
        assert 'device2' in device_ids
        assert 'device3' in device_ids
    
    @pytest.mark.timeout(10)
    def test_connected_devices_empty_list(self, auth_session):
        """Test getting connected devices when there are none."""
        # Get device_auth_token from session
        with auth_session.session_transaction() as sess:
            device_auth_token = sess['device_auth_token']
        
        # Don't add any connected devices - just query
        response = auth_session.get('/api/dashboard/connected-devices')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['status'] == 'ok'
        assert data['count'] == 0
        assert len(data['devices']) == 0
    
    @pytest.mark.timeout(10)
    def test_connected_devices_includes_names(self, auth_session):
        """Test that connected devices API returns device names."""
        from database import create_device
        
        # Get device_auth_token from session
        with auth_session.session_transaction() as sess:
            device_auth_token = sess['device_auth_token']
        
        db = auth_session.application.test_db
        
        # Create devices with names
        create_device(
            db=db,
            device_id='device1',
            device_auth_token=device_auth_token,
            name='Parent Phone'
        )
        create_device(
            db=db,
            device_id='device2',
            device_auth_token=device_auth_token,
            name='Child Tablet'
        )
        # device3 has no name
        
        # Save connected devices
        save_connected_devices(db, device_auth_token, ['device1', 'device2', 'device3'])
        
        response = auth_session.get('/api/dashboard/connected-devices')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['status'] == 'ok'
        assert data['count'] == 3
        
        # Verify names are included
        device1 = next((d for d in data['devices'] if d['device_id'] == 'device1'), None)
        device2 = next((d for d in data['devices'] if d['device_id'] == 'device2'), None)
        device3 = next((d for d in data['devices'] if d['device_id'] == 'device3'), None)
        
        assert device1 is not None
        assert 'name' in device1
        assert device1['name'] == 'Parent Phone'
        
        assert device2 is not None
        assert 'name' in device2
        assert device2['name'] == 'Child Tablet'
        
        assert device3 is not None
        assert 'name' in device3
        assert device3['name'] is None  # No name in devices table
    
    @pytest.mark.timeout(10)
    def test_connected_devices_includes_last_seen(self, auth_session):
        """Test that connected devices API returns last_seen timestamps."""
        from database import create_device
        import time
        
        # Get device_auth_token from session
        with auth_session.session_transaction() as sess:
            device_auth_token = sess['device_auth_token']
        
        db = auth_session.application.test_db
        
        # Create a device
        create_device(
            db=db,
            device_id='device1',
            device_auth_token=device_auth_token,
            name='Test Device'
        )
        
        # Save connected devices
        save_connected_devices(db, device_auth_token, ['device1'])
        
        response = auth_session.get('/api/dashboard/connected-devices')
        
        data = json.loads(response.data)
        assert data['status'] == 'ok'
        
        # Verify last_seen is included and is a valid timestamp
        device1 = next((d for d in data['devices'] if d['device_id'] == 'device1'), None)
        assert device1 is not None
        assert 'last_seen' in device1
        assert isinstance(device1['last_seen'], int)
        # last_seen should be a reasonable timestamp (within last 10 seconds)
        current_time_ms = int(time.time() * 1000)
        assert abs(current_time_ms - device1['last_seen']) < 10000
    
    @pytest.mark.timeout(10)
    def test_connected_devices_large_list(self, auth_session):
        """Test getting connected devices with a large number of devices."""
        # Get device_auth_token from session
        with auth_session.session_transaction() as sess:
            device_auth_token = sess['device_auth_token']
        
        db = auth_session.application.test_db
        
        # Create a large number of device IDs
        num_devices = 100
        device_ids = [f'device{i:03d}' for i in range(num_devices)]
        
        # Save connected devices
        save_connected_devices(db, device_auth_token, device_ids)
        
        response = auth_session.get('/api/dashboard/connected-devices')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['status'] == 'ok'
        assert data['count'] == num_devices
        assert len(data['devices']) == num_devices
        
        # Verify all device IDs are present
        returned_ids = [d['device_id'] for d in data['devices']]
        for device_id in device_ids:
            assert device_id in returned_ids
    
    @pytest.mark.timeout(10)
    def test_connected_devices_all_names_none(self, auth_session):
        """Test connected devices when all devices have no names in devices table."""
        # Get device_auth_token from session
        with auth_session.session_transaction() as sess:
            device_auth_token = sess['device_auth_token']
        
        db = auth_session.application.test_db
        
        # Save connected devices WITHOUT creating device records
        # This means all devices will have name=None
        save_connected_devices(db, device_auth_token, ['device1', 'device2'])
        
        response = auth_session.get('/api/dashboard/connected-devices')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['status'] == 'ok'
        assert data['count'] == 2
        
        # Verify all devices have name field (even if None)
        for device in data['devices']:
            assert 'name' in device
            assert device['name'] is None


class TestDashboardStream:
    """Tests for /api/dashboard/stream endpoint."""
    
    @pytest.mark.timeout(10)
    def test_stream_unauthenticated(self, client):
        """Test SSE stream without authentication."""
        response = client.get('/api/dashboard/stream')
        
        assert response.status_code == 401
        data = json.loads(response.data)
        assert data['status'] == 'error'
        assert data['error'] == 'Not authenticated'
    
    @pytest.mark.timeout(10)
    def test_stream_no_device_auth_token(self, client):
        """Test SSE stream without device auth token in session."""
        with client.session_transaction() as sess:
            sess['device_auth_token'] = None
        
        response = client.get('/api/dashboard/stream')
        
        assert response.status_code == 400
        data = json.loads(response.data)
        assert data['status'] == 'error'
        assert data['error'] == 'No device auth token'
    
    @pytest.mark.timeout(10)
    def test_stream_authenticated(self, auth_session):
        """Test SSE stream with authentication."""
        # Set environment variable to limit keep-alive messages for testing
        original_max_keepalives = os.environ.get('TEST_MAX_KEEPALIVES')
        os.environ['TEST_MAX_KEEPALIVES'] = '1'
        
        try:
            # Create a mock queue that raises Empty immediately when get() is called
            class MockQueue:
                def get(self, timeout=None):
                    raise queue.Empty()
            
            # Patch the get_event_queue function in the app module
            with patch('app.get_event_queue', return_value=MockQueue()):
                # Make a request that will trigger the SSE stream
                response = auth_session.get('/api/dashboard/stream')
                
                assert response.status_code == 200
                # Close the response to avoid blocking
                response.close()
        finally:
            # Restore original environment
            if original_max_keepalives is None:
                os.environ.pop('TEST_MAX_KEEPALIVES', None)
            else:
                os.environ['TEST_MAX_KEEPALIVES'] = original_max_keepalives


class TestDashboardIntegration:
    """Integration tests for dashboard API."""
    
    @pytest.mark.timeout(10)
    def test_full_dashboard_flow(self, auth_session):
        """Test the full dashboard data flow."""
        # Get device_auth_token from session
        with auth_session.session_transaction() as sess:
            device_auth_token = sess['device_auth_token']
        
        db = auth_session.application.test_db
        
        # Add users
        save_users(db, device_auth_token, [
            {
                'id': 'user1',
                'name': 'Parent User',
                'type': 'parent',
                'mail': 'parent@example.com',
                'timeZone': 'Europe/Amsterdam'
            }
        ])
        
        # Add devices
        from database import create_device
        create_device(
            db=db,
            device_id='device1',
            device_auth_token=device_auth_token,
            name='Parent Phone',
            model='Pixel 7'
        )
        
        # Add categories
        save_categories(db, device_auth_token, [
            {
                'id': 'cat1',
                'title': 'Work',
                'childId': 'user1'
            }
        ])
        
        # Add connected devices
        save_connected_devices(db, device_auth_token, ['device1'])
        
        # Test users endpoint
        response = auth_session.get('/api/dashboard/users')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['count'] == 1
        
        # Test devices endpoint
        response = auth_session.get('/api/dashboard/devices')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['count'] == 1
        
        # Test categories endpoint
        response = auth_session.get('/api/dashboard/categories')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['count'] == 1
        
        # Test connected devices endpoint
        response = auth_session.get('/api/dashboard/connected-devices')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['count'] == 1

class TestSessionStatus:
    """Tests for /api/session/status endpoint."""
    
    @pytest.mark.timeout(10)
    def test_session_status_unauthenticated(self, client):
        """Test session status when not authenticated."""
        # Mock the pre-loaded tokens to simulate no persisted session
        import app as app_module
        app_module._preloaded_device_auth_token = None
        app_module._preloaded_own_device_id = None
        
        response = client.get('/api/session/status')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['authenticated'] is False
        assert data['configured_app_version'] == 226
    
    @pytest.mark.timeout(10)
    def test_session_status_configured_app_version(self, client):
        """Test session status returns configured_app_version (hardcoded to 226)."""
        response = client.get('/api/session/status')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['configured_app_version'] == 226
    
    @pytest.mark.timeout(10)
    def test_session_status_authenticated(self, auth_session):
        """Test session status when authenticated."""
        response = auth_session.get('/api/session/status')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['authenticated'] is True
        assert data['has_device_auth_token'] is True
        assert data['configured_app_version'] == 226
        assert 'device_auth_token' in data
        assert 'own_device_id' in data
    
    @pytest.mark.timeout(10)
    def test_session_status_includes_password_hash_fields(self, client):
        """Test session status includes password hash fields."""
        # Mock the pre-loaded tokens to simulate no persisted session
        import app as app_module
        app_module._preloaded_device_auth_token = None
        app_module._preloaded_own_device_id = None
        
        response = client.get('/api/session/status')
        assert response.status_code == 200
        data = json.loads(response.data)
        # Verify password hash fields are present
        assert 'has_parent_password_second_hash' in data
        assert 'parent_password_second_hash' in data
    
    @pytest.mark.timeout(10)
    def test_session_status_no_password_hash_when_not_set(self, auth_session):
        """Test session status shows no password hash when not set."""
        # Get the device_auth_token from session
        with auth_session.session_transaction() as sess:
            device_auth_token = sess.get('device_auth_token')
        
        # Clear the password hash from the database to test the case where no hash is set
        db = auth_session.application.test_db
        with db._lock:
            conn = db.get_connection()
            cursor = conn.cursor()
            cursor.execute(
                'UPDATE families SET parent_password_second_hash = NULL WHERE device_auth_token = ?',
                (device_auth_token,)
            )
            conn.commit()
        
        response = auth_session.get('/api/session/status')
        assert response.status_code == 200
        data = json.loads(response.data)
        # When no hash is set in session or database, should be False/None
        assert data['has_parent_password_second_hash'] is False
        assert data['parent_password_second_hash'] is None
    
    @pytest.mark.timeout(10)
    def test_session_status_with_password_hash_in_session(self, client):
        """Test session status returns password hash from session."""
        # Get the database from the app
        db = client.application.test_db
        
        # Create a test device auth token
        device_auth_token = 'device_token_hash_test'
        own_device_id = 'device_hash_test'
        
        # Store auth token in database
        store_auth_token(
            db=db,
            token_type='device_auth_token',
            token_value=device_auth_token,
            device_id=own_device_id,
            mail='hashtest@example.com'
        )
        
        # Create a device record
        from database import create_device
        create_device(
            db=db,
            device_id=own_device_id,
            device_auth_token=device_auth_token,
            name='Hash Test Device'
        )
        
        # Set up session with device auth token and password hash
        with client.session_transaction() as sess:
            sess['device_auth_token'] = device_auth_token
            sess['own_device_id'] = own_device_id
            sess['parent_password_second_hash'] = '$2a$12$test_hash_in_session'
        
        # Mock the pre-loaded tokens
        import app as app_module
        app_module._preloaded_device_auth_token = device_auth_token
        app_module._preloaded_own_device_id = own_device_id
        
        response = client.get('/api/session/status')
        assert response.status_code == 200
        data = json.loads(response.data)
        
        assert data['authenticated'] is True
        assert data['has_parent_password_second_hash'] is True
        assert data['parent_password_second_hash'] == '$2a$12$test_hash_in_session'
    
    @pytest.mark.timeout(10)
    def test_session_status_with_password_hash_in_database(self, client):
        """Test session status falls back to database for password hash."""
        # Get the database from the app
        db = client.application.test_db
        
        # Create a test device auth token
        device_auth_token = 'device_token_db_hash_test'
        own_device_id = 'device_db_hash_test'
        
        # Store auth token in database
        store_auth_token(
            db=db,
            token_type='device_auth_token',
            token_value=device_auth_token,
            device_id=own_device_id,
            mail='dbhashtest@example.com'
        )
        
        # Create a device record
        from database import create_device
        create_device(
            db=db,
            device_id=own_device_id,
            device_auth_token=device_auth_token,
            name='DB Hash Test Device'
        )
        
        # Store password hash in database (simulating login with hash)
        from database import upsert_family_password_hash
        upsert_family_password_hash(
            db=db,
            device_auth_token=device_auth_token,
            parent_password_second_hash='$2a$12$test_hash_in_db'
        )
        
        # Set up session with device auth token but NO password hash in session
        with client.session_transaction() as sess:
            sess['device_auth_token'] = device_auth_token
            sess['own_device_id'] = own_device_id
            # Note: NOT setting parent_password_second_hash in session
        
        # Mock the pre-loaded tokens
        import app as app_module
        app_module._preloaded_device_auth_token = device_auth_token
        app_module._preloaded_own_device_id = own_device_id
        
        response = client.get('/api/session/status')
        assert response.status_code == 200
        data = json.loads(response.data)
        
        assert data['authenticated'] is True
        # Should fall back to database
        assert data['has_parent_password_second_hash'] is True
        assert data['parent_password_second_hash'] == '$2a$12$test_hash_in_db'
    
    @pytest.mark.timeout(10)
    def test_session_status_session_hash_takes_precedence(self, client):
        """Test that session password hash takes precedence over database."""
        # Get the database from the app
        db = client.application.test_db
        
        # Create a test device auth token
        device_auth_token = 'device_token_precedence_test'
        own_device_id = 'device_precedence_test'
        
        # Store auth token in database
        store_auth_token(
            db=db,
            token_type='device_auth_token',
            token_value=device_auth_token,
            device_id=own_device_id,
            mail='precedencetest@example.com'
        )
        
        # Create a device record
        from database import create_device
        create_device(
            db=db,
            device_id=own_device_id,
            device_auth_token=device_auth_token,
            name='Precedence Test Device'
        )
        
        # Store a DIFFERENT password hash in database
        from database import upsert_family_password_hash
        upsert_family_password_hash(
            db=db,
            device_auth_token=device_auth_token,
            parent_password_second_hash='$2a$12$hash_in_database'
        )
        
        # Set up session with device auth token AND password hash in session
        with client.session_transaction() as sess:
            sess['device_auth_token'] = device_auth_token
            sess['own_device_id'] = own_device_id
            sess['parent_password_second_hash'] = '$2a$12$hash_in_session'
        
        # Mock the pre-loaded tokens
        import app as app_module
        app_module._preloaded_device_auth_token = device_auth_token
        app_module._preloaded_own_device_id = own_device_id
        
        response = client.get('/api/session/status')
        assert response.status_code == 200
        data = json.loads(response.data)
        
        assert data['authenticated'] is True
        # Session hash should take precedence
        assert data['has_parent_password_second_hash'] is True
        assert data['parent_password_second_hash'] == '$2a$12$hash_in_session'
    
    @pytest.mark.timeout(10)
    def test_session_status_includes_has_signing_key(self, client):
        """Test session status includes has_signing_key field."""
        # Mock the pre-loaded tokens to simulate no persisted session
        import app as app_module
        app_module._preloaded_device_auth_token = None
        app_module._preloaded_own_device_id = None
        
        response = client.get('/api/session/status')
        assert response.status_code == 200
        data = json.loads(response.data)
        # Verify has_signing_key field is present
        assert 'has_signing_key' in data
        # By default, should be False when no signing key file exists
        assert isinstance(data['has_signing_key'], bool)
    
    @pytest.mark.timeout(10)
    def test_session_status_has_signing_key_true_when_file_exists(self, client):
        """Test session status shows has_signing_key=True when signing key file exists."""
        # Mock the pre-loaded tokens to simulate no persisted session
        import app as app_module
        app_module._preloaded_device_auth_token = None
        app_module._preloaded_own_device_id = None
        
        response = client.get('/api/session/status')
        assert response.status_code == 200
        data = json.loads(response.data)
        # When signing key file exists, should be True
        # Note: The test environment has dashboard_signing_key.json present
        assert data['has_signing_key'] is True



class TestSessionRestoration:
    """Tests for session restoration from persistent storage.
    
    These tests verify that:
    - Session is restored from database on app startup
    - Database takes precedence over JSON file
    - Fallback to JSON when database is empty
    - Pre-loaded tokens at startup work correctly
    """
    
    @pytest.mark.timeout(10)
    def test_session_restored_from_database(self, client):
        """Test that session is restored from database on app startup."""
        # Get the database from the app
        db = client.application.test_db
        
        # Create a test device auth token
        device_auth_token = 'device_token_restored_test'
        own_device_id = 'device_own_restored_test'
        
        # Store auth token in database
        store_auth_token(
            db=db,
            token_type='device_auth_token',
            token_value=device_auth_token,
            device_id=own_device_id,
            mail='restored@example.com'
        )
        
        # Create a device record for own_device_id
        from database import create_device
        create_device(
            db=db,
            device_id=own_device_id,
            device_auth_token=device_auth_token,
            name='Restored Device'
        )
        
        # Mock the pre-loaded tokens to simulate app startup with database tokens
        import app as app_module
        app_module._preloaded_device_auth_token = device_auth_token
        app_module._preloaded_own_device_id = own_device_id
        
        # Make a request - session should be restored from database
        response = client.get('/api/session/status')
        assert response.status_code == 200
        data = json.loads(response.data)
        
        # Session should be restored
        assert data['authenticated'] is True
        assert data['device_auth_token'] == device_auth_token
        assert data['own_device_id'] == own_device_id
    
    @pytest.mark.timeout(10)
    def test_database_token_takes_precedence_over_json(self, client):
        """Test that database token takes precedence over JSON file."""
        db = client.application.test_db
        
        # Store token in database
        db_token = 'device_token_from_db'
        store_auth_token(
            db=db,
            token_type='device_auth_token',
            token_value=db_token,
            device_id='device_db',
            mail='db@example.com'
        )
        
        # Mock the pre-loaded tokens to simulate database token
        import app as app_module
        app_module._preloaded_device_auth_token = db_token
        app_module._preloaded_own_device_id = None
        
        # Make request - should get database token
        response = client.get('/api/session/status')
        assert response.status_code == 200
        data = json.loads(response.data)
        
        # Should get database token (takes precedence)
        assert data['device_auth_token'] == db_token
    
    @pytest.mark.timeout(10)
    def test_fallback_to_json_when_database_empty(self, client):
        """Test fallback to JSON when database is empty."""
        db = client.application.test_db
        
        # Don't store anything in database
        # The JSON file should have the token from persistence
        from persistence import set_persisted_device_auth_token, set_persisted_own_device_id
        
        json_token = 'device_token_json_fallback'
        json_device_id = 'device_json_fallback'
        
        set_persisted_device_auth_token(json_token)
        set_persisted_own_device_id(json_device_id)
        
        # Mock the pre-loaded tokens to simulate JSON fallback
        import app as app_module
        app_module._preloaded_device_auth_token = json_token
        app_module._preloaded_own_device_id = json_device_id
        
        # Make request - should get JSON token
        response = client.get('/api/session/status')
        assert response.status_code == 200
        data = json.loads(response.data)
        
        # Should get JSON token as fallback
        assert data['authenticated'] is True
        assert data['device_auth_token'] == json_token
        assert data['own_device_id'] == json_device_id
    
    @pytest.mark.timeout(10)
    def test_session_not_restored_when_no_persistence(self, client):
        """Test that session is not restored when no persistence exists."""
        # Mock the persistence functions to return None
        # This simulates the case where there's no persisted token in database or JSON file
        # We need to patch the functions in the app module since they are imported at module level
        from unittest.mock import patch
        
        with patch('app.get_persisted_device_auth_token', return_value=None), \
             patch('app.get_persisted_own_device_id', return_value=None):
            # Make request without any persisted tokens
            response = client.get('/api/session/status')
            assert response.status_code == 200
            data = json.loads(response.data)
            
            # Should not be authenticated
            assert data['authenticated'] is False
            assert data['device_auth_token'] is None
            assert data['own_device_id'] is None
    
    @pytest.mark.timeout(10)
    def test_own_device_id_restored_from_database(self, client):
        """Test that own_device_id is restored from database."""
        db = client.application.test_db
        
        # Create a device with a specific ID
        device_auth_token = 'device_token_own_id_test'
        own_device_id = 'device_own_id_test'
        
        store_auth_token(
            db=db,
            token_type='device_auth_token',
            token_value=device_auth_token,
            device_id=own_device_id,
            mail='ownid@example.com'
        )
        
        from database import create_device
        create_device(
            db=db,
            device_id=own_device_id,
            device_auth_token=device_auth_token,
            name='Own Device Test'
        )
        
        # Mock the pre-loaded tokens to simulate database token
        import app as app_module
        app_module._preloaded_device_auth_token = device_auth_token
        app_module._preloaded_own_device_id = own_device_id
        
        # Make request
        response = client.get('/api/session/status')
        assert response.status_code == 200
        data = json.loads(response.data)
        
        # own_device_id should be restored
        assert data['own_device_id'] == own_device_id
    
    @pytest.mark.timeout(10)
    def test_session_persistence_across_requests(self, client):
        """Test that session persists across multiple requests."""
        db = client.application.test_db
        
        # Store auth token
        device_auth_token = 'device_token_persist_test'
        store_auth_token(
            db=db,
            token_type='device_auth_token',
            token_value=device_auth_token,
            device_id='device_persist',
            mail='persist@example.com'
        )
        
        # Mock the pre-loaded tokens to simulate database token
        import app as app_module
        app_module._preloaded_device_auth_token = device_auth_token
        app_module._preloaded_own_device_id = None
        
        # First request - session should be restored
        response1 = client.get('/api/session/status')
        data1 = json.loads(response1.data)
        assert data1['authenticated'] is True
        
        # Second request - session should still be restored
        response2 = client.get('/api/session/status')
        data2 = json.loads(response2.data)
        assert data2['authenticated'] is True
        assert data2['device_auth_token'] == device_auth_token


class TestApiClearAll:
    """Tests for /api/clear-all endpoint."""
    
    @pytest.mark.timeout(10)
    def test_clear_all_unauthenticated(self, client):
        """Test clear all endpoint without authentication."""
        response = client.post('/api/clear-all')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['status'] == 'ok'
        assert 'tables_cleared' in data
        assert 'message' in data
    
    @pytest.mark.timeout(10)
    def test_clear_all_clears_database_tables(self, auth_session):
        """Test that clear all endpoint clears database tables."""
        # Get device_auth_token from session
        with auth_session.session_transaction() as sess:
            device_auth_token = sess['device_auth_token']
        
        db = auth_session.application.test_db
        
        # Add some data
        save_users(db, device_auth_token, [
            {'id': 'user1', 'name': 'Test User', 'type': 'parent', 'mail': 'test@example.com'}
        ])
        save_categories(db, device_auth_token, [
            {'id': 'cat1', 'title': 'Test Category'}
        ])
        save_connected_devices(db, device_auth_token, ['device1'])
        
        # Verify data exists
        users = get_users_by_device_auth_token(db, device_auth_token)
        assert len(users) > 0
        
        # Call clear all endpoint
        response = auth_session.post('/api/clear-all')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['status'] == 'ok'
        
        # Verify data is cleared
        users = get_users_by_device_auth_token(db, device_auth_token)
        assert len(users) == 0
        
        categories = get_categories_by_device_auth_token(db, device_auth_token)
        assert len(categories) == 0
        
        connected = get_connected_devices(db, device_auth_token)
        assert len(connected) == 0
    
    @pytest.mark.timeout(10)
    def test_clear_all_clears_session(self, auth_session):
        """Test that clear all endpoint clears session."""
        # Verify session has device_auth_token
        with auth_session.session_transaction() as sess:
            assert 'device_auth_token' in sess
        
        # Call clear all endpoint
        response = auth_session.post('/api/clear-all')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['status'] == 'ok'
        
        # Verify session is cleared
        with auth_session.session_transaction() as sess:
            assert 'device_auth_token' not in sess
    
    @pytest.mark.timeout(10)
    def test_clear_all_returns_table_counts(self, auth_session):
        """Test that clear all endpoint returns row counts for each table."""
        response = auth_session.post('/api/clear-all')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['status'] == 'ok'
        
        # Verify tables_cleared contains expected tables
        assert 'tables_cleared' in data
        tables_cleared = data['tables_cleared']
        
        expected_tables = [
            'connected_devices', 'categories', 'sync_state', 'users',
            'auth_tokens', 'devices', 'families', 'server_checks'
        ]
        for table in expected_tables:
            assert table in tables_cleared
            assert isinstance(tables_cleared[table], int)
    
    @pytest.mark.timeout(10)
    def test_clear_all_includes_duration(self, auth_session):
        """Test that clear all endpoint includes duration in response."""
        response = auth_session.post('/api/clear-all')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['status'] == 'ok'
        assert 'duration_ms' in data
        assert isinstance(data['duration_ms'], int)
        assert data['duration_ms'] >= 0
    
    @pytest.mark.timeout(10)
    def test_clear_all_clears_auth_tokens(self, auth_session):
        """Test that clear all endpoint clears auth tokens from database."""
        # Get device_auth_token from session
        with auth_session.session_transaction() as sess:
            device_auth_token = sess['device_auth_token']
        
        db = auth_session.application.test_db
        
        # Verify auth token exists
        tokens = get_device_auth_tokens(db)
        assert len(tokens) > 0
        
        # Call clear all endpoint
        response = auth_session.post('/api/clear-all')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['status'] == 'ok'
        
        # Verify auth tokens are cleared
        tokens = get_device_auth_tokens(db)
        assert len(tokens) == 0
    
    @pytest.mark.timeout(10)
    def test_clear_all_clears_server_selection(self, auth_session):
        """Test that clear all endpoint clears server selection from persistence."""
        from persistence import get_current_server_key, get_current_server_url
        
        # Set a server selection first
        from persistence import set_current_server_key, set_current_server_url
        set_current_server_key('local')
        set_current_server_url('http://localhost:8080')
        
        # Verify server selection exists
        server_key = get_current_server_key()
        assert server_key == 'local'
        
        # Call clear all endpoint
        response = auth_session.post('/api/clear-all')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['status'] == 'ok'
        
        # Verify server selection is cleared
        server_key = get_current_server_key()
        assert server_key is None
        
        server_url = get_current_server_url()
        assert server_url is None


class TestApiAuthBackup:
    """Tests for /api/auth/backup endpoint."""
    
    @pytest.mark.timeout(10)
    def test_backup_creates_backup_file(self, auth_session):
        """Test that backup endpoint creates a backup file."""
        from persistence import get_auth_token_backup_path
        import os
        
        # Get device_auth_token from session
        with auth_session.session_transaction() as sess:
            device_auth_token = sess['device_auth_token']
            sess['own_device_id'] = 'test_device_id_backup'
        
        # Call backup endpoint
        response = auth_session.post('/api/auth/backup')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['status'] == 'ok'
        assert data['backup_successful'] is True
        assert data['has_device_auth_token'] is True
        assert data['has_own_device_id'] is True
        
        # Verify backup file was created
        backup_path = get_auth_token_backup_path()
        assert os.path.exists(backup_path)
    
    @pytest.mark.timeout(10)
    def test_backup_returns_token_info(self, auth_session):
        """Test that backup endpoint returns token information."""
        # Get device_auth_token from session
        with auth_session.session_transaction() as sess:
            device_auth_token = sess['device_auth_token']
            sess['own_device_id'] = 'device_for_backup_test'
        
        response = auth_session.post('/api/auth/backup')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['status'] == 'ok'
        assert data['device_auth_token'] == device_auth_token
        assert data['own_device_id'] == 'device_for_backup_test'


class TestApiAuthRestore:
    """Tests for /api/auth/restore endpoint."""
    
    @pytest.mark.timeout(10)
    def test_restore_from_backup(self, auth_session):
        """Test restoring auth tokens from backup."""
        from persistence import get_auth_token_backup_path, backup_auth_tokens
        import os
        
        # First create a backup
        with auth_session.session_transaction() as sess:
            sess['own_device_id'] = 'device_to_restore'
        
        # Create backup
        backup_result = backup_auth_tokens()
        assert backup_result['backup_successful'] is True
        
        # Clear the session
        with auth_session.session_transaction() as sess:
            sess.clear()
        
        # Call restore endpoint
        response = auth_session.post('/api/auth/restore')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['status'] == 'ok'
        assert data['restore_successful'] is True
    
    @pytest.mark.timeout(10)
    def test_restore_no_backup_file(self, client):
        """Test restore when no backup file exists."""
        from persistence import get_auth_token_backup_path
        import os
        
        # Ensure no backup file exists
        backup_path = get_auth_token_backup_path()
        if os.path.exists(backup_path):
            os.unlink(backup_path)
        
        response = client.post('/api/auth/restore')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['status'] == 'ok'
        assert data['restore_successful'] is False
        assert 'No backup file found' in data.get('error', '')


class TestApiAuthClearBackup:
    """Tests for /api/auth/clear-backup endpoint."""
    
    @pytest.mark.timeout(10)
    def test_clear_backup(self, auth_session):
        """Test clearing the backup file."""
        from persistence import get_auth_token_backup_path, backup_auth_tokens
        import os
        
        # First create a backup
        backup_result = backup_auth_tokens()
        assert backup_result['backup_successful'] is True
        
        # Verify backup file exists
        backup_path = get_auth_token_backup_path()
        assert os.path.exists(backup_path)
        
        # Call clear backup endpoint
        response = auth_session.post('/api/auth/clear-backup')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['status'] == 'ok'
        assert data['cleared'] is True
        
        # Verify backup file was deleted
        assert not os.path.exists(backup_path)
    
    @pytest.mark.timeout(10)
    def test_clear_backup_no_file(self, client):
        """Test clearing backup when no backup file exists."""
        from persistence import get_auth_token_backup_path
        import os
        
        # Ensure no backup file exists
        backup_path = get_auth_token_backup_path()
        if os.path.exists(backup_path):
            os.unlink(backup_path)
        
        response = client.post('/api/auth/clear-backup')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['status'] == 'ok'
        # Should still return True even if no file existed
        assert data['cleared'] is True


class TestApiDashboardDevicesRemove:
    """Tests for /api/dashboard/devices/remove endpoint."""
    
    @pytest.mark.timeout(10)
    def test_remove_device_unauthenticated(self, client):
        """Test device removal without authentication."""
        response = client.post('/api/dashboard/devices/remove',
                               json={'deviceId': 'device_to_remove'})
        
        # When session is empty, the code returns 401 (Not authenticated)
        assert response.status_code == 401
        data = json.loads(response.data)
        assert data['status'] == 'error'
        assert data['error'] == 'Not authenticated'
    
    @pytest.mark.timeout(10)
    def test_remove_device_no_device_auth_token(self, client):
        """Test device removal without device auth token in session."""
        with client.session_transaction() as sess:
            sess['device_auth_token'] = None
        
        response = client.post('/api/dashboard/devices/remove',
                               json={'deviceId': 'device_to_remove'})
        
        assert response.status_code == 400
        data = json.loads(response.data)
        assert data['status'] == 'error'
        assert data['error'] == 'No device auth token'
    
    @pytest.mark.timeout(10)
    def test_remove_device_missing_device_id(self, client, auth_session):
        """Test device removal without deviceId in request."""
        # Set parent password hash so we can test missing device_id
        with auth_session.session_transaction() as sess:
            sess['parent_password_second_hash'] = '$2b$12$test_hash'
            sess['parent_user_id'] = 'user_parent_123'
        
        response = auth_session.post('/api/dashboard/devices/remove',
                                     json={})
        
        assert response.status_code == 400
        data = json.loads(response.data)
        assert data['status'] == 'error'
        assert data['error'] == 'Missing deviceId'
    
    @pytest.mark.timeout(10)
    def test_remove_device_no_parent_password_hash(self, client, auth_session):
        """Test device removal without parent password hash in session."""
        # Get device_auth_token from session
        with auth_session.session_transaction() as sess:
            device_auth_token = sess['device_auth_token']
            # Ensure parent_password_second_hash is not set
            sess.pop('parent_password_second_hash', None)
        
        response = auth_session.post('/api/dashboard/devices/remove',
                                     json={'deviceId': 'device_to_remove'})
        
        assert response.status_code == 400
        data = json.loads(response.data)
        assert data['status'] == 'error'
        assert 'Parent password hash' in data['error']
    
    @pytest.mark.timeout(10)
    def test_remove_device_cannot_remove_own_device(self, client, auth_session):
        """Test that a device cannot remove itself."""
        # Get device_auth_token from session
        with auth_session.session_transaction() as sess:
            device_auth_token = sess['device_auth_token']
            # Set own_device_id to match the device we're trying to remove
            sess['own_device_id'] = 'device_to_remove'
            # Set parent password hash
            sess['parent_password_second_hash'] = '$2b$12$test_hash'
        
        response = auth_session.post('/api/dashboard/devices/remove',
                                     json={'deviceId': 'device_to_remove'})
        
        assert response.status_code == 400
        data = json.loads(response.data)
        assert data['status'] == 'error'
        assert data['error'] == 'Cannot remove the current device'
    
    @pytest.mark.timeout(10)
    @patch('app.AuthClient')
    def test_remove_device_success(self, mock_auth_client_class, auth_session):
        """Test successful device removal via REST API."""
        # Get device_auth_token from session
        with auth_session.session_transaction() as sess:
            device_auth_token = sess['device_auth_token']
            # Set parent password hash
            sess['parent_password_second_hash'] = '$2b$12$test_hash'
            sess['parent_user_id'] = 'user_parent_123'
        
        # Mock the AuthClient and its remove_device method
        mock_client = Mock()
        mock_response = Mock()
        mock_response.success = True
        mock_response.error_code = None
        mock_response.error_message = None
        mock_response.status_code = 200
        mock_client.remove_device.return_value = mock_response
        mock_auth_client_class.return_value = mock_client
        
        response = auth_session.post('/api/dashboard/devices/remove',
                                     json={'deviceId': 'device_to_remove'})
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['status'] == 'ok'
        assert data['message'] == 'Device removed successfully'
        
        # Verify the client was called with correct parameters
        mock_client.remove_device.assert_called_once()
        call_kwargs = mock_client.remove_device.call_args[1]
        assert call_kwargs['device_auth_token'] == device_auth_token
        assert call_kwargs['parent_user_id'] == 'user_parent_123'
        assert call_kwargs['parent_password_second_hash'] == '$2b$12$test_hash'
        assert call_kwargs['device_id'] == 'device_to_remove'
    
    @pytest.mark.timeout(10)
    @patch('app.AuthClient')
    def test_remove_device_failure(self, mock_auth_client_class, auth_session):
        """Test device removal when REST API call fails."""
        # Get device_auth_token from session
        with auth_session.session_transaction() as sess:
            device_auth_token = sess['device_auth_token']
            # Set parent password hash
            sess['parent_password_second_hash'] = '$2b$12$test_hash'
            sess['parent_user_id'] = 'user_parent_123'
        
        # Mock the AuthClient to return a failed response
        mock_client = Mock()
        mock_response = Mock()
        mock_response.success = False
        mock_response.error_code = 'unauthorized'
        mock_response.error_message = 'Unauthorized'
        mock_response.status_code = 401
        mock_client.remove_device.return_value = mock_response
        mock_auth_client_class.return_value = mock_client
        
        response = auth_session.post('/api/dashboard/devices/remove',
                                     json={'deviceId': 'device_to_remove'})
        
        assert response.status_code == 401
        data = json.loads(response.data)
        assert data['status'] == 'error'
        assert data['error_code'] == 'unauthorized'
        assert data['error_message'] == 'Unauthorized'

    @pytest.mark.timeout(10)
    @patch('app.AuthClient')
    def test_remove_device_parent_user_id_from_database(self, mock_auth_client_class, client):
        """Test device removal when parent_user_id is fetched from database."""
        # Create a test device auth token
        device_auth_token = 'device_token_db_parent_user_test'
        own_device_id = 'device_own_db_parent_user_test'
        parent_user_id = 'user_parent_from_db'
        
        db = client.application.test_db
        
        # Create a family with parent_user_id in the database
        from database import create_family, create_device, store_auth_token, update_family_parent_user_id
        create_family(
            db=db,
            device_auth_token=device_auth_token,
            mail='test@example.com',
            parent_password_hash='$2b$12$hash1',
            parent_password_second_hash='$2b$12$hash2',
            parent_password_second_salt='$2b$12$salt',
            parent_password_encrypted=False
        )
        # Update the family with parent_user_id
        update_family_parent_user_id(db, device_auth_token, parent_user_id)
        
        # Create a device
        create_device(
            db=db,
            device_id='device1',
            device_auth_token=device_auth_token,
            name='Test Device'
        )
        
        # Store auth token
        store_auth_token(
            db=db,
            token_type='device_auth_token',
            token_value=device_auth_token,
            device_id=own_device_id,
            mail='test@example.com'
        )
        
        # Set up session WITHOUT parent_user_id (to test database fallback)
        with client.session_transaction() as sess:
            sess['device_auth_token'] = device_auth_token
            sess['own_device_id'] = own_device_id
            sess['parent_password_second_hash'] = '$2b$12$test_hash'
            # Note: NOT setting parent_user_id in session
        
        # Mock the AuthClient
        mock_client = Mock()
        mock_response = Mock()
        mock_response.success = True
        mock_response.error_code = None
        mock_response.error_message = None
        mock_response.status_code = 200
        mock_client.remove_device.return_value = mock_response
        mock_auth_client_class.return_value = mock_client
        
        response = client.post('/api/dashboard/devices/remove',
                               json={'deviceId': 'device1'})
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['status'] == 'ok'
        assert data['message'] == 'Device removed successfully'
        
        # Verify the client was called with parent_user_id from database
        mock_client.remove_device.assert_called_once()
        call_kwargs = mock_client.remove_device.call_args[1]
        assert call_kwargs['device_auth_token'] == device_auth_token
        assert call_kwargs['parent_user_id'] == parent_user_id
        assert call_kwargs['parent_password_second_hash'] == '$2b$12$test_hash'
        assert call_kwargs['device_id'] == 'device1'

    @pytest.mark.timeout(10)
    def test_remove_device_parent_user_id_not_found(self, client):
        """Test device removal when parent_user_id is not in session or database."""
        # Create a test device auth token
        device_auth_token = 'device_token_no_parent_user_test'
        own_device_id = 'device_own_no_parent_user_test'
        
        db = client.application.test_db
        
        # Create a family WITHOUT parent_user_id
        from database import create_family, create_device, store_auth_token
        create_family(
            db=db,
            device_auth_token=device_auth_token,
            mail='test@example.com',
            parent_password_hash='$2b$12$hash1',
            parent_password_second_hash='$2b$12$hash2',
            parent_password_second_salt='$2b$12$salt',
            parent_password_encrypted=False
        )
        # Note: NOT calling update_family_parent_user_id
        
        # Create a device
        create_device(
            db=db,
            device_id='device1',
            device_auth_token=device_auth_token,
            name='Test Device'
        )
        
        # Store auth token
        store_auth_token(
            db=db,
            token_type='device_auth_token',
            token_value=device_auth_token,
            device_id=own_device_id,
            mail='test@example.com'
        )
        
        # Set up session WITHOUT parent_user_id
        with client.session_transaction() as sess:
            sess['device_auth_token'] = device_auth_token
            sess['own_device_id'] = own_device_id
            sess['parent_password_second_hash'] = '$2b$12$test_hash'
            # Note: NOT setting parent_user_id in session
        
        response = client.post('/api/dashboard/devices/remove',
                               json={'deviceId': 'device1'})
        
        assert response.status_code == 400
        data = json.loads(response.data)
        assert data['status'] == 'error'
        assert data['error'] == 'Parent user ID not found'


class TestDebugDatabase:
    """Tests for /debug/database endpoint."""

    @pytest.mark.timeout(10)
    def test_debug_database_returns_html(self, client):
        """Test that debug database returns HTML response."""
        response = client.get('/debug/database')

        assert response.status_code == 200
        assert response.content_type == 'text/html; charset=utf-8'

    @pytest.mark.timeout(10)
    def test_debug_database_contains_database_viewer(self, client):
        """Test that debug database page contains database viewer elements."""
        response = client.get('/debug/database')

        assert response.status_code == 200
        html = response.data.decode('utf-8')

        # Check for expected elements in the template
        assert 'Database Viewer' in html
        assert 'Back to Dashboard' in html

    @pytest.mark.timeout(10)
    def test_debug_database_shows_tables(self, client):
        """Test that debug database shows table names."""
        response = client.get('/debug/database')

        assert response.status_code == 200
        html = response.data.decode('utf-8')

        # Check that at least some tables are shown
        # The database should have tables like server_checks, families, devices, etc.
        assert 'server_checks' in html or 'families' in html or 'devices' in html

    @pytest.mark.timeout(10)
    def test_debug_database_shows_row_counts(self, client):
        """Test that debug database shows row counts for tables."""
        response = client.get('/debug/database')

        assert response.status_code == 200
        html = response.data.decode('utf-8')

        # Check for row count display
        assert 'rows' in html.lower() or 'row' in html.lower()

    @pytest.mark.timeout(10)
    def test_debug_database_handles_empty_database(self, client):
        """Test that debug database handles empty database gracefully."""
        # Clear all tables first
        db = client.application.test_db
        from database import clear_all_tables
        clear_all_tables(db)

        response = client.get('/debug/database')

        assert response.status_code == 200
        html = response.data.decode('utf-8')

        # Should still render the page, just with empty tables
        assert 'Database Viewer' in html

    @pytest.mark.timeout(10)
    def test_debug_database_shows_table_data(self, client):
        """Test that debug database shows actual table data."""
        # Add some test data
        db = client.application.test_db
        from database import create_family, store_auth_token

        create_family(
            db=db,
            device_auth_token='test_device_token_for_debug',
            mail='debug@test.com',
            parent_password_hash='$2b$12$hash1',
            parent_password_second_hash='$2b$12$hash2',
            parent_password_second_salt='$2b$12$salt',
            parent_password_encrypted=False
        )

        store_auth_token(
            db=db,
            token_type='device_auth_token',
            token_value='test_device_token_for_debug',
            device_id='test_device_id',
            mail='debug@test.com'
        )

        response = client.get('/debug/database')

        assert response.status_code == 200
        html = response.data.decode('utf-8')

        # Check that the test data is visible
        assert 'debug@test.com' in html or 'test_device_token_for_debug' in html

    @pytest.mark.timeout(10)
    def test_debug_database_shows_multiple_tables(self, client):
        """Test that debug database shows multiple tables."""
        response = client.get('/debug/database')

        assert response.status_code == 200
        html = response.data.decode('utf-8')

        # Should show multiple tables
        # Check for common table names that should exist
        table_names = ['server_checks', 'families', 'devices', 'auth_tokens', 'users', 'sync_state', 'categories', 'connected_devices']
        found_tables = [name for name in table_names if name in html]

        # At least some tables should be present
        assert len(found_tables) > 0