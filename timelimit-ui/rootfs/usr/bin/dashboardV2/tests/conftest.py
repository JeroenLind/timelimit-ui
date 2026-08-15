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

from app import app as flask_app
from config import Config
from database import Database, reset_database


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
def client(app):
    """Create a test client for the Flask application.
    
    Args:
        app: Flask application fixture.
        
    Returns:
        Flask test client instance.
    """
    # Initialize database for tests that need it
    from database import get_database
    db = get_database()
    db.init_db()
    
    return app.test_client()


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