# Dashboard V2 Implementation

This document describes the current implementation status of the Dashboard V2 Flask-based authentication system.

## Overview

Dashboard V2 is a Flask-based web application that provides authentication, server status checking, and device management functionality. It serves as a modern replacement for the legacy dashboard, implementing a proper authentication flow with the debug-server API.

## Architecture

```
dashboardV2/
├── app.py                    # Flask application with routes and session management
├── config.py                 # Configuration with environment variables
├── database.py               # SQLite database operations
├── auth_client.py            # HTTP client for debug-server API
├── scheduler.py              # APScheduler for background tasks
├── sync_manager.py           # Sync protocol management
├── key_manager.py            # Signing key management
├── persistence.py            # Persistence abstraction for server selection
├── middleware/
│   └── request_logging.py    # Request logging middleware
├── utils/
│   ├── audit_log.py          # Audit logging for API requests
│   ├── family_logging.py     # Family-specific logging
│   ├── log_rotation.py       # Log file rotation
│   ├── logging.py            # Logging configuration
│   └── sanitization.py       # Input sanitization utilities
├── static/
│   ├── css/
│   │   └── dashboardV2.css
│   └── js/
│       └── dashboardV2.js
├── templates/
│   ├── base.html             # Base template with nav/toggle
│   ├── landing.html          # Landing page: toggle legacy/new dashboard
│   ├── dashboardV2.html      # Main dashboard
│   ├── create_family.html    # Create family flow (3 steps)
│   ├── login_as_parent.html  # Login as parent flow (4 steps)
│   ├── recover_parent_password.html  # Password recovery flow (3 steps)
│   ├── set_parent_password.html      # Set parent password flow
│   └── debug_database.html   # Database viewer for debugging
└── tests/
    ├── conftest.py
    ├── pytest.ini
    ├── test_database.py
    ├── test_config.py
    ├── test_auth_client.py
    ├── test_landing.py
    ├── test_timechecker.py
    ├── test_scheduler.py
    ├── test_create_family.py
    ├── test_login_as_parent.py
    ├── test_recover_parent_password.py
    ├── test_set_parent_password.py
    ├── test_sync_manager.py
    ├── test_persistence.py
    ├── test_key_manager.py
    ├── test_dashboard_api.py
    ├── test_audit_log.py
    ├── test_logging.py
    └── ... (many more test files)
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
| `SCHEDULER_INTERVAL` | `60` | Timechecker interval (seconds) |
| `SECRET_KEY` | `dev-secret-key-change-in-production` | Session signing key |
| `PERSISTENCE_DIR` | Platform-specific | Directory for persistence files |
| `APP_VERSION` | Auto-detected | Application version |

Server options:
- `local`: `http://192.168.68.30:8080` (pre-configured local server)
- `official`: `https://api.timelimit.io` (production server)
- `debug`: `http://localhost:8080` (development server)

### 2. Database (`database.py`)

SQLite database with **8 tables**:

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
| device_auth_token | TEXT | **Primary key** - Family authentication token |
| mail | TEXT | Parent email |
| created_at | TEXT | ISO timestamp |
| parent_password_hash | TEXT | Bcrypt hash ($2a$ prefix) |
| parent_password_second_hash | TEXT | Second hash for password verification |
| parent_password_second_salt | TEXT | Salt for second hash |
| parent_password_encrypted | INTEGER | DH-encrypted flag |

#### devices
| Column | Type | Description |
|--------|------|-------------|
| id | TEXT | Device ID |
| device_auth_token | TEXT | Foreign key to families |
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
| mail | TEXT | Associated email |
| code | TEXT | Verification code |
| created_at | TEXT | ISO timestamp |
| expires_at | TEXT | Expiration timestamp |

#### users
| Column | Type | Description |
|--------|------|-------------|
| id | TEXT | User ID |
| device_auth_token | TEXT | Foreign key to families |
| name | TEXT | User name |
| age | INTEGER | User age |
| created_at | TEXT | ISO timestamp |

