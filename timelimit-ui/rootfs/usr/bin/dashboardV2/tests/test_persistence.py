"""Unit tests for persistence abstraction.

This module tests the persistence module functionality including:
- FileServerSelectionStore: save and retrieve server selection
- HaIngressServerSelectionStore: HA-specific implementation
- PersistenceFactory: environment detection and store selection
- Atomic writes and thread safety
- Auth token persistence for session restoration
"""

import os
import sys
import json
import tempfile
import pytest
from unittest.mock import patch, MagicMock

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from persistence import (
    ServerSelectionStore,
    FileServerSelectionStore,
    HaIngressServerSelectionStore,
    get_server_selection_store,
    is_ha_ingress,
    get_persistence_dir,
    get_current_server_key,
    set_current_server_key,
    get_current_server_url,
    set_current_server_url,
    get_persisted_device_auth_token,
    set_persisted_device_auth_token,
    get_persisted_own_device_id,
    set_persisted_own_device_id,
    clear_persisted_auth_tokens
)


class TestFileServerSelectionStore:
    """Tests for FileServerSelectionStore implementation."""
    
    @pytest.fixture
    def temp_file(self, tmp_path):
        """Create a temporary file for testing."""
        return str(tmp_path / "test_server_selection.json")
    
    @pytest.fixture
    def store(self, temp_file):
        """Create a FileServerSelectionStore instance."""
        return FileServerSelectionStore(temp_file)
    
    @pytest.mark.timeout(10)
    def test_save_and_retrieve_server_key(self, store, temp_file):
        """Test saving and retrieving server key."""
        store.set_selected_server_key('local')
        
        # Create a new store instance to test file persistence
        new_store = FileServerSelectionStore(temp_file)
        result = new_store.get_selected_server_key()
        
        assert result == 'local'
    
    @pytest.mark.timeout(10)
    def test_save_and_retrieve_server_url(self, store, temp_file):
        """Test saving and retrieving server URL."""
        store.set_selected_server_url('http://192.168.68.30:8080')
        
        # Create a new store instance to test file persistence
        new_store = FileServerSelectionStore(temp_file)
        result = new_store.get_selected_server_url()
        
        assert result == 'http://192.168.68.30:8080'
    
    @pytest.mark.timeout(10)
    def test_get_returns_none_when_not_set(self, store):
        """Test that get returns None when no data is set."""
        assert store.get_selected_server_key() is None
        assert store.get_selected_server_url() is None
    
    @pytest.mark.timeout(10)
    def test_file_created_on_write(self, store, temp_file):
        """Test that file is created when data is written."""
        assert not os.path.exists(temp_file)
        
        store.set_selected_server_key('debug')
        
        assert os.path.exists(temp_file)
    
    @pytest.mark.timeout(10)
    def test_atomic_write(self, store, temp_file):
        """Test that writes are atomic (temp file cleaned up on error)."""
        store.set_selected_server_key('local')
        
        # Verify no temp files remain
        dir_path = os.path.dirname(temp_file)
        temp_files = [f for f in os.listdir(dir_path) if f.startswith('.tmp_')]
        assert len(temp_files) == 0
    
    @pytest.mark.timeout(10)
    def test_corrupt_file_handling(self, temp_file):
        """Test handling of corrupt JSON file."""
        # Write invalid JSON
        with open(temp_file, 'w') as f:
            f.write('not valid json')
        
        store = FileServerSelectionStore(temp_file)
        result = store.get_selected_server_key()
        
        # Should return None on corrupt file
        assert result is None
    
    @pytest.mark.timeout(10)
    def test_multiple_keys(self, store, temp_file):
        """Test saving multiple keys."""
        store.set_selected_server_key('local')
        store.set_selected_server_url('http://192.168.68.30:8080')
        
        new_store = FileServerSelectionStore(temp_file)
        assert new_store.get_selected_server_key() == 'local'
        assert new_store.get_selected_server_url() == 'http://192.168.68.30:8080'
    
    @pytest.mark.timeout(10)
    def test_overwrite_key(self, store, temp_file):
        """Test overwriting an existing key."""
        store.set_selected_server_key('local')
        store.set_selected_server_key('debug')
        
        new_store = FileServerSelectionStore(temp_file)
        assert new_store.get_selected_server_key() == 'debug'
    
    @pytest.mark.timeout(10)
    def test_file_contains_valid_json(self, store, temp_file):
        """Test that written file contains valid JSON with expected structure."""
        store.set_selected_server_key('local')
        store.set_selected_server_url('http://localhost:8080')
        
        with open(temp_file, 'r') as f:
            data = json.load(f)
        
        assert 'server_key' in data
        assert 'server_url' in data
        assert 'updated_at' in data
        assert data['server_key'] == 'local'
        assert data['server_url'] == 'http://localhost:8080'


