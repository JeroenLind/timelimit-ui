"""Pytest fixtures for the debug server tests.

This module provides shared fixtures for all test modules.
"""

import os
import sys

# Set required environment variables before importing the app
# This is needed because pydantic_settings looks for .env relative to cwd
# which may not be the debug-server directory when running pytest
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-pytest-testing-min-32-chars")
os.environ.setdefault("JWT_ALGORITHM", "HS256")
os.environ.setdefault("ACCESS_TOKEN_EXPIRE_MINUTES", "60")
os.environ.setdefault("BCRYPT_COST", "12")
os.environ.setdefault("TEST_MODE", "true")

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client() -> TestClient:
    """Create a test client for the FastAPI application.
    
    Returns:
        TestClient: A test client instance for making requests to the app.
    """
    return TestClient(app)


@pytest.fixture
def test_user() -> dict:
    """Provide a sample user dictionary for testing.
    
    Returns:
        dict: A dictionary containing test user data with email and password.
    """
    return {
        "email": "testuser@example.com",
        "password": "testpassword123",
    }