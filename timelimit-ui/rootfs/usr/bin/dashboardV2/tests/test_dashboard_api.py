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
    
    yield app
    
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
def client(test_app):
    """Create a test client."""
    return test_app.test_client()


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
        
        assert response.status_code == 401
        data = json.loads(response.data)
        assert data['status'] == 'error'
        assert data['error_code'] == 'unauthorized'
    
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
        
        assert response.status_code == 401
        data = json.loads(response.data)
        assert data['status'] == 'error'
        assert data['error'] == 'Not authenticated'
    
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
        
        assert response.status_code == 401
        data = json.loads(response.data)
        assert data['status'] == 'error'
        assert data['error'] == 'Not authenticated'
    
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


class TestApiDashboardCategories:
    """Tests for /api/dashboard/categories endpoint."""
    
    @pytest.mark.timeout(10)
    def test_categories_unauthenticated(self, client):
        """Test getting categories without authentication."""
        response = client.get('/api/dashboard/categories')
        
        assert response.status_code == 401
        data = json.loads(response.data)
        assert data['status'] == 'error'
        assert data['error'] == 'Not authenticated'
    
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
        
        assert response.status_code == 401
        data = json.loads(response.data)
        assert data['status'] == 'error'
        assert data['error'] == 'Not authenticated'
    
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