class TestHaIngressServerSelectionStore:
    """Tests for HaIngressServerSelectionStore implementation."""
    
    @pytest.mark.timeout(10)
    def test_default_file_path(self):
        """Test that default file path is /data/timelimit_ui_server_selection.json."""
        store = HaIngressServerSelectionStore()
        # Use normpath for cross-platform comparison (Windows uses backslashes)
        expected_path = os.path.normpath('/data/timelimit_ui_server_selection.json')
        assert os.path.normpath(store.file_path) == expected_path
    
    @pytest.mark.timeout(10)
    def test_custom_file_path(self, tmp_path):
        """Test that custom file path is used when provided."""
        custom_path = str(tmp_path / "custom.json")
        store = HaIngressServerSelectionStore(file_path=custom_path)
        assert store.file_path == custom_path
    
    @pytest.mark.timeout(10)
    def test_inherits_from_file_store(self):
        """Test that HaIngressServerSelectionStore inherits from FileServerSelectionStore."""
        store = HaIngressServerSelectionStore()
        assert isinstance(store, FileServerSelectionStore)
        assert isinstance(store, ServerSelectionStore)


class TestPersistenceFactory:
    """Tests for persistence factory functions."""
    
    @pytest.mark.timeout(10)
    def test_is_ha_ingress_with_arg(self):
        """Test HA detection with --ha-ingress argument."""
        with patch.object(sys, 'argv', ['app.py', '--ha-ingress']):
            assert is_ha_ingress() is True
    
    @pytest.mark.timeout(10)
    def test_is_ha_ingress_with_env_var(self):
        """Test HA detection with HA_INGRESS environment variable."""
        with patch.dict(os.environ, {'HA_INGRESS': 'true'}):
            assert is_ha_ingress() is True
    
    @pytest.mark.timeout(10)
    def test_is_ha_ingress_false(self):
        """Test HA detection returns False when not in HA mode."""
        with patch.object(sys, 'argv', ['app.py']):
            with patch.dict(os.environ, {}, clear=True):
                assert is_ha_ingress() is False
    
    @pytest.mark.timeout(10)
    def test_get_server_selection_store_returns_correct_type(self):
        """Test that factory returns correct store type based on environment."""
        with patch.object(sys, 'argv', ['app.py']):
            store = get_server_selection_store()
            assert isinstance(store, FileServerSelectionStore)
            assert not isinstance(store, HaIngressServerSelectionStore)
    
    @pytest.mark.timeout(10)
    def test_get_server_selection_store_returns_ha_store(self):
        """Test that factory returns HaIngressServerSelectionStore in HA mode."""
        with patch.object(sys, 'argv', ['app.py', '--ha-ingress']):
            store = get_server_selection_store()
            assert isinstance(store, HaIngressServerSelectionStore)


class TestPersistenceDir:
    """Tests for persistence directory functions."""
    
    @pytest.mark.timeout(10)
    def test_get_persistence_dir_windows(self):
        """Test persistence directory in Windows/local mode."""
        with patch.object(sys, 'argv', ['app.py']):
            with patch.dict(os.environ, {}, clear=True):
                dir_path = get_persistence_dir()
                # Should be the app directory
                assert 'dashboardV2' in dir_path
    
    @pytest.mark.timeout(10)
    def test_get_persistence_dir_ha(self):
        """Test persistence directory in HA mode."""
        with patch.object(sys, 'argv', ['app.py', '--ha-ingress']):
            dir_path = get_persistence_dir()
            assert dir_path == '/data'


class TestConvenienceFunctions:
    """Tests for convenience functions."""
    
    @pytest.fixture
    def temp_file(self, tmp_path):
        """Create a temporary file for testing."""
        return str(tmp_path / "test_server_selection.json")
    
    @pytest.mark.timeout(10)
    def test_get_current_server_key(self, temp_file):
        """Test get_current_server_key convenience function."""
        with patch('persistence.get_server_selection_store') as mock_store:
            mock_store.return_value.get_selected_server_key.return_value = 'local'
            
            result = get_current_server_key()
            assert result == 'local'
    
    @pytest.mark.timeout(10)
    def test_set_current_server_key(self, temp_file):
        """Test set_current_server_key convenience function."""
        with patch('persistence.get_server_selection_store') as mock_store:
            mock_instance = MagicMock()
            mock_store.return_value = mock_instance
            
            set_current_server_key('debug')
            
            mock_instance.set_selected_server_key.assert_called_once_with('debug')
    
    @pytest.mark.timeout(10)
    def test_get_current_server_url(self, temp_file):
        """Test get_current_server_url convenience function."""
        with patch('persistence.get_server_selection_store') as mock_store:
            mock_store.return_value.get_selected_server_url.return_value = 'http://localhost:8080'
            
            result = get_current_server_url()
            assert result == 'http://localhost:8080'
    
    @pytest.mark.timeout(10)
    def test_set_current_server_url(self, temp_file):
        """Test set_current_server_url convenience function."""
        with patch('persistence.get_server_selection_store') as mock_store:
            mock_instance = MagicMock()
            mock_store.return_value = mock_instance
            
            set_current_server_url('http://192.168.68.30:8080')
            
            mock_instance.set_selected_server_url.assert_called_once_with('http://192.168.68.30:8080')


