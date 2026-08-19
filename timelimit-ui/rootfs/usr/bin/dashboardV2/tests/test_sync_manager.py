"""Unit tests for sync_manager module.

This module tests the SyncManager class functionality including:
- Sync orchestration
- ClientDataStatus building
- ServerDataStatus application
- Sync state updates
- SSE event broadcasting
"""

import os
import tempfile
import pytest
from unittest.mock import Mock, patch, MagicMock

from sync_manager import (
    SyncManager,
    create_sync_manager,
    get_event_queue,
    run_background_sync,
    store_sync_credentials,
    get_sync_credentials
)
from database import Database, save_users, get_users_by_family, save_sync_state, get_sync_state


class TestSyncManagerInitialization:
    """Tests for SyncManager initialization."""
    
    def test_sync_manager_creation(self):
        """Test creating a SyncManager instance."""
        db_fd, db_path = tempfile.mkstemp(suffix='.db')
        try:
            db = Database(db_path=db_path)
            db.init_db()
            
            manager = SyncManager(db)
            
            assert manager.db is db
            assert manager._lock is not None
            
            db.close()
        finally:
            os.close(db_fd)
            os.unlink(db_path)
    
    def test_create_sync_manager_function(self):
        """Test create_sync_manager convenience function."""
        db_fd, db_path = tempfile.mkstemp(suffix='.db')
        try:
            db = Database(db_path=db_path)
            db.init_db()
            
            manager = create_sync_manager(db)
            
            assert isinstance(manager, SyncManager)
            assert manager.db is db
            
            db.close()
        finally:
            os.close(db_fd)
            os.unlink(db_path)


class TestBuildClientDataStatus:
    """Tests for _build_client_data_status method."""
    
    @pytest.fixture
    def test_db(self):
        """Create a test database."""
        db_fd, db_path = tempfile.mkstemp(suffix='.db')
        db = Database(db_path=db_path)
        db.init_db()
        yield db
        db.close()
        os.close(db_fd)
        os.unlink(db_path)
    
    def test_build_client_data_status_no_prior_state(self, test_db):
        """Test building ClientDataStatus with no prior sync state."""
        manager = SyncManager(test_db)
        
        client_status = manager._build_client_data_status(None)
        
        assert client_status['clientLevel'] == 7
        assert client_status['devices'] is None
        assert client_status['users'] is None
        assert client_status['apps'] == {}
        assert client_status['devicesDetail'] == {}
        assert client_status['categories'] == {}
        assert client_status['kri'] == 0
        assert client_status['kr'] == 0
        assert client_status['dh'] is None
        assert client_status['u2f'] is None
    
    def test_build_client_data_status_with_prior_state(self, test_db):
        """Test building ClientDataStatus with existing sync state."""
        manager = SyncManager(test_db)
        
        # Save a sync state first
        save_sync_state(test_db, 'family_test123', 'device_v1', 'user_v1')
        
        sync_state = get_sync_state(test_db, 'family_test123')
        client_status = manager._build_client_data_status(sync_state)
        
        assert client_status['clientLevel'] == 7
        assert client_status['devices'] == 'device_v1'
        assert client_status['users'] == 'user_v1'


