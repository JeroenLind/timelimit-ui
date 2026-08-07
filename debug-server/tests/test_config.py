"""Unit tests for environment configuration and settings.

This module tests the configuration management using environment variables
and Pydantic settings.
"""

import pytest
from app.core.config import settings


def test_settings_loaded():
    """Verify that the settings object is properly loaded and not None."""
    assert settings is not None
    assert isinstance(settings, object)


def test_project_name():
    """Check that PROJECT_NAME is set to 'Debug Server'."""
    assert settings.PROJECT_NAME == "Debug Server"


def test_api_v1_str():
    """Check that API_V1_STR is set to '/api/v1'."""
    assert settings.API_V1_STR == "/api/v1"


def test_log_level():
    """Check that LOG_LEVEL is set to 'INFO'."""
    assert settings.LOG_LEVEL == "INFO"


def test_log_file_path():
    """Check that LOG_FILE_PATH is set to 'logs/debug-server.log'."""
    assert settings.LOG_FILE_PATH == "logs/debug-server.log"


def test_enable_https():
    """Check that ENABLE_HTTPS is set to False."""
    assert settings.ENABLE_HTTPS is False


def test_bcrypt_cost():
    """Check that BCRYPT_COST is set to 12."""
    assert settings.BCRYPT_COST == 12


def test_access_token_expire_minutes():
    """Check that ACCESS_TOKEN_EXPIRE_MINUTES is set to 60."""
    assert settings.ACCESS_TOKEN_EXPIRE_MINUTES == 60