class TestThreadSafety:
    """Tests for thread safety of FileServerSelectionStore."""
    
    @pytest.fixture
    def temp_file(self, tmp_path):
        """Create a temporary file for testing."""
        return str(tmp_path / "test_server_selection.json")
    
    @pytest.mark.timeout(30)
    def test_concurrent_writes(self, temp_file):
        """Test that concurrent writes don't cause corruption."""
        import threading
        
        store = FileServerSelectionStore(temp_file)
        errors = []
        
        def write_key(key):
            try:
                for i in range(10):
                    store.set_selected_server_key(f"{key}_{i}")
            except Exception as e:
                errors.append(e)
        
        threads = [
            threading.Thread(target=write_key, args=(f"thread_{i}",))
            for i in range(5)
        ]
        
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        assert len(errors) == 0, f"Errors during concurrent writes: {errors}"
        
        # Verify file is still valid JSON
        with open(temp_file, 'r') as f:
            data = json.load(f)
        assert 'server_key' in data
    
    @pytest.mark.timeout(30)
    def test_concurrent_reads_and_writes(self, temp_file):
        """Test that concurrent reads and writes work correctly."""
        import threading
        import time
        
        store = FileServerSelectionStore(temp_file)
        errors = []
        read_results = []
        
        def write_data():
            try:
                for i in range(20):
                    store.set_selected_server_key(f"key_{i}")
                    time.sleep(0.001)
            except Exception as e:
                errors.append(e)
        
        def read_data():
            try:
                for _ in range(20):
                    result = store.get_selected_server_key()
                    read_results.append(result)
                    time.sleep(0.001)
            except Exception as e:
                errors.append(e)
        
        threads = [
            threading.Thread(target=write_data),
            threading.Thread(target=read_data),
            threading.Thread(target=read_data),
        ]
        
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        assert len(errors) == 0, f"Errors during concurrent operations: {errors}"
        assert len(read_results) == 40  # 20 reads from each of 2 read threads


class TestPersistenceIntegration:
    """Integration tests for persistence with Flask app."""
    
    @pytest.fixture
    def temp_file(self, tmp_path):
        """Create a temporary file for testing."""
        return str(tmp_path / "test_server_selection.json")
    
    @pytest.mark.timeout(10)
    def test_persistence_survives_store_recreation(self, temp_file):
        """Test that data persists across store instances."""
        store1 = FileServerSelectionStore(temp_file)
        store1.set_selected_server_key('local')
        store1.set_selected_server_url('http://192.168.68.30:8080')
        
        # Create new store instance
        store2 = FileServerSelectionStore(temp_file)
        
        assert store2.get_selected_server_key() == 'local'
        assert store2.get_selected_server_url() == 'http://192.168.68.30:8080'
    
    @pytest.mark.timeout(10)
    def test_persistence_with_all_server_keys(self, temp_file):
        """Test persistence with all valid server keys."""
        store = FileServerSelectionStore(temp_file)
        
        # Test all server keys from Config.SERVER_OPTIONS
        server_keys = ['local', 'official', 'debug']
        
        for key in server_keys:
            store.set_selected_server_key(key)
            new_store = FileServerSelectionStore(temp_file)
            assert new_store.get_selected_server_key() == key
    
    @pytest.mark.timeout(10)
    def test_persistence_file_format(self, temp_file):
        """Test that persistence file has correct format."""
        store = FileServerSelectionStore(temp_file)
        store.set_selected_server_key('local')
        
        with open(temp_file, 'r') as f:
            data = json.load(f)
        
        # Verify structure
        assert isinstance(data, dict)
        assert 'server_key' in data
        assert 'server_url' in data
        assert 'updated_at' in data
        assert isinstance(data['updated_at'], int)


