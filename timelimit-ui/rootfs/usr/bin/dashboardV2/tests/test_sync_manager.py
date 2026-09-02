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
from database import Database, save_users, get_users_by_device_auth_token, save_sync_state, get_sync_state, save_connected_devices, get_connected_devices


class TestAddOwnDeviceToConnectedDevices:
    """Tests for _add_own_device_to_connected_devices method."""
    
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
    
    def test_add_own_device_to_empty_list(self, test_db):
        """Test adding own device when connected devices list is empty."""
        manager = SyncManager(test_db)
        
        manager._add_own_device_to_connected_devices(
            device_auth_token='device_token_123',
            own_device_id='dashboard_device_1'
        )
        
        # Verify device was added
        devices = get_connected_devices(test_db, 'device_token_123')
        device_ids = [d.get('device_id') for d in devices]
        assert 'dashboard_device_1' in device_ids
    
    def test_add_own_device_to_existing_list(self, test_db):
        """Test adding own device when connected devices list already has devices."""
        # First, add some existing devices
        save_connected_devices(test_db, 'device_token_123', ['device_1', 'device_2'])
        
        manager = SyncManager(test_db)
        
        manager._add_own_device_to_connected_devices(
            device_auth_token='device_token_123',
            own_device_id='dashboard_device_1'
        )
        
        # Verify all devices are present
        devices = get_connected_devices(test_db, 'device_token_123')
        device_ids = [d.get('device_id') for d in devices]
        assert 'device_1' in device_ids
        assert 'device_2' in device_ids
        assert 'dashboard_device_1' in device_ids
    
    def test_add_own_device_already_present(self, test_db):
        """Test that adding own device when already present doesn't duplicate."""
        # First, add the device
        save_connected_devices(test_db, 'device_token_123', ['dashboard_device_1'])
        
        manager = SyncManager(test_db)
        
        # Try to add it again
        manager._add_own_device_to_connected_devices(
            device_auth_token='device_token_123',
            own_device_id='dashboard_device_1'
        )
        
        # Verify device is not duplicated
        devices = get_connected_devices(test_db, 'device_token_123')
        device_ids = [d.get('device_id') for d in devices]
        assert device_ids.count('dashboard_device_1') == 1
    
    def test_add_own_device_creates_device_record(self, test_db):
        """Test that adding own device creates a device record with a friendly name."""
        from database import get_device
        from config import Config
        
        manager = SyncManager(test_db)
        
        # Add the dashboard's own device
        manager._add_own_device_to_connected_devices(
            device_auth_token='device_token_123',
            own_device_id='dashboard_device_1'
        )
        
        # Verify device was created in the devices table with the correct name
        device = get_device(test_db, 'dashboard_device_1')
        assert device is not None
        assert device['id'] == 'dashboard_device_1'
        assert device['device_auth_token'] == 'device_token_123'
        assert device['name'] == Config.DASHBOARD_DEVICE_NAME
    
    def test_add_own_device_uses_existing_device_record(self, test_db):
        """Test that adding own device updates existing device record with dashboard info.
        
        The dashboard device should always have the correct platform info and name,
        even if a previous record had different values.
        """
        from database import create_device, get_device
        from config import Config
        
        # Create a device record with a custom name first (simulating old data)
        create_device(
            db=test_db,
            device_id='dashboard_device_1',
            device_auth_token='device_token_123',
            name='Custom Dashboard Name'
        )
        
        manager = SyncManager(test_db)
        
        # Add the dashboard's own device
        manager._add_own_device_to_connected_devices(
            device_auth_token='device_token_123',
            own_device_id='dashboard_device_1'
        )
        
        # Verify the device record is updated with dashboard platform info
        device = get_device(test_db, 'dashboard_device_1')
        assert device is not None
        assert device['name'] == Config.DASHBOARD_DEVICE_NAME  # 'Dashboard'
        assert device['platform_type'] == 'dashboard'
        assert device['platform_level'] == 1
    
    def test_add_own_device_preserves_all_existing_fields(self, test_db):
        """Test that adding own device preserves ALL existing device fields.
        
        This is a regression test for a bug where _add_own_device_to_connected_devices()
        used INSERT OR REPLACE via create_device(), which overwrote the entire row
        including model, current_user_id, current_protection_level, highest_protection_level,
        current_app_version, highest_app_version, and public_key fields that were set
        by _save_device_from_server() and update_device_app_version() earlier in the
        do_sync() flow.
        """
        from database import create_device, get_device, update_device_app_version
        from config import Config
        
        # Create a device record with all fields set (simulating data from server)
        create_device(
            db=test_db,
            device_id='dashboard_device_1',
            device_auth_token='device_token_123',
            name='Old Name',
            model='Pixel 7',
            current_user_id='user123',
            current_protection_level=2,
            highest_protection_level=3,
            current_app_version='36',
            highest_app_version='36',
            public_key='pubkey123'
        )
        
        manager = SyncManager(test_db)
        
        # Add the dashboard's own device (this should NOT overwrite existing fields)
        manager._add_own_device_to_connected_devices(
            device_auth_token='device_token_123',
            own_device_id='dashboard_device_1'
        )
        
        # Verify ALL existing fields are preserved
        device = get_device(test_db, 'dashboard_device_1')
        assert device is not None
        assert device['name'] == Config.DASHBOARD_DEVICE_NAME  # 'Dashboard'
        assert device['platform_type'] == 'dashboard'
        assert device['platform_level'] == 1
        # These fields must be preserved from the existing record
        assert device['model'] == 'Pixel 7'
        assert device['current_user_id'] == 'user123'
        assert device['current_protection_level'] == 2
        assert device['highest_protection_level'] == 3
        assert device['current_app_version'] == '36'
        assert device['highest_app_version'] == '36'
        assert device['public_key'] == 'pubkey123'
    
    def test_add_own_device_updates_name_when_device_record_created(self, test_db):
        """Test that connected devices list is updated when device record is created.
        
        This tests the scenario where:
        1. Device is added to connected devices list in a previous sync (without name)
        2. Device record is created in a later sync (with name from server)
        3. Connected devices list should be updated with the correct name
        """
        from database import create_device, get_device, save_connected_devices, get_connected_devices
        from config import Config
        
        # Simulate previous sync: device added to connected devices list without name
        save_connected_devices(test_db, 'device_token_123', ['dashboard_device_1'])
        
        # Verify the device doesn't have a record in the devices table yet
        device = get_device(test_db, 'dashboard_device_1')
        assert device is None
        
        # Verify the connected devices list has the device but no name
        devices = get_connected_devices(test_db, 'device_token_123')
        dashboard_device = next((d for d in devices if d.get('device_id') == 'dashboard_device_1'), None)
        assert dashboard_device is not None
        assert dashboard_device['name'] is None  # No name yet
        
        # Simulate current sync: device record is created with name from server
        create_device(
            db=test_db,
            device_id='dashboard_device_1',
            device_auth_token='device_token_123',
            name='Dashboard'  # Name from server
        )
        
        manager = SyncManager(test_db)
        
        # Add the dashboard's own device (this should update the connected devices list)
        manager._add_own_device_to_connected_devices(
            device_auth_token='device_token_123',
            own_device_id='dashboard_device_1'
        )
        
        # Verify the connected devices list is updated with the correct name
        devices = get_connected_devices(test_db, 'device_token_123')
        dashboard_device = next((d for d in devices if d.get('device_id') == 'dashboard_device_1'), None)
        assert dashboard_device is not None
        assert dashboard_device['name'] == 'Dashboard'
    
    def test_add_own_device_updates_name_when_device_record_has_no_name(self, test_db):
        """Test that connected devices list is updated when device record exists but has no name.
        
        This tests the edge case where:
        1. Device is added to connected devices list in a previous sync (without name)
        2. Device record exists but has no name (e.g., created by another process)
        3. Connected devices list should still be updated when name is added
        
        This is a regression test for the bug where the else branch in
        _add_own_device_to_connected_devices would skip calling save_connected_devices
        if the device record didn't have a name yet.
        """
        from database import create_device, get_device, save_connected_devices, get_connected_devices
        from config import Config
        
        # Simulate previous sync: device added to connected devices list without name
        save_connected_devices(test_db, 'device_token_123', ['dashboard_device_1'])
        
        # Verify the connected devices list has the device but no name
        devices = get_connected_devices(test_db, 'device_token_123')
        dashboard_device = next((d for d in devices if d.get('device_id') == 'dashboard_device_1'), None)
        assert dashboard_device is not None
        assert dashboard_device['name'] is None  # No name yet
        
        # Simulate current sync: device record exists but has no name
        # (e.g., created by another process or partial sync)
        create_device(
            db=test_db,
            device_id='dashboard_device_1',
            device_auth_token='device_token_123',
            name=None  # No name yet
        )
        
        manager = SyncManager(test_db)
        
        # Add the dashboard's own device (this should update the device record with name)
        manager._add_own_device_to_connected_devices(
            device_auth_token='device_token_123',
            own_device_id='dashboard_device_1'
        )
        
        # Verify the device record is updated with the dashboard name
        device = get_device(test_db, 'dashboard_device_1')
        assert device is not None
        assert device['name'] == Config.DASHBOARD_DEVICE_NAME
        
        # Verify the connected devices list is updated with the correct name
        devices = get_connected_devices(test_db, 'device_token_123')
        dashboard_device = next((d for d in devices if d.get('device_id') == 'dashboard_device_1'), None)
        assert dashboard_device is not None
        assert dashboard_device['name'] == Config.DASHBOARD_DEVICE_NAME


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
        """Test building ClientDataStatus with no prior sync state.
        
        The format matches Android app's ClientDataStatus.empty:
        - devices and users are empty strings (not null)
        - Optional fields (devicesDetail, kri, kr, dh, u2f) are omitted
        """
        manager = SyncManager(test_db)
        
        client_status = manager._build_client_data_status(None)
        
        assert client_status['clientLevel'] == 7
        assert client_status['devices'] == ""
        assert client_status['users'] == ""
        assert client_status['apps'] == {}
        assert client_status['categories'] == {}
        # Optional fields should be omitted when empty
        assert 'devicesDetail' not in client_status
        assert 'kri' not in client_status
        assert 'kr' not in client_status
        assert 'dh' not in client_status
        assert 'u2f' not in client_status
    
    def test_build_client_data_status_with_prior_state(self, test_db):
        """Test building ClientDataStatus with existing sync state."""
        manager = SyncManager(test_db)
        
        # Save a sync state first
        save_sync_state(test_db, 'device_test123', 'device_v1', 'user_v1')
        
        sync_state = get_sync_state(test_db, 'device_test123')
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
        
        manager._apply_server_data_status(server_data, 'device_test123')
        
        users = get_users_by_device_auth_token(test_db, 'device_test123')
        
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
        
        manager._apply_server_data_status(server_data, 'device_test123')
        
        from database import get_categories_by_device_auth_token
        categories = get_categories_by_device_auth_token(test_db, 'device_test123')
        
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
        
        manager._apply_server_data_status(server_data, 'device_test123')
        
        from database import get_connected_devices
        devices = get_connected_devices(test_db, 'device_test123')
        
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
        
        manager._update_sync_state(server_data, 'device_test123')
        
        state = get_sync_state(test_db, 'device_test123')
        
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
        
        manager._broadcast_sync_complete('device_test123', server_data)
        
        # Get the event queue and verify event was broadcast
        q = get_event_queue('device_test123')
        event = q.get(timeout=5)
        
        assert event['type'] == 'sync_complete'
        assert event['data']['users_count'] == 2
        assert event['data']['devices_count'] == 1


