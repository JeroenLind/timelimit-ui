"""Unit tests for persistence abstraction.

This module tests the persistence module functionality including:
- FileServerSelectionStore: save and retrieve server selection
- HaIngressServerSelectionStore: HA-specific implementation
- PersistenceFactory: environment detection and store selection
- Atomic writes and thread safety
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
    set_current_server_url
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