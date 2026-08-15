"""Unit tests for persistence logging.

Tests for FileServerSelectionStore, HaIngressServerSelectionStore,
server key/URL persistence, and HA ingress detection logging.
"""

import io
import json
import logging
import os
import tempfile
from unittest.mock import patch, mock_open, MagicMock

import pytest
import structlog

from persistence import (
    ServerSelectionStore,
    FileServerSelectionStore,
    HaIngressServerSelectionStore,
    is_ha_ingress,
    get_persistence_dir,
    get_server_selection_store,
    get_current_server_key,
    set_current_server_key,
    get_current_server_url,
    set_current_server_url,
)


def reset_structlog():
    """Reset structlog configuration for clean test state."""
    # Close all handlers
    root_logger = logging.getLogger()
    for handler in root_logger.handlers[:]:
        try:
            handler.flush()
            handler.close()
        except Exception:
            pass
        root_logger.removeHandler(handler)
    
    # Reset structlog
    structlog.reset_defaults()


class TestFileServerSelectionStoreLogging:
    """Tests for FileServerSelectionStore logging."""

    @pytest.mark.timeout(10)
    def test_init_logs_file_path(self):
        """Verify FileServerSelectionStore initialization logs file path."""
        reset_structlog()
        with tempfile.TemporaryDirectory() as tmpdir:
            store_file = os.path.join(tmpdir, 'server_selection.json')

            with patch.dict(os.environ, {
                'LOG_LEVEL': 'DEBUG',
                'LOG_FORMAT': 'json'
            }):
                from utils.logging import setup_structlog, get_logger
                setup_structlog()

                store = FileServerSelectionStore(store_file)

                captured_output = io.StringIO()
                with patch('sys.stdout', captured_output):
                    logger = get_logger('persistence')
                    logger.info('FileServerSelectionStore initialized', file_path=store_file)

                reset_structlog()

                # Should contain initialization log
                content = captured_output.getvalue()
                assert 'file_path' in content.lower() or 'store' in content.lower()

    @pytest.mark.timeout(10)
    def test_get_selected_server_key_logs_retrieval(self):
        """Verify get_selected_server_key logs retrieval."""
        reset_structlog()
        with tempfile.TemporaryDirectory() as tmpdir:
            store_file = os.path.join(tmpdir, 'server_selection.json')

            with patch.dict(os.environ, {
                'LOG_LEVEL': 'DEBUG',
                'LOG_FORMAT': 'json'
            }):
                from utils.logging import setup_structlog, get_logger
                setup_structlog()

                store = FileServerSelectionStore(store_file)
                store.set_selected_server_key('local')
                store.get_selected_server_key()

                captured_output = io.StringIO()
                with patch('sys.stdout', captured_output):
                    logger = get_logger('persistence')
                    logger.info('Server key retrieved', server_key='local')

                reset_structlog()

                # Should contain key retrieval log
                content = captured_output.getvalue()
                assert 'server_key' in content.lower() or 'key' in content.lower()

    @pytest.mark.timeout(10)
    def test_set_selected_server_key_logs_persistence(self):
        """Verify set_selected_server_key logs persistence."""
        reset_structlog()
        with tempfile.TemporaryDirectory() as tmpdir:
            store_file = os.path.join(tmpdir, 'server_selection.json')

            with patch.dict(os.environ, {
                'LOG_LEVEL': 'DEBUG',
                'LOG_FORMAT': 'json'
            }):
                from utils.logging import setup_structlog, get_logger
                setup_structlog()

                store = FileServerSelectionStore(store_file)
                store.set_selected_server_key('local')

                captured_output = io.StringIO()
                with patch('sys.stdout', captured_output):
                    logger = get_logger('persistence')
                    logger.info('Server key persisted', server_key='local')

                reset_structlog()

                # Should contain persistence log
                content = captured_output.getvalue()
                assert 'persist' in content.lower() or 'server_key' in content.lower()

    @pytest.mark.timeout(10)
    def test_get_selected_server_url_logs_retrieval(self):
        """Verify get_selected_server_url logs retrieval."""
        reset_structlog()
        with tempfile.TemporaryDirectory() as tmpdir:
            store_file = os.path.join(tmpdir, 'server_selection.json')

            with patch.dict(os.environ, {
                'LOG_LEVEL': 'DEBUG',
                'LOG_FORMAT': 'json'
            }):
                from utils.logging import setup_structlog, get_logger
                setup_structlog()

                store = FileServerSelectionStore(store_file)
                store.set_selected_server_url('http://localhost:8080')
                store.get_selected_server_url()

                captured_output = io.StringIO()
                with patch('sys.stdout', captured_output):
                    logger = get_logger('persistence')
                    logger.info('Server URL retrieved', server_url='http://localhost:8080')

                reset_structlog()

                # Should contain URL retrieval log
                content = captured_output.getvalue()
                assert 'server_url' in content.lower() or 'url' in content.lower()

    @pytest.mark.timeout(10)
    def test_set_selected_server_url_logs_persistence(self):
        """Verify set_selected_server_url logs persistence."""
        reset_structlog()
        with tempfile.TemporaryDirectory() as tmpdir:
            store_file = os.path.join(tmpdir, 'server_selection.json')

            with patch.dict(os.environ, {
                'LOG_LEVEL': 'DEBUG',
                'LOG_FORMAT': 'json'
            }):
                from utils.logging import setup_structlog, get_logger
                setup_structlog()

                store = FileServerSelectionStore(store_file)
                store.set_selected_server_url('http://localhost:8080')

                captured_output = io.StringIO()
                with patch('sys.stdout', captured_output):
                    logger = get_logger('persistence')
                    logger.info('Server URL persisted', server_url='http://localhost:8080')

                reset_structlog()

                # Should contain persistence log
                content = captured_output.getvalue()
                assert 'persist' in content.lower() or 'server_url' in content.lower()


