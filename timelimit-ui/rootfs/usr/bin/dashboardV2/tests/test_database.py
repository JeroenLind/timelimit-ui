"""Unit tests for SQLite database operations.

This module tests the database module functionality including:
- Database initialization
- Server checks CRUD operations
- Families CRUD operations
- Devices CRUD operations
- Auth tokens CRUD operations
- Thread safety for Flask threaded mode
"""

import os
import tempfile
import threading
import pytest
from datetime import datetime, timedelta, timezone

from database import (
    Database,
    get_database,
    reset_database,
    save_server_check,
    get_server_checks,
    get_latest_server_check,
    create_family,
    get_family,
    get_family_by_mail,
    update_family,
    delete_family,
    create_device,
    get_device,
    get_devices_by_family,
    delete_device,
    store_auth_token,
    get_auth_token,
    delete_auth_token,
    cleanup_expired_tokens
)


class TestDatabaseInitialization:
    """Tests for database initialization."""
    
    def test_database_creation(self):
        """Test that database is created successfully."""
        db_fd, db_path = tempfile.mkstemp(suffix='.db')
        try:
            db = Database(db_path=db_path)
            db.init_db()
            
            # Verify file exists
            assert os.path.exists(db_path)
            
            # Verify tables exist
            conn = db.get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]
            
            assert 'server_checks' in tables
            assert 'families' in tables
            assert 'devices' in tables
            assert 'auth_tokens' in tables
            
            db.close()
        finally:
            os.close(db_fd)
            os.unlink(db_path)
    
    def test_database_connection(self):
        """Test that database connection works."""
        db_fd, db_path = tempfile.mkstemp(suffix='.db')
        try:
            db = Database(db_path=db_path)
            db.init_db()
            
            conn = db.get_connection()
            assert conn is not None
            assert conn.execute('SELECT 1').fetchone()[0] == 1
            
            db.close()
        finally:
            os.close(db_fd)
            os.unlink(db_path)


class TestServerChecks:
    """Tests for server_checks table operations."""
    
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
    def test_save_server_check_success(self, test_db):
        """Test saving a successful server check."""
        row_id = save_server_check(
            db=test_db,
            success=True,
            error_code=None,
            user_message=None,
            technical_detail=None,
            server_time=1704067200000,
            attempts=1,
            server_url='http://localhost:8080'
        )
        
        assert row_id is not None
        assert row_id > 0
    
    @pytest.mark.timeout(10)
    def test_save_server_check_failure(self, test_db):
        """Test saving a failed server check."""
        row_id = save_server_check(
            db=test_db,
            success=False,
            error_code='timeout',
            user_message='Connection timeout',
            technical_detail='Timeout after 10s',
            server_time=None,
            attempts=3,
            server_url='http://localhost:8080'
        )
        
        assert row_id is not None
        assert row_id > 0
    
    @pytest.mark.timeout(10)
    def test_get_server_checks(self, test_db):
        """Test retrieving server checks."""
        # Save multiple checks
        save_server_check(
            db=test_db,
            success=True,
            error_code=None,
            user_message=None,
            technical_detail=None,
            server_time=1704067200000,
            attempts=1,
            server_url='http://localhost:8080'
        )
        
        save_server_check(
            db=test_db,
            success=False,
            error_code='unreachable',
            user_message='Cannot connect',
            technical_detail='Connection refused',
            server_time=None,
            attempts=1,
            server_url='http://localhost:8080'
        )
        
        checks = get_server_checks(test_db, limit=10)
        
        assert len(checks) == 2
        assert checks[0]['success'] == 0  # Most recent first
        assert checks[1]['success'] == 1
    
    @pytest.mark.timeout(10)
    def test_get_latest_server_check(self, test_db):
        """Test retrieving the latest server check."""
        save_server_check(
            db=test_db,
            success=True,
            error_code=None,
            user_message=None,
            technical_detail=None,
            server_time=1704067200000,
            attempts=1,
            server_url='http://localhost:8080'
        )
        
        latest = get_latest_server_check(test_db, 'http://localhost:8080')
        
        assert latest is not None
        assert latest['success'] == 1
        assert latest['server_time'] == 1704067200000
    
    @pytest.mark.timeout(10)
    def test_get_latest_server_check_not_found(self, test_db):
        """Test retrieving latest server check for non-existent server."""
        latest = get_latest_server_check(test_db, 'http://nonexistent:8080')
        
        assert latest is None


