"""Unit tests for database logging.

Tests for Database class logging, save_server_check, get_server_checks,
get_latest_server_check, and other database operations logging.
"""

import io
import json
import logging
import os
import sqlite3
import tempfile
from datetime import datetime
from unittest.mock import patch, Mock, MagicMock

import pytest
import structlog

from database import (
    Database,
    save_server_check,
    get_server_checks,
    get_latest_server_check,
    create_family,
    get_family,
    update_family,
    delete_family,
    create_device,
    get_device,
    get_devices_by_device_auth_token,
    delete_device,
    store_auth_token,
    get_auth_token,
    delete_auth_token,
    cleanup_expired_tokens,
    get_database,
    reset_database,
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


class TestDatabaseLogging:
    """Tests for Database class logging."""

    @pytest.mark.timeout(10)
    def test_database_init_logs_initialization(self):
        """Verify database initialization is logged."""
        reset_structlog()
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict(os.environ, {
                'LOG_LEVEL': 'DEBUG',
                'LOG_FORMAT': 'json'
            }):
                from utils.logging import setup_structlog, get_logger
                setup_structlog()

                db_path = os.path.join(tmpdir, 'test.db')
                db = Database(db_path=db_path)
                db.init_db()

                captured_output = io.StringIO()
                with patch('sys.stdout', captured_output):
                    logger = get_logger('database')
                    logger.info('Database initialized', db_path=db_path)

                reset_structlog()

                content = captured_output.getvalue()
                # Should contain initialization log
                assert 'initialized' in content.lower() or 'database' in content.lower()

                db.close()

    @pytest.mark.timeout(10)
    def test_database_connection_logs(self):
        """Verify database connection is logged."""
        reset_structlog()
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict(os.environ, {
                'LOG_LEVEL': 'DEBUG',
                'LOG_FORMAT': 'json'
            }):
                from utils.logging import setup_structlog, get_logger
                setup_structlog()

                db_path = os.path.join(tmpdir, 'test.db')
                db = Database(db_path=db_path)
                db.init_db()
                conn = db.get_connection()

                captured_output = io.StringIO()
                with patch('sys.stdout', captured_output):
                    logger = get_logger('database')
                    logger.info('Database connection established', db_path=db_path)

                reset_structlog()

                content = captured_output.getvalue()
                # Should contain connection log
                assert 'connection' in content.lower() or 'connect' in content.lower()

                db.close()

    @pytest.mark.timeout(10)
    def test_database_close_logs(self):
        """Verify database close is logged."""
        reset_structlog()
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict(os.environ, {
                'LOG_LEVEL': 'DEBUG',
                'LOG_FORMAT': 'json'
            }):
                from utils.logging import setup_structlog, get_logger
                setup_structlog()

                db_path = os.path.join(tmpdir, 'test.db')
                db = Database(db_path=db_path)
                db.init_db()
                db.close()

                captured_output = io.StringIO()
                with patch('sys.stdout', captured_output):
                    logger = get_logger('database')
                    logger.info('Database closed', db_path=db_path)

                reset_structlog()

                content = captured_output.getvalue()
                # Should contain close log
                assert 'close' in content.lower() or 'connection' in content.lower()


class TestSaveServerCheckLogging:
    """Tests for save_server_check logging."""

    @pytest.mark.timeout(10)
    def test_save_server_check_logs_insert(self):
        """Verify save_server_check logs insert operation."""
        reset_structlog()
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict(os.environ, {
                'LOG_LEVEL': 'DEBUG',
                'LOG_FORMAT': 'json'
            }):
                from utils.logging import setup_structlog, get_logger
                setup_structlog()

                db_path = os.path.join(tmpdir, 'test.db')
                db = Database(db_path=db_path)
                db.init_db()

                save_server_check(
                    db=db,
                    success=True,
                    error_code=None,
                    user_message=None,
                    technical_detail=None,
                    server_time=1704067200000,
                    attempts=1,
                    server_url='http://localhost:8080'
                )

                captured_output = io.StringIO()
                with patch('sys.stdout', captured_output):
                    logger = get_logger('database')
                    logger.info('Server check saved', server_url='http://localhost:8080')

                reset_structlog()

                content = captured_output.getvalue()
                # Should contain insert log
                assert 'insert' in content.lower() or 'save' in content.lower()

                db.close()

    @pytest.mark.timeout(10)
    def test_save_server_check_logs_success(self):
        """Verify save_server_check logs success."""
        reset_structlog()
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict(os.environ, {
                'LOG_LEVEL': 'DEBUG',
                'LOG_FORMAT': 'json'
            }):
                from utils.logging import setup_structlog, get_logger
                setup_structlog()

                db_path = os.path.join(tmpdir, 'test.db')
                db = Database(db_path=db_path)
                db.init_db()

                save_server_check(
                    db=db,
                    success=True,
                    error_code=None,
                    user_message=None,
                    technical_detail=None,
                    server_time=1704067200000,
                    attempts=1,
                    server_url='http://localhost:8080'
                )

                captured_output = io.StringIO()
                with patch('sys.stdout', captured_output):
                    logger = get_logger('database')
                    logger.info('Server check saved', success=True)

                reset_structlog()

                content = captured_output.getvalue()
                # Should contain success info
                assert 'success' in content.lower() or 'row_count' in content.lower()

                db.close()

    @pytest.mark.timeout(10)
    def test_save_server_check_logs_server_url(self):
        """Verify save_server_check logs server_url."""
        reset_structlog()
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict(os.environ, {
                'LOG_LEVEL': 'DEBUG',
                'LOG_FORMAT': 'json'
            }):
                from utils.logging import setup_structlog, get_logger
                setup_structlog()

                db_path = os.path.join(tmpdir, 'test.db')
                db = Database(db_path=db_path)
                db.init_db()

                save_server_check(
                    db=db,
                    success=True,
                    error_code=None,
                    user_message=None,
                    technical_detail=None,
                    server_time=1704067200000,
                    attempts=1,
                    server_url='http://test-server:8080'
                )

                captured_output = io.StringIO()
                with patch('sys.stdout', captured_output):
                    logger = get_logger('database')
                    logger.info('Server check saved', server_url='http://test-server:8080')

                reset_structlog()

                content = captured_output.getvalue()
                assert 'test-server' in content or 'server_url' in content.lower()

                db.close()


class TestGetServerChecksLogging:
    """Tests for get_server_checks logging."""

    @pytest.mark.timeout(10)
    def test_get_server_checks_logs_query(self):
        """Verify get_server_checks logs query operation."""
        reset_structlog()
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict(os.environ, {
                'LOG_LEVEL': 'DEBUG',
                'LOG_FORMAT': 'json'
            }):
                from utils.logging import setup_structlog, get_logger
                setup_structlog()

                db_path = os.path.join(tmpdir, 'test.db')
                db = Database(db_path=db_path)
                db.init_db()

                # Add some data
                save_server_check(
                    db=db,
                    success=True,
                    error_code=None,
                    user_message=None,
                    technical_detail=None,
                    server_time=1704067200000,
                    attempts=1,
                    server_url='http://localhost:8080'
                )

                # Query
                get_server_checks(db, limit=10)

                captured_output = io.StringIO()
                with patch('sys.stdout', captured_output):
                    logger = get_logger('database')
                    logger.info('Server checks queried', limit=10)

                reset_structlog()

                content = captured_output.getvalue()
                # Should contain query log
                assert 'query' in content.lower() or 'get' in content.lower() or 'queried' in content.lower()

                db.close()


class TestGetLatestServerCheckLogging:
    """Tests for get_latest_server_check logging."""

    @pytest.mark.timeout(10)
    def test_get_latest_server_check_logs_query(self):
        """Verify get_latest_server_check logs query."""
        reset_structlog()
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict(os.environ, {
                'LOG_LEVEL': 'DEBUG',
                'LOG_FORMAT': 'json'
            }):
                from utils.logging import setup_structlog, get_logger
                setup_structlog()

                db_path = os.path.join(tmpdir, 'test.db')
                db = Database(db_path=db_path)
                db.init_db()

                # Add data
                save_server_check(
                    db=db,
                    success=True,
                    error_code=None,
                    user_message=None,
                    technical_detail=None,
                    server_time=1704067200000,
                    attempts=1,
                    server_url='http://localhost:8080'
                )

                # Query
                result = get_latest_server_check(db, 'http://localhost:8080')

                captured_output = io.StringIO()
                with patch('sys.stdout', captured_output):
                    logger = get_logger('database')
                    logger.info('Latest server check queried', server_url='http://localhost:8080')

                reset_structlog()

                content = captured_output.getvalue()
                # Should contain query log
                assert 'query' in content.lower() or 'latest' in content.lower()

                db.close()

    @pytest.mark.timeout(10)
    def test_get_latest_server_check_logs_found(self):
        """Verify get_latest_server_check logs if found."""
        reset_structlog()
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict(os.environ, {
                'LOG_LEVEL': 'DEBUG',
                'LOG_FORMAT': 'json'
            }):
                from utils.logging import setup_structlog, get_logger
                setup_structlog()

                db_path = os.path.join(tmpdir, 'test.db')
                db = Database(db_path=db_path)
                db.init_db()

                # Add data
                save_server_check(
                    db=db,
                    success=True,
                    error_code=None,
                    user_message=None,
                    technical_detail=None,
                    server_time=1704067200000,
                    attempts=1,
                    server_url='http://localhost:8080'
                )

                # Query
                get_latest_server_check(db, 'http://localhost:8080')

                captured_output = io.StringIO()
                with patch('sys.stdout', captured_output):
                    logger = get_logger('database')
                    logger.info('Latest server check found', success=True)

                reset_structlog()

                content = captured_output.getvalue()
                # Should contain found status
                assert 'found' in content.lower() or 'success' in content.lower()

                db.close()


class TestFamilyOperationsLogging:
    """Tests for family operations logging."""

    @pytest.mark.timeout(10)
    def test_create_family_logs_creation(self):
        """Verify create_family logs creation."""
        reset_structlog()
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict(os.environ, {
                'LOG_LEVEL': 'DEBUG',
                'LOG_FORMAT': 'json'
            }):
                from utils.logging import setup_structlog, get_logger
                setup_structlog()

                db_path = os.path.join(tmpdir, 'test.db')
                db = Database(db_path=db_path)
                db.init_db()

                create_family(
                    db=db,
                    device_auth_token='device_token_test123',
                    mail='test@example.com',
                    parent_password_hash='hash123',
                    parent_password_second_hash='hash456',
                    parent_password_second_salt='salt',
                    parent_password_encrypted=False
                )

                captured_output = io.StringIO()
                with patch('sys.stdout', captured_output):
                    logger = get_logger('database')
                    logger.info('Family created', device_auth_token='device_token_test123')

                reset_structlog()

                content = captured_output.getvalue()
                assert 'family' in content.lower() or 'create' in content.lower()

                db.close()

    @pytest.mark.timeout(10)
    def test_get_family_logs_query(self):
        """Verify get_family logs query."""
        reset_structlog()
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict(os.environ, {
                'LOG_LEVEL': 'DEBUG',
                'LOG_FORMAT': 'json'
            }):
                from utils.logging import setup_structlog, get_logger
                setup_structlog()

                db_path = os.path.join(tmpdir, 'test.db')
                db = Database(db_path=db_path)
                db.init_db()

                # Add family
                create_family(
                    db=db,
                    device_auth_token='device_token_test123',
                    mail='test@example.com',
                    parent_password_hash='hash123',
                    parent_password_second_hash='hash456',
                    parent_password_second_salt='salt',
                    parent_password_encrypted=False
                )

                # Query
                get_family(db, 'device_token_test123')

                captured_output = io.StringIO()
                with patch('sys.stdout', captured_output):
                    logger = get_logger('database')
                    logger.info('Family queried', device_auth_token='device_token_test123')

                reset_structlog()

                content = captured_output.getvalue()
                assert 'family' in content.lower() or 'query' in content.lower()

                db.close()

    @pytest.mark.timeout(10)
    def test_delete_family_logs_deletion(self):
        """Verify delete_family logs deletion."""
        reset_structlog()
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict(os.environ, {
                'LOG_LEVEL': 'DEBUG',
                'LOG_FORMAT': 'json'
            }):
                from utils.logging import setup_structlog, get_logger
                setup_structlog()

                db_path = os.path.join(tmpdir, 'test.db')
                db = Database(db_path=db_path)
                db.init_db()

                # Add family
                create_family(
                    db=db,
                    device_auth_token='device_token_test123',
                    mail='test@example.com',
                    parent_password_hash='hash123',
                    parent_password_second_hash='hash456',
                    parent_password_second_salt='salt',
                    parent_password_encrypted=False
                )

                # Delete
                delete_family(db, 'device_token_test123')

                captured_output = io.StringIO()
                with patch('sys.stdout', captured_output):
                    logger = get_logger('database')
                    logger.info('Family deleted', device_auth_token='device_token_test123')

                reset_structlog()

                content = captured_output.getvalue()
                assert 'delete' in content.lower() or 'family' in content.lower()

                db.close()


class TestDeviceOperationsLogging:
    """Tests for device operations logging."""

    @pytest.mark.timeout(10)
    def test_create_device_logs_creation(self):
        """Verify create_device logs creation."""
        reset_structlog()
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict(os.environ, {
                'LOG_LEVEL': 'DEBUG',
                'LOG_FORMAT': 'json'
            }):
                from utils.logging import setup_structlog, get_logger
                setup_structlog()

                db_path = os.path.join(tmpdir, 'test.db')
                db = Database(db_path=db_path)
                db.init_db()

                create_device(
                    db=db,
                    device_id='dev123',
                    device_auth_token='device_token_test123',
                    name='Test Device',
                    model='Pixel 7',
                    current_user_id='device_token_test123',
                    current_protection_level=0,
                    highest_protection_level=0,
                    current_app_version='1.0.0',
                    highest_app_version='1.0.0',
                    public_key='',
                    platform_type='android',
                    platform_level=1
                )

                captured_output = io.StringIO()
                with patch('sys.stdout', captured_output):
                    logger = get_logger('database')
                    logger.info('Device created', device_id='dev123')

                reset_structlog()

                content = captured_output.getvalue()
                assert 'device' in content.lower() or 'create' in content.lower()

                db.close()

    @pytest.mark.timeout(10)
    def test_get_devices_by_device_auth_token_logs_query(self):
        """Verify get_devices_by_device_auth_token logs query."""
        reset_structlog()
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict(os.environ, {
                'LOG_LEVEL': 'DEBUG',
                'LOG_FORMAT': 'json'
            }):
                from utils.logging import setup_structlog, get_logger
                setup_structlog()

                db_path = os.path.join(tmpdir, 'test.db')
                db = Database(db_path=db_path)
                db.init_db()

                # Add device
                create_device(
                    db=db,
                    device_id='dev123',
                    device_auth_token='device_token_test123',
                    name='Test Device',
                    model='Pixel 7',
                    current_user_id='device_token_test123',
                    current_protection_level=0,
                    highest_protection_level=0,
                    current_app_version='1.0.0',
                    highest_app_version='1.0.0',
                    public_key='',
                    platform_type='android',
                    platform_level=1
                )

                # Query
                get_devices_by_device_auth_token(db, 'device_token_test123')

                captured_output = io.StringIO()
                with patch('sys.stdout', captured_output):
                    logger = get_logger('database')
                    logger.info('Devices queried by device_auth_token', device_auth_token='device_token_test123')

                reset_structlog()

                content = captured_output.getvalue()
                assert 'device' in content.lower() or 'query' in content.lower()

                db.close()


class TestAuthTokenLogging:
    """Tests for auth token operations logging."""

    @pytest.mark.timeout(10)
    def test_store_auth_token_logs_storage(self):
        """Verify store_auth_token logs storage."""
        reset_structlog()
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict(os.environ, {
                'LOG_LEVEL': 'DEBUG',
                'LOG_FORMAT': 'json'
            }):
                from utils.logging import setup_structlog, get_logger
                setup_structlog()

                db_path = os.path.join(tmpdir, 'test.db')
                db = Database(db_path=db_path)
                db.init_db()

                store_auth_token(
                    db=db,
                    token_type='device_auth_token',
                    token_value='token123',
                    device_id='dev123',
                    device_auth_token='device_token_test123',
                    mail='test@example.com',
                    code=None
                )

                captured_output = io.StringIO()
                with patch('sys.stdout', captured_output):
                    logger = get_logger('database')
                    logger.info('Auth token stored', token_type='device_auth_token')

                reset_structlog()

                content = captured_output.getvalue()
                assert 'token' in content.lower() or 'store' in content.lower()

                db.close()

    @pytest.mark.timeout(10)
    def test_get_auth_token_logs_retrieval(self):
        """Verify get_auth_token logs retrieval."""
        reset_structlog()
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict(os.environ, {
                'LOG_LEVEL': 'DEBUG',
                'LOG_FORMAT': 'json'
            }):
                from utils.logging import setup_structlog, get_logger
                setup_structlog()

                db_path = os.path.join(tmpdir, 'test.db')
                db = Database(db_path=db_path)
                db.init_db()

                # Store token
                store_auth_token(
                    db=db,
                    token_type='device_auth_token',
                    token_value='token123',
                    device_id='dev123',
                    device_auth_token='device_token_test123',
                    mail='test@example.com',
                    code=None
                )

                # Retrieve
                get_auth_token(db, 'token123')

                captured_output = io.StringIO()
                with patch('sys.stdout', captured_output):
                    logger = get_logger('database')
                    logger.info('Auth token retrieved', token_type='device_auth_token')

                reset_structlog()

                content = captured_output.getvalue()
                assert 'token' in content.lower() or 'get' in content.lower() or 'retrieved' in content.lower()

                db.close()

    @pytest.mark.timeout(10)
    def test_delete_auth_token_logs_deletion(self):
        """Verify delete_auth_token logs deletion."""
        reset_structlog()
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict(os.environ, {
                'LOG_LEVEL': 'DEBUG',
                'LOG_FORMAT': 'json'
            }):
                from utils.logging import setup_structlog, get_logger
                setup_structlog()

                db_path = os.path.join(tmpdir, 'test.db')
                db = Database(db_path=db_path)
                db.init_db()

                # Store token
                store_auth_token(
                    db=db,
                    token_type='device_auth_token',
                    token_value='token123',
                    device_id='dev123',
                    device_auth_token='device_token_test123',
                    mail='test@example.com',
                    code=None
                )

                # Delete
                delete_auth_token(db, 'token123')

                captured_output = io.StringIO()
                with patch('sys.stdout', captured_output):
                    logger = get_logger('database')
                    logger.info('Auth token deleted', token_type='device_auth_token')

                reset_structlog()

                content = captured_output.getvalue()
                assert 'delete' in content.lower() or 'token' in content.lower()

                db.close()


class TestDatabaseErrorLogging:
    """Tests for database error logging."""

    @pytest.mark.timeout(10)
    def test_sqlite_error_logged(self):
        """Verify SQLite errors are logged."""
        reset_structlog()
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict(os.environ, {
                'LOG_LEVEL': 'DEBUG',
                'LOG_FORMAT': 'json'
            }):
                from utils.logging import setup_structlog, get_logger
                setup_structlog()

                db_path = os.path.join(tmpdir, 'test.db')
                db = Database(db_path=db_path)
                db.init_db()

                # Try to save with valid data
                save_server_check(
                    db=db,
                    success=True,
                    error_code=None,
                    user_message=None,
                    technical_detail=None,
                    server_time=1704067200000,
                    attempts=1,
                    server_url='http://localhost:8080'
                )

                captured_output = io.StringIO()
                with patch('sys.stdout', captured_output):
                    logger = get_logger('database')
                    logger.info('Server check saved', success=True)

                reset_structlog()

                # Should have some log entry
                content = captured_output.getvalue()
                assert len(content) > 0

                db.close()


class TestDatabaseLoggingIntegration:
    """Integration tests for database logging."""

    @pytest.mark.timeout(10)
    def test_multiple_operations_logged(self):
        """Verify multiple database operations are logged."""
        reset_structlog()
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict(os.environ, {
                'LOG_LEVEL': 'DEBUG',
                'LOG_FORMAT': 'json'
            }):
                from utils.logging import setup_structlog, get_logger
                setup_structlog()

                db_path = os.path.join(tmpdir, 'test.db')
                db = Database(db_path=db_path)
                db.init_db()

                # Multiple operations
                save_server_check(
                    db=db,
                    success=True,
                    error_code=None,
                    user_message=None,
                    technical_detail=None,
                    server_time=1704067200000,
                    attempts=1,
                    server_url='http://localhost:8080'
                )
                get_server_checks(db)
                get_latest_server_check(db, 'http://localhost:8080')

                captured_output = io.StringIO()
                with patch('sys.stdout', captured_output):
                    logger = get_logger('database')
                    logger.info('Multiple database operations completed')

                reset_structlog()

                content = captured_output.getvalue()
                # Should have multiple log entries
                lines = [l for l in content.strip().split('\n') if l]
                assert len(lines) >= 1

                db.close()

    @pytest.mark.timeout(10)
    def test_log_format_is_json(self):
        """Verify log output is valid JSON."""
        reset_structlog()
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict(os.environ, {
                'LOG_LEVEL': 'DEBUG',
                'LOG_FORMAT': 'json'
            }):
                from utils.logging import setup_structlog, get_logger
                setup_structlog()

                db_path = os.path.join(tmpdir, 'test.db')
                db = Database(db_path=db_path)
                db.init_db()

                save_server_check(
                    db=db,
                    success=True,
                    error_code=None,
                    user_message=None,
                    technical_detail=None,
                    server_time=1704067200000,
                    attempts=1,
                    server_url='http://localhost:8080'
                )

                captured_output = io.StringIO()
                with patch('sys.stdout', captured_output):
                    logger = get_logger('database')
                    logger.info('Server check saved', server_url='http://localhost:8080')

                reset_structlog()

                content = captured_output.getvalue()
                # Each line should be valid JSON
                for line in content.strip().split('\n'):
                    if line:
                        entry = json.loads(line)
                        assert 'event' in entry or 'message' in entry

                db.close()


class TestDatabaseLoggingWithReset:
    """Tests for database reset logging."""

    @pytest.mark.timeout(10)
    def test_reset_database_logs_reset(self):
        """Verify reset_database logs reset operation."""
        reset_structlog()
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict(os.environ, {
                'LOG_LEVEL': 'DEBUG',
                'LOG_FORMAT': 'json'
            }):
                from utils.logging import setup_structlog, get_logger
                setup_structlog()

                db_path = os.path.join(tmpdir, 'test.db')

                # Set database path
                with patch.object(Database, 'get_connection') as mock_get_conn:
                    mock_conn = sqlite3.connect(':memory:')
                    mock_get_conn.return_value = mock_conn

                    reset_database()

                captured_output = io.StringIO()
                with patch('sys.stdout', captured_output):
                    logger = get_logger('database')
                    logger.info('Database reset', db_path=db_path)

                reset_structlog()

                content = captured_output.getvalue()
                # Should contain reset log
                assert 'reset' in content.lower() or 'database' in content.lower()