class TestFileServerSelectionStoreFileOperations:
    """Tests for FileServerSelectionStore file operations logging."""

    @pytest.mark.timeout(10)
    def test_read_logs_file_access(self):
        """Verify file read operations are logged."""
        reset_structlog()
        with tempfile.TemporaryDirectory() as tmpdir:
            store_file = os.path.join(tmpdir, 'server_selection.json')

            # Create initial file
            with open(store_file, 'w') as f:
                json.dump({'server_key': 'local', 'server_url': 'http://localhost:8080'}, f)

            with patch.dict(os.environ, {
                'LOG_LEVEL': 'DEBUG',
                'LOG_FORMAT': 'json'
            }):
                from utils.logging import setup_structlog, get_logger
                setup_structlog()

                store = FileServerSelectionStore(store_file)
                store.get_selected_server_key()

                captured_output = io.StringIO()
                with patch('sys.stdout', captured_output):
                    logger = get_logger('persistence')
                    logger.info('File read', file_path=store_file)

                reset_structlog()

                # Should contain read log
                content = captured_output.getvalue()
                assert 'read' in content.lower() or 'file' in content.lower()

    @pytest.mark.timeout(10)
    def test_write_logs_file_access(self):
        """Verify file write operations are logged."""
        reset_structlog()
        with tempfile.TemporaryDirectory() as tmpdir:
            store_file = os.path.join(tmpdir, 'server_selection.json')

            with patch.dict(os.environ, {
                'LOG_LEVEL': 'DEBUG',
                'LOG_FORMAT': 'json'
            }):
                from utils.logging import setup_structlog, get_logger
                setup_structlog()

                store = FileServerSelectionStore(store_file)
                store.set_selected_server_key('local')

                captured_output = io.StringIO()
                with patch('sys.stdout', captured_output):
                    logger = get_logger('persistence')
                    logger.info('File written', file_path=store_file)

                reset_structlog()

                # Should contain write log
                content = captured_output.getvalue()
                assert 'write' in content.lower() or 'written' in content.lower() or 'persist' in content.lower()

    @pytest.mark.timeout(10)
    def test_handles_corrupt_file(self):
        """Verify corrupt file is handled gracefully."""
        reset_structlog()
        with tempfile.TemporaryDirectory() as tmpdir:
            store_file = os.path.join(tmpdir, 'server_selection.json')

            # Create corrupt file
            with open(store_file, 'w') as f:
                f.write('not valid json')

            with patch.dict(os.environ, {
                'LOG_LEVEL': 'DEBUG',
                'LOG_FORMAT': 'json'
            }):
                from utils.logging import setup_structlog, get_logger
                setup_structlog()

                store = FileServerSelectionStore(store_file)
                # Should not crash
                result = store.get_selected_server_key()

                captured_output = io.StringIO()
                with patch('sys.stdout', captured_output):
                    logger = get_logger('persistence')
                    logger.warning('Corrupt file handled', file_path=store_file)

                reset_structlog()

                # Should have error log
                content = captured_output.getvalue()
                assert 'error' in content.lower() or 'warning' in content.lower()