class TestFamilies:
    """Tests for families table operations."""
    
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
    def test_create_family(self, test_db):
        """Test creating a family."""
        create_family(
            db=test_db,
            family_id='family_test123',
            mail='test@example.com',
            parent_password_hash='$2b$12$hash1',
            parent_password_second_hash='$2b$12$hash2',
            parent_password_second_salt='$2b$12$salt',
            parent_password_encrypted=False
        )
        
        family = get_family(test_db, 'family_test123')
        
        assert family is not None
        assert family['mail'] == 'test@example.com'
        assert family['parent_password_hash'] == '$2b$12$hash1'
    
    @pytest.mark.timeout(10)
    def test_get_family_not_found(self, test_db):
        """Test getting a non-existent family."""
        family = get_family(test_db, 'nonexistent')
        
        assert family is None
    
    @pytest.mark.timeout(10)
    def test_get_family_by_mail(self, test_db):
        """Test getting a family by email."""
        create_family(
            db=test_db,
            family_id='family_test123',
            mail='test@example.com',
            parent_password_hash='$2b$12$hash1',
            parent_password_second_hash='$2b$12$hash2',
            parent_password_second_salt='$2b$12$salt',
            parent_password_encrypted=False
        )
        
        family = get_family_by_mail(test_db, 'test@example.com')
        
        assert family is not None
        assert family['family_id'] == 'family_test123'
    
    @pytest.mark.timeout(10)
    def test_get_family_by_mail_not_found(self, test_db):
        """Test getting a family by non-existent email."""
        family = get_family_by_mail(test_db, 'nonexistent@example.com')
        
        assert family is None
    
    @pytest.mark.timeout(10)
    def test_update_family(self, test_db):
        """Test updating a family."""
        create_family(
            db=test_db,
            family_id='family_test123',
            mail='test@example.com',
            parent_password_hash='$2b$12$hash1',
            parent_password_second_hash='$2b$12$hash2',
            parent_password_second_salt='$2b$12$salt',
            parent_password_encrypted=False
        )
        
        result = update_family(
            db=test_db,
            family_id='family_test123',
            updates={'parent_password_hash': '$2b$12$newhash'}
        )
        
        assert result is True
        
        family = get_family(test_db, 'family_test123')
        assert family['parent_password_hash'] == '$2b$12$newhash'
    
    @pytest.mark.timeout(10)
    def test_update_family_not_found(self, test_db):
        """Test updating a non-existent family."""
        result = update_family(
            db=test_db,
            family_id='nonexistent',
            updates={'parent_password_hash': 'newhash'}
        )
        
        assert result is False
    
    @pytest.mark.timeout(10)
    def test_delete_family(self, test_db):
        """Test deleting a family."""
        create_family(
            db=test_db,
            family_id='family_test123',
            mail='test@example.com',
            parent_password_hash='$2b$12$hash1',
            parent_password_second_hash='$2b$12$hash2',
            parent_password_second_salt='$2b$12$salt',
            parent_password_encrypted=False
        )
        
        result = delete_family(test_db, 'family_test123')
        
        assert result is True
        assert get_family(test_db, 'family_test123') is None
    
    @pytest.mark.timeout(10)
    def test_delete_family_not_found(self, test_db):
        """Test deleting a non-existent family."""
        result = delete_family(test_db, 'nonexistent')
        
        assert result is False


