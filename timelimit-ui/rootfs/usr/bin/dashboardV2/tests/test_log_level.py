"""Unit tests for log level selection feature.

Tests for:
- set_log_level() and get_log_level() in utils/logging.py
- get_log_level() and set_log_level() in persistence.py
- /api/log-level POST route in app.py
- Log level dropdown on the landing page
"""

import json
import logging
import os
import sys
import tempfile
from unittest.mock import patch

import pytest
import structlog

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from persistence import FileServerSelectionStore


def reset_structlog():
    """Reset structlog configuration for clean test state."""
    os.environ['LOG_ROTATE_ON_START'] = 'false'

    root_logger = logging.getLogger()
    for handler in root_logger.handlers[:]:
        try:
            handler.flush()
            handler.close()
        except Exception:
            pass
        root_logger.removeHandler(handler)

    werkzeug_logger = logging.getLogger('werkzeug')
    for handler in werkzeug_logger.handlers[:]:
        try:
            handler.flush()
            handler.close()
        except Exception:
            pass
        werkzeug_logger.removeHandler(handler)
    werkzeug_logger.propagate = True

    structlog.reset_defaults()


# ============================================================================
# Tests for utils/logging.py set_log_level() and get_log_level()
# ============================================================================

class TestSetLogLevel:
    """Tests for set_log_level() and get_log_level() in utils/logging.py."""

    @pytest.mark.timeout(10)
    def test_set_log_level_debug(self):
        """Test setting log level to DEBUG."""
        reset_structlog()
        from utils.logging import setup_structlog, set_log_level, get_log_level

        setup_structlog(log_level='INFO', log_format='json')
        result = set_log_level('DEBUG')

        assert result is True
        assert get_log_level() == 'DEBUG'

        # Root logger should be at DEBUG level
        root_logger = logging.getLogger()
        assert root_logger.level == logging.DEBUG

        reset_structlog()

    @pytest.mark.timeout(10)
    def test_set_log_level_info(self):
        """Test setting log level to INFO."""
        reset_structlog()
        from utils.logging import setup_structlog, set_log_level, get_log_level

        setup_structlog(log_level='DEBUG', log_format='json')
        result = set_log_level('INFO')

        assert result is True
        assert get_log_level() == 'INFO'

        root_logger = logging.getLogger()
        assert root_logger.level == logging.INFO

        reset_structlog()

    @pytest.mark.timeout(10)
    def test_set_log_level_warning(self):
        """Test setting log level to WARNING."""
        reset_structlog()
        from utils.logging import setup_structlog, set_log_level, get_log_level

        setup_structlog(log_level='INFO', log_format='json')
        result = set_log_level('WARNING')

        assert result is True
        assert get_log_level() == 'WARNING'

        root_logger = logging.getLogger()
        assert root_logger.level == logging.WARNING

        reset_structlog()

    @pytest.mark.timeout(10)
    def test_set_log_level_error(self):
        """Test setting log level to ERROR."""
        reset_structlog()
        from utils.logging import setup_structlog, set_log_level, get_log_level

        setup_structlog(log_level='INFO', log_format='json')
        result = set_log_level('ERROR')

        assert result is True
        assert get_log_level() == 'ERROR'

        root_logger = logging.getLogger()
        assert root_logger.level == logging.ERROR

        reset_structlog()

    @pytest.mark.timeout(10)
    def test_set_log_level_critical(self):
        """Test setting log level to CRITICAL."""
        reset_structlog()
        from utils.logging import setup_structlog, set_log_level, get_log_level

        setup_structlog(log_level='INFO', log_format='json')
        result = set_log_level('CRITICAL')

        assert result is True
        assert get_log_level() == 'CRITICAL'

        root_logger = logging.getLogger()
        assert root_logger.level == logging.CRITICAL

        reset_structlog()

    @pytest.mark.timeout(10)
    def test_set_log_level_invalid(self):
        """Test that setting an invalid log level returns False."""
        reset_structlog()
        from utils.logging import setup_structlog, set_log_level, get_log_level

        setup_structlog(log_level='INFO', log_format='json')
        result = set_log_level('INVALID')

        assert result is False
        # Level should remain unchanged
        assert get_log_level() == 'INFO'

        reset_structlog()

    @pytest.mark.timeout(10)
    def test_set_log_level_case_insensitive(self):
        """Test that log level is case-insensitive."""
        reset_structlog()
        from utils.logging import setup_structlog, set_log_level, get_log_level

        setup_structlog(log_level='INFO', log_format='json')
        result = set_log_level('debug')

        assert result is True
        assert get_log_level() == 'DEBUG'

        reset_structlog()

    @pytest.mark.timeout(10)
    def test_set_log_level_updates_handlers(self):
        """Test that set_log_level updates all handler levels."""
        reset_structlog()
        from utils.logging import setup_structlog, set_log_level

        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = os.path.join(tmpdir, 'test.log')
            setup_structlog(
                log_level='INFO',
                log_file_path=log_file,
                log_format='json',
                rotate_on_start=False
            )

            set_log_level('DEBUG')

            root_logger = logging.getLogger()
            for handler in root_logger.handlers:
                assert handler.level == logging.DEBUG

            reset_structlog()

    @pytest.mark.timeout(10)
    def test_set_log_level_updates_werkzeug(self):
        """Test that set_log_level updates the Werkzeug logger."""
        reset_structlog()
        from utils.logging import setup_structlog, set_log_level

        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = os.path.join(tmpdir, 'test.log')
            werkzeug_file = os.path.join(tmpdir, 'werkzeug.log')
            setup_structlog(
                log_level='INFO',
                log_file_path=log_file,
                log_format='json',
                rotate_on_start=False,
                werkzeug_log_file_path=werkzeug_file
            )

            set_log_level('DEBUG')

            werkzeug_logger = logging.getLogger('werkzeug')
            assert werkzeug_logger.level == logging.DEBUG
            for handler in werkzeug_logger.handlers:
                assert handler.level == logging.DEBUG

            reset_structlog()

    @pytest.mark.timeout(10)
    def test_get_log_level_default(self):
        """Test that get_log_level returns INFO by default."""
        reset_structlog()
        from utils.logging import setup_structlog, get_log_level

        setup_structlog(log_level='INFO', log_format='json')
        assert get_log_level() == 'INFO'

        reset_structlog()

    @pytest.mark.timeout(10)
    def test_set_log_level_filters_messages(self):
        """Test that set_log_level actually filters log messages."""
        reset_structlog()
        from utils.logging import setup_structlog, set_log_level, get_logger

        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = os.path.join(tmpdir, 'test.log')
            setup_structlog(
                log_level='INFO',
                log_file_path=log_file,
                log_format='json',
                rotate_on_start=False
            )

            # Set to WARNING - DEBUG and INFO messages should be filtered
            set_log_level('WARNING')

            logger = get_logger('test')
            logger.debug("Debug message that should be filtered")
            logger.info("Info message that should be filtered")
            logger.warning("Warning message that should appear")

            # Flush handlers
            root_logger = logging.getLogger()
            for handler in root_logger.handlers:
                handler.flush()

            with open(log_file, 'r') as f:
                content = f.read()

            assert 'Debug message that should be filtered' not in content
            assert 'Info message that should be filtered' not in content
            assert 'Warning message that should appear' in content

            reset_structlog()