#### sync_state
| Column | Type | Description |
|--------|------|-------------|
| device_auth_token | TEXT | Primary key - Family authentication token |
| users_version | INTEGER | Last synced users version |
| categories_version | INTEGER | Last synced categories version |
| connected_devices_version | INTEGER | Last synced connected devices version |
| last_sync_at | TEXT | Last sync timestamp |

#### categories
| Column | Type | Description |
|--------|------|-------------|
| id | TEXT | Category ID |
| device_auth_token | TEXT | Foreign key to families |
| name | TEXT | Category name |
| icon | TEXT | Icon identifier |
| color | TEXT | Color code |
| order | INTEGER | Display order |
| created_at | TEXT | ISO timestamp |

#### connected_devices
| Column | Type | Description |
|--------|------|-------------|
| id | TEXT | Device ID |
| device_auth_token | TEXT | Foreign key to families |
| name | TEXT | Device name |
| last_seen | TEXT | Last seen timestamp |

### 3. Auth Client (`auth_client.py`)

Standalone HTTP client for debug-server API communication:

| Method | Endpoint | Description |
|--------|----------|-------------|
| `get_server_time()` | POST `/time` | Get server time |
| `send_mail_login_code(mail, locale, device_auth_token)` | POST `/auth/send-mail-login-code-v2` | Send login code |
| `sign_in_by_mail_code(mail_login_token, received_code)` | POST `/auth/sign-in-by-mail-code` | Sign in with code |
| `get_status_by_mail_address(mail_auth_token)` | POST `/parent/get-status-by-mail-address` | Get family status |
| `create_family(mail_auth_token, parent_password, locale, device_name, device_model)` | POST `/parent/create-family` | Create family |
| `create_family_rest(mail_auth_token, parent_password, locale, device_name, device_model)` | POST `/parent/create-family-rest` | Create family (REST API) |
| `sign_in_into_family(mail_auth_token, parent_password_second_hash, locale, device_name, device_model)` | POST `/parent/sign-in-into-family` | Sign in to family |
| `create_add_device_token(device_auth_token, parent_password_second_hash)` | POST `/parent/create-add-device-token` | Create add-device token |
| `add_device(register_token, device_name, device_model, client_level)` | POST `/child/add-device` | Register child device |
| `recover_parent_password(mail_auth_token, new_password)` | POST `/parent/recover-parent-password` | Recover password |
| `pull_status(device_auth_token, sync_state)` | POST `/sync/pull` | Pull sync data |
| `push_actions(device_auth_token, actions)` | POST `/sync/push` | Push sync actions |
| `remove_device(device_auth_token, device_id)` | POST `/sync/remove-device` | Remove device from server |
| `check_server_connection()` | GET `/health` | Check server connectivity |

### 4. Scheduler (`scheduler.py`)

APScheduler BackgroundScheduler with:
- 60-second interval timechecker job
- Server connection checking via `check_server_connection()`
- Automatic server status updates
- Sync job for periodic data synchronization
- Server URL management for session-based server selection

### 5. Persistence (`persistence.py`)

Persistence abstraction for server selection and auth token storage:

| Function | Description |
|----------|-------------|
| `get_server_selection_store()` | Get the persistence store instance |
| `get_current_server_key()` | Get the last selected server key |
| `set_current_server_key(key)` | Save the selected server key |
| `get_current_server_url()` | Get the last selected server URL |
| `set_current_server_url(url)` | Save the selected server URL |
| `get_persisted_device_auth_token()` | Get persisted device auth token |
| `set_persisted_device_auth_token(token)` | Save device auth token |
| `get_persisted_own_device_id()` | Get persisted own device ID |
| `set_persisted_own_device_id(device_id)` | Save own device ID |
| `backup_auth_tokens()` | Create backup of auth tokens |
| `restore_auth_tokens()` | Restore auth tokens from backup |
| `clear_auth_token_backup()` | Clear the backup file |
| `sync_session_to_database()` | Sync session data to database |