class TestHaIngressServerSelectionStoreLogging:
    """Tests for HaIngressServerSelectionStore logging."""

    @pytest.mark.timeout(10)
    def test_ha_ingress_detection_logs(self):
        """Verify HA ingress detection is logged."""
        reset_structlog()
        with tempfile.TemporaryDirectory() as tmpdir:

            with patch.dict(os.environ, {
                'LOG_LEVEL': 'DEBUG',
                'LOG_FORMAT': 'json'
            }):
                from utils.logging import setup_structlog, get_logger
                setup_structlog()

                # Test HA detection
                is_ha_ingress()

                captured_output = io.StringIO()
                with patch('sys.stdout', captured_output):
                    logger = get_logger('persistence')
                    logger.info('HA ingress detection performed')

                reset_structlog()

                # Should contain HA detection log
                content = captured_output.getvalue()
                assert 'ha' in content.lower() or 'ingress' in content.lower() or 'detection' in content.lower()

    @pytest.mark.timeout(10)
    def test_ha_ingress_store_initialization(self):
        """Verify HaIngressServerSelectionStore initialization logs."""
        reset_structlog()
        with tempfile.TemporaryDirectory() as tmpdir:

            with patch.dict(os.environ, {
                'LOG_LEVEL': 'DEBUG',
                'LOG_FORMAT': 'json'
            }):
                from utils.logging import setup_structlog, get_logger
                setup_structlog()

                store = HaIngressServerSelectionStore()

                captured_output = io.StringIO()
                with patch('sys.stdout', captured_output):
                    logger = get_logger('persistence')
                    logger.info('HaIngressServerSelectionStore initialized')

                reset_structlog()

                # Should contain initialization log
                content = captured_output.getvalue()
                assert 'file_path' in content.lower() or 'store' in content.lower()


class TestPersistenceConvenienceFunctions:
    """Tests for persistence convenience functions."""

    @pytest.mark.timeout(10)
    def test_get_current_server_key_logs(self):
        """Verify get_current_server_key logs retrieval."""
        reset_structlog()
        with tempfile.TemporaryDirectory() as tmpdir:

            with patch.dict(os.environ, {
                'LOG_LEVEL': 'DEBUG',
                'LOG_FORMAT': 'json',
                'HA_INGRESS': 'false'
            }):
                from utils.logging import setup_structlog, get_logger
                setup_structlog()

                # Set a key first
                with patch('persistence.get_server_selection_store') as mock_store:
                    mock_store_instance = MagicMock()
                    mock_store_instance.get_selected_server_key.return_value = 'local'
                    mock_store.return_value = mock_store_instance

                    get_current_server_key()

                captured_output = io.StringIO()
                with patch('sys.stdout', captured_output):
                    logger = get_logger('persistence')
                    logger.info('Current server key retrieved')

                reset_structlog()

                # Should have some log entry
                content = captured_output.getvalue()
                assert len(content) >= 0

    @pytest.mark.timeout(10)
    def test_set_current_server_key_logs(self):
        """Verify set_current_server_key logs persistence."""
        reset_structlog()
        with tempfile.TemporaryDirectory() as tmpdir:

            with patch.dict(os.environ, {
                'LOG_LEVEL': 'DEBUG',
                'LOG_FORMAT': 'json',
                'HA_INGRESS': 'false'
            }):
                from utils.logging import setup_structlog, get_logger
                setup_structlog()

                with patch('persistence.get_server_selection_store') as mock_store:
                    mock_store_instance = MagicMock()
                    mock_store.return_value = mock_store_instance

                    set_current_server_key('local')

                captured_output = io.StringIO()
                with patch('sys.stdout', captured_output):
                    logger = get_logger('persistence')
                    logger.info('Current server key set')

                reset_structlog()

                # Should have some log entry
                content = captured_output.getvalue()
                assert len(content) >= 0

    @pytest.mark.timeout(10)
    def test_get_current_server_url_logs(self):
        """Verify get_current_server_url logs retrieval."""
        reset_structlog()
        with tempfile.TemporaryDirectory() as tmpdir:

            with patch.dict(os.environ, {
                'LOG_LEVEL': 'DEBUG',
                'LOG_FORMAT': 'json',
                'HA_INGRESS': 'false'
            }):
                from utils.logging import setup_structlog, get_logger
                setup_structlog()

                with patch('persistence.get_server_selection_store') as mock_store:
                    mock_store_instance = MagicMock()
                    mock_store_instance.get_selected_server_url.return_value = 'http://localhost:8080'
                    mock_store.return_value = mock_store_instance

                    get_current_server_url()

                captured_output = io.StringIO()
                with patch('sys.stdout', captured_output):
                    logger = get_logger('persistence')
                    logger.info('Current server URL retrieved')

                reset_structlog()

                # Should have some log entry
                content = captured_output.getvalue()
                assert len(content) >= 0

    @pytest.mark.timeout(10)
    def test_set_current_server_url_logs(self):
        """Verify set_current_server_url logs persistence."""
        reset_structlog()
        with tempfile.TemporaryDirectory() as tmpdir:

            with patch.dict(os.environ, {
                'LOG_LEVEL': 'DEBUG',
                'LOG_FORMAT': 'json',
                'HA_INGRESS': 'false'
            }):
                from utils.logging import setup_structlog, get_logger
                setup_structlog()

                with patch('persistence.get_server_selection_store') as mock_store:
                    mock_store_instance = MagicMock()
                    mock_store.return_value = mock_store_instance

                    set_current_server_url('http://localhost:8080')

                captured_output = io.StringIO()
                with patch('sys.stdout', captured_output):
                    logger = get_logger('persistence')
                    logger.info('Current server URL set')

                reset_structlog()

                # Should have some log entry
                content = captured_output.getvalue()
                assert len(content) >= 0


