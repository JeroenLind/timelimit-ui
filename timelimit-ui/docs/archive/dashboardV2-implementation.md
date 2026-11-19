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
| parent_user_id | TEXT | Parent user ID |

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
| password | TEXT | User password hash |
| second_password_salt | TEXT | Salt for second password |
| type | TEXT | parent/child |
| time_zone | TEXT | User time zone |
| disable_limits_until | INTEGER | Timestamp to disable limits |
| mail | TEXT | User email |
| current_device | TEXT | Current device name |
| category_for_not_assigned_apps | TEXT | Default category |
| relax_primary_device | INTEGER | Relax primary device flag |
| flags | INTEGER | User flags |
| limit_login_category | TEXT | Category for limit login |
| pre_block_duration | INTEGER | Pre-block duration |
| last_updated | INTEGER | Last update timestamp |

#### sync_state
| Column | Type | Description |
|--------|------|-------------|
| device_auth_token | TEXT | Primary key |
| device_list_version | TEXT | Device list version |
| user_list_version | TEXT | User list version |
| last_sync_timestamp | INTEGER | Last sync timestamp |
| last_sync_success | INTEGER | 1 if last sync succeeded |
| next_sequence_number | INTEGER | Next sequence number |

#### categories
| Column | Type | Description |
|--------|------|-------------|
| id | TEXT | Category ID |
| device_auth_token | TEXT | Foreign key to families |
| child_id | TEXT | Child user ID |
| title | TEXT | Category title |
| blocked_times | TEXT | Blocked time periods |
| extra_time | INTEGER | Extra time in minutes |
| extra_time_day | INTEGER | Extra time for the day |
| temp_blocked | INTEGER | Temporary blocked flag |
| temp_block_time | INTEGER | Temporary block time |
| version | TEXT | Category version |
| parent_category_id | TEXT | Parent category ID |
| block_all_notifications | INTEGER | Block all notifications flag |
| time_warnings | INTEGER | Time warnings flag |
| sort_order | INTEGER | Sort order |
| flags | INTEGER | Category flags |
| last_updated | INTEGER | Last update timestamp |

#### connected_devices
| Column | Type | Description |
|--------|------|-------------|
| device_auth_token | TEXT | Foreign key to families |
| device_id | TEXT | Device ID |
| last_seen | INTEGER | Last seen timestamp |
| name | TEXT | Device name |

#### time_limit_rules
| Column | Type | Description |
|--------|------|-------------|
| id | TEXT | Unique rule ID |
| device_auth_token | TEXT | Foreign key to families |
| user_id | TEXT | Foreign key to users |
| category_id | TEXT | Foreign key to categories |
| rule_type | INTEGER | Type of rule |
| start_time | TEXT | Start time (HH:MM) |
| end_time | TEXT | End time (HH:MM) |
| days | INTEGER | Days bitmask (0-127) |
| limit_minutes | INTEGER | Time limit in minutes |
| version | TEXT | Rule version |
| created_at | TEXT | Creation timestamp |
| last_updated | INTEGER | Last update timestamp |

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
| `/api/dashboard/time-limit-rules` | GET | Get time limit rules |
| `/api/dashboard/time-limit-rules` | POST | Create time limit rule |
| `/api/dashboard/time-limit-rules/{ruleId}` | PUT | Update time limit rule |
| `/api/dashboard/time-limit-rules/{ruleId}` | DELETE | Delete time limit rule |
| `/health` | GET | Health check endpoint |

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

**All phases COMPLETE** - Full implementation with 1028 tests passing:

- [x] Flask application structure with 50+ routes
- [x] SQLite database with 8 tables
- [x] APScheduler configuration with background jobs
- [x] Auth client module with full API coverage
- [x] Test infrastructure with 1028 passing tests
- [x] All authentication flows implemented
- [x] Server selection persistence
- [x] Sync protocol implementation
- [x] Device management (add/remove)
- [x] Time limit rules (add/update/delete)
- [x] Audit logging
- [x] SSE real-time updates
- [x] Debug database viewer
- [x] Password recovery flow
- [x] Session status API

### Key Features Implemented

1. **Server Status Checking**: Timechecker runs every 60 seconds, stores results in database
2. **Authentication Flows**: Create family, login as parent, password recovery, set password
3. **Device Management**: Add devices, remove devices, view device list
4. **User Management**: Add users to family
5. **Time Limit Rules**: Create, update, delete time limit rules
6. **Sync Protocol**: Pull/push data synchronization with server
7. **Session Persistence**: Server selection and auth tokens persist across restarts
8. **Audit Logging**: All API requests logged with structured format
9. **Real-time Updates**: SSE endpoint for dashboard streaming
10. **Debug Tools**: Database viewer for troubleshooting

## References

- [API Reference](api/api-reference.md)
- [Data Models](architecture/data-models.md)
- [Design Overview](architecture/design.md)
- [Testing Guide](development/testing-guide.md)
- [UI Patterns](development/ui-patterns.md)
- [Add User to Family Plan](plans/add-user-to-family/)
- [Time Limit Rules Plan](plans/time-limit-rules/)