class TestDevices:
    """Tests for devices table operations."""
    
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
    def test_create_device(self, test_db):
        """Test creating a device."""
        create_device(
            db=test_db,
            device_id='device_test123',
            family_id='family_test123',
            name='Test Device',
            model='Pixel 7'
        )
        
        device = get_device(test_db, 'device_test123')
        
        assert device is not None
        assert device['name'] == 'Test Device'
        assert device['model'] == 'Pixel 7'
        assert device['family_id'] == 'family_test123'
    
    @pytest.mark.timeout(10)
    def test_get_device_not_found(self, test_db):
        """Test getting a non-existent device."""
        device = get_device(test_db, 'nonexistent')
        
        assert device is None
    
    @pytest.mark.timeout(10)
    def test_get_devices_by_family(self, test_db):
        """Test getting devices by family."""
        create_device(
            db=test_db,
            device_id='device1',
            family_id='family_test123',
            name='Device 1'
        )
        
        create_device(
            db=test_db,
            device_id='device2',
            family_id='family_test123',
            name='Device 2'
        )
        
        create_device(
            db=test_db,
            device_id='device3',
            family_id='family_other',
            name='Device 3'
        )
        
        devices = get_devices_by_family(test_db, 'family_test123')
        
        assert len(devices) == 2
        assert all(d['family_id'] == 'family_test123' for d in devices)
    
    @pytest.mark.timeout(10)
    def test_delete_device(self, test_db):
        """Test deleting a device."""
        create_device(
            db=test_db,
            device_id='device_test123',
            family_id='family_test123',
            name='Test Device'
        )
        
        result = delete_device(test_db, 'device_test123')
        
        assert result is True
        assert get_device(test_db, 'device_test123') is None
    
    @pytest.mark.timeout(10)
    def test_delete_device_not_found(self, test_db):
        """Test deleting a non-existent device."""
        result = delete_device(test_db, 'nonexistent')
        
        assert result is False


class TestAuthTokens:
    """Tests for auth_tokens table operations."""
    
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
    def test_store_auth_token(self, test_db):
        """Test storing an auth token."""
        store_auth_token(
            db=test_db,
            token_type='device_auth_token',
            token_value='test_token_123',
            device_id='device_test123',
            family_id='family_test123',
            mail='test@example.com'
        )
        
        token = get_auth_token(test_db, 'test_token_123')
        
        assert token is not None
        assert token['token_type'] == 'device_auth_token'
        assert token['token_value'] == 'test_token_123'
    
    @pytest.mark.timeout(10)
    def test_get_auth_token_not_found(self, test_db):
        """Test getting a non-existent auth token."""
        token = get_auth_token(test_db, 'nonexistent_token')
        
        assert token is None
    
    @pytest.mark.timeout(10)
    def test_delete_auth_token(self, test_db):
        """Test deleting an auth token."""
        store_auth_token(
            db=test_db,
            token_type='device_auth_token',
            token_value='test_token_123',
            device_id='device_test123',
            family_id='family_test123'
        )
        
        result = delete_auth_token(test_db, 'test_token_123')
        
        assert result is True
        assert get_auth_token(test_db, 'test_token_123') is None
    
    @pytest.mark.timeout(10)
    def test_delete_auth_token_not_found(self, test_db):
        """Test deleting a non-existent auth token."""
        result = delete_auth_token(test_db, 'nonexistent_token')
        
        assert result is False
    
    @pytest.mark.timeout(10)
    def test_cleanup_expired_tokens(self, test_db):
        """Test cleaning up expired tokens."""
        # Store a token with past expiration
        store_auth_token(
            db=test_db,
            token_type='device_auth_token',
            token_value='expired_token',
            device_id='device_test123',
            family_id='family_test123',
            expires_at=datetime.now(timezone.utc) - timedelta(hours=1)
        )
        
        # Store a valid token
        store_auth_token(
            db=test_db,
            token_type='device_auth_token',
            token_value='valid_token',
            device_id='device_test123',
            family_id='family_test123',
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1)
        )
        
        count = cleanup_expired_tokens(test_db)
        
        assert count == 1
        assert get_auth_token(test_db, 'expired_token') is None
        assert get_auth_token(test_db, 'valid_token') is not None


class TestDatabaseSingleton:
    """Tests for database singleton functionality."""
    
    def test_get_database_returns_same_instance(self):
        """Test that get_database returns the same instance."""
        reset_database()
        
        db1 = get_database()
        db2 = get_database()
        
        assert db1 is db2
        
        reset_database()
    
    def test_reset_database(self):
        """Test that reset_database clears the instance."""
        reset_database()
        
        db1 = get_database()
        reset_database()
        db2 = get_database()
        
        assert db1 is not db2