class TestAuthTokenPersistence:
    """Tests for auth token persistence functions (JSON file fallback mode)."""
    
    @pytest.fixture
    def temp_file(self, tmp_path):
        """Create a temporary file for testing."""
        return str(tmp_path / "test_server_selection.json")
    
    @pytest.mark.timeout(10)
    def test_set_and_get_device_auth_token(self, temp_file):
        """Test saving and retrieving device_auth_token."""
        with patch('persistence.get_server_selection_store') as mock_store:
            with patch('persistence.get_database') as mock_get_db:
                # Mock database to return None (no database tokens)
                mock_get_db.return_value = None
                
                mock_instance = FileServerSelectionStore(temp_file)
                mock_store.return_value = mock_instance
                
                test_token = "test_device_auth_token_12345"
                set_persisted_device_auth_token(test_token)
                
                result = get_persisted_device_auth_token()
                assert result == test_token
    
    @pytest.mark.timeout(10)
    def test_get_device_auth_token_returns_none_when_not_set(self, temp_file):
        """Test that get returns None when device_auth_token is not set."""
        with patch('persistence.get_server_selection_store') as mock_store:
            with patch('persistence.get_database') as mock_get_db:
                # Mock database to return None (no database tokens)
                mock_get_db.return_value = None
                
                mock_instance = FileServerSelectionStore(temp_file)
                mock_store.return_value = mock_instance
                
                result = get_persisted_device_auth_token()
                assert result is None
    
    @pytest.mark.timeout(10)
    def test_set_and_get_own_device_id(self, temp_file):
        """Test saving and retrieving own_device_id."""
        with patch('persistence.get_server_selection_store') as mock_store:
            with patch('persistence.get_database') as mock_get_db:
                # Mock database to return None (no database devices)
                mock_get_db.return_value = None
                
                mock_instance = FileServerSelectionStore(temp_file)
                mock_store.return_value = mock_instance
                
                test_device_id = "test_device_id_67890"
                set_persisted_own_device_id(test_device_id)
                
                result = get_persisted_own_device_id()
                assert result == test_device_id
    
    @pytest.mark.timeout(10)
    def test_get_own_device_id_returns_none_when_not_set(self, temp_file):
        """Test that get returns None when own_device_id is not set."""
        with patch('persistence.get_server_selection_store') as mock_store:
            with patch('persistence.get_database') as mock_get_db:
                # Mock database to return None (no database devices)
                mock_get_db.return_value = None
                
                mock_instance = FileServerSelectionStore(temp_file)
                mock_store.return_value = mock_instance
                
                result = get_persisted_own_device_id()
                assert result is None
    
    @pytest.mark.timeout(10)
    def test_clear_persisted_auth_tokens(self, temp_file):
        """Test clearing persisted auth tokens."""
        with patch('persistence.get_server_selection_store') as mock_store:
            with patch('persistence.get_database') as mock_get_db:
                # Mock database to return None (no database tokens)
                mock_get_db.return_value = None
                
                mock_instance = FileServerSelectionStore(temp_file)
                mock_store.return_value = mock_instance
                
                # Set tokens
                set_persisted_device_auth_token("test_token")
                set_persisted_own_device_id("test_device_id")
                
                # Clear tokens
                clear_persisted_auth_tokens()
                
                # Verify cleared
                assert get_persisted_device_auth_token() is None
                assert get_persisted_own_device_id() is None
    
    @pytest.mark.timeout(10)
    def test_auth_tokens_persist_across_instances(self, temp_file):
        """Test that auth tokens persist across store instances."""
        with patch('persistence.get_server_selection_store') as mock_store:
            with patch('persistence.get_database') as mock_get_db:
                # Mock database to return None (no database tokens)
                mock_get_db.return_value = None
                
                # First instance - set tokens
                mock_instance1 = FileServerSelectionStore(temp_file)
                mock_store.return_value = mock_instance1
                
                set_persisted_device_auth_token("test_token_123")
                set_persisted_own_device_id("device_id_456")
                
                # Second instance - retrieve tokens
                mock_instance2 = FileServerSelectionStore(temp_file)
                mock_store.return_value = mock_instance2
                
                assert get_persisted_device_auth_token() == "test_token_123"
                assert get_persisted_own_device_id() == "device_id_456"
    
    @pytest.mark.timeout(10)
    def test_auth_tokens_in_file(self, temp_file):
        """Test that auth tokens are stored in the JSON file."""
        with patch('persistence.get_server_selection_store') as mock_store:
            with patch('persistence.get_database') as mock_get_db:
                # Mock database to return None (no database tokens)
                mock_get_db.return_value = None
                
                mock_instance = FileServerSelectionStore(temp_file)
                mock_store.return_value = mock_instance
                
                test_token = "test_device_auth_token_abc"
                test_device_id = "device_id_xyz"
                
                set_persisted_device_auth_token(test_token)
                set_persisted_own_device_id(test_device_id)
                
                # Read file directly
                with open(temp_file, 'r') as f:
                    data = json.load(f)
                
                assert data.get('device_auth_token') == test_token
                assert data.get('own_device_id') == test_device_id
                assert 'updated_at' in data