### 6. Sync Manager (`sync_manager.py`)

Sync protocol management for device data synchronization:
- Pull status from server
- Push actions to server
- Handle device removal
- Manage sync state versioning

### 7. Key Manager (`key_manager.py`)

Signing key management for secure operations:
- Load signing key from JSON file
- Validate key integrity
- Handle key rotation

### 8. Middleware (`middleware/request_logging.py`)

Request logging middleware for audit trails:
- Logs all incoming requests
- Captures request/response data
- Integrates with audit logging

### 9. Utils

#### audit_log.py
Structured audit logging for API requests with format:
- Sync Pull Request/Response
- Sync Push Request/Response
- Family Creation Request/Response
- Device Removal Request/Response
- Add User Request/Response

#### sanitization.py
Input sanitization utilities for security:
- Email validation
- Password validation
- Device ID sanitization

## Routes

### Page Routes

| Route | Method | Description |
|-------|--------|-------------|
| `/` | GET | Landing page with dashboard toggle |
| `/legacy-dashboard` | GET | Redirect to original dashboard |
| `/dashboardV2` | GET | Main dashboard (requires server selection) |
| `/select-server` | POST | Select server (local/official/debug) |
| `/create-family` | GET | Create family flow (renders appropriate step) |
| `/create-family` | POST | Create family flow (processes all steps) |
| `/create-family/cancel` | POST | Cancel create family flow |
| `/login-as-parent` | GET | Login as parent flow (renders appropriate step) |
| `/login-as-parent` | POST | Login as parent flow (processes all steps) |
| `/login-as-parent/cancel` | POST | Cancel login as parent flow |
| `/recover-parent-password` | GET | Password recovery flow (renders appropriate step) |
| `/recover-parent-password` | POST | Password recovery flow (processes all steps) |
| `/set-parent-password` | GET | Set parent password page |
| `/set-parent-password` | POST | Set parent password action |
| `/debug/database` | GET | Database viewer for debugging |

### API Routes

| Route | Method | Description |
|-------|--------|-------------|
| `/api/time` | POST | Time endpoint proxy |
| `/api/log-level` | POST | Set log level |
| `/api/server-selection` | GET | Get server selection |
| `/api/auth/send-mail-login-code` | POST | Send mail login code |
| `/api/auth/sign-in-by-mail-code` | POST | Sign in by mail code |
| `/api/auth/create-family` | POST | Create family |
| `/api/families` | POST | Create family (REST) |
| `/api/auth/sign-in-into-family` | POST | Sign in into family |
| `/api/auth/regenerate-hash` | POST | Regenerate password hash |
| `/api/parent/create-add-device-token` | POST | Create add device token |
| `/api/child/add-device` | POST | Add child device |
| `/api/auth/get-status-by-mail-address` | POST | Get status by mail address |
| `/api/auth/recover-parent-password` | POST | Recover parent password |
| `/api/session/clear` | POST | Clear session |
| `/api/session/status` | GET | Get session status |
| `/api/sync/pull` | POST | Pull sync data |
| `/api/dashboard/users` | GET | Get users for dashboard |
| `/api/dashboard/devices` | GET | Get devices for dashboard |
| `/api/dashboard/categories` | GET | Get categories for dashboard |
| `/api/dashboard/connected-devices` | GET | Get connected devices |
| `/api/dashboard/stream` | GET | SSE endpoint for real-time updates |
| `/api/timechecker/status` | GET | Timechecker status |
| `/api/timechecker/history` | GET | Timechecker history |
| `/api/clear-all` | POST | Clear all data |
| `/api/clear-server-checks` | POST | Clear server checks |
| `/api/auth/backup` | POST | Backup auth tokens |
| `/api/auth/restore` | POST | Restore auth tokens |
| `/api/auth/clear-backup` | POST | Clear auth token backup |
| `/api/dashboard/devices/remove` | POST | Remove device from dashboard |
| `/api/dashboard/users/add` | POST | Add user to family |
| `/health` | GET | Health check endpoint |