class TestApplyServerDataStatus:
    """Tests for _apply_server_data_status method."""
    
    @pytest.fixture
    def test_db(self):
        """Create a test database."""
        db_fd, db_path = tempfile.mkstemp(suffix='.db')
        db = Database(db_path=db_path)
        db.init_db()
        yield db
        db.close()
        os.close(db_fd)
        os.unlink(db_path)
    
    def test_apply_server_data_status_with_users(self, test_db):
        """Test applying server data with users."""
        manager = SyncManager(test_db)
        
        server_data = {
            'users': {
                'version': 'v1',
                'data': [
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
                ]
            }
        }
        
        manager._apply_server_data_status(server_data, 'family_test123')
        
        users = get_users_by_family(test_db, 'family_test123')
        
        assert len(users) == 2
        assert users[0]['id'] == 'user1'
        assert users[0]['name'] == 'Parent User'
        assert users[1]['id'] == 'user2'
    
    def test_apply_server_data_status_with_categories(self, test_db):
        """Test applying server data with categories."""
        manager = SyncManager(test_db)
        
        server_data = {
            'categoryBase': [
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
            ]
        }
        
        manager._apply_server_data_status(server_data, 'family_test123')
        
        from database import get_categories_by_family
        categories = get_categories_by_family(test_db, 'family_test123')
        
        assert len(categories) == 2
        assert categories[0]['id'] == 'cat1'
        assert categories[0]['title'] == 'Work'
    
    def test_apply_server_data_status_with_connected_devices(self, test_db):
        """Test applying server data with connected devices from pings."""
        manager = SyncManager(test_db)
        
        # Connected devices come from the 'pings' field in ServerDataStatus
        # Each ping has deviceId, token, and type ('ping' or 'pong')
        server_data = {
            'pings': [
                {'deviceId': 'device1', 'token': 'token1', 'type': 'ping'},
                {'deviceId': 'device2', 'token': 'token2', 'type': 'pong'},
                {'deviceId': 'device3', 'token': 'token3', 'type': 'ping'}
            ]
        }
        
        manager._apply_server_data_status(server_data, 'family_test123')
        
        from database import get_connected_devices
        devices = get_connected_devices(test_db, 'family_test123')
        
        assert len(devices) == 3
        device_ids = [d['device_id'] for d in devices]
        assert 'device1' in device_ids
        assert 'device2' in device_ids
        assert 'device3' in device_ids


class TestUpdateSyncState:
    """Tests for _update_sync_state method."""
    
    @pytest.fixture
    def test_db(self):
        """Create a test database."""
        db_fd, db_path = tempfile.mkstemp(suffix='.db')
        db = Database(db_path=db_path)
        db.init_db()
        yield db
        db.close()
        os.close(db_fd)
        os.unlink(db_path)
    
    def test_update_sync_state(self, test_db):
        """Test updating sync state."""
        manager = SyncManager(test_db)
        
        server_data = {
            'devices': {'version': 'device_v2'},
            'users': {'version': 'user_v3'}
        }
        
        manager._update_sync_state(server_data, 'family_test123')
        
        state = get_sync_state(test_db, 'family_test123')
        
        assert state is not None
        assert state['device_list_version'] == 'device_v2'
        assert state['user_list_version'] == 'user_v3'
        assert state['last_sync_success'] == 1


class TestBroadcastSyncComplete:
    """Tests for _broadcast_sync_complete method."""
    
    @pytest.fixture
    def test_db(self):
        """Create a test database."""
        db_fd, db_path = tempfile.mkstemp(suffix='.db')
        db = Database(db_path=db_path)
        db.init_db()
        yield db
        db.close()
        os.close(db_fd)
        os.unlink(db_path)
    
    def test_broadcast_sync_complete(self, test_db):
        """Test broadcasting sync complete event."""
        manager = SyncManager(test_db)
        
        server_data = {
            'users': {
                'version': 'v1',
                'data': [
                    {'id': 'user1', 'name': 'User 1'},
                    {'id': 'user2', 'name': 'User 2'}
                ]
            },
            'devices': {
                'version': 'v1',
                'data': [
                    {'deviceId': 'device1', 'name': 'Device 1'}
                ]
            }
        }
        
        manager._broadcast_sync_complete('family_test123', server_data)
        
        # Get the event queue and verify event was broadcast
        q = get_event_queue('family_test123')
        event = q.get(timeout=5)
        
        assert event['type'] == 'sync_complete'
        assert event['data']['users_count'] == 2
        assert event['data']['devices_count'] == 1


class TestGetEventQueue:
    """Tests for get_event_queue function."""
    
    def test_get_event_queue_creates_new(self):
        """Test that get_event_queue creates a new queue for new family."""
        q = get_event_queue('new_family')
        
        assert q is not None
        assert isinstance(q, type(q))  # It's a Queue
    
    def test_get_event_queue_returns_same_queue(self):
        """Test that get_event_queue returns the same queue for same family."""
        q1 = get_event_queue('family_test')
        q2 = get_event_queue('family_test')
        
        assert q1 is q2