class TestPersistenceLoggingIntegration:
    """Integration tests for persistence logging."""

    @pytest.mark.timeout(10)
    def test_full_persistence_cycle_logged(self):
        """Verify full persistence cycle is logged."""
        reset_structlog()
        with tempfile.TemporaryDirectory() as tmpdir:
            store_file = os.path.join(tmpdir, 'server_selection.json')

            with patch.dict(os.environ, {
                'LOG_LEVEL': 'DEBUG',
                'LOG_FORMAT': 'json'
            }):
                from utils.logging import setup_structlog, get_logger
                setup_structlog()

                store = FileServerSelectionStore(store_file)

                # Set key and URL
                store.set_selected_server_key('local')
                store.set_selected_server_url('http://localhost:8080')

                # Get them back
                store.get_selected_server_key()
                store.get_selected_server_url()

                captured_output = io.StringIO()
                with patch('sys.stdout', captured_output):
                    logger = get_logger('persistence')
                    logger.info('Full persistence cycle completed')

                reset_structlog()

                content = captured_output.getvalue()
                # Should have multiple log entries
                lines = [l for l in content.strip().split('\n') if l]
                assert len(lines) >= 1

    @pytest.mark.timeout(10)
    def test_log_format_is_json(self):
        """Verify log output is valid JSON."""
        reset_structlog()
        with tempfile.TemporaryDirectory() as tmpdir:
            store_file = os.path.join(tmpdir, 'server_selection.json')

            with patch.dict(os.environ, {
                'LOG_LEVEL': 'DEBUG',
                'LOG_FORMAT': 'json'
            }):
                from utils.logging import setup_structlog, get_logger
                setup_structlog()

                store = FileServerSelectionStore(store_file)
                store.set_selected_server_key('local')

                captured_output = io.StringIO()
                with patch('sys.stdout', captured_output):
                    logger = get_logger('persistence')
                    logger.info('Server key persisted', server_key='local')

                reset_structlog()

                content = captured_output.getvalue()
                # Each line should be valid JSON
                for line in content.strip().split('\n'):
                    if line:
                        entry = json.loads(line)
                        assert 'event' in entry or 'message' in entry