class TestGetEventQueue:
    """Tests for get_event_queue function."""
    
    def test_get_event_queue_creates_new(self):
        """Test that get_event_queue creates a new queue for new device."""
        q = get_event_queue('device_test')
        
        assert q is not None
        assert isinstance(q, type(q))  # It's a Queue
    
    def test_get_event_queue_returns_same_queue(self):
        """Test that get_event_queue returns the same queue for same device."""
        q1 = get_event_queue('device_test')
        q2 = get_event_queue('device_test')
        
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
            'device_token_abc123'
        )
        
        # Verify the token was stored
        from database import get_auth_token
        token = get_auth_token(test_db, 'device_token_abc123')
        
        assert token is not None
        assert token['token_type'] == 'sync_device_auth_token'
        assert token['token_value'] == 'device_token_abc123'
        assert token['device_auth_token'] == 'device_token_abc123'


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
            'device_token_abc123'
        )
        
        token = get_sync_credentials(test_db, 'device_token_abc123')
        
        assert token == 'device_token_abc123'
    
    def test_get_sync_credentials_not_found(self, test_db):
        """Test getting sync credentials when they don't exist."""
        token = get_sync_credentials(test_db, 'nonexistent_device_token')
        
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
        result = manager.do_sync('device_token_123', 'http://localhost:8080')
        
        assert result is True
        mock_client.pull_status.assert_called_once()
        
        # Verify data was saved
        users = get_users_by_device_auth_token(test_db, 'device_token_123')
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
        result = manager.do_sync('invalid_token', 'http://localhost:8080')
        
        assert result is False
    
    @pytest.mark.timeout(10)
    @patch('sync_manager.AuthClient')
    def test_do_sync_with_own_device_id(self, mock_client_class, test_db):
        """Test sync with own_device_id pushes app version action and preserves app version."""
        from database import create_device, get_device
        from config import Config
        
        # Create the device first so update_device_app_version can set the app version
        create_device(
            db=test_db,
            device_id='device1',
            device_auth_token='device_token_123',
            name='Old Name'
        )
        
        # Mock the auth client
        mock_client = Mock()
        
        # Mock pull_status response
        mock_pull_response = Mock()
        mock_pull_response.success = True
        mock_pull_response.data = {
            'devices': {'version': 'v1', 'data': []},
            'users': {'version': 'v1', 'data': []},
            'categoryBase': []
        }
        
        # Mock push_actions response
        mock_push_response = Mock()
        mock_push_response.success = True
        
        mock_client.pull_status.return_value = mock_pull_response
        mock_client.push_actions.return_value = mock_push_response
        mock_client_class.return_value = mock_client
        
        manager = SyncManager(test_db)
        result = manager.do_sync('device_token_123', 'http://localhost:8080', own_device_id='device1')
        
        assert result is True
        mock_client.pull_status.assert_called_once()
        mock_client.push_actions.assert_called_once()
        
        # Verify push_actions was called with correct action format
        call_args = mock_client.push_actions.call_args
        assert call_args[0][0] == 'device_token_123'
        actions = call_args[0][1]
        assert len(actions) == 1
        action = actions[0]
        assert action['type'] == 'appLogic'
        assert action['userId'] == ''
        assert action['integrity'] == ''
        assert 'encodedAction' in action
        assert 'sequenceNumber' in action
        
        # Verify the encoded action contains UPDATE_DEVICE_STATUS
        import json
        encoded = json.loads(action['encodedAction'])
        assert encoded['type'] == 'UPDATE_DEVICE_STATUS'
        assert encoded['appVersion'] == 226  # From Config.APP_VERSION
        
        # Verify the device was added to connected devices
        devices = get_connected_devices(test_db, 'device_token_123')
        device_ids = [d.get('device_id') for d in devices]
        assert 'device1' in device_ids
        
        # Verify app version is preserved after the full sync flow
        # This is a regression test for the bug where _add_own_device_to_connected_devices()
        # used INSERT OR REPLACE via create_device(), overwriting the app version set by
        # update_device_app_version() earlier in do_sync()
        device = get_device(test_db, 'device1')
        assert device is not None
        assert device['current_app_version'] == str(Config().APP_VERSION)  # '226'
        assert device['highest_app_version'] == str(Config().APP_VERSION)  # '226'
        assert device['platform_type'] == 'dashboard'
        assert device['platform_level'] == 1