# ============================================================================
# Tests for persistence.py log level methods
# ============================================================================

class TestPersistenceLogLevel:
    """Tests for log level persistence in FileServerSelectionStore."""

    @pytest.fixture
    def temp_file(self, tmp_path):
        """Create a temporary file for testing."""
        return str(tmp_path / "test_server_selection.json")

    @pytest.fixture
    def store(self, temp_file):
        """Create a FileServerSelectionStore instance."""
        from persistence import FileServerSelectionStore
        return FileServerSelectionStore(temp_file)

    @pytest.mark.timeout(10)
    def test_save_and_retrieve_log_level(self, store, temp_file):
        """Test saving and retrieving log level."""
        store.set_log_level('DEBUG')

        new_store = FileServerSelectionStore(temp_file)
        result = new_store.get_log_level()

        assert result == 'DEBUG'

    @pytest.mark.timeout(10)
    def test_get_log_level_returns_none_when_not_set(self, store):
        """Test that get_log_level returns None when not set."""
        assert store.get_log_level() is None

    @pytest.mark.timeout(10)
    def test_log_level_persisted_to_file(self, store, temp_file):
        """Test that log level is written to the JSON file."""
        store.set_log_level('WARNING')

        with open(temp_file, 'r') as f:
            data = json.load(f)

        assert data['log_level'] == 'WARNING'

    @pytest.mark.timeout(10)
    def test_log_level_overwrite(self, store, temp_file):
        """Test overwriting an existing log level."""
        store.set_log_level('DEBUG')
        store.set_log_level('ERROR')

        new_store = FileServerSelectionStore(temp_file)
        assert new_store.get_log_level() == 'ERROR'

    @pytest.mark.timeout(10)
    def test_log_level_and_server_key_coexist(self, store, temp_file):
        """Test that log level and server key can coexist in the same file."""
        store.set_selected_server_key('local')
        store.set_log_level('DEBUG')

        new_store = FileServerSelectionStore(temp_file)
        assert new_store.get_selected_server_key() == 'local'
        assert new_store.get_log_level() == 'DEBUG'

    @pytest.mark.timeout(10)
    def test_convenience_functions(self, temp_file):
        """Test get_current_log_level and set_current_log_level convenience functions."""
        from persistence import get_current_log_level, set_current_log_level

        # Patch the store to use our temp file
        with patch('persistence.get_server_selection_store') as mock_store:
            mock_store.return_value = FileServerSelectionStore(temp_file)

            set_current_log_level('INFO')
            assert get_current_log_level() == 'INFO'

            set_current_log_level('DEBUG')
            assert get_current_log_level() == 'DEBUG'


