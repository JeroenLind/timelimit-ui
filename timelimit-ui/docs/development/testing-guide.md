# Testing Guide

## Table of Contents

1. [Overview](#overview)
2. [Test Structure](#test-structure)
3. [Pytest Configuration](#pytest-configuration)
4. [Test Patterns](#test-patterns)
5. [Test Data Management](#test-data-management)
6. [Running Tests](#running-tests)
7. [Test Categories](#test-categories)
8. [Mocking External Services](#mocking-external-services)
9. [Test Fixtures](#test-fixtures)
10. [Best Practices](#best-practices)
11. [Continuous Integration](#continuous-integration)

---

## Overview

This document describes the testing patterns and practices used in Dashboard V2. The project uses pytest as the testing framework with comprehensive test coverage for all components.

### Test Statistics

- **Total Tests**: 1028 tests passing
- **Test Framework**: pytest
- **Coverage**: High coverage across all modules
- **Test Types**: Unit, Integration, and End-to-End tests

---

## Test Structure

Tests are organized by component:

```
tests/
├── conftest.py           # Pytest fixtures
├── pytest.ini            # Pytest configuration
├── test_create_family.py # Create family flow tests
├── test_login_as_parent.py # Login as parent tests
├── test_dashboard_api.py # Dashboard API tests
├── test_database.py      # Database operation tests
├── test_sync_manager.py  # Sync manager tests
├── test_auth_client.py   # Auth client tests
├── test_scheduler.py     # Scheduler tests
├── test_key_manager.py   # Key manager tests
├── test_persistence.py   # Persistence tests
├── test_audit_log.py     # Audit log tests
├── test_logging.py       # Logging tests
└── ...
```

### Test File Naming Convention

- `test_*.py` - Test files
- `Test*` - Test classes
- `test_*` - Test functions

---

## Pytest Configuration

### pytest.ini

```ini
[pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
addopts = -v --tb=short --timeout=30
```

### conftest.py

```python
import pytest
from app import app, db


@pytest.fixture
def client():
    """Create a test client for the app."""
    app.config["TESTING"] = True
    with app.test_client() as client:
        with app.app_context():
            yield client


@pytest.fixture
def db():
    """Get database instance."""
    return get_database()
```

---

## Test Patterns

### API Endpoint Tests

```python
def test_get_session_status(client):
    """Test session status endpoint."""
    response = client.get("/api/session/status")
    assert response.status_code == 200
    data = response.get_json()
    assert "authenticated" in data
    assert "server_url" in data


def test_get_session_status_unauthenticated(client):
    """Test session status when not authenticated."""
    response = client.get("/api/session/status")
    data = response.get_json()
    assert data["authenticated"] == False
```

### Database Operation Tests

```python
def test_create_family(db):
    """Test family creation."""
    device_auth_token = "test_token_123"
    mail = "test@example.com"

    create_family(
        db=db,
        device_auth_token=device_auth_token,
        mail=mail,
        parent_password_hash="$2a$10$hash1",
        parent_password_second_hash="$2a$10$hash2",
        parent_password_second_salt="salt123",
    )

    family = get_family(db, device_auth_token)
    assert family is not None
    assert family["mail"] == mail
```

### Authentication Flow Tests

```python
def test_create_family_flow(client):
    """Test complete create family flow."""
    # Step 1: Send mail login code
    response = client.post(
        "/create-family", data={"step": "1", "mail": "test@example.com"}
    )
    assert response.status_code == 302  # Redirect

    # Step 2: Sign in by mail code
    with client.session_transaction() as sess:
        sess["mail_login_token"] = "test_token"

    response = client.post(
        "/create-family", data={"step": "2", "receivedCode": "word1 word2 word3"}
    )
    assert response.status_code == 302
```

---

## Test Data Management

### Test Data Files

Test data is stored in JSON files:

- `test_data.json` - General test data
- `test_create_family.json` - Create family test cases
- `test_sign_in.json` - Sign in test cases

### Example Test Data

```json
{
    "valid_family": {
        "mail": "parent@example.com",
        "password": "securepassword123",
        "device_name": "Test Device",
        "device_model": "Test Model"
    },
    "invalid_inputs": [
        {"mail": "", "expected_error": "Email is required"},
        {"mail": "invalid", "expected_error": "Invalid email format"}
    ]
}
```

---

## Running Tests

### Run All Tests

```bash
cd timelimit-ui/rootfs/usr/bin/dashboardV2
python -m pytest tests/ -v
```

### Run Specific Test File

```bash
python -m pytest tests/test_create_family.py -v
```

### Run Specific Test

```bash
python -m pytest tests/test_create_family.py::test_create_family_success -v
```

### Run with Coverage

```bash
python -m pytest tests/ --cov=app --cov-report=html
```

### Run with Timeout

```bash
python -m pytest tests/ --timeout=30
```

---

## Test Categories

### Unit Tests

Test individual functions and methods in isolation.

```python
def test_format_days():
    """Test days bitmask formatting."""
    assert formatDays(127) == "Every day"
    assert formatDays(1) == "Mon"
    assert formatDays(3) == "Mon, Tue"
```

### Integration Tests

Test complete workflows and API endpoints.

```python
def test_full_sign_in_flow(client):
    """Test complete sign in flow."""
    # Create family first
    # Then sign in
    # Verify session is established
```

### End-to-End Tests

Test complete user journeys from UI to API.

```python
def test_e2e_create_family_and_sync(client):
    """Test E2E: Create family and verify sync."""
    # 1. Create family
    # 2. Verify device auth token stored
    # 3. Trigger sync
    # 4. Verify users/devices loaded
```

---

## Mocking External Services

### Mock AuthClient

```python
from unittest.mock import patch, MagicMock


@patch("app.AuthClient")
def test_api_time_with_mock(mock_client_class, client):
    """Test time API with mocked AuthClient."""
    mock_client = MagicMock()
    mock_client_class.return_value = mock_client

    mock_response = MagicMock()
    mock_response.success = True
    mock_response.data = {"ms": 1234567890}
    mock_client.get_server_time.return_value = mock_response

    response = client.post("/api/time")
    assert response.status_code == 200
    assert response.get_json()["status"] == "ok"
```

---

## Test Fixtures

### Common Fixtures

```python
@pytest.fixture
def authenticated_client(client):
    """Client with authenticated session."""
    with client.session_transaction() as sess:
        sess["device_auth_token"] = "test_token"
        sess["own_device_id"] = "device_123"
    return client


@pytest.fixture
def sample_user():
    """Sample user data."""
    return {"id": "user_123", "name": "Test User", "type": "child", "mail": None}
```

---

## Best Practices

1. **Use descriptive test names**: `test_function_name_condition`
2. **Test edge cases**: Empty inputs, invalid data, missing fields
3. **Clean up test data**: Use fixtures with teardown
4. **Mock external services**: Don't make real API calls in tests
5. **Test both success and failure paths**
6. **Use parameterized tests** for multiple test cases
7. **Keep tests independent**: Don't rely on test execution order
8. **Use timeouts** for async operations

### Parameterized Test Example

```python
import pytest


@pytest.mark.parametrize(
    "days,expected",
    [
        (127, "Every day"),
        (1, "Mon"),
        (3, "Mon, Tue"),
        (64, "Sun"),
    ],
)
def test_format_days_parameterized(days, expected):
    """Test days formatting with multiple inputs."""
    assert formatDays(days) == expected
```

---

## Continuous Integration

Tests should be run in CI with:

```bash
python -m pytest tests/ -v --tb=short
```

Expected output: All tests passing with no warnings or errors.

### CI Pipeline Example

```yaml
# .github/workflows/test.yml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.10'
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install pytest pytest-cov pytest-timeout
      - name: Run tests
        run: |
          python -m pytest tests/ -v --tb=short --timeout=30