## Add User to Family Feature

### Overview

The "Add User to Family" feature allows parents to add new child users directly from the dashboard interface. This is accomplished through a three-step process that orchestrates the add-device flow to register a new child device and user to the parent's family.

### New Route: POST /api/dashboard/users/add

#### Endpoint Documentation

**Route:** `POST /api/dashboard/users/add`

**Purpose:** Add a new user (child) to the parent's family by orchestrating the add-device flow.

**Request Body:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | Yes | Child's display name |
| `deviceName` | string | No | Name for the child's device |
| `deviceModel` | string | No | Model of the child's device |

**Response (Success - 200):**

```json
{
    "status": "ok",
    "userId": "<user_id>",
    "deviceAuthToken": "<child_device_auth_token>",
    "ownDeviceId": "<child_device_id>"
}
```

**Response (Error - 400):**

```json
{
    "status": "error",
    "error": "<error_message>",
    "error_code": "<error_code>"
}
```

**Response (Error - 401):**

```json
{
    "status": "error",
    "error": "Not authenticated",
    "error_code": "unauthorized"
}
```

**Response (Error - 500):**

```json
{
    "status": "error",
    "error": "<error_message>",
    "error_code": "<error_code>"
}
```

#### Route Handler: `api_add_user_to_family()`

The route handler function `api_add_user_to_family()` in `app.py` implements the following flow:

1. **Input Validation**
   - Validates that user name is provided
   - Strips and sanitizes device name and device model (converts empty strings to None)

2. **Authentication Check**
   - Verifies `device_auth_token` is present in session
   - Verifies `parent_password_second_hash` is present in session
   - Returns 401 if not authenticated
   - Returns 400 if device_auth_token is missing
   - Returns 400 if parent_password_second_hash is missing

3. **Parent User ID Lookup**
   - Retrieves parent user ID from database using `get_parent_user_id()`
   - Returns 500 if parent user ID not found

4. **Audit Logging**
   - Logs the add user request using `log_add_user_request()`

5. **Three-Step Add Device Flow**
   - **Step 1: Create Add Device Token**
     - Calls `AuthClient.create_add_device_token()` with device_auth_token and parent_password_second_hash
     - Receives register token and device ID
     - Returns 500 on failure

   - **Step 2: Add Device**
     - Calls `AuthClient.add_device()` with register token, device name, device model, and client_level=7
     - Receives child device auth token and own device ID
     - Returns 500 on failure

   - **Step 3: Pull Status (Sync)**
     - Calls `AuthClient.pull_status()` with child device auth token
     - Receives users data from server
     - Finds the newly created user by name
     - Returns 500 on failure

6. **Database Persistence**
   - Saves users to database using `save_users()` with child device auth token
   - This ensures the new user is available locally for display in the dashboard

7. **Response**
   - Returns user ID, child device auth token, and own device ID on success
   - Logs success response using `log_add_user_response()`

### Database Schema Documentation

#### No Schema Changes Required

The "Add User to Family" feature does not require any database schema changes. The existing `users` table schema is sufficient:

```sql
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    device_auth_token TEXT NOT NULL,
    name TEXT,
    password TEXT,
    second_password_salt TEXT,
    type TEXT,
    time_zone TEXT,
    disable_limits_until INTEGER,
    mail TEXT,
    current_device TEXT,
    category_for_not_assigned_apps TEXT,
    relax_primary_device INTEGER DEFAULT 0,
    flags INTEGER DEFAULT 0,
    limit_login_category TEXT,
    pre_block_duration INTEGER DEFAULT 0,
    last_updated INTEGER,
    FOREIGN KEY (device_auth_token) REFERENCES families(device_auth_token)
)
```

#### User Creation Flow

The user creation flow works as follows:

1. **Parent Authentication**
   - Parent must be authenticated with valid `device_auth_token` in session
   - Parent must have `parent_password_second_hash` in session (required for device operations)