class TestDatabaseThreadSafety:
    """Tests for database thread safety in Flask threaded mode.
    
    These tests verify that the database connection can be safely used
    across multiple threads, which is required for Flask's threaded mode.
    """
    
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
    def test_connection_usable_in_different_thread(self, test_db):
        """Test that database connection can be used in a different thread.
        
        This simulates the Flask threaded mode where different requests
        are handled by different threads.
        """
        results = {'success': False, 'error': None}
        
        def thread_function():
            try:
                # Get connection in a different thread
                conn = test_db.get_connection()
                cursor = conn.cursor()
                cursor.execute('SELECT 1')
                result = cursor.fetchone()
                results['success'] = (result[0] == 1)
            except Exception as e:
                results['error'] = str(e)
        
        # Create and start thread
        thread = threading.Thread(target=thread_function)
        thread.start()
        thread.join(timeout=5)
        
        assert results['error'] is None, f"Thread error: {results['error']}"
        assert results['success'] is True, "Connection not usable in different thread"
    
    @pytest.mark.timeout(10)
    def test_save_and_retrieve_in_different_threads(self, test_db):
        """Test that data saved in one thread can be retrieved in another.
        
        This simulates the Flask threaded mode where one request saves data
        and another request retrieves it.
        """
        errors = []
        
        def save_thread():
            try:
                save_server_check(
                    db=test_db,
                    success=True,
                    error_code=None,
                    user_message=None,
                    technical_detail=None,
                    server_time=1704067200000,
                    attempts=1,
                    server_url='http://localhost:8080'
                )
            except Exception as e:
                errors.append(f"Save error: {e}")
        
        def retrieve_thread():
            try:
                # Give save thread time to complete
                import time
                time.sleep(0.1)
                checks = get_server_checks(test_db, limit=10)
                if len(checks) == 0:
                    errors.append("No checks retrieved")
            except Exception as e:
                errors.append(f"Retrieve error: {e}")
        
        # Run threads
        t1 = threading.Thread(target=save_thread)
        t2 = threading.Thread(target=retrieve_thread)
        
        t1.start()
        t2.start()
        
        t1.join(timeout=5)
        t2.join(timeout=5)
        
        assert len(errors) == 0, f"Thread errors: {errors}"
    
    @pytest.mark.timeout(10)
    def test_multiple_concurrent_reads(self, test_db):
        """Test that multiple concurrent reads work correctly.
        
        This simulates multiple concurrent requests reading from the database.
        """
        # First, save some data
        save_server_check(
            db=test_db,
            success=True,
            error_code=None,
            user_message=None,
            technical_detail=None,
            server_time=1704067200000,
            attempts=1,
            server_url='http://localhost:8080'
        )
        
        results = []
        errors = []
        
        def read_thread():
            try:
                checks = get_server_checks(test_db, limit=10)
                results.append(len(checks))
            except Exception as e:
                errors.append(str(e))
        
        # Create multiple threads doing concurrent reads
        threads = [threading.Thread(target=read_thread) for _ in range(5)]
        
        for t in threads:
            t.start()
        
        for t in threads:
            t.join(timeout=5)
        
        assert len(errors) == 0, f"Thread errors: {errors}"
        assert all(r == 1 for r in results), f"Unexpected results: {results}"
    
    @pytest.mark.timeout(10)
    def test_check_same_thread_false_in_connection(self, test_db):
        """Test that check_same_thread=False is set in the connection.
        
        This verifies the fix for the SQLite threading issue.
        """
        conn = test_db.get_connection()
        
        # Verify the connection has check_same_thread=False
        # This is done by checking if we can use it in a different thread
        results = {'value': None, 'error': None}
        
        def use_connection():
            try:
                cursor = conn.cursor()
                cursor.execute('SELECT 42')
                results['value'] = cursor.fetchone()[0]
            except Exception as e:
                results['error'] = str(e)
        
        thread = threading.Thread(target=use_connection)
        thread.start()
        thread.join(timeout=5)
        
        assert results['error'] is None, f"Connection error: {results['error']}"
        assert results['value'] == 42, f"Unexpected value: {results['value']}"