class TestBuildUpdateDeviceStatusAction:
    """Tests for _build_update_device_status_action method."""
    
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
    
    def test_build_update_device_status_action_format(self, test_db):
        """Test that the action is built with correct format."""
        manager = SyncManager(test_db)
        
        action = manager._build_update_device_status_action(226)
        
        assert action['type'] == 'appLogic'
        assert action['userId'] == ''
        assert action['integrity'] == ''
        assert action['sequenceNumber'] == 0  # Will be updated by push method
        assert 'encodedAction' in action
        
        # Verify the encoded action
        import json
        encoded = json.loads(action['encodedAction'])
        assert encoded['type'] == 'UPDATE_DEVICE_STATUS'
        assert encoded['appVersion'] == 226
    
    def test_build_update_device_status_action_different_versions(self, test_db):
        """Test building action with different app versions."""
        manager = SyncManager(test_db)
        
        action_100 = manager._build_update_device_status_action(100)
        action_226 = manager._build_update_device_status_action(226)
        
        import json
        encoded_100 = json.loads(action_100['encodedAction'])
        encoded_226 = json.loads(action_226['encodedAction'])
        
        assert encoded_100['appVersion'] == 100
        assert encoded_226['appVersion'] == 226


class TestPushAppVersionAction:
    """Tests for _push_app_version_action method."""
    
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
    def test_push_app_version_action_success(self, mock_client_class, test_db):
        """Test successful push of app version action."""
        # Mock the auth client
        mock_client = Mock()
        mock_response = Mock()
        mock_response.success = True
        mock_client.push_actions.return_value = mock_response
        mock_client_class.return_value = mock_client
        
        manager = SyncManager(test_db)
        result = manager._push_app_version_action(
            device_auth_token='device_token_123',
            server_url='http://localhost:8080',
            app_version=226
        )
        
        assert result is True
        mock_client.push_actions.assert_called_once()
        
        # Verify sequence number was incremented
        from database import get_next_sequence_number
        seq = get_next_sequence_number(test_db, 'device_token_123')
        assert seq == 1
    
    @pytest.mark.timeout(10)
    @patch('sync_manager.AuthClient')
    def test_push_app_version_action_failure(self, mock_client_class, test_db):
        """Test failed push of app version action."""
        # Mock the auth client to return failure
        mock_client = Mock()
        mock_response = Mock()
        mock_response.success = False
        mock_response.error_code = 'unauthorized'
        mock_response.error_message = 'Invalid token'
        mock_client.push_actions.return_value = mock_response
        mock_client_class.return_value = mock_client
        
        manager = SyncManager(test_db)
        result = manager._push_app_version_action(
            device_auth_token='device_token_123',
            server_url='http://localhost:8080',
            app_version=226
        )
        
        assert result is False
    
    @pytest.mark.timeout(10)
    @patch('sync_manager.AuthClient')
    def test_push_app_version_action_multiple_calls(self, mock_client_class, test_db):
        """Test that sequence number increments on multiple pushes."""
        # Mock the auth client
        mock_client = Mock()
        mock_response = Mock()
        mock_response.success = True
        mock_client.push_actions.return_value = mock_response
        mock_client_class.return_value = mock_client
        
        manager = SyncManager(test_db)
        
        # First push
        result1 = manager._push_app_version_action(
            device_auth_token='device_token_123',
            server_url='http://localhost:8080',
            app_version=226
        )
        assert result1 is True
        
        # Second push
        result2 = manager._push_app_version_action(
            device_auth_token='device_token_123',
            server_url='http://localhost:8080',
            app_version=226
        )
        assert result2 is True
        
        # Verify sequence number is 2
        from database import get_next_sequence_number
        seq = get_next_sequence_number(test_db, 'device_token_123')
        assert seq == 2


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
        
        run_background_sync('device_token_123', 'http://localhost:8080')
        
        mock_manager.do_sync.assert_called_once_with(
            'device_token_123',
            'http://localhost:8080',
            None  # own_device_id is None when not provided
        )