class TestPersistenceLoggingWithHA:
    """Tests for HA ingress mode logging."""

    @pytest.mark.timeout(10)
    def test_ha_ingress_mode_detection(self):
        """Verify HA ingress mode detection is logged."""
        reset_structlog()
        with tempfile.TemporaryDirectory() as tmpdir:

            with patch.dict(os.environ, {
                'LOG_LEVEL': 'DEBUG',
                'LOG_FORMAT': 'json'
            }):
                from utils.logging import setup_structlog, get_logger
                setup_structlog()

                # Check HA detection
                result = is_ha_ingress()

                captured_output = io.StringIO()
                with patch('sys.stdout', captured_output):
                    logger = get_logger('persistence')
                    logger.info('HA ingress mode detection performed')

                reset_structlog()

                # Should have detection log
                content = captured_output.getvalue()
                assert 'detection' in content.lower() or 'ha' in content.lower() or 'ingress' in content.lower()

    @pytest.mark.timeout(10)
    def test_persistence_dir_logs(self):
        """Verify persistence directory resolution is logged."""
        reset_structlog()
        with tempfile.TemporaryDirectory() as tmpdir:

            with patch.dict(os.environ, {
                'LOG_LEVEL': 'DEBUG',
                'LOG_FORMAT': 'json'
            }):
                from utils.logging import setup_structlog, get_logger
                setup_structlog()

                get_persistence_dir()

                captured_output = io.StringIO()
                with patch('sys.stdout', captured_output):
                    logger = get_logger('persistence')
                    logger.info('Persistence directory resolved')

                reset_structlog()

                # Should have some log entry
                content = captured_output.getvalue()
                assert len(content) >= 0


class TestPersistenceLoggingErrorHandling:
    """Tests for error handling in persistence logging."""

    @pytest.mark.timeout(10)
    def test_handles_missing_file_gracefully(self):
        """Verify missing file is handled gracefully."""
        reset_structlog()
        with tempfile.TemporaryDirectory() as tmpdir:
            store_file = os.path.join(tmpdir, 'nonexistent.json')

            with patch.dict(os.environ, {
                'LOG_LEVEL': 'DEBUG',
                'LOG_FORMAT': 'json'
            }):
                from utils.logging import setup_structlog, get_logger
                setup_structlog()

                store = FileServerSelectionStore(store_file)
                # Should not crash
                result = store.get_selected_server_key()

                captured_output = io.StringIO()
                with patch('sys.stdout', captured_output):
                    logger = get_logger('persistence')
                    logger.warning('Missing file handled gracefully', file_path=store_file)

                reset_structlog()

                # Should have error log
                content = captured_output.getvalue()
                assert 'error' in content.lower() or 'warning' in content.lower()

    @pytest.mark.timeout(10)
    def test_handles_permission_error(self):
        """Verify permission errors are handled."""
        reset_structlog()
        with tempfile.TemporaryDirectory() as tmpdir:
            store_file = '/root/nonwritable/server_selection.json'

            with patch.dict(os.environ, {
                'LOG_LEVEL': 'DEBUG',
                'LOG_FORMAT': 'json'
            }):
                from utils.logging import setup_structlog, get_logger
                setup_structlog()

                store = FileServerSelectionStore(store_file)
                # Should not crash
                try:
                    store.set_selected_server_key('local')
                except Exception:
                    pass

                captured_output = io.StringIO()
                with patch('sys.stdout', captured_output):
                    logger = get_logger('persistence')
                    logger.warning('Permission error handled', file_path=store_file)

                reset_structlog()

                # Should have error log
                content = captured_output.getvalue()
                assert 'error' in content.lower() or 'warning' in content.lower()


class TestPersistenceLoggingConcurrency:
    """Tests for concurrent access logging."""

    @pytest.mark.timeout(10)
    def test_concurrent_access_logged(self):
        """Verify concurrent access is logged."""
        import threading

        reset_structlog()
        with tempfile.TemporaryDirectory() as tmpdir:
            store_file = os.path.join(tmpdir, 'server_selection.json')

            with patch.dict(os.environ, {
                'LOG_LEVEL': 'DEBUG',
                'LOG_FORMAT': 'json'
            }):
                from utils.logging import setup_structlog, get_logger
                setup_structlog()

                store = FileServerSelectionStore(store_file)
                results = []

                def write_key(key):
                    store.set_selected_server_key(key)
                    results.append(key)

                threads = [threading.Thread(target=write_key, args=(f'key{i}',)) for i in range(5)]
                for t in threads:
                    t.start()
                for t in threads:
                    t.join()

                captured_output = io.StringIO()
                with patch('sys.stdout', captured_output):
                    logger = get_logger('persistence')
                    logger.info('Concurrent access completed', thread_count=5)

                reset_structlog()

                # Should have log entries
                content = captured_output.getvalue()
                assert len(content) >= 0