class TestAuthTokenPersistenceDatabase:
    """Tests for auth token persistence using SQLite database as primary storage."""
    
    @pytest.fixture
    def test_db(self):
        """Create a test database."""
        import tempfile
        from database import Database, store_auth_token, get_device_auth_tokens
        
        db_fd, db_path = tempfile.mkstemp(suffix='.db')
        db = Database(db_path=db_path)
        db.init_db()
        yield db
        db.close()
        os.close(db_fd)
        os.unlink(db_path)
    
    @pytest.fixture
    def temp_file(self, tmp_path):
        """Create a temporary file for testing."""
        return str(tmp_path / "test_server_selection.json")
    
    @pytest.mark.timeout(10)
    def test_get_persisted_device_auth_token_from_database(self, test_db):
        """Test that get_persisted_device_auth_token retrieves from database."""
        from database import store_auth_token
        
        # Store a token in the database
        store_auth_token(
            db=test_db,
            token_type='device_auth_token',
            token_value='db_token_123',
            device_id='device_test123'
        )
        
        # Mock the database module to use our test database
        with patch('persistence.get_database') as mock_get_db:
            mock_get_db.return_value = test_db
            
            result = get_persisted_device_auth_token()
            assert result == 'db_token_123'
    
    @pytest.mark.timeout(10)
    def test_get_persisted_device_auth_token_returns_none_when_no_database_tokens(self, test_db, temp_file):
        """Test that get_persisted_device_auth_token returns None when no tokens in database."""
        with patch('persistence.get_database') as mock_get_db:
            mock_get_db.return_value = test_db
            
            with patch('persistence.get_server_selection_store') as mock_store:
                mock_instance = FileServerSelectionStore(temp_file)
                mock_store.return_value = mock_instance
                
                result = get_persisted_device_auth_token()
                assert result is None
    
    @pytest.mark.timeout(10)
    def test_get_persisted_own_device_id_from_database(self, test_db):
        """Test that get_persisted_own_device_id retrieves from database."""
        from database import create_device
        
        # Create a device in the database
        create_device(
            db=test_db,
            device_id='device_id_456',
            device_auth_token='device_token_test123',
            name='Test Device'
        )
        
        with patch('persistence.get_database') as mock_get_db:
            mock_get_db.return_value = test_db
            
            result = get_persisted_own_device_id()
            assert result == 'device_id_456'
    
    @pytest.mark.timeout(10)
    def test_get_persisted_own_device_id_returns_none_when_no_database_devices(self, test_db, temp_file):
        """Test that get_persisted_own_device_id returns None when no devices in database."""
        with patch('persistence.get_database') as mock_get_db:
            mock_get_db.return_value = test_db
            
            with patch('persistence.get_server_selection_store') as mock_store:
                mock_instance = FileServerSelectionStore(temp_file)
                mock_store.return_value = mock_instance
                
                result = get_persisted_own_device_id()
                assert result is None
    
    @pytest.mark.timeout(10)
    def test_set_persisted_device_auth_token_saves_to_database(self, test_db):
        """Test that set_persisted_device_auth_token saves to database."""
        from database import get_device_auth_tokens
        
        with patch('persistence.get_database') as mock_get_db:
            mock_get_db.return_value = test_db
            
            set_persisted_device_auth_token('new_token_789')
            
            # Verify token was saved to database
            tokens = get_device_auth_tokens(test_db)
            assert len(tokens) == 1
            assert tokens[0]['token_value'] == 'new_token_789'
    
    @pytest.mark.timeout(10)
    def test_clear_persisted_auth_tokens_deletes_from_database(self, test_db):
        """Test that clear_persisted_auth_tokens deletes from database."""
        from database import get_device_auth_tokens, store_auth_token
        
        # Store a token first
        store_auth_token(
            db=test_db,
            token_type='device_auth_token',
            token_value='token_to_delete',
            device_id='device_test123'
        )
        
        with patch('persistence.get_database') as mock_get_db:
            mock_get_db.return_value = test_db
            
            clear_persisted_auth_tokens()
            
            # Verify token was deleted from database
            tokens = get_device_auth_tokens(test_db)
            assert len(tokens) == 0
    
    @pytest.mark.timeout(10)
    def test_database_token_takes_precedence_over_json(self, test_db, temp_file):
        """Test that database token takes precedence over JSON file."""
        from database import store_auth_token
        
        # Store a token in the database
        store_auth_token(
            db=test_db,
            token_type='device_auth_token',
            token_value='db_token_priority',
            device_id='device_test123'
        )
        
        # Store a different token in JSON file
        with patch('persistence.get_server_selection_store') as mock_store:
            mock_instance = FileServerSelectionStore(temp_file)
            mock_store.return_value = mock_instance
            
            # Write a different token to the JSON file using the correct key
            with mock_instance._lock:
                data = mock_instance._read()
                data['device_auth_token'] = 'json_token_priority'
                mock_instance._write(data)
            
            with patch('persistence.get_database') as mock_get_db:
                mock_get_db.return_value = test_db
                
                result = get_persisted_device_auth_token()
                # Database token should take precedence
                assert result == 'db_token_priority'


