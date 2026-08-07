"""Test configuration for TimeLimit API.

This module provides configuration settings for testing.
"""

import os
from typing import Optional


class TestConfig:
    """Test configuration settings."""
    
    # Server settings
    BASE_URL: str = os.getenv("TEST_BASE_URL", "http://localhost:8080")
    TIMEOUT: int = int(os.getenv("TEST_TIMEOUT", "30"))
    VERIFY_SSL: bool = os.getenv("TEST_VERIFY_SSL", "true").lower() == "true"
    
    # Test data settings
    TEST_MAIL: str = os.getenv("TEST_MAIL", "test@example.com")
    TEST_PASSWORD: str = os.getenv("TEST_PASSWORD", "test_password_123")
    TEST_DEVICE_NAME: str = os.getenv("TEST_DEVICE_NAME", "Test Device")
    TEST_DEVICE_MODEL: str = os.getenv("TEST_DEVICE_MODEL", "Pixel 7")
    
    # Mock data settings
    MOCK_DATA_SEED: int = int(os.getenv("MOCK_DATA_SEED", "42"))
    
    # Test mode
    TEST_MODE: bool = os.getenv("TEST_MODE", "true").lower() == "true"
    
    # Logging settings
    LOG_LEVEL: str = os.getenv("TEST_LOG_LEVEL", "INFO")
    
    @classmethod
    def get_test_mail(cls) -> str:
        """Get test email address."""
        return cls.TEST_MAIL
    
    @classmethod
    def get_test_password(cls) -> str:
        """Get test password."""
        return cls.TEST_PASSWORD
    
    @classmethod
    def get_base_url(cls) -> str:
        """Get base URL for tests."""
        return cls.BASE_URL
    
    @classmethod
    def get_timeout(cls) -> int:
        """Get request timeout."""
        return cls.TIMEOUT


# Global test config instance
test_config = TestConfig()


def get_test_config() -> TestConfig:
    """Get the test configuration instance.
    
    Returns:
        TestConfig instance.
    """
    return test_config