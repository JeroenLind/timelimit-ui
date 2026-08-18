# Dashboard V2 Implementation

This document describes the current implementation level of the Dashboard V2 Flask-based authentication system.

## Overview

Dashboard V2 is a Flask-based web application that provides authentication and server status checking functionality. It serves as a modern replacement for the legacy dashboard, implementing a proper authentication flow with the debug-server API.

## Architecture

```
dashboardV2/
├── app.py           # Flask application with routes and session management
├── config.py        # Configuration with environment variables
├── database.py      # SQLite database operations
├── auth_client.py   # HTTP client for debug-server API
├── scheduler.py     # APScheduler for background tasks
├── static/
│   ├── css/
│   │   └── dashboardV2.css
│   └── js/
│       └── dashboardV2.js
├── templates/
│   ├── base.html    # Base template with nav/toggle
│   ├── landing.html # Landing page: toggle legacy/new dashboard
│   └── dashboardV2.html  # New dashboard
└── tests/
    ├── conftest.py
    ├── pytest.ini
    ├── test_database.py
    ├── test_config.py
    ├── test_auth_client.py
    ├── test_landing.py
    ├── test_timechecker.py
    └── test_scheduler.py
```

## Components

### 1. Configuration (`config.py`)

Configuration class with environment variable support for cross-platform compatibility:

| Property | Default | Description |
|----------|---------|-------------|
| `DEBUG_SERVER_URL` | `http://localhost:8080` | Debug-server API URL |
| `FLASK_HOST` | `0.0.0.0` | Flask server host |
| `FLASK_PORT` | `8099` | Flask server port |
| `DATABASE_PATH` | `dashboardV2.db` | SQLite database path |
| `SCHEDULER_INTERVAL` | `10` | Timechecker interval (seconds) |
| `SECRET_KEY` | `dev-secret-key-change-in-production` | Session signing key |

Server options:
- `local`: `http://192.168.68.30:8080`
- `official`: `https://api.timelimit.io`
- `debug`: `http://localhost:8080`

### 2. Database (`database.py`)

SQLite database with four tables:

#### server_checks
| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER | Primary key |
| timestamp | INTEGER | Unix timestamp (ms) |
| success | INTEGER | 0/1 |
| error_code | TEXT | Error code if failed |
| user_message | TEXT | User-friendly message |
| technical_detail | TEXT | Debug info |
| server_time | INTEGER | Server time (ms) |
| attempts | INTEGER | Retry count |
| server_url | TEXT | Checked server URL |

#### families
| Column | Type | Description |
|--------|------|-------------|
| id | TEXT | Family ID |
| mail | TEXT | Parent email |
| created_at | TEXT | ISO timestamp |
| parent_password_hash | TEXT | Bcrypt hash |
| parent_password_second_hash | TEXT | Second hash |
| parent_password_second_salt | TEXT | Salt for second hash |
| parent_password_encrypted | INTEGER | DH-encrypted flag |

#### devices
| Column | Type | Description |
|--------|------|-------------|
| id | TEXT | Device ID |
| family_id | TEXT | Foreign key to families |
| name | TEXT | Device name |
| model | TEXT | Device model |
| created_at | TEXT | ISO timestamp |
| current_user_id | TEXT | Current user |
| current_protection_level | INTEGER | Protection level |
| highest_protection_level | INTEGER | Max protection |
| current_app_version | TEXT | App version |
| highest_app_version | TEXT | Max app version |
| public_key | TEXT | Encryption key |
| platform_type | TEXT | Platform (android, etc.) |
| platform_level | INTEGER | Platform level |

#### auth_tokens
| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER | Primary key |
| token_type | TEXT | Token type |
| token_value | TEXT | Token string |
| device_id | TEXT | Associated device |
| family_id | TEXT | Associated family |
| mail | TEXT | Associated email |
| code | TEXT | Verification code |
| created_at | TEXT | ISO timestamp |
| expires_at | TEXT | Expiration timestamp |

### 3. Auth Client (`auth_client.py`)

Standalone HTTP client for debug-server API communication:

| Method | Endpoint | Description |
|--------|----------|-------------|
| `get_server_time()` | POST `/time` | Get server time |
| `send_mail_login_code(mail, locale, device_auth_token)` | POST `/auth/send-mail-login-code-v2` | Send login code |
| `sign_in_by_mail_code(mail_login_token, received_code)` | POST `/auth/sign-in-by-mail-code` | Sign in with code |
| `get_status_by_mail_address(mail_auth_token)` | POST `/parent/get-status-by-mail-address` | Get family status |
| `create_family(mail_auth_token, parent_password, locale, device_name, device_model)` | POST `/parent/create-family` | Create family |
| `sign_in_into_family(mail_auth_token, parent_password_second_hash, locale, device_name, device_model)` | POST `/parent/sign-in-into-family` | Sign in to family |
| `create_add_device_token(device_auth_token, parent_password_second_hash)` | POST `/parent/create-add-device-token` | Create add-device token |
| `add_device(register_token, device_name, device_model, client_level)` | POST `/child/add-device` | Register child device |
| `recover_parent_password(mail_auth_token, new_password)` | POST `/parent/recover-parent-password` | Recover password |

### 4. Scheduler (`scheduler.py`)

APScheduler BackgroundScheduler with:
- 10-second interval timechecker job
- Server connection checking via `check_server_connection()`
- Automatic server status updates
- Server URL management for session-based server selection

### 5. Flask Application (`app.py`)

Routes:
- `/` - Landing page
- `/legacy-dashboard` - Redirect to original dashboard
- `/dashboardV2` - Main dashboard
- `/select-server` - Server selection
- `/api/time` - Time endpoint proxy
- `/api/auth/*` - Auth endpoint proxies
- `/api/session/*` - Session management endpoints
- `/api/timechecker/status` - Timechecker status endpoint
- `/api/timechecker/history` - Historical data endpoint
- `/health` - Health check endpoint

Session management:
- Flask session with secret key
- Server selection persistence
- Token storage for authentication

## Templates

### base.html
Base Jinja2 template providing:
- Common HTML structure
- Header with server info display
- Footer with version info
- CSS and JS includes

### landing.html
Landing page template with:
- Dashboard version toggle (New Dashboard v2 / Legacy Dashboard)
- Server selection dropdown (Local, Official, Debug Server)
- JavaScript for form submission and navigation
- Authentication status check for New Dashboard v2 button
- Warning message displayed when user is not authenticated
- Disabled button state for unauthenticated New Dashboard access

### dashboardV2.html
Main dashboard template with:
- Server status display with real-time indicators
- Historical data table (last 10 checks)
- Alert notifications (toast-style)
- Session information
- Refresh button for manual status update
- Responsive design for mobile and desktop

## Test Coverage

All tests use `pytest` with `FlaskClient` and include timeout mechanisms.

| Test File | Tests | Description |
|-----------|-------|-------------|
| `test_database.py` | 26 | Database operations |
| `test_config.py` | 28 | Configuration management |
| `test_auth_client.py` | 35 | HTTP client functionality |
| `test_landing.py` | 42 | Landing page, server selection, and app configuration |
| `test_timechecker.py` | 29 | Timechecker dashboard and status endpoints |
| `test_scheduler.py` | 24 | Scheduler creation, lifecycle, and callbacks |

**Total: 178 unit tests**

**Note:** The `/dashboardV2` route is now accessible without authentication. The authentication flow (Phase 4) will be implemented separately. Users can navigate to the new dashboard directly from the landing page.

### App Configuration Tests

The `TestAppConfiguration` class in `test_landing.py` includes tests that verify:
- Flask app creates successfully without TypeError
- SECRET_KEY is a valid string for session signing
- Session configuration is valid

These tests catch issues where Config properties are accessed incorrectly (e.g., `Config.SECRET_KEY` instead of `config.SECRET_KEY`).

### Test Infrastructure

- pytest with timeout markers (`@pytest.mark.timeout(10)`)
- Fixtures for app, client, test_db, test_config
- Mock-based testing for HTTP requests

## Authentication Flow

### Parent Flow (3 steps)

1. **Email Entry**: User enters email address
2. **Code Verification**: User receives and enters verification code
3. **Password Setup**: User provides password hashes, family is created

### Child Login Flow (2 steps)

1. **Token Creation**: Parent creates add-device token
2. **Device Registration**: Child registers using the token

## Server Selection

Three server options available:
- **Local**: `http://192.168.68.30:8080` (pre-configured local server)
- **Official**: `https://api.timelimit.io` (production server)
- **Debug**: `http://localhost:8080` (development server)

Server selection is stored in Flask session via `/select-server` route.

## Database Initialization

Database is created on first access with all required tables. The `init_db()` method creates tables if they don't exist.

## Cross-Platform Compatibility

- All file paths use `os.path` for Windows/Home Assistant compatibility
- Configuration via environment variables
- SQLite for simple, portable storage

## Current Implementation Status

**Phase 1 COMPLETE** - Core components implemented and tested:
- [x] Flask application structure
- [x] SQLite database with all tables
- [x] APScheduler configuration
- [x] Auth client module
- [x] Test infrastructure
- [x] Unit tests (89 tests passing)

**Phase 2 COMPLETE** - Landing page and navigation implemented:
- [x] Base template with Jinja2 structure (`base.html`)
- [x] Landing page route (`/`) with dashboard toggle
- [x] Legacy dashboard redirect (`/legacy-dashboard`)
- [x] New dashboard route (`/dashboardV2`)
- [x] Server selection dropdown (3 options: Local, Official, Debug Server)
- [x] Server selection stored in Flask session via `/select-server` route
- [x] Unit tests for landing page and server selection (24 tests)
- [x] CSS styles for responsive design
- [x] JavaScript for essential interactions

**Phase 3 COMPLETE** - Timechecker dashboard implemented:
- [x] `dashboardV2.html` template with real-time status display
- [x] APScheduler job running every 10 seconds
- [x] Server check results stored in SQLite database
- [x] Real-time status display with visual indicators
- [x] Historical data table showing last 10 checks
- [x] Alert notifications (toast-style)
- [x] Data refresh endpoint (`/api/timechecker/status`)
- [x] Historical data endpoint (`/api/timechecker/history`)
- [x] Unit tests for timechecker dashboard (27 tests)
- [x] Unit tests for scheduler (24 tests)

**Phase 4+** - Not implemented (per user request to cease after Phase 3)

## Usage

### Running Tests

```bash
cd timelimit-ui/rootfs/usr/bin/dashboardV2/tests
py -3 -m pytest test_database.py test_config.py test_auth_client.py test_landing.py test_timechecker.py test_scheduler.py -v --timeout=30
```

### Starting the Application

#### Windows (PowerShell)

```powershell
cd timelimit-ui\rootfs\usr\bin\dashboardV2
py -3 app.py
```

#### Windows (Command Prompt)

```cmd
cd timelimit-ui\rootfs\usr\bin\dashboardV2
py -3 app.py
```

#### Linux/macOS

```bash
cd timelimit-ui/rootfs/usr/bin/dashboardV2
python3 app.py
```

### Configuration via Environment Variables

#### Windows (PowerShell)

```powershell
$env:DEBUG_SERVER_URL="http://localhost:8080"
$env:FLASK_HOST="0.0.0.0"
$env:FLASK_PORT="8099"
$env:DATABASE_PATH="dashboardV2.db"
$env:SCHEDULER_INTERVAL="10"
$env:SECRET_KEY="your-secret-key"
py -3 app.py
```

#### Windows (Command Prompt)

```cmd
set DEBUG_SERVER_URL=http://localhost:8080
set FLASK_HOST=0.0.0.0
set FLASK_PORT=8099
set DATABASE_PATH=dashboardV2.db
set SCHEDULER_INTERVAL=10
set SECRET_KEY=your-secret-key
py -3 app.py
```

#### Linux/macOS

```bash
export DEBUG_SERVER_URL="http://localhost:8080"
export FLASK_HOST="0.0.0.0"
export FLASK_PORT="8099"
export DATABASE_PATH="dashboardV2.db"
export SCHEDULER_INTERVAL="10"
export SECRET_KEY="your-secret-key"
python3 app.py
```

### Accessing the Dashboard

Once the application is running, open your web browser and navigate to:

```
http://localhost:8099
```

### Dashboard Pages

1. **Landing Page** (`/`) - Shows dashboard version toggle and server selection
2. **Dashboard V2** (`/dashboardV2`) - Main dashboard (requires server selection)
3. **Legacy Dashboard** (`/legacy-dashboard`) - Redirects to original dashboard

### Testing Server Selection

You can test the server selection API directly:

```bash
# Select local server
curl -X POST http://localhost:8099/select-server \
  -H "Content-Type: application/json" \
  -d '{"server_key": "local"}'

# Select official server
curl -X POST http://localhost:8099/select-server \
  -H "Content-Type: application/json" \
  -d '{"server_key": "official"}'

# Select debug server
curl -X POST http://localhost:8099/select-server \
  -H "Content-Type: application/json" \
  -d '{"server_key": "debug"}'
```

### Testing Timechecker Endpoints

```bash
# Get current server status
curl http://localhost:8099/api/timechecker/status

# Get historical data (last 10 checks)
curl http://localhost:8099/api/timechecker/history

# Get historical data with custom limit
curl "http://localhost:8099/api/timechecker/history?limit=20"
```

### Health Check

Verify the server is running:

```bash
curl http://localhost:8099/health
```

Expected response:
```json
{"status": "healthy"}
```

## Create New Family Flow

The createNewFamily flow allows users to create a new TimeLimit family (parent account + device) from the dashboardV2 web UI. This is a server-side rendered flow that maximizes Python backend logic and minimizes JavaScript.

### Flow Overview

The flow consists of 3 steps:

1. **Email Entry** → User enters their email → `AuthClient.send_mail_login_code()` → returns `mailLoginToken` (stored in Flask session)
2. **Code Verification** → User enters verification code → `AuthClient.sign_in_by_mail_code()` → returns `mailAuthToken` (stored in Flask session)
3. **Password + Device Info** → User enters password and device info → `crypto_utils.generate_family_hashes()` → `AuthClient.create_family_rest()` → returns `deviceAuthToken` + `ownDeviceId` (stored in Flask session)

### Routes

| Route | Method | Description |
|-------|--------|-------------|
| `/create-family` | GET | Renders the appropriate step based on session state |
| `/create-family` | POST | Processes form submissions for all 3 steps |
| `/create-family/cancel` | POST | Clears session and redirects to dashboard |

### Templates

| Template | Purpose |
|----------|---------|
| `create_family.html` | Server-rendered template for all 3 steps of the create-family flow |

### Session Keys

| Key | Purpose |
|-----|---------|
| `mail_login_token` | Token for step 1 → step 2 transition |
| `mail_auth_token` | Token for step 2 → step 3 transition |
| `device_auth_token` | Final authentication token for accessing the dashboard |
| `own_device_id` | The newly created device ID |
| `create_family_error` | Error message to display (popped after display) |

### Testing

Run the create family tests:

```bash
# Unit tests for routes and validation
py -3 -m pytest tests/test_create_family.py -v --timeout=30

# Unit tests for password hash generation
py -3 -m pytest tests/test_crypto_utils.py -v --timeout=30

# Integration tests for full flow
py -3 -m pytest tests/test_create_family_integration.py -v --timeout=30

# All tests together
py -3 -m pytest tests/test_create_family.py tests/test_crypto_utils.py tests/test_create_family_integration.py -v --timeout=30
```

### Design Principles

- **Server-side rendering**: Flask templates render each step's form
- **Standard HTML forms**: `method="POST"` with `action="/create-family"` — no AJAX
- **Server-side validation**: All validation in Python (email regex, code format, password rules)
- **Inline password hashing**: `crypto_utils.generate_family_hashes()` called directly in the route handler
- **Zero JavaScript**: No new JavaScript functions added

## References

- Plan: `plans/create-new-family-interaction-plan.md`
- Debug Server API: See `debug-server/app/api/` for endpoint definitions
- Original Dashboard: `timelimit-ui/rootfs/usr/bin/dashboard.html`