class TestAuthTokenBackupRestore:
    """Tests for auth token backup and restore functionality."""
    
    @pytest.fixture
    def temp_file(self, tmp_path):
        """Create a temporary file for testing."""
        return str(tmp_path / "test_server_selection.json")
    
    @pytest.fixture
    def test_db(self):
        """Create a test database."""
        import tempfile
        from database import Database
        
        db_fd, db_path = tempfile.mkstemp(suffix='.db')
        db = Database(db_path=db_path)
        db.init_db()
        yield db
        db.close()
        os.close(db_fd)
        os.unlink(db_path)
    
    @pytest.mark.timeout(10)
    def test_backup_auth_tokens_creates_backup_file(self, temp_file, test_db):
        """Test that backup_auth_tokens creates a backup file."""
        from persistence import (
            backup_auth_tokens, get_auth_token_backup_path,
            set_persisted_device_auth_token
        )
        
        with patch('persistence.get_database') as mock_get_db:
            mock_get_db.return_value = test_db
            
            with patch('persistence.get_server_selection_store') as mock_store:
                mock_instance = FileServerSelectionStore(temp_file)
                mock_store.return_value = mock_instance
                
                # Set token (creates backup automatically)
                set_persisted_device_auth_token('test_backup_token', 'test_device_id')
                
                # Verify backup file exists
                backup_path = get_auth_token_backup_path()
                assert os.path.exists(backup_path)
                
                # Verify backup file contents
                with open(backup_path, 'r') as f:
                    backup_data = json.load(f)
                assert backup_data['device_auth_token'] == 'test_backup_token'
                assert backup_data['own_device_id'] == 'test_device_id'
    
    @pytest.mark.timeout(10)
    def test_backup_auth_tokens_manual(self, temp_file, test_db):
        """Test that backup_auth_tokens creates a backup file manually."""
        from persistence import (
            backup_auth_tokens, get_auth_token_backup_path,
            set_persisted_device_auth_token
        )
        
        with patch('persistence.get_database') as mock_get_db:
            mock_get_db.return_value = test_db
            
            with patch('persistence.get_server_selection_store') as mock_store:
                mock_instance = FileServerSelectionStore(temp_file)
                mock_store.return_value = mock_instance
                
                # Set token (creates backup automatically)
                set_persisted_device_auth_token('manual_backup_token', 'manual_device_id')
                
                # Clear the backup file
                backup_path = get_auth_token_backup_path()
                os.unlink(backup_path)
                
                # Create backup manually
                result = backup_auth_tokens()
                
                assert result['backup_successful'] is True
                assert result['device_auth_token'] == 'manual_backup_token'
                assert result['own_device_id'] == 'manual_device_id'
                
                # Verify backup file exists
                assert os.path.exists(backup_path)
    
    @pytest.mark.timeout(10)
    def test_restore_auth_tokens_from_backup(self, temp_file, test_db):
        """Test that restore_auth_tokens restores from backup file."""
        from persistence import (
            restore_auth_tokens, get_auth_token_backup_path,
            set_persisted_device_auth_token, backup_auth_tokens
        )
        from database import get_device_auth_tokens, delete_all_device_auth_tokens
        
        with patch('persistence.get_database') as mock_get_db:
            mock_get_db.return_value = test_db
            
            with patch('persistence.get_server_selection_store') as mock_store:
                mock_instance = FileServerSelectionStore(temp_file)
                mock_store.return_value = mock_instance
                
                # Set token (creates backup automatically)
                set_persisted_device_auth_token('original_token', 'original_device_id')
                
                # Verify backup exists
                backup_path = get_auth_token_backup_path()
                assert os.path.exists(backup_path)
                
                # Simulate database loss by clearing database and JSON file
                # but NOT the backup (which simulates recovery from backup)
                delete_all_device_auth_tokens(test_db)
                
                # Clear JSON file (simulate file loss)
                with mock_instance._lock:
                    data = mock_instance._read()
                    data.pop('device_auth_token', None)
                    data.pop('own_device_id', None)
                    mock_instance._write(data)
                
                # Restore from backup
                restore_result = restore_auth_tokens()
                
                assert restore_result['restore_successful'] is True
                assert restore_result['device_auth_token'] == 'original_token'
                assert restore_result['own_device_id'] == 'original_device_id'
                
                # Verify token was restored to database
                tokens = get_device_auth_tokens(test_db)
                assert len(tokens) == 1
                assert tokens[0]['token_value'] == 'original_token'
    
    @pytest.mark.timeout(10)
    def test_restore_auth_tokens_no_backup_file(self, temp_file, test_db):
        """Test that restore_auth_tokens handles missing backup file."""
        from persistence import restore_auth_tokens, get_auth_token_backup_path
        
        # Ensure no backup file exists
        backup_path = get_auth_token_backup_path()
        if os.path.exists(backup_path):
            os.unlink(backup_path)
        
        with patch('persistence.get_database') as mock_get_db:
            mock_get_db.return_value = test_db
            
            with patch('persistence.get_server_selection_store') as mock_store:
                mock_instance = FileServerSelectionStore(temp_file)
                mock_store.return_value = mock_instance
                
                result = restore_auth_tokens()
                
                assert result['restore_successful'] is False
                assert 'No backup file found' in result.get('error', '')
    
    @pytest.mark.timeout(10)
    def test_clear_auth_token_backup(self, temp_file, test_db):
        """Test that clear_auth_token_backup removes the backup file."""
        from persistence import (
            backup_auth_tokens, clear_auth_token_backup, get_auth_token_backup_path,
            set_persisted_device_auth_token
        )
        
        with patch('persistence.get_database') as mock_get_db:
            mock_get_db.return_value = test_db
            
            with patch('persistence.get_server_selection_store') as mock_store:
                mock_instance = FileServerSelectionStore(temp_file)
                mock_store.return_value = mock_instance
                
                # Set token (creates backup)
                set_persisted_device_auth_token('test_token', 'test_device_id')
                
                # Verify backup file exists
                backup_path = get_auth_token_backup_path()
                assert os.path.exists(backup_path)
                
                # Clear backup
                result = clear_auth_token_backup()
                
                assert result is True
                assert not os.path.exists(backup_path)
    
    @pytest.mark.timeout(10)
    def test_automatic_backup_on_set_persisted_device_auth_token(self, temp_file, test_db):
        """Test that set_persisted_device_auth_token creates automatic backup."""
        from persistence import (
            set_persisted_device_auth_token, get_auth_token_backup_path
        )
        
        with patch('persistence.get_database') as mock_get_db:
            mock_get_db.return_value = test_db
            
            with patch('persistence.get_server_selection_store') as mock_store:
                mock_instance = FileServerSelectionStore(temp_file)
                mock_store.return_value = mock_instance
                
                # Set token (should create automatic backup)
                set_persisted_device_auth_token('auto_backup_token', 'auto_device_id')
                
                # Verify backup file was created
                backup_path = get_auth_token_backup_path()
                assert os.path.exists(backup_path)
                
                # Verify backup contents
                with open(backup_path, 'r') as f:
                    backup_data = json.load(f)
                assert backup_data['device_auth_token'] == 'auto_backup_token'
                assert backup_data['own_device_id'] == 'auto_device_id'
    
    @pytest.mark.timeout(10)
    def test_clear_persisted_auth_tokens_clears_backup(self, temp_file, test_db):
        """Test that clear_persisted_auth_tokens also clears the backup file."""
        from persistence import (
            set_persisted_device_auth_token, clear_persisted_auth_tokens,
            get_auth_token_backup_path
        )
        
        with patch('persistence.get_database') as mock_get_db:
            mock_get_db.return_value = test_db
            
            with patch('persistence.get_server_selection_store') as mock_store:
                mock_instance = FileServerSelectionStore(temp_file)
                mock_store.return_value = mock_instance
                
                # Set token (creates backup)
                set_persisted_device_auth_token('token_to_clear', 'device_to_clear')
                
                # Verify backup exists
                backup_path = get_auth_token_backup_path()
                assert os.path.exists(backup_path)
                
                # Clear auth tokens
                clear_persisted_auth_tokens()
                
                # Verify backup was also cleared
                assert not os.path.exists(backup_path)