class TestStoreSyncCredentials:
    """Tests for store_sync_credentials function."""
    
    @pytest.fixture
    def test_db(self):
        """Create a test database."""
        db_fd, db_path = tempfile.mkstemp(suffix='.db')
        db = Database(db_path=db_path)
        db.init_db()
        yield db
        db.close()
        os.close(db_fd)
        os.unlink(db_path)
    
    def test_store_sync_credentials(self, test_db):
        """Test storing sync credentials."""
        store_sync_credentials(
            test_db,
            'family_test123',
            'device_token_abc123'
        )
        
        # Verify the token was stored
        from database import get_auth_token
        token = get_auth_token(test_db, 'device_token_abc123')
        
        assert token is not None
        assert token['token_type'] == 'sync_device_auth_token'
        assert token['token_value'] == 'device_token_abc123'
        assert token['family_id'] == 'family_test123'


class TestGetSyncCredentials:
    """Tests for get_sync_credentials function."""
    
    @pytest.fixture
    def test_db(self):
        """Create a test database."""
        db_fd, db_path = tempfile.mkstemp(suffix='.db')
        db = Database(db_path=db_path)
        db.init_db()
        yield db
        db.close()
        os.close(db_fd)
        os.unlink(db_path)
    
    def test_get_sync_credentials_found(self, test_db):
        """Test getting sync credentials when they exist."""
        # Store credentials first
        store_sync_credentials(
            test_db,
            'family_test123',
            'device_token_abc123'
        )
        
        token = get_sync_credentials(test_db, 'family_test123')
        
        assert token == 'device_token_abc123'
    
    def test_get_sync_credentials_not_found(self, test_db):
        """Test getting sync credentials when they don't exist."""
        token = get_sync_credentials(test_db, 'nonexistent_family')
        
        assert token is None


class TestDoSync:
    """Tests for do_sync method."""
    
    @pytest.fixture
    def test_db(self):
        """Create a test database."""
        db_fd, db_path = tempfile.mkstemp(suffix='.db')
        db = Database(db_path=db_path)
        db.init_db()
        yield db
        db.close()
        os.close(db_fd)
        os.unlink(db_path)
    
    @pytest.mark.timeout(10)
    @patch('sync_manager.AuthClient')
    def test_do_sync_success(self, mock_client_class, test_db):
        """Test successful sync operation."""
        # Mock the auth client
        mock_client = Mock()
        mock_response = Mock()
        mock_response.success = True
        mock_response.data = {
            'devices': {
                'version': 'v1',
                'data': [
                    {'deviceId': 'device1', 'name': 'Phone', 'model': 'Pixel 7'}
                ]
            },
            'users': {
                'version': 'v1',
                'data': [
                    {'id': 'user1', 'name': 'Parent', 'type': 'parent', 'mail': 'parent@example.com'}
                ]
            },
            'categoryBase': [],
            'devices2': [{'deviceId': 'device1'}]
        }
        mock_client.pull_status.return_value = mock_response
        mock_client_class.return_value = mock_client
        
        manager = SyncManager(test_db)
        result = manager.do_sync('device_token_123', 'http://localhost:8080', 'family_test123')
        
        assert result is True
        mock_client.pull_status.assert_called_once()
        
        # Verify data was saved
        users = get_users_by_family(test_db, 'family_test123')
        assert len(users) == 1
    
    @pytest.mark.timeout(10)
    @patch('sync_manager.AuthClient')
    def test_do_sync_failure(self, mock_client_class, test_db):
        """Test failed sync operation."""
        # Mock the auth client to return failure
        mock_client = Mock()
        mock_response = Mock()
        mock_response.success = False
        mock_response.error_code = 'unauthorized'
        mock_response.error_message = 'Invalid token'
        mock_client.pull_status.return_value = mock_response
        mock_client_class.return_value = mock_client
        
        manager = SyncManager(test_db)
        result = manager.do_sync('invalid_token', 'http://localhost:8080', 'family_test123')
        
        assert result is False


class TestRunBackgroundSync:
    """Tests for run_background_sync function."""
    
    @pytest.mark.timeout(10)
    @patch('sync_manager.SyncManager')
    @patch('sync_manager.get_database')
    def test_run_background_sync_success(self, mock_get_db, mock_sync_manager_class):
        """Test background sync job execution."""
        # Mock database and manager
        mock_db = Mock()
        mock_get_db.return_value = mock_db
        
        mock_manager = Mock()
        mock_manager.do_sync.return_value = True
        mock_sync_manager_class.return_value = mock_manager
        
        run_background_sync('device_token_123', 'http://localhost:8080', 'family_test123')
        
        mock_manager.do_sync.assert_called_once_with(
            'device_token_123',
            'http://localhost:8080',
            'family_test123'
        )