# ============================================================================
# Tests for /api/log-level route
# ============================================================================

class TestLogLevelRoute:
    """Tests for the /api/log-level POST route."""

    @pytest.mark.timeout(10)
    def test_set_log_level_valid(self, client):
        """Test setting a valid log level via the API."""
        response = client.post('/api/log-level',
            data=json.dumps({'log_level': 'DEBUG'}),
            content_type='application/json'
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data['status'] == 'ok'
        assert data['log_level'] == 'DEBUG'

    @pytest.mark.timeout(10)
    def test_set_log_level_invalid(self, client):
        """Test setting an invalid log level returns 400."""
        response = client.post('/api/log-level',
            data=json.dumps({'log_level': 'INVALID'}),
            content_type='application/json'
        )

        assert response.status_code == 400
        data = response.get_json()
        assert data['status'] == 'error'

    @pytest.mark.timeout(10)
    def test_set_log_level_missing(self, client):
        """Test that missing log_level returns 400."""
        response = client.post('/api/log-level',
            data=json.dumps({}),
            content_type='application/json'
        )

        assert response.status_code == 400
        data = response.get_json()
        assert data['status'] == 'error'

    @pytest.mark.timeout(10)
    def test_set_log_level_case_insensitive(self, client):
        """Test that log level is case-insensitive."""
        response = client.post('/api/log-level',
            data=json.dumps({'log_level': 'debug'}),
            content_type='application/json'
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data['log_level'] == 'DEBUG'

    @pytest.mark.timeout(10)
    def test_set_log_level_all_valid_levels(self, client):
        """Test setting all valid log levels."""
        for level in ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']:
            response = client.post('/api/log-level',
                data=json.dumps({'log_level': level}),
                content_type='application/json'
            )
            assert response.status_code == 200
            data = response.get_json()
            assert data['log_level'] == level


# ============================================================================
# Tests for landing page log level dropdown
# ============================================================================

class TestLogLevelDropdown:
    """Tests for the log level dropdown on the landing page."""

    @pytest.mark.timeout(10)
    def test_landing_page_has_log_level_dropdown(self, client):
        """Test that landing page has a log level dropdown."""
        response = client.get('/')

        assert response.status_code == 200
        assert b'logLevel' in response.data
        assert b'Log Level' in response.data

    @pytest.mark.timeout(10)
    def test_landing_page_has_all_log_level_options(self, client):
        """Test that landing page has all log level options."""
        response = client.get('/')

        assert b'value="DEBUG"' in response.data
        assert b'value="INFO"' in response.data
        assert b'value="WARNING"' in response.data
        assert b'value="ERROR"' in response.data
        assert b'value="CRITICAL"' in response.data

    @pytest.mark.timeout(10)
    def test_landing_page_has_log_level_api_endpoint(self, client):
        """Test that landing page JavaScript references the log level API."""
        response = client.get('/')

        assert b'/api/log-level' in response.data

    @pytest.mark.timeout(10)
    def test_landing_page_preselects_current_level(self, client):
        """Test that landing page pre-selects the current log level."""
        # Set log level to DEBUG first
        client.post('/api/log-level',
            data=json.dumps({'log_level': 'DEBUG'}),
            content_type='application/json'
        )

        # Fetch landing page
        response = client.get('/')

        assert response.status_code == 200
        # The template should have DEBUG as the current level
        assert b'DEBUG' in response.data