2. **Token Generation**
   - Server generates a one-time use add-device token via `/parent/create-add-device-token`
   - Token is valid for a limited time and can only be used once

3. **Device Registration**
   - Child device is registered via `/child/add-device` endpoint
   - Server returns new `deviceAuthToken` and `ownDeviceId` for the child

4. **Sync and User Creation**
   - `pull_status()` is called with the child's device auth token
   - Server returns the complete user list including the newly created user
   - User is identified by matching the `name` field

5. **Local Persistence**
   - Users are saved to local SQLite database via `save_users()`
   - User data is available for display in the dashboard

### Auth Client Integration

The `api_add_user_to_family()` route integrates with three key methods from `auth_client.py`:

#### 1. `create_add_device_token(device_auth_token, parent_password_second_hash)`

**Endpoint:** `POST /parent/create-add-device-token`

**Purpose:** Creates a one-time use token that allows a child device to be registered to the parent's family.

**Request Body:**
```json
{
    "deviceAuthToken": "<parent_device_auth_token>",
    "parentPasswordSecondHash": "<parent_second_hash>"
}
```

**Response (Success):**
```json
{
    "token": "<register_token>",
    "deviceId": "<device_id>"
}
```

**Authentication:** Uses Bearer token authentication with `device_auth_token`.

#### 2. `add_device(register_token, device_name, device_model, client_level)`

**Endpoint:** `POST /child/add-device`

**Purpose:** Registers a new child device using the token from `create_add_device_token()`.

**Request Body:**
```json
{
    "registerToken": "<token_from_create_add_device_token>",
    "deviceName": "<optional_device_name>",
    "deviceModel": "<optional_device_model>",
    "clientLevel": 7
}
```

**Response (Success):**
```json
{
    "deviceAuthToken": "<child_device_auth_token>",
    "ownDeviceId": "<child_device_id>"
}
```

**Note:** `clientLevel` is set to 7 to match the Android app's `ClientDataStatus.CLIENT_LEVEL_VALUE`.

#### 3. `pull_status(device_auth_token, client_data_status)`

**Endpoint:** `POST /sync/pull-status`

**Purpose:** Pulls the complete sync data from the server, including the newly created user.

**Request Body:**
```json
{
    "deviceAuthToken": "<child_device_auth_token>",
    "status": {
        "clientLevel": 7,
        "devices": "",
        "users": "",
        "apps": {},
        "categories": {}
    }
}
```

**Response (Success):**
```json
{
    "users": {
        "data": [
            {
                "id": "<user_id>",
                "name": "<user_name>",
                ...
            }
        ]
    },
    "devices": {
        "data": [...]
    },
    "categories": {
        "data": [...]
    }
}
```

**Note:** The request body is gzip-compressed automatically by the AuthClient.

### Audit Logging Documentation

The "Add User to Family" feature includes comprehensive audit logging for security and compliance purposes.

#### Audit Log Functions

##### `log_add_user_request()`

**Purpose:** Logs the add user request with complete fidelity before processing.

**Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `device_auth_token` | string | Yes | Parent's device auth token |
| `parent_user_id` | string | Yes | Parent's user ID |
| `user_name` | string | Yes | Child's display name |
| `device_name` | string | No | Optional device name |
| `device_model` | string | No | Optional device model |
| `request_id` | string | No | Request ID for correlation |
| `server_url` | string | No | Server URL being contacted |
| `audit_log_path` | string | No | Path to audit log file |

**Log Format:**
```json
{
    "event": "add_user_request",
    "timestamp": "2026-09-13T11:23:20.000000Z",
    "timestamp_unix_ms": 1726190600000,
    "device_auth_token": "<token>",
    "parent_user_id": "<parent_user_id>",
    "user_name": "<user_name>",
    "device_name": "<device_name>",
    "device_model": "<device_model>",
    "request_id": "<request_id>",
    "server_url": "<server_url>"
}
```

##### `log_add_user_response()`

**Purpose:** Logs the add user response with complete fidelity after processing.

**Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `device_auth_token` | string | Yes | Parent's device auth token |
| `parent_user_id` | string | Yes | Parent's user ID |
| `user_id` | string | No | New child user's ID (if successful) |
| `child_device_auth_token` | string | No | New child device's auth token (if successful) |
| `own_device_id` | string | No | New child device's ID (if successful) |
| `request_id` | string | No | Request ID for correlation |
| `success` | boolean | No | Whether the operation succeeded |
| `status_code` | integer | No | HTTP status code |
| `response_data` | object | No | Complete response data |
| `error_code` | string | No | Error code if failed |
| `error_message` | string | No | Error message if failed |
| `audit_log_path` | string | No | Path to audit log file |

**Log Format (Success):**
```json
{
    "event": "add_user_response",
    "timestamp": "2026-09-13T11:23:20.100000Z",
    "timestamp_unix_ms": 1726190600100,
    "device_auth_token": "<token>",
    "parent_user_id": "<parent_user_id>",
    "user_id": "<user_id>",
    "child_device_auth_token": "<child_device_auth_token>",
    "own_device_id": "<own_device_id>",
    "request_id": "<request_id>",
    "success": true,
    "status_code": 200,
    "response_data": {
        "status": "ok",
        "userId": "<user_id>",
        "deviceAuthToken": "<child_device_auth_token>",
        "ownDeviceId": "<own_device_id>"
    }
}
```

**Log Format (Failure):**
```json
{
    "event": "add_user_response",
    "timestamp": "2026-09-13T11:23:20.100000Z",
    "timestamp_unix_ms": 1726190600100,
    "device_auth_token": "<token>",
    "parent_user_id": "<parent_user_id>",
    "user_id": null,
    "child_device_auth_token": null,
    "own_device_id": null,
    "request_id": "<request_id>",
    "success": false,
    "status_code": 500,
    "response_data": null,
    "error_code": "<error_code>",
    "error_message": "<error_message>"
}
```

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
- Users table with parent/child users
- Devices table with device details
- Categories table
- Connected devices table
- Refresh button for manual status update
- SSE stream endpoint for real-time updates
- Responsive design for mobile and desktop

### create_family.html
Server-rendered template for the create family flow (3 steps):
1. Email entry
2. Code verification
3. Password + device info

### login_as_parent.html
Server-rendered template for the login as parent flow (4 steps):
1. Email entry
2. Code verification
3. Password entry (optional - can skip)
4. Set password (if skipped in step 3)

### recover_parent_password.html
Server-rendered template for password recovery flow (3 steps):
1. Email entry
2. Code verification
3. New password setup

### set_parent_password.html
Template for setting parent password after login.

### debug_database.html
Database viewer page for debugging purposes.

## Authentication Flows

### 1. Create New Family Flow (3 steps)

1. **Email Entry** → User enters email address
2. **Code Verification** → User receives and enters verification code
3. **Password + Device Info** → User enters password and device info

Routes: `/create-family` (GET/POST), `/create-family/cancel` (POST)

### 2. Login as Parent Flow (4 steps)

1. **Email Entry** → User enters email address
2. **Code Verification** → User receives and enters verification code
3. **Password Entry** → User enters password (optional - can skip)
4. **Set Password** → User sets password if skipped in step 3

Routes: `/login-as-parent` (GET/POST), `/login-as-parent/cancel` (POST)

### 3. Recover Parent Password Flow (3 steps)

1. **Email Entry** → User enters email address
2. **Code Verification** → User receives and enters verification code
3. **New Password Setup** → User sets new password

Routes: `/recover-parent-password` (GET/POST)

### 4. Set Parent Password Flow

Single step to set parent password after login.

Routes: `/set-parent-password` (GET/POST)

## Server Selection

Three server options available:
- **Local**: `http://192.168.68.30:8080` (pre-configured local server)
- **Official**: `https://api.timelimit.io` (production server)
- **Debug**: `http://localhost:8080` (development server)

