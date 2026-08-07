# Testing Integration Documentation

This document describes the testing infrastructure for the TimeLimit debug server.

## Overview

The testing infrastructure provides:
- Test scenario definitions for automated testing
- Python test client for API interaction
- Test configuration management
- Pre-generated test fixtures
- Comprehensive test documentation

## Test Scenarios

Test scenarios are defined in JSON format in the `tests/scenarios/` directory.

### Available Scenarios

1. **auth_flow.json** - Complete authentication flow
   - Email login code generation
   - Code verification
   - Mail auth token management
   - Family creation
   - Device auth token generation
   - Sync status pull

2. **sync_flow.json** - Sync protocol flow
   - Push actions
   - Pull status
   - Report removed
   - Check device removal

3. **crypto_flow.json** - Cryptographic operations
   - Password hashing
   - JWT token generation/validation
   - HMAC calculation
   - Curve25519 key generation
   - AES-GCM encryption/decryption

4. **error_scenarios.json** - Error handling
   - Invalid tokens
   - Missing credentials
   - Invalid request bodies
   - Validation errors

## Test Client

The `tests/client.py` module provides a Python test client for interacting with the API.

### Usage

```python
from tests.client import TestClient

# Create client
client = TestClient(base_url="http://localhost:8080")

# Set authentication token
client.set_device_token("your_device_token")

# Make API calls
response = client.pull_status(
    device_auth_token="your_token",
    client_status={
        "clientLevel": 7,
        "devices": "",
        "users": "",
        "apps": {},
        "devicesDetail": {},
        "categories": {},
        "kri": 0,
        "kr": 0,
        "dh": "",
        "u2f": ""
    }
)

# Assertions
client.assert_status_ok(response)

# Close client
client.close()
```

### Available Methods

#### Health Check
- `get_health()` - GET /health
- `get_ready()` - GET /ready

#### Auth Endpoints
- `post_time()` - POST /time
- `send_mail_login_code(mail, locale)` - POST /auth/send-mail-login-code-v2
- `sign_in_by_mail_code(mail_login_token, received_code)` - POST /auth/sign-in-by-mail-code
- `get_status_by_mail_address(mail_auth_token)` - POST /parent/get-status-by-mail-address
- `create_family(mail_auth_token, parent_password, ...)` - POST /parent/create-family
- `sign_in_into_family(mail_auth_token, parent_password_second_hash, ...)` - POST /parent/sign-in-into-family
- `recover_parent_password(mail_auth_token, new_password)` - POST /parent/recover-parent-password

#### Sync Endpoints
- `push_actions(device_auth_token, actions)` - POST /sync/push-actions
- `pull_status(device_auth_token, client_status)` - POST /sync/pull-status
- `report_removed(device_auth_token)` - POST /sync/report-removed
- `is_device_removed(device_auth_token)` - POST /sync/is-device-removed

#### Parent Endpoints
- `create_add_device_token(device_auth_token, parent_id, parent_password_second_hash)` - POST /parent/create-add-device-token
- `remove_device(device_auth_token, device_id)` - POST /parent/remove-device
- `link_mail_address(device_auth_token, mail_auth_token)` - POST /parent/link-mail-address
- `create_identity_token(device_auth_token)` - POST /parent/create-identity-token
- `delete_account(device_auth_token)` - POST /parent/delete-account

#### Child Endpoints
- `add_device(register_token, device_name, device_model)` - POST /child/add-device
- `update_primary_device(device_auth_token, primary_device_id)` - POST /child/update-primary-device
- `logout_at_primary_device(device_auth_token)` - POST /child/logout-at-primary-device

#### Purchase Endpoints
- `can_do_purchase(device_auth_token, product_id)` - POST /purchase/can-do-purchase
- `finish_purchase_by_google_play(device_auth_token, product_id, purchase_token, signature)` - POST /purchase/finish-purchase-by-google-play

### Assertion Helpers

- `assert_status(response, expected)` - Assert status code
- `assert_status_ok(response)` - Assert status is 'ok'
- `assert_status_error(response)` - Assert status is 'error'
- `assert_has_field(response, field)` - Assert field exists
- `assert_not_empty(value, field)` - Assert value is not empty

## Test Configuration

Test configuration is managed in `tests/config.py`:

```python
from tests.config import TestConfig, test_config

# Access configuration
base_url = TestConfig.BASE_URL
timeout = TestConfig.TIMEOUT
test_mail = TestConfig.TEST_MAIL
test_password = TestConfig.TEST_PASSWORD

# Or use the global instance
config = test_config
```

### Configuration Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `BASE_URL` | `http://localhost:8080` | Base URL for API server |
| `TIMEOUT` | `30` | Request timeout in seconds |
| `VERIFY_SSL` | `true` | Whether to verify SSL certificates |
| `TEST_MAIL` | `test@example.com` | Test email address |
| `TEST_PASSWORD` | `test_password_123` | Test password |
| `TEST_DEVICE_NAME` | `Test Device` | Test device name |
| `TEST_DEVICE_MODEL` | `Pixel 7` | Test device model |
| `MOCK_DATA_SEED` | `42` | Seed for mock data generation |
| `TEST_MODE` | `true` | Test mode flag |
| `LOG_LEVEL` | `INFO` | Logging level |

## Test Fixtures

Test fixtures are pre-generated mock data stored in `tests/fixtures/`.

### Fixture Types

1. **auth_fixtures.json** - Authentication test data
2. **sync_fixtures.json** - Sync protocol test data
3. **device_fixtures.json** - Device test data
4. **family_fixtures.json** - Family test data

### Using Fixtures

```python
import json
from pathlib import Path

# Load fixtures
fixtures_path = Path("tests/fixtures/auth_fixtures.json")
with open(fixtures_path) as f:
    fixtures = json.load(f)

# Use fixture data
mail_login_token = fixtures["mail_login_token"]
mail_auth_token = fixtures["mail_auth_token"]
device_auth_token = fixtures["device_auth_token"]
```

## Running Tests

### Using pytest

```bash
# Run all tests
pytest tests/

# Run specific test file
pytest tests/test_auth.py

# Run with verbose output
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=app --cov-report=html
```

### Using the Test Client

```python
# Example test using the client
from tests.client import TestClient
from tests.config import TestConfig

def test_health_check():
    client = TestClient(base_url=TestConfig.BASE_URL)
    
    response = client.get_health()
    
    assert response["status"] == "ok"
    
    client.close()
```

## Test Organization

```
tests/
├── __init__.py
├── conftest.py              # Pytest fixtures
├── config.py                # Test configuration
├── client.py                # Test client
├── scenarios/               # Test scenario definitions
│   ├── auth_flow.json
│   ├── sync_flow.json
│   ├── crypto_flow.json
│   └── error_scenarios.json
├── fixtures/                # Pre-generated test fixtures
│   ├── auth_fixtures.json
│   ├── sync_fixtures.json
│   └── device_fixtures.json
├── test_auth.py             # Authentication tests
├── test_sync.py             # Sync protocol tests
├── test_crypto.py           # Crypto tests
├── test_state.py            # State management tests
├── test_gzip.py             # Gzip tests
├── test_response.py         # Response format tests
├── test_auth_endpoints.py   # Auth endpoint tests
├── test_sync_endpoints.py   # Sync endpoint tests
├── test_parent_endpoints.py # Parent endpoint tests
├── test_child_endpoints.py  # Child endpoint tests
├── test_purchase_endpoints.py # Purchase endpoint tests
├── test_websocket.py        # WebSocket tests
└── test_load.py             # Load tests
```

## Best Practices

### Writing Tests

1. Use the test client for API interactions
2. Set appropriate authentication tokens
3. Use assertions for validation
4. Clean up resources after tests
5. Use fixtures for reusable test data

### Test Data Management

1. Use unique identifiers for test data
2. Clean up test data after tests
3. Use deterministic data for reproducibility
4. Document test data requirements

### Performance Testing

1. Use the load test scenarios
2. Monitor response times
3. Check for memory leaks
4. Test under concurrent load

## Related Files

- `tests/client.py` - Test client implementation
- `tests/config.py` - Test configuration
- `tests/scenarios/*.json` - Test scenario definitions
- `tests/fixtures/*.json` - Test fixtures
- `docs/testing.md` - This documentation