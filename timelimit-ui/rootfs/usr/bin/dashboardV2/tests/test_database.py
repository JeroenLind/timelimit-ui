"""Unit tests for SQLite database operations.

This module tests the database module functionality including:
- Database initialization
- Server checks CRUD operations
- Families CRUD operations
- Devices CRUD operations
- Auth tokens CRUD operations
- Thread safety for Flask threaded mode

Key change: Using device_auth_token as primary key instead of family_id,
matching the official Android app's approach where the server looks up
family from device using deviceAuthToken.
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
    get_devices_by_device_auth_token,
    delete_device,
    update_device_app_version,
    store_auth_token,
    get_auth_token,
    get_device_auth_tokens,
    delete_auth_token,
    cleanup_expired_tokens,
    save_users,
    get_users_by_device_auth_token,
    save_sync_state,
    get_sync_state,
    save_categories,
    get_categories_by_device_auth_token,
    save_connected_devices,
    get_connected_devices,
    get_next_sequence_number,
    increment_sequence_number,
    get_latest_device_auth_token,
    get_latest_own_device_id,
    delete_all_device_auth_tokens,
    get_parent_password_hash,
    update_family_password_hash,
    upsert_family_password_hash,
    validate_password_hash,
    get_family_with_valid_hash,
    clear_family_password_hash,
    has_parent_password_hash,
    clear_all_tables
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
            assert 'users' in tables
            assert 'sync_state' in tables
            assert 'categories' in tables
            assert 'connected_devices' in tables
            
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
    
    def test_connected_devices_name_column_migration(self):
        """Test that the name column is added to connected_devices table via migration.
        
        This test verifies that:
        1. The name column exists in the connected_devices table after init_db()
        2. The migration runs correctly for existing databases
        """
        db_fd, db_path = tempfile.mkstemp(suffix='.db')
        try:
            db = Database(db_path=db_path)
            db.init_db()
            
            # Verify the name column exists in connected_devices table
            conn = db.get_connection()
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(connected_devices)")
            columns = [row[1] for row in cursor.fetchall()]
            
            assert 'name' in columns, "name column should exist in connected_devices table"
            
            db.close()
        finally:
            os.close(db_fd)
            os.unlink(db_path)
    
    def test_connected_devices_name_column_migration_from_old_schema(self):
        """Test migration from old schema without name column.
        
        This test simulates an existing database that was created before
        the name column was added, and verifies that the migration
        correctly adds the column.
        """
        db_fd, db_path = tempfile.mkstemp(suffix='.db')
        try:
            # Create database with old schema (without name column)
            db = Database(db_path=db_path)
            conn = db.get_connection()
            cursor = conn.cursor()
            
            # Create tables without the name column
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS families (
                    device_auth_token TEXT PRIMARY KEY,
                    mail TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
            ''')
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS devices (
                    id TEXT PRIMARY KEY,
                    device_auth_token TEXT NOT NULL,
                    name TEXT,
                    created_at TEXT NOT NULL
                )
            ''')
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS connected_devices (
                    device_auth_token TEXT NOT NULL,
                    device_id TEXT NOT NULL,
                    last_seen INTEGER,
                    PRIMARY KEY (device_auth_token, device_id),
                    FOREIGN KEY (device_auth_token) REFERENCES families(device_auth_token)
                )
            ''')
            conn.commit()
            db.close()
            
            # Now reinitialize the database (this should run migrations)
            db = Database(db_path=db_path)
            db.init_db()
            
            # Verify the name column was added
            conn = db.get_connection()
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(connected_devices)")
            columns = [row[1] for row in cursor.fetchall()]
            
            assert 'name' in columns, "name column should be added via migration"
            
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
            device_auth_token='device_token_test123',
            mail='test@example.com',
            parent_password_hash='$2b$12$hash1',
            parent_password_second_hash='$2b$12$hash2',
            parent_password_second_salt='$2b$12$salt',
            parent_password_encrypted=False
        )
        
        family = get_family(test_db, 'device_token_test123')
        
        assert family is not None
        assert family['mail'] == 'test@example.com'
        assert family['parent_password_hash'] == '$2b$12$hash1'
    
    @pytest.mark.timeout(10)
    def test_get_family_not_found(self, test_db):
        """Test getting a non-existent family."""
        family = get_family(test_db, 'nonexistent_token')
        
        assert family is None
    
    @pytest.mark.timeout(10)
    def test_get_family_by_mail(self, test_db):
        """Test getting a family by email."""
        create_family(
            db=test_db,
            device_auth_token='device_token_test123',
            mail='test@example.com',
            parent_password_hash='$2b$12$hash1',
            parent_password_second_hash='$2b$12$hash2',
            parent_password_second_salt='$2b$12$salt',
            parent_password_encrypted=False
        )
        
        family = get_family_by_mail(test_db, 'test@example.com')
        
        assert family is not None
        assert family['device_auth_token'] == 'device_token_test123'
    
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
            device_auth_token='device_token_test123',
            mail='test@example.com',
            parent_password_hash='$2b$12$hash1',
            parent_password_second_hash='$2b$12$hash2',
            parent_password_second_salt='$2b$12$salt',
            parent_password_encrypted=False
        )
        
        result = update_family(
            db=test_db,
            device_auth_token='device_token_test123',
            updates={'parent_password_hash': '$2b$12$newhash'}
        )
        
        assert result is True
        
        family = get_family(test_db, 'device_token_test123')
        assert family['parent_password_hash'] == '$2b$12$newhash'
    
    @pytest.mark.timeout(10)
    def test_update_family_not_found(self, test_db):
        """Test updating a non-existent family."""
        result = update_family(
            db=test_db,
            device_auth_token='nonexistent_token',
            updates={'parent_password_hash': 'newhash'}
        )
        
        assert result is False
    
    @pytest.mark.timeout(10)
    def test_delete_family(self, test_db):
        """Test deleting a family."""
        create_family(
            db=test_db,
            device_auth_token='device_token_test123',
            mail='test@example.com',
            parent_password_hash='$2b$12$hash1',
            parent_password_second_hash='$2b$12$hash2',
            parent_password_second_salt='$2b$12$salt',
            parent_password_encrypted=False
        )
        
        result = delete_family(test_db, 'device_token_test123')
        
        assert result is True
        assert get_family(test_db, 'device_token_test123') is None
    
    @pytest.mark.timeout(10)
    def test_delete_family_not_found(self, test_db):
        """Test deleting a non-existent family."""
        result = delete_family(test_db, 'nonexistent_token')
        
        assert result is False


class TestParentPasswordHash:
    """Tests for parent password hash operations."""
    
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
    def test_get_parent_password_hash_existing(self, test_db):
        """Test getting parent password hash for existing family."""
        create_family(
            db=test_db,
            device_auth_token='device_token_test123',
            mail='test@example.com',
            parent_password_hash='$2b$12$hash1',
            parent_password_second_hash='$2b$12$hash2',
            parent_password_second_salt='$2b$12$salt',
            parent_password_encrypted=False
        )
        
        hash_value = get_parent_password_hash(test_db, 'device_token_test123')
        
        assert hash_value == '$2b$12$hash2'
    
    @pytest.mark.timeout(10)
    def test_get_parent_password_hash_not_found(self, test_db):
        """Test getting parent password hash for non-existent family."""
        hash_value = get_parent_password_hash(test_db, 'nonexistent_token')
        
        assert hash_value is None
    
    @pytest.mark.timeout(10)
    def test_update_family_password_hash(self, test_db):
        """Test updating family password hash."""
        create_family(
            db=test_db,
            device_auth_token='device_token_test123',
            mail='test@example.com',
            parent_password_hash='$2b$12$hash1',
            parent_password_second_hash='$2b$12$hash2',
            parent_password_second_salt='$2b$12$salt',
            parent_password_encrypted=False
        )
        
        result = update_family_password_hash(
            db=test_db,
            device_auth_token='device_token_test123',
            parent_password_second_hash='$2b$12$newhash'
        )
        
        assert result is True
        
        hash_value = get_parent_password_hash(test_db, 'device_token_test123')
        assert hash_value == '$2b$12$newhash'
    
    @pytest.mark.timeout(10)
    def test_update_family_password_hash_not_found(self, test_db):
        """Test updating password hash for non-existent family."""
        result = update_family_password_hash(
            db=test_db,
            device_auth_token='nonexistent_token',
            parent_password_second_hash='$2b$12$newhash'
        )
        
        assert result is False
    
    @pytest.mark.timeout(10)
    def test_upsert_family_password_hash_insert(self, test_db):
        """Test upserting family password hash when family doesn't exist."""
        result = upsert_family_password_hash(
            db=test_db,
            device_auth_token='device_token_test123',
            parent_password_second_hash='$2b$12$hash1'
        )
        
        assert result is True
        
        # Verify the hash was inserted
        hash_value = get_parent_password_hash(test_db, 'device_token_test123')
        assert hash_value == '$2b$12$hash1'
        
        # Verify family record was created
        family = get_family(test_db, 'device_token_test123')
        assert family is not None
        assert family['parent_password_second_hash'] == '$2b$12$hash1'
    
    @pytest.mark.timeout(10)
    def test_upsert_family_password_hash_update(self, test_db):
        """Test upserting family password hash when family exists."""
        # First, create a family
        create_family(
            db=test_db,
            device_auth_token='device_token_test123',
            mail='test@example.com',
            parent_password_hash='$2b$12$hash1',
            parent_password_second_hash='$2b$12$hash2',
            parent_password_second_salt='$2b$12$salt',
            parent_password_encrypted=False
        )
        
        # Now upsert a new hash
        result = upsert_family_password_hash(
            db=test_db,
            device_auth_token='device_token_test123',
            parent_password_second_hash='$2b$12$newhash'
        )
        
        assert result is True
        
        # Verify the hash was updated
        hash_value = get_parent_password_hash(test_db, 'device_token_test123')
        assert hash_value == '$2b$12$newhash'
    
    @pytest.mark.timeout(10)
    def test_upsert_family_password_hash_preserves_mail(self, test_db):
        """Test that upsert preserves existing mail field."""
        # First, create a family with mail
        create_family(
            db=test_db,
            device_auth_token='device_token_test123',
            mail='test@example.com',
            parent_password_hash='$2b$12$hash1',
            parent_password_second_hash='$2b$12$hash2',
            parent_password_second_salt='$2b$12$salt',
            parent_password_encrypted=False
        )
        
        # Upsert hash
        upsert_family_password_hash(
            db=test_db,
            device_auth_token='device_token_test123',
            parent_password_second_hash='$2b$12$newhash'
        )
        
        # Verify mail is preserved
        family = get_family(test_db, 'device_token_test123')
        assert family['mail'] == 'test@example.com'


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
            device_auth_token='device_token_test123',
            name='Test Device',
            model='Pixel 7'
        )
        
        device = get_device(test_db, 'device_test123')
        
        assert device is not None
        assert device['name'] == 'Test Device'
        assert device['model'] == 'Pixel 7'
        assert device['device_auth_token'] == 'device_token_test123'
    
    @pytest.mark.timeout(10)
    def test_get_device_not_found(self, test_db):
        """Test getting a non-existent device."""
        device = get_device(test_db, 'nonexistent')
        
        assert device is None
    
    @pytest.mark.timeout(10)
    def test_get_devices_by_device_auth_token(self, test_db):
        """Test getting devices by device auth token."""
        create_device(
            db=test_db,
            device_id='device1',
            device_auth_token='device_token_test123',
            name='Device 1'
        )
        
        create_device(
            db=test_db,
            device_id='device2',
            device_auth_token='device_token_test123',
            name='Device 2'
        )
        
        create_device(
            db=test_db,
            device_id='device3',
            device_auth_token='device_token_other',
            name='Device 3'
        )
        
        devices = get_devices_by_device_auth_token(test_db, 'device_token_test123')
        
        assert len(devices) == 2
        assert all(d['device_auth_token'] == 'device_token_test123' for d in devices)
    
    @pytest.mark.timeout(10)
    def test_delete_device(self, test_db):
        """Test deleting a device."""
        create_device(
            db=test_db,
            device_id='device_test123',
            device_auth_token='device_token_test123',
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
    
    @pytest.mark.timeout(10)
    def test_update_device_app_version(self, test_db):
        """Test updating device app version."""
        create_device(
            db=test_db,
            device_id='device_test123',
            device_auth_token='device_token_test123',
            name='Test Device',
            model='Pixel 7'
        )
        
        # Initially, app version should be None or default
        device = get_device(test_db, 'device_test123')
        assert device['current_app_version'] is None or device['current_app_version'] == '0'
        
        # Update the app version
        result = update_device_app_version(
            db=test_db,
            device_id='device_test123',
            current_app_version='123',
            highest_app_version='123'
        )
        
        assert result is True
        
        # Verify the update
        device = get_device(test_db, 'device_test123')
        assert device['current_app_version'] == '123'
        assert device['highest_app_version'] == '123'
    
    @pytest.mark.timeout(10)
    def test_update_device_app_version_not_found(self, test_db):
        """Test updating app version for non-existent device."""
        result = update_device_app_version(
            db=test_db,
            device_id='nonexistent',
            current_app_version='123',
            highest_app_version='123'
        )
        
        assert result is False
    
    @pytest.mark.timeout(10)
    def test_update_device_app_version_with_different_highest(self, test_db):
        """Test updating device app version with different highest version."""
        create_device(
            db=test_db,
            device_id='device_test123',
            device_auth_token='device_token_test123',
            name='Test Device'
        )
        
        result = update_device_app_version(
            db=test_db,
            device_id='device_test123',
            current_app_version='100',
            highest_app_version='123'
        )
        
        assert result is True
        
        device = get_device(test_db, 'device_test123')
        assert device['current_app_version'] == '100'
        assert device['highest_app_version'] == '123'
    
    @pytest.mark.timeout(10)
    def test_update_device_app_version_defaults_highest(self, test_db):
        """Test that highest_app_version defaults to current_app_version."""
        create_device(
            db=test_db,
            device_id='device_test123',
            device_auth_token='device_token_test123',
            name='Test Device'
        )
        
        result = update_device_app_version(
            db=test_db,
            device_id='device_test123',
            current_app_version='456'
        )
        
        assert result is True
        
        device = get_device(test_db, 'device_test123')
        assert device['current_app_version'] == '456'
        assert device['highest_app_version'] == '456'


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
            device_auth_token='device_token_test123',
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
            device_auth_token='device_token_test123'
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
            device_auth_token='device_token_test123',
            expires_at=datetime.now(timezone.utc) - timedelta(hours=1)
        )
        
        # Store a valid token
        store_auth_token(
            db=test_db,
            token_type='device_auth_token',
            token_value='valid_token',
            device_id='device_test123',
            device_auth_token='device_token_test123',
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
        
        assert results['value'] == 42, f"Unexpected value: {results['value']}"
        assert results['error'] is None, f"Thread error: {results['error']}"


class TestUsers:
    """Tests for users table operations."""
    
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
    def test_save_users(self, test_db):
        """Test saving users to the database."""
        users_data = [
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
        
        save_users(test_db, 'device_token_test123', users_data)
        
        users = get_users_by_device_auth_token(test_db, 'device_token_test123')
        
        assert len(users) == 2
        assert users[0]['id'] == 'user1'
        assert users[0]['name'] == 'Parent User'
        assert users[0]['type'] == 'parent'
        assert users[1]['id'] == 'user2'
        assert users[1]['type'] == 'child'
    
    @pytest.mark.timeout(10)
    def test_get_users_by_device_auth_token_empty(self, test_db):
        """Test getting users for a device auth token with no users."""
        users = get_users_by_device_auth_token(test_db, 'device_token_test123')
        
        assert len(users) == 0
    
    @pytest.mark.timeout(10)
    def test_save_users_updates_existing(self, test_db):
        """Test that save_users updates existing users."""
        users_data = [
            {
                'id': 'user1',
                'name': 'Parent User',
                'type': 'parent',
                'mail': 'parent@example.com'
            }
        ]
        
        save_users(test_db, 'device_token_test123', users_data)
        
        # Update the user
        users_data[0]['name'] = 'Updated Parent'
        save_users(test_db, 'device_token_test123', users_data)
        
        users = get_users_by_device_auth_token(test_db, 'device_token_test123')
        
        assert len(users) == 1
        assert users[0]['name'] == 'Updated Parent'


class TestSyncState:
    """Tests for sync_state table operations."""
    
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
    def test_save_sync_state(self, test_db):
        """Test saving sync state."""
        save_sync_state(
            test_db,
            'device_token_test123',
            device_list_version='v1',
            user_list_version='v2'
        )
        
        state = get_sync_state(test_db, 'device_token_test123')
        
        assert state is not None
        assert state['device_auth_token'] == 'device_token_test123'
        assert state['device_list_version'] == 'v1'
        assert state['user_list_version'] == 'v2'
        assert state['last_sync_success'] == 1
    
    @pytest.mark.timeout(10)
    def test_get_sync_state_not_found(self, test_db):
        """Test getting sync state for non-existent device auth token."""
        state = get_sync_state(test_db, 'nonexistent_token')
        
        assert state is None
    
    @pytest.mark.timeout(10)
    def test_save_sync_state_updates_existing(self, test_db):
        """Test that save_sync_state updates existing state."""
        save_sync_state(
            test_db,
            'device_token_test123',
            device_list_version='v1',
            user_list_version='v1'
        )
        
        # Update the state
        save_sync_state(
            test_db,
            'device_token_test123',
            device_list_version='v2',
            user_list_version='v3'
        )
        
        state = get_sync_state(test_db, 'device_token_test123')
        
        assert state['device_list_version'] == 'v2'
        assert state['user_list_version'] == 'v3'


class TestSequenceNumber:
    """Tests for sequence number operations."""
    
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
    def test_get_next_sequence_number_no_state(self, test_db):
        """Test getting sequence number when no sync state exists."""
        # Should return 0 when no sync state exists
        seq = get_next_sequence_number(test_db, 'device_token_test123')
        
        assert seq == 0
    
    @pytest.mark.timeout(10)
    def test_get_next_sequence_number_with_state(self, test_db):
        """Test getting sequence number when sync state exists."""
        # Create a sync state with a sequence number
        save_sync_state(
            test_db,
            'device_token_test123',
            device_list_version='v1',
            user_list_version='v1'
        )
        
        # Manually set the sequence number
        from database import Database
        conn = test_db.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            'UPDATE sync_state SET next_sequence_number = 5 WHERE device_auth_token = ?',
            ('device_token_test123',)
        )
        conn.commit()
        
        seq = get_next_sequence_number(test_db, 'device_token_test123')
        
        assert seq == 5
    
    @pytest.mark.timeout(10)
    def test_increment_sequence_number_first_time(self, test_db):
        """Test incrementing sequence number for first time."""
        # Should start at 0 and increment to 1
        seq = increment_sequence_number(test_db, 'device_token_test123')
        
        assert seq == 1
        
        # Verify it was saved
        state = get_sync_state(test_db, 'device_token_test123')
        assert state is not None
        assert state['next_sequence_number'] == 1
    
    @pytest.mark.timeout(10)
    def test_increment_sequence_number_multiple_times(self, test_db):
        """Test incrementing sequence number multiple times."""
        # First increment
        seq1 = increment_sequence_number(test_db, 'device_token_test123')
        assert seq1 == 1
        
        # Second increment
        seq2 = increment_sequence_number(test_db, 'device_token_test123')
        assert seq2 == 2
        
        # Third increment
        seq3 = increment_sequence_number(test_db, 'device_token_test123')
        assert seq3 == 3
        
        # Verify final state
        state = get_sync_state(test_db, 'device_token_test123')
        assert state['next_sequence_number'] == 3
    
    @pytest.mark.timeout(10)
    def test_increment_sequence_number_different_tokens(self, test_db):
        """Test that sequence numbers are independent per device auth token."""
        # Increment for first token
        seq1 = increment_sequence_number(test_db, 'device_token_1')
        assert seq1 == 1
        
        # Increment for second token
        seq2 = increment_sequence_number(test_db, 'device_token_2')
        assert seq2 == 1
        
        # Increment first token again
        seq1_again = increment_sequence_number(test_db, 'device_token_1')
        assert seq1_again == 2
        
        # Verify both tokens have correct sequence numbers
        state1 = get_sync_state(test_db, 'device_token_1')
        state2 = get_sync_state(test_db, 'device_token_2')
        
        assert state1['next_sequence_number'] == 2
        assert state2['next_sequence_number'] == 1
    
    @pytest.mark.timeout(10)
    def test_save_sync_state_preserves_sequence_number(self, test_db):
        """Test that save_sync_state preserves the sequence number after increment.
        
        This is a regression test for the bug where save_sync_state() would
        reset the next_sequence_number when called after increment_sequence_number().
        
        The scenario:
        1. increment_sequence_number() is called (e.g., during push_app_version_action)
        2. save_sync_state() is called (e.g., during _update_sync_state)
        3. The sequence number should be preserved, not reset
        """
        # First, increment the sequence number (simulating push_app_version_action)
        seq = increment_sequence_number(test_db, 'device_token_test123')
        assert seq == 1
        
        # Verify the sequence number was incremented
        state = get_sync_state(test_db, 'device_token_test123')
        assert state is not None
        assert state['next_sequence_number'] == 1
        
        # Now call save_sync_state (simulating _update_sync_state)
        save_sync_state(
            test_db,
            'device_token_test123',
            device_list_version='device_v2',
            user_list_version='user_v2'
        )
        
        # Verify the sequence number is still 1 (not reset to 0)
        state = get_sync_state(test_db, 'device_token_test123')
        assert state['next_sequence_number'] == 1
        assert state['device_list_version'] == 'device_v2'
        assert state['user_list_version'] == 'user_v2'
        
        # Increment again and verify save_sync_state preserves it
        seq2 = increment_sequence_number(test_db, 'device_token_test123')
        assert seq2 == 2
        
        save_sync_state(
            test_db,
            'device_token_test123',
            device_list_version='device_v3',
            user_list_version='user_v3'
        )
        
        state = get_sync_state(test_db, 'device_token_test123')
        assert state['next_sequence_number'] == 2


class TestCategories:
    """Tests for categories table operations."""
    
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
    def test_save_categories(self, test_db):
        """Test saving categories to the database."""
        categories_data = [
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
        
        save_categories(test_db, 'device_token_test123', categories_data)
        
        categories = get_categories_by_device_auth_token(test_db, 'device_token_test123')
        
        assert len(categories) == 2
        assert categories[0]['id'] == 'cat1'
        assert categories[0]['title'] == 'Work'
        assert categories[1]['id'] == 'cat2'
        assert categories[1]['title'] == 'Play'
    
    @pytest.mark.timeout(10)
    def test_get_categories_by_device_auth_token_empty(self, test_db):
        """Test getting categories for a device auth token with no categories."""
        categories = get_categories_by_device_auth_token(test_db, 'device_token_test123')
        
        assert len(categories) == 0
    
    @pytest.mark.timeout(10)
    def test_save_categories_updates_existing(self, test_db):
        """Test that save_categories updates existing categories."""
        categories_data = [
            {
                'id': 'cat1',
                'title': 'Work',
                'extraTime': 60
            }
        ]
        
        save_categories(test_db, 'device_token_test123', categories_data)
        
        # Update the category
        categories_data[0]['title'] = 'Work & Study'
        save_categories(test_db, 'device_token_test123', categories_data)
        
        categories = get_categories_by_device_auth_token(test_db, 'device_token_test123')
        
        assert len(categories) == 1
        assert categories[0]['title'] == 'Work & Study'


class TestConnectedDevices:
    """Tests for connected_devices table operations."""
    
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
    def test_save_connected_devices(self, test_db):
        """Test saving connected devices."""
        device_ids = ['device1', 'device2', 'device3']
        
        save_connected_devices(test_db, 'device_token_test123', device_ids)
        
        retrieved = get_connected_devices(test_db, 'device_token_test123')
        
        assert len(retrieved) == 3
        device_id_list = [d['device_id'] for d in retrieved]
        assert 'device1' in device_id_list
        assert 'device2' in device_id_list
        assert 'device3' in device_id_list
    
    @pytest.mark.timeout(10)
    def test_get_connected_devices_empty(self, test_db):
        """Test getting connected devices for a device auth token with none."""
        devices = get_connected_devices(test_db, 'device_token_test123')
        
        assert len(devices) == 0
    
    @pytest.mark.timeout(10)
    def test_save_connected_devices_replaces_existing(self, test_db):
        """Test that save_connected_devices replaces existing devices."""
        device_ids_1 = ['device1', 'device2']
        device_ids_2 = ['device3', 'device4']
        
        save_connected_devices(test_db, 'device_token_test123', device_ids_1)
        save_connected_devices(test_db, 'device_token_test123', device_ids_2)
        
        devices = get_connected_devices(test_db, 'device_token_test123')
        
        assert len(devices) == 2
        device_id_list = [d['device_id'] for d in devices]
        assert 'device1' not in device_id_list
        assert 'device2' not in device_id_list
        assert 'device3' in device_id_list
        assert 'device4' in device_id_list
    
    @pytest.mark.timeout(10)
    def test_save_connected_devices_includes_device_names(self, test_db):
        """Test that save_connected_devices looks up and stores device names."""
        # Create devices with names
        create_device(
            db=test_db,
            device_id='device1',
            device_auth_token='device_token_test123',
            name='Parent Phone'
        )
        create_device(
            db=test_db,
            device_id='device2',
            device_auth_token='device_token_test123',
            name='Child Tablet'
        )
        # device3 has no name in devices table
        
        device_ids = ['device1', 'device2', 'device3']
        save_connected_devices(test_db, 'device_token_test123', device_ids)
        
        retrieved = get_connected_devices(test_db, 'device_token_test123')
        
        assert len(retrieved) == 3
        
        # Find each device and verify name
        device1 = next((d for d in retrieved if d['device_id'] == 'device1'), None)
        device2 = next((d for d in retrieved if d['device_id'] == 'device2'), None)
        device3 = next((d for d in retrieved if d['device_id'] == 'device3'), None)
        
        assert device1 is not None
        assert device1['name'] == 'Parent Phone'
        
        assert device2 is not None
        assert device2['name'] == 'Child Tablet'
        
        assert device3 is not None
        assert device3['name'] is None  # No name in devices table
    
    @pytest.mark.timeout(10)
    def test_get_connected_devices_includes_name(self, test_db):
        """Test that get_connected_devices returns the name field."""
        # Create a device with a name
        create_device(
            db=test_db,
            device_id='device1',
            device_auth_token='device_token_test123',
            name='Test Device Name'
        )
        
        # Save connected devices
        save_connected_devices(test_db, 'device_token_test123', ['device1'])
        
        # Get connected devices
        devices = get_connected_devices(test_db, 'device_token_test123')
        
        assert len(devices) == 1
        assert 'name' in devices[0]
        assert devices[0]['name'] == 'Test Device Name'
    
    @pytest.mark.timeout(10)
    def test_connected_devices_name_field_present(self, test_db):
        """Test that the name field is present in connected devices records."""
        # Save connected devices without any devices in devices table
        save_connected_devices(test_db, 'device_token_test123', ['device1'])
        
        devices = get_connected_devices(test_db, 'device_token_test123')
        
        assert len(devices) == 1
        # Name should be None since device doesn't exist in devices table
        assert 'name' in devices[0]
        assert devices[0]['name'] is None
    
    @pytest.mark.timeout(10)
    def test_connected_devices_with_empty_string_name(self, test_db):
        """Test that connected devices handles devices with empty string name."""
        # Create a device with an empty string name
        create_device(
            db=test_db,
            device_id='device1',
            device_auth_token='device_token_test123',
            name=''  # Empty string
        )
        
        save_connected_devices(test_db, 'device_token_test123', ['device1'])
        
        devices = get_connected_devices(test_db, 'device_token_test123')
        
        assert len(devices) == 1
        # Empty string should be preserved
        assert devices[0]['name'] == ''
    
    @pytest.mark.timeout(10)
    def test_connected_devices_with_whitespace_name(self, test_db):
        """Test that connected devices handles devices with whitespace-only name."""
        # Create a device with whitespace-only name
        create_device(
            db=test_db,
            device_id='device1',
            device_auth_token='device_token_test123',
            name='   '  # Whitespace only
        )
        
        save_connected_devices(test_db, 'device_token_test123', ['device1'])
        
        devices = get_connected_devices(test_db, 'device_token_test123')
        
        assert len(devices) == 1
        # Whitespace should be preserved
        assert devices[0]['name'] == '   '
    
    @pytest.mark.timeout(10)
    def test_connected_devices_with_none_name(self, test_db):
        """Test that connected devices handles devices with None/null name."""
        # Create a device without specifying a name (should be None)
        create_device(
            db=test_db,
            device_id='device1',
            device_auth_token='device_token_test123',
            name=None
        )
        
        save_connected_devices(test_db, 'device_token_test123', ['device1'])
        
        devices = get_connected_devices(test_db, 'device_token_test123')
        
        assert len(devices) == 1
        # None should be preserved
        assert devices[0]['name'] is None
    
    @pytest.mark.timeout(10)
    def test_connected_devices_dashboard_device_name(self, test_db):
        """Test that dashboard device shows 'Dashboard' as name in connected devices.
        
        This is a regression test for the issue where the dashboard device
        was showing its device ID (e.g., 'eR3IUu') instead of the friendly
        name 'Dashboard' in the connected devices section.
        """
        from config import Config
        
        # Create the dashboard device with the correct name
        create_device(
            db=test_db,
            device_id='eR3IUu',
            device_auth_token='dashboard_token',
            name=Config.DASHBOARD_DEVICE_NAME  # 'Dashboard'
        )
        
        # Save connected devices
        save_connected_devices(test_db, 'dashboard_token', ['eR3IUu'])
        
        # Get connected devices
        devices = get_connected_devices(test_db, 'dashboard_token')
        
        assert len(devices) == 1
        assert devices[0]['device_id'] == 'eR3IUu'
        assert devices[0]['name'] == Config.DASHBOARD_DEVICE_NAME


class TestLatestDeviceAuthToken:
    """Tests for get_latest_device_auth_token function."""
    
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
    def test_get_latest_device_auth_token_no_tokens(self, test_db):
        """Test getting latest device auth token when no tokens exist."""
        token = get_latest_device_auth_token(test_db)
        
        assert token is None
    
    @pytest.mark.timeout(10)
    def test_get_latest_device_auth_token_single_token(self, test_db):
        """Test getting latest device auth token with a single token."""
        store_auth_token(
            db=test_db,
            token_type='device_auth_token',
            token_value='test_token_123',
            device_id='device_test123'
        )
        
        token = get_latest_device_auth_token(test_db)
        
        assert token == 'test_token_123'
    
    @pytest.mark.timeout(10)
    def test_get_latest_device_auth_token_multiple_tokens(self, test_db):
        """Test getting latest device auth token with multiple tokens."""
        # Store multiple tokens
        store_auth_token(
            db=test_db,
            token_type='device_auth_token',
            token_value='old_token',
            device_id='device1'
        )
        
        store_auth_token(
            db=test_db,
            token_type='device_auth_token',
            token_value='new_token',
            device_id='device2'
        )
        
        token = get_latest_device_auth_token(test_db)
        
        # Should return the most recent token
        assert token == 'new_token'
    
    @pytest.mark.timeout(10)
    def test_get_latest_device_auth_token_ignores_other_token_types(self, test_db):
        """Test that get_latest_device_auth_token only returns device_auth_token type."""
        # Store a different type of token
        store_auth_token(
            db=test_db,
            token_type='mail_auth_token',
            token_value='mail_token_123',
            device_id='device_test123'
        )
        
        token = get_latest_device_auth_token(test_db)
        
        # Should return None since no device_auth_token exists
        assert token is None


class TestLatestOwnDeviceId:
    """Tests for get_latest_own_device_id function."""
    
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
    def test_get_latest_own_device_id_no_devices(self, test_db):
        """Test getting latest own device ID when no devices exist."""
        device_id = get_latest_own_device_id(test_db)
        
        assert device_id is None
    
    @pytest.mark.timeout(10)
    def test_get_latest_own_device_id_single_device(self, test_db):
        """Test getting latest own device ID with a single device."""
        create_device(
            db=test_db,
            device_id='device_test123',
            device_auth_token='device_token_test123',
            name='Test Device'
        )
        
        device_id = get_latest_own_device_id(test_db)
        
        assert device_id == 'device_test123'
    
    @pytest.mark.timeout(10)
    def test_get_latest_own_device_id_multiple_devices(self, test_db):
        """Test getting latest own device ID with multiple devices."""
        # Create multiple devices
        create_device(
            db=test_db,
            device_id='device1',
            device_auth_token='device_token_test123',
            name='Device 1'
        )
        
        create_device(
            db=test_db,
            device_id='device2',
            device_auth_token='device_token_test123',
            name='Device 2'
        )
        
        device_id = get_latest_own_device_id(test_db)
        
        # Should return the most recently created device
        assert device_id == 'device2'


class TestDeleteAllDeviceAuthTokens:
    """Tests for delete_all_device_auth_tokens function."""
    
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
    def test_delete_all_device_auth_tokens(self, test_db):
        """Test deleting all device auth tokens."""
        # Store multiple tokens
        store_auth_token(
            db=test_db,
            token_type='device_auth_token',
            token_value='token1',
            device_id='device1'
        )
        
        store_auth_token(
            db=test_db,
            token_type='device_auth_token',
            token_value='token2',
            device_id='device2'
        )
        
        # Verify tokens exist
        tokens = get_device_auth_tokens(test_db)
        assert len(tokens) == 2
        
        # Delete all device auth tokens
        count = delete_all_device_auth_tokens(test_db)
        
        assert count == 2
        
        # Verify tokens are deleted
        tokens = get_device_auth_tokens(test_db)
        assert len(tokens) == 0
    
    @pytest.mark.timeout(10)
    def test_delete_all_device_auth_tokens_empty(self, test_db):
        """Test deleting all device auth tokens when none exist."""
        count = delete_all_device_auth_tokens(test_db)
        
        assert count == 0
    
    @pytest.mark.timeout(10)
    def test_delete_all_device_auth_tokens_preserves_other_tokens(self, test_db):
        """Test that delete_all_device_auth_tokens only deletes device_auth_token type."""
        # Store a device auth token
        store_auth_token(
            db=test_db,
            token_type='device_auth_token',
            token_value='device_token',
            device_id='device1'
        )
        
        # Store a different type of token
        store_auth_token(
            db=test_db,
            token_type='mail_auth_token',
            token_value='mail_token',
            device_id='device1'
        )
        
        # Delete all device auth tokens
        delete_all_device_auth_tokens(test_db)
        
        # Verify device auth token is deleted
        tokens = get_device_auth_tokens(test_db)
        assert len(tokens) == 0
        
        # Verify mail auth token still exists
        mail_token = get_auth_token(test_db, 'mail_token')
        assert mail_token is not None
        assert mail_token['token_type'] == 'mail_auth_token'


class TestValidatePasswordHash:
    """Tests for validate_password_hash function."""
    
    @pytest.mark.timeout(10)
    def test_valid_hash_2a(self):
        """Test that valid $2a$ hash returns True."""
        assert validate_password_hash('$2a$12$testhash123') is True
    
    @pytest.mark.timeout(10)
    def test_valid_hash_2b(self):
        """Test that valid $2b$ hash returns True."""
        assert validate_password_hash('$2b$12$testhash123') is True
    
    @pytest.mark.timeout(10)
    def test_valid_hash_2y(self):
        """Test that valid $2y$ hash returns True."""
        assert validate_password_hash('$2y$12$testhash123') is True
    
    @pytest.mark.timeout(10)
    def test_invalid_hash_wrong_prefix(self):
        """Test that invalid hash (wrong prefix) returns False."""
        assert validate_password_hash('$3a$12$testhash123') is False
        assert validate_password_hash('$2c$12$testhash123') is False
    
    @pytest.mark.timeout(10)
    def test_empty_string(self):
        """Test that empty string returns False."""
        assert validate_password_hash('') is False
    
    @pytest.mark.timeout(10)
    def test_none_value(self):
        """Test that None returns False."""
        assert validate_password_hash(None) is False
    
    @pytest.mark.timeout(10)
    def test_too_short_string(self):
        """Test that too short string returns False."""
        assert validate_password_hash('$2a$') is False
        assert validate_password_hash('short') is False


class TestGetFamilyWithValidHash:
    """Tests for get_family_with_valid_hash function."""
    
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
    def test_returns_family_with_valid_hash(self, test_db):
        """Test that get_family_with_valid_hash returns family when valid hash exists."""
        create_family(
            db=test_db,
            device_auth_token='device_token_test123',
            mail='test@example.com',
            parent_password_hash='$2b$12$hash12345678',
            parent_password_second_hash='$2b$12$hash22345678',
            parent_password_second_salt='$2b$12$salt12345678',
            parent_password_encrypted=False
        )
        
        family = get_family_with_valid_hash(test_db, 'device_token_test123')
        
        assert family is not None
        assert family['mail'] == 'test@example.com'
        assert family['parent_password_second_hash'] == '$2b$12$hash22345678'
    
    @pytest.mark.timeout(10)
    def test_returns_none_when_family_not_found(self, test_db):
        """Test that get_family_with_valid_hash returns None when family doesn't exist."""
        family = get_family_with_valid_hash(test_db, 'nonexistent_token')
        
        assert family is None
    
    @pytest.mark.timeout(10)
    def test_returns_none_when_hash_is_invalid(self, test_db):
        """Test that get_family_with_valid_hash returns None when hash is invalid."""
        create_family(
            db=test_db,
            device_auth_token='device_token_test123',
            mail='test@example.com',
            parent_password_hash='$2b$12$hash1',
            parent_password_second_hash='invalid_hash',
            parent_password_second_salt='$2b$12$salt',
            parent_password_encrypted=False
        )
        
        family = get_family_with_valid_hash(test_db, 'device_token_test123')
        
        assert family is None
    
    @pytest.mark.timeout(10)
    def test_returns_none_when_hash_is_none(self, test_db):
        """Test that get_family_with_valid_hash returns None when hash is None."""
        create_family(
            db=test_db,
            device_auth_token='device_token_test123',
            mail='test@example.com',
            parent_password_hash='$2b$12$hash1',
            parent_password_second_hash=None,
            parent_password_second_salt='$2b$12$salt',
            parent_password_encrypted=False
        )
        
        family = get_family_with_valid_hash(test_db, 'device_token_test123')
        
        assert family is None


class TestClearFamilyPasswordHash:
    """Tests for clear_family_password_hash function."""
    
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
    def test_clears_hash_successfully(self, test_db):
        """Test that clear_family_password_hash clears the hash."""
        create_family(
            db=test_db,
            device_auth_token='device_token_test123',
            mail='test@example.com',
            parent_password_hash='$2b$12$hash1',
            parent_password_second_hash='$2b$12$hash2',
            parent_password_second_salt='$2b$12$salt',
            parent_password_encrypted=False
        )
        
        result = clear_family_password_hash(test_db, 'device_token_test123')
        
        assert result is True
        
        # Verify hash is cleared
        family = get_family(test_db, 'device_token_test123')
        assert family['parent_password_second_hash'] is None
    
    @pytest.mark.timeout(10)
    def test_returns_false_when_family_not_found(self, test_db):
        """Test that clear_family_password_hash returns False when family doesn't exist."""
        result = clear_family_password_hash(test_db, 'nonexistent_token')
        
        assert result is False


class TestHasParentPasswordHash:
    """Tests for has_parent_password_hash function."""
    
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
    def test_returns_true_when_valid_hash_exists(self, test_db):
        """Test that has_parent_password_hash returns True when valid hash exists."""
        create_family(
            db=test_db,
            device_auth_token='device_token_test123',
            mail='test@example.com',
            parent_password_hash='$2b$12$hash12345678',
            parent_password_second_hash='$2b$12$hash22345678',
            parent_password_second_salt='$2b$12$salt12345678',
            parent_password_encrypted=False
        )
        
        result = has_parent_password_hash(test_db, 'device_token_test123')
        
        assert result is True
    
    @pytest.mark.timeout(10)
    def test_returns_false_when_family_not_found(self, test_db):
        """Test that has_parent_password_hash returns False when family doesn't exist."""
        result = has_parent_password_hash(test_db, 'nonexistent_token')
        
        assert result is False
    
    @pytest.mark.timeout(10)
    def test_returns_false_when_hash_is_invalid(self, test_db):
        """Test that has_parent_password_hash returns False when hash is invalid."""
        create_family(
            db=test_db,
            device_auth_token='device_token_test123',
            mail='test@example.com',
            parent_password_hash='$2b$12$hash1',
            parent_password_second_hash='invalid_hash',
            parent_password_second_salt='$2b$12$salt',
            parent_password_encrypted=False
        )
        
        result = has_parent_password_hash(test_db, 'device_token_test123')
        
        assert result is False
    
    @pytest.mark.timeout(10)
    def test_returns_false_when_hash_is_none(self, test_db):
        """Test that has_parent_password_hash returns False when hash is None."""
        create_family(
            db=test_db,
            device_auth_token='device_token_test123',
            mail='test@example.com',
            parent_password_hash='$2b$12$hash1',
            parent_password_second_hash=None,
            parent_password_second_salt='$2b$12$salt',
            parent_password_encrypted=False
        )
        
        result = has_parent_password_hash(test_db, 'device_token_test123')
        
        assert result is False


class TestUpsertFamilyPasswordHashWithMail:
    """Tests for upsert_family_password_hash with optional mail parameter."""
    
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
    def test_upsert_with_mail_parameter(self, test_db):
        """Test that upsert_family_password_hash accepts optional mail parameter."""
        result = upsert_family_password_hash(
            db=test_db,
            device_auth_token='device_token_test123',
            parent_password_second_hash='$2b$12$hash1',
            mail='test@example.com'
        )
        
        assert result is True
        
        # Verify family was created with correct mail
        family = get_family(test_db, 'device_token_test123')
        assert family is not None
        assert family['mail'] == 'test@example.com'
        assert family['parent_password_second_hash'] == '$2b$12$hash1'
    
    @pytest.mark.timeout(10)
    def test_upsert_without_mail_uses_placeholder(self, test_db):
        """Test that upsert_family_password_hash uses placeholder when mail not provided."""
        result = upsert_family_password_hash(
            db=test_db,
            device_auth_token='device_token_test123',
            parent_password_second_hash='$2b$12$hash1'
        )
        
        assert result is True
        
        # Verify family was created with placeholder mail
        family = get_family(test_db, 'device_token_test123')
        assert family is not None
        assert family['mail'] == 'pending@unknown'
        assert family['parent_password_second_hash'] == '$2b$12$hash1'
    
    @pytest.mark.timeout(10)
    def test_upsert_updates_existing_family_with_mail(self, test_db):
        """Test that upsert updates existing family and preserves mail."""
        # First create a family
        create_family(
            db=test_db,
            device_auth_token='device_token_test123',
            mail='original@example.com',
            parent_password_hash='$2b$12$hash1',
            parent_password_second_hash='$2b$12$oldhash',
            parent_password_second_salt='$2b$12$salt',
            parent_password_encrypted=False
        )
        
        # Now upsert with new hash and different mail
        result = upsert_family_password_hash(
            db=test_db,
            device_auth_token='device_token_test123',
            parent_password_second_hash='$2b$12$newhash',
            mail='new@example.com'
        )
        
        assert result is True
        
        # Verify hash was updated but mail was preserved (UPDATE doesn't change mail)
        family = get_family(test_db, 'device_token_test123')
        assert family['parent_password_second_hash'] == '$2b$12$newhash'
        # Note: UPDATE doesn't change mail, so it should still be original
        assert family['mail'] == 'original@example.com'


class TestClearAllTables:
    """Tests for clear_all_tables function."""
    
    @pytest.fixture
    def test_db(self):
        """Create a test database with sample data."""
        db_fd, db_path = tempfile.mkstemp(suffix='.db')
        db = Database(db_path=db_path)
        db.init_db()
        
        # Add sample data to each table
        device_auth_token = 'test_device_token_123'
        
        # Add family
        create_family(
            db=db,
            device_auth_token=device_auth_token,
            mail='test@example.com',
            parent_password_hash='$2b$12$hash1',
            parent_password_second_hash='$2b$12$hash2',
            parent_password_second_salt='$2b$12$salt',
            parent_password_encrypted=False
        )
        
        # Add device
        create_device(
            db=db,
            device_id='device_1',
            device_auth_token=device_auth_token,
            name='Test Device',
            model='Test Model'
        )
        
        # Add user
        save_users(db, device_auth_token, [
            {'id': 'user_1', 'name': 'Parent', 'type': 'parent', 'mail': 'parent@example.com'}
        ])
        
        # Add category
        save_categories(db, device_auth_token, [
            {'id': 'cat_1', 'title': 'Test Category'}
        ])
        
        # Add sync state
        save_sync_state(db, device_auth_token, 'v1', 'v1')
        
        # Add server check
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
        
        # Add auth token
        store_auth_token(
            db=db,
            token_type='device_auth_token',
            token_value=device_auth_token,
            device_id='device_1'
        )
        
        yield db
        db.close()
        os.close(db_fd)
        os.unlink(db_path)
    
    @pytest.mark.timeout(10)
    def test_clear_all_tables_removes_all_data(self, test_db):
        """Test that clear_all_tables removes all data from all tables."""
        # Verify data exists before clearing
        families = get_family(test_db, 'test_device_token_123')
        assert families is not None
        
        devices = get_devices_by_device_auth_token(test_db, 'test_device_token_123')
        assert len(devices) > 0
        
        users = get_users_by_device_auth_token(test_db, 'test_device_token_123')
        assert len(users) > 0
        
        categories = get_categories_by_device_auth_token(test_db, 'test_device_token_123')
        assert len(categories) > 0
        
        sync_state = get_sync_state(test_db, 'test_device_token_123')
        assert sync_state is not None
        
        checks = get_server_checks(test_db, limit=10)
        assert len(checks) > 0
        
        # Clear all tables
        results = clear_all_tables(test_db)
        
        # Verify all tables are empty
        families = get_family(test_db, 'test_device_token_123')
        assert families is None
        
        devices = get_devices_by_device_auth_token(test_db, 'test_device_token_123')
        assert len(devices) == 0
        
        users = get_users_by_device_auth_token(test_db, 'test_device_token_123')
        assert len(users) == 0
        
        categories = get_categories_by_device_auth_token(test_db, 'test_device_token_123')
        assert len(categories) == 0
        
        sync_state = get_sync_state(test_db, 'test_device_token_123')
        assert sync_state is None
        
        checks = get_server_checks(test_db, limit=10)
        assert len(checks) == 0
    
    @pytest.mark.timeout(10)
    def test_clear_all_tables_returns_row_counts(self, test_db):
        """Test that clear_all_tables returns correct row counts."""
        results = clear_all_tables(test_db)
        
        # Verify results is a dictionary
        assert isinstance(results, dict)
        
        # Verify all expected tables are in results
        expected_tables = [
            'connected_devices', 'categories', 'sync_state', 'users',
            'auth_tokens', 'devices', 'families', 'server_checks'
        ]
        for table in expected_tables:
            assert table in results
            assert isinstance(results[table], int)
    
    @pytest.mark.timeout(10)
    def test_clear_all_tables_preserves_schema(self, test_db):
        """Test that clear_all_tables preserves the database schema."""
        # Clear all tables
        clear_all_tables(test_db)
        
        # Verify tables still exist by checking we can query them
        conn = test_db.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        tables = [row[0] for row in cursor.fetchall()]
        
        expected_tables = [
            'server_checks', 'families', 'devices', 'auth_tokens',
            'users', 'sync_state', 'categories', 'connected_devices'
        ]
        for table in expected_tables:
            assert table in tables
    
    @pytest.mark.timeout(10)
    def test_clear_all_tables_idempotent(self, test_db):
        """Test that clear_all_tables can be called multiple times safely."""
        # Clear all tables twice
        results1 = clear_all_tables(test_db)
        results2 = clear_all_tables(test_db)
        
        # Both should succeed
        assert isinstance(results1, dict)
        assert isinstance(results2, dict)
        
        # Second call should return 0 for all tables
        for table, count in results2.items():
            assert count == 0
    
    @pytest.mark.timeout(10)
    def test_clear_all_tables_clears_connected_devices(self, test_db):
        """Test that clear_all_tables clears connected_devices table."""
        # Add connected device
        save_connected_devices(test_db, 'test_device_token_123', ['device_1'])
        
        # Verify it exists
        connected = get_connected_devices(test_db, 'test_device_token_123')
        assert len(connected) > 0
        
        # Clear all tables
        clear_all_tables(test_db)
        
        # Verify connected devices are cleared
        connected = get_connected_devices(test_db, 'test_device_token_123')
        assert len(connected) == 0
    
    @pytest.mark.timeout(10)
    def test_clear_all_tables_clears_auth_tokens(self, test_db):
        """Test that clear_all_tables clears auth_tokens table."""
        # Verify auth tokens exist
        tokens = get_device_auth_tokens(test_db)
        assert len(tokens) > 0
        
        # Clear all tables
        clear_all_tables(test_db)
        
        # Verify auth tokens are cleared
        tokens = get_device_auth_tokens(test_db)
        assert len(tokens) == 0