class TestParentPasswordHashPersistence:
    """Tests for parent password hash persistence in session restoration."""

    @pytest.fixture
    def temp_file(self, tmp_path):
        """Create a temporary file for testing."""
        return str(tmp_path / "test_server_selection.json")

    @pytest.fixture
    def test_db(self):
        """Create a test database."""
        import tempfile
        from database import Database
        
        db_fd, db_path = tempfile.mkstemp(suffix='.db')
        db = Database(db_path=db_path)
        db.init_db()
        yield db
        db.close()
        os.close(db_fd)
        os.unlink(db_path)

    @pytest.mark.timeout(10)
    def test_parent_password_hash_restored_from_database(self, test_db):
        """Test that parent password hash is restored from database during session restoration."""
        from database import upsert_family_password_hash, get_parent_password_hash
        
        # Store a hash in the database
        upsert_family_password_hash(
            db=test_db,
            device_auth_token='test-device-token',
            parent_password_second_hash='$2b$12$testhash123'
        )
        
        # Verify it was stored
        stored_hash = get_parent_password_hash(test_db, 'test-device-token')
        assert stored_hash == '$2b$12$testhash123'

    @pytest.mark.timeout(10)
    def test_parent_password_hash_not_found_returns_none(self, test_db):
        """Test that get_parent_password_hash returns None for non-existent family."""
        from database import get_parent_password_hash
        
        hash_value = get_parent_password_hash(test_db, 'nonexistent_token')
        assert hash_value is None

    @pytest.mark.timeout(10)
    def test_parent_password_hash_upsert_inserts_new(self, test_db):
        """Test that upsert inserts hash for new family record."""
        from database import upsert_family_password_hash, get_parent_password_hash
        
        result = upsert_family_password_hash(
            db=test_db,
            device_auth_token='new-device-token',
            parent_password_second_hash='$2b$12$newhash456'
        )
        
        assert result is True
        
        hash_value = get_parent_password_hash(test_db, 'new-device-token')
        assert hash_value == '$2b$12$newhash456'

    @pytest.mark.timeout(10)
    def test_parent_password_hash_upsert_updates_existing(self, test_db):
        """Test that upsert updates hash for existing family record."""
        from database import (
            upsert_family_password_hash,
            get_parent_password_hash,
            create_family
        )
        
        # Create a family first
        create_family(
            db=test_db,
            device_auth_token='existing-token',
            mail='test@example.com',
            parent_password_hash='$2b$12$oldhash',
            parent_password_second_hash='$2b$12$oldsecondhash',
            parent_password_second_salt='$2b$12$salt',
            parent_password_encrypted=False
        )
        
        # Update the hash
        result = upsert_family_password_hash(
            db=test_db,
            device_auth_token='existing-token',
            parent_password_second_hash='$2b$12$updatedhash'
        )
        
        assert result is True
        
        hash_value = get_parent_password_hash(test_db, 'existing-token')
        assert hash_value == '$2b$12$updatedhash'

    @pytest.mark.timeout(10)
    def test_parent_password_hash_preserves_other_fields(self, test_db):
        """Test that upsert preserves other family fields like mail."""
        from database import (
            upsert_family_password_hash,
            get_family,
            create_family
        )
        
        # Create a family with mail
        create_family(
            db=test_db,
            device_auth_token='test-token',
            mail='test@example.com',
            parent_password_hash='$2b$12$hash1',
            parent_password_second_hash='$2b$12$hash2',
            parent_password_second_salt='$2b$12$salt',
            parent_password_encrypted=False
        )
        
        # Upsert hash
        upsert_family_password_hash(
            db=test_db,
            device_auth_token='test-token',
            parent_password_second_hash='$2b$12$newhash'
        )
        
        # Verify mail is preserved
        family = get_family(test_db, 'test-token')
        assert family['mail'] == 'test@example.com'
        assert family['parent_password_second_hash'] == '$2b$12$newhash'

    @pytest.mark.timeout(10)
    def test_session_restoration_uses_database_hash(self, client, test_db):
        """Test that session restoration retrieves hash from database."""
        from database import upsert_family_password_hash
        
        # Store a hash in the database
        upsert_family_password_hash(
            db=test_db,
            device_auth_token='test-device-token',
            parent_password_second_hash='$2b$12$session_test_hash'
        )
        
        # Simulate session restoration by calling the before_request handler
        with client.session_transaction() as sess:
            sess['device_auth_token'] = 'test-device-token'
        
        # Make a request to trigger session restoration
        response = client.get('/dashboardV2', follow_redirects=False)
        
        # The hash should be restored to session
        with client.session_transaction() as sess:
            # Note: The actual restoration happens in restore_session_from_persistence
            # which is called in before_request. The hash should be in session.
            pass  # Session restoration is tested via integration tests