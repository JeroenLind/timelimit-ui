"""Pytest fixtures for dashboardV2 tests.

This module provides shared fixtures for all test modules.
"""

import os
import sys
import tempfile

import pytest
from flask import Flask

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# CRITICAL: Set environment variables BEFORE any imports that trigger setup_structlog()
# This must be done at module level, before any test files are loaded
tests_dir = os.path.dirname(os.path.abspath(__file__))
log_dir = os.path.join(tests_dir, 'logs')

# Ensure the logs directory exists
os.makedirs(log_dir, exist_ok=True)

# Set environment variables for test logging
os.environ['LOG_FILE_PATH'] = os.path.join(log_dir, 'dashboardV2.log')
os.environ['LOG_WERKZEUG_FILE_PATH'] = os.path.join(log_dir, 'werkzeug.log')
os.environ['LOG_ROTATE_ON_START'] = 'false'  # Use fixed filename for tests
os.environ['LOG_LEVEL'] = 'INFO'  # Default log level for tests

# Set DATABASE_PATH to a test database BEFORE any imports
# This ensures the real dashboardV2.db is never used during tests
os.environ['DATABASE_PATH'] = os.path.join(tests_dir, 'test_isolation.db')

# Skip port check during testing to allow module import
os.environ['SKIP_PORT_CHECK'] = 'true'


def pytest_configure(config):
    """Configure test environment before any imports or collection.
    
    This hook runs before any test modules are imported, allowing us to
    set environment variables that affect logging configuration before
    the app module is loaded.
    
    IMPORTANT: DATABASE_PATH must be set BEFORE any imports to ensure
    the real database is never used during test collection or import.
    """
    # Environment variables are already set at module level above
    # This hook is kept for potential future use and for pytest to call
    pass


# Import app and other modules after environment variables are set
from app import app as flask_app
from config import Config
from database import Database, reset_database, create_family, store_auth_token


@pytest.fixture
def app():
    """Create a Flask application for testing.
    
    Returns:
        Flask application instance configured for testing.
    """
    flask_app.config['TESTING'] = True
    flask_app.config['SECRET_KEY'] = 'test-secret-key-for-testing'
    flask_app.config['WTF_CSRF_ENABLED'] = False
    
    yield flask_app


@pytest.fixture
def client(app, request):
    """Create a test client for the Flask application.
    
    Args:
        app: Flask application fixture.
        
    Returns:
        Flask test client instance.
    """
    # Use a unique database path for each test
    test_name = request.node.name
    db_path = os.path.abspath(os.path.join(os.path.dirname(__file__), f'test_client_{test_name}.db'))
    
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
    
    # Create a new database instance with the unique path
    db = Database(db_path=db_path)
    db.init_db()
    
    # Store the db instance in the app for later use
    app.test_db = db
    
    # Update the global database singleton to use the test database
    import database as db_module
    db_module._db_instance = db
    
    # Clear persistence file to ensure clean session state
    from persistence import get_persistence_dir, clear_persisted_auth_tokens
    persistence_dir = get_persistence_dir()
    persistence_file = os.path.join(persistence_dir, 'server_selection.json')
    if os.path.exists(persistence_file):
        try:
            os.unlink(persistence_file)
        except OSError:
            pass
    clear_persisted_auth_tokens()
    
    # Mock persistence functions for non-restoration tests to ensure clean state
    from unittest.mock import patch
    is_restoration_test = request.cls and request.cls.__name__ in ['TestSessionRestoration', 'TestSessionRestorationAfterSignOut']
    
    if not is_restoration_test:
        with patch('app.get_persisted_device_auth_token', return_value=None), \
             patch('app.get_persisted_own_device_id', return_value=None):
            yield app.test_client()
    else:
        yield app.test_client()
    
    # Cleanup: close database and remove file
    db.close()
    if os.path.exists(db_path):
        try:
            os.unlink(db_path)
        except PermissionError:
            pass
    
    # Restore original environment
    if 'DATABASE_PATH' in os.environ:
        del os.environ['DATABASE_PATH']
    
    # Reset database singleton after test
    reset_database()


@pytest.fixture
def auth_session(client, request):
    """Create an authenticated session for testing.
    
    Args:
        client: Flask test client fixture.
        
    Returns:
        Flask test client with authenticated session.
    """
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


@pytest.fixture
def runner(app):
    """Create a test CLI runner for the Flask application.
    
    Args:
        app: Flask application fixture.
        
    Returns:
        Flask CLI test runner instance.
    """
    return app.test_cli_runner()


@pytest.fixture
def test_db():
    """Create a test database with a temporary file.
    
    Returns:
        Database instance with temporary database.
    """
    # Create a temporary database file
    db_fd, db_path = tempfile.mkstemp(suffix='.db')
    
    # Create database instance with temp path
    db = Database(db_path=db_path)
    db.init_db()
    
    yield db
    
    # Cleanup
    db.close()
    os.close(db_fd)
    os.unlink(db_path)


@pytest.fixture
def test_database_factory(tmp_path):
    """Factory fixture that provides isolated test databases.
    
    This fixture provides a factory function that creates new test databases
    with unique paths. Each database is isolated and automatically cleaned up
    when the tmp_path fixture is cleaned up.
    
    Yields:
        A function that creates a new test database when called.
        Usage: db, db_path = test_database_factory('my_test_db')
    
    Example:
        def test_something(test_database_factory):
            db, db_path = test_database_factory('test_something')
            # Use db for testing
            # Database is automatically cleaned up
    """
    def _create_test_db(db_name='test_db'):
        """Create a new test database with a unique name.
        
        Args:
            db_name: Name for the database file (without .db extension).
                     Defaults to 'test_db'.
        
        Returns:
            Tuple of (Database instance, database path string).
        """
        db_path = str(tmp_path / f'{db_name}.db')
        reset_database()
        db = Database(db_path=db_path)
        db.init_db()
        return db, db_path
    
    yield _create_test_db
    
    # Cleanup: reset the singleton after all tests using this factory
    reset_database()


@pytest.fixture
def test_config():
    """Create a test configuration.
    
    Returns:
        Test configuration instance.
    """
    # Set test environment variables
    os.environ['DEBUG_SERVER_URL'] = 'http://192.168.68.30:8080'
    os.environ['FLASK_HOST'] = '127.0.0.1'
    os.environ['FLASK_PORT'] = '8099'
    os.environ['DATABASE_PATH'] = ':memory:'
    os.environ['SECRET_KEY'] = 'test-secret-key-for-testing'
    
    yield Config
    
    # Cleanup
    for key in ['DEBUG_SERVER_URL', 'FLASK_HOST', 'FLASK_PORT', 'DATABASE_PATH', 'SECRET_KEY']:
        if key in os.environ:
            del os.environ[key]


@pytest.fixture
def reset_db():
    """Reset the database before each test.
    
    Returns:
        Function to reset the database.
    """
    def _reset():
        reset_database()
    
    yield _reset
    
    # Cleanup after test
    reset_database()


@pytest.fixture
def sample_server_check():
    """Create sample server check data.
    
    Returns:
        Dictionary with sample server check data.
    """
    return {
        'timestamp': 1704067200000,  # 2024-01-01 00:00:00 UTC in ms
        'success': True,
        'error_code': None,
        'user_message': None,
        'technical_detail': None,
        'server_time': 1704067200000,
        'attempts': 1,
        'server_url': 'http://192.168.68.30:8080'
    }


@pytest.fixture
def sample_family():
    """Create sample family data.
    
    Returns:
        Dictionary with sample family data.
    """
    return {
        'family_id': 'family_test123',
        'mail': 'test@example.com',
        'parent_password_hash': '$2b$12$test_hash',
        'parent_password_second_hash': '$2b$12$test_second_hash',
        'parent_password_second_salt': '$2b$12$salt',
        'parent_password_encrypted': False
    }


@pytest.fixture
def sample_device():
    """Create sample device data.
    
    Returns:
        Dictionary with sample device data.
    """
    return {
        'device_id': 'device_test123',
        'family_id': 'family_test123',
        'name': 'Test Device',
        'model': 'Pixel 7',
        'current_user_id': 'family_test123',
        'current_protection_level': 0,
        'highest_protection_level': 0,
        'current_app_version': '1.0.0',
        'highest_app_version': '1.0.0',
        'public_key': '',
        'platform_type': 'android',
        'platform_level': 1
    }


@pytest.fixture
def sample_auth_token():
    """Create sample auth token data.
    
    Returns:
        Dictionary with sample auth token data.
    """
    return {
        'token_type': 'device_auth_token',
        'token_value': 'test_token_value_12345',
        'device_id': 'device_test123',
        'family_id': 'family_test123',
        'mail': 'test@example.com',
        'code': None
    }