Server selection is stored in Flask session via `/select-server` route and persisted to JSON file.

## Database Initialization

Database is created on first access with all required tables. The `init_db()` method creates tables if they don't exist. Schema migrations are handled automatically.

## Session Management

- Flask session with secret key
- Server selection persistence (JSON file)
- Auth tokens stored in database and JSON backup
- Session restoration from persistence on startup
- Device auth token as primary session identifier

## Cross-Platform Compatibility

- All file paths use `os.path` for Windows/Home Assistant compatibility
- Configuration via environment variables
- SQLite for simple, portable storage
- JSON files for persistence

## Current Implementation Status

**All phases COMPLETE** - Full implementation with 1035 tests passing:

- [x] Flask application structure with 50+ routes
- [x] SQLite database with 8 tables
- [x] APScheduler configuration with background jobs
- [x] Auth client module with full API coverage
- [x] Test infrastructure with 1035 passing tests
- [x] All authentication flows implemented
- [x] Server selection persistence
- [x] Sync protocol implementation
- [x] Device management (add/remove)
- [x] Audit logging
- [x] SSE real-time updates
- [x] Debug database viewer
- [x] Password recovery flow
- [x] Session status API
- [x] Add User to Family feature

### Key Features Implemented

1. **Server Status Checking**: Timechecker runs every 60 seconds, stores results in database
2. **Authentication Flows**: Create family, login as parent, password recovery, set password
3. **Device Management**: Add devices, remove devices, view device list
4. **Sync Protocol**: Pull/push data synchronization with server
5. **Session Persistence**: Server selection and auth tokens persist across restarts
6. **Audit Logging**: All API requests logged with structured format
7. **Real-time Updates**: SSE endpoint for dashboard streaming
8. **Debug Tools**: Database viewer for troubleshooting
9. **Add User to Family**: Parent can add new child users from dashboard

## Usage

### Running Tests

```bash
cd timelimit-ui/rootfs/usr/bin/dashboardV2
python -m pytest tests/ -v --timeout=30
```

Or run specific test files:
```bash
python -m pytest test_database.py test_config.py test_auth_client.py test_landing.py test_timechecker.py test_scheduler.py -v --timeout=30
```

### Starting the Application

#### Windows (PowerShell)

```powershell
cd timelimit-ui\rootfs\usr\bin\dashboardV2
python app.py
```

#### Windows (Command Prompt)

```cmd
cd timelimit-ui\rootfs\usr\bin\dashboardV2
python app.py
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
$env:SCHEDULER_INTERVAL="60"
$env:SECRET_KEY="your-secret-key"
python app.py
```

#### Windows (Command Prompt)

```cmd
set DEBUG_SERVER_URL=http://localhost:8080
set FLASK_HOST=0.0.0.0
set FLASK_PORT=8099
set DATABASE_PATH=dashboardV2.db
set SCHEDULER_INTERVAL=60
set SECRET_KEY=your-secret-key
python app.py
```

#### Linux/macOS

```bash
export DEBUG_SERVER_URL="http://localhost:8080"
export FLASK_HOST="0.0.0.0"
export FLASK_PORT="8099"
export DATABASE_PATH="dashboardV2.db"
export SCHEDULER_INTERVAL="60"
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

## Audit Log Format

Audit logs are written to `logs/audit.log` with structured JSON format:

### Sync Pull Request
```json
{"timestamp": "...", "event_type": "sync_pull_request", "device_auth_token": "...", "sync_state": {...}}
```

### Sync Pull Response
```json
{"timestamp": "...", "event_type": "sync_pull_response", "device_auth_token": "...", "users_count": N, "categories_count": N, "connected_devices_count": N}
```

### Sync Push Request
```json
{"timestamp": "...", "event_type": "sync_push_request", "device_auth_token": "...", "actions": [...]}
```

### Sync Push Response
```json
{"timestamp": "...", "event_type": "sync_push_response", "device_auth_token": "...", "success": true/false}
```

### Family Creation Request
```json
{"timestamp": "...", "event_type": "family_creation_request", "mail": "...", "device_name": "..."}
```

### Family Creation Response
```json
{"timestamp": "...", "event_type": "family_creation_response", "device_auth_token": "...", "own_device_id": "..."}
```

### Device Removal Request
```json
{"timestamp": "...", "event_type": "device_removal_request", "device_auth_token": "...", "device_id": "..."}
```

### Add User Request
```json
{
    "event": "add_user_request",
    "timestamp": "2026-09-13T11:23:20.000000Z",
    "timestamp_unix_ms": 1726190600000,
    "device_auth_token": "<token>",
    "parent_user_id": "<parent_user_id>",
    "user_name": "<user_name>",
    "device_name": "<device_name>",
    "device_model": "<device_model>",
    "request_id": "<request_id>",
    "server_url": "<server_url>"
}
```

### Add User Response
```json
{
    "event": "add_user_response",
    "timestamp": "2026-09-13T11:23:20.100000Z",
    "timestamp_unix_ms": 1726190600100,
    "device_auth_token": "<token>",
    "parent_user_id": "<parent_user_id>",
    "user_id": "<user_id>",
    "child_device_auth_token": "<child_device_auth_token>",
    "own_device_id": "<own_device_id>",
    "request_id": "<request_id>",
    "success": true,
    "status_code": 200,
    "response_data": {
        "status": "ok",
        "userId": "<user_id>",
        "deviceAuthToken": "<child_device_auth_token>",
        "ownDeviceId": "<own_device_id>"
    }
}
```

## Data Flow Documentation

### Device Removal Verification

1. User clicks remove button in dashboard
2. Frontend sends POST to `/api/dashboard/devices/remove`
3. Backend calls `auth_client.remove_device()`
4. Server removes device from TimeLimit server
5. Backend calls `auth_client.pull_status()` to sync
6. Dashboard updates device list

### Sync Verification

1. User clicks refresh button or auto-sync triggers
2. Frontend sends POST to `/api/sync/pull`
3. Backend calls `auth_client.pull_status()`
4. Server returns updated users, categories, connected_devices
5. Backend stores in database
6. Frontend updates dashboard tables

### Family Creation Audit Logging Verification

1. User enters email in create family flow
2. Backend calls `auth_client.send_mail_login_code()`
3. Audit log records `mail_login_token`
4. User enters code
5. Backend calls `auth_client.sign_in_by_mail_code()`
6. Audit log records `mail_auth_token`
7. User enters password and device info
8. Backend calls `auth_client.create_family_rest()`
9. Audit log records `device_auth_token` and `own_device_id`

### Signing Key Display Verification

1. Dashboard loads `/dashboardV2`
2. Backend loads signing key from `dashboard_signing_key.json`
3. Key is displayed in UI for verification
4. Key is NOT stored in database

### Login-as-Parent Sync Verification

1. User logs in via login-as-parent flow
2. Backend calls `auth_client.pull_status()`
3. Users, categories, connected devices synced to database
4. Dashboard displays all synced data

### Add User to Family Verification

1. Parent clicks "Add User" button in dashboard
2. Modal opens with user name, device name, and device model fields
3. Parent enters user name (required) and optional device info
4. Frontend sends POST to `/api/dashboard/users/add`
5. Backend validates authentication and parent password hash
6. Backend calls `auth_client.create_add_device_token()`
7. Backend calls `auth_client.add_device()` with register token
8. Backend calls `auth_client.pull_status()` to sync new user
9. Backend saves users to database
10. Audit log records request and response
11. Frontend displays success message and updates user list

### Double Log File Creation Fix Verification

1. Application starts
2. Only one log file is created (no duplicates)
3. Log rotation works correctly

## References

- Plan: `plans/create-new-family-interaction-plan.md`
- Original Dashboard: `timelimit-ui/rootfs/usr/bin/dashboard.html`
- CONTEXT.md: Project context with recent fixes and test results