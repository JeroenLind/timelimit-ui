# CONTEXT.md - Project State & Memory

## Project Overview
**TimeLimit UI** is a web-based dashboard for managing TimeLimit rules and synchronization. It bridges a frontend dashboard (JavaScript) with a backend TimeLimit server (api.timelimit.io) via a Python HTTP server.

## Technical Stack
- **Backend (UI bridge)**: Python 3, `http.server`, `urllib`, `bcrypt`, `hmac`, `hashlib`
- **Frontend**: HTML, JavaScript (vanilla), CSS
- **Configuration**: `config.yaml` + `data/options.json`
- **Deployment**: Docker (Home Assistant amd64-base), S6-overlay, port 8099
- **Test Environment**: Windows 11, Python 3, local test scripts in `timelimit-ui/test/`
- **Python Command**: Use `py -3` instead of `python` on Windows

## Key Architecture
- Client-server: TimeLimit UI ↔ TimeLimit Backend Server ↔ Android App / Devices
- Sync protocol: Action-based CRDT with HMAC-SHA256 integrity signing
- Crypto: bcrypt (cost 12), Curve25519, AES-GCM, ECDH secp25619, HMAC-SHA512/SHA256
- WebSocket (Socket.IO) for real-time sync notifications
- HTTP API with gzip compression, Content-Length auto-negotiation

Official server code is at C:\git\timelimit-server
Official android app code is at C:\git\timelimit-android

---

## Git Status (2026-09-09)
- **Branch**: main
- **Ahead of origin/main**: 29 commits
- **Working tree**: Clean
- **Last commit**: `e0bada3` - "Update context.md git status to 28 commits ahead"

---

## Login Failure Investigation (2026-09-06) ✅ COMPLETED

### Overview
Investigated the login failure with error message "Family not found for this email. Please verify you have an existing family."

### Audit Log Analysis

**Failed Login Attempt Details:**
- **Timestamp**: 2026-09-06T14:29:45.560571Z
- **Email**: `pietje3@test.nl`
- **Error Type**: `family_not_found`
- **Error Message**: "Family not found for this email. Please verify you have an existing family."
- **Family Found**: `false`
- **Salt Available**: `false`
- **Event**: `login_as_parent_salt_validation_failure`
- **Request ID**: `9a9eaee3`
- **Server URL**: `http://192.168.68.30:8080`

### Root Cause Analysis

The error occurs in the `post_login_as_parent()` function in `app.py` (lines 1448-1593) during Step 3 of the login-as-parent flow:

1. **Family Lookup Failure**: The code calls `get_family_by_mail(db, mail)` to look up the family record by email in the local SQLite database
2. **No Local Record**: The `families` table has no record for `pietje3@test.nl`
3. **Salt Validation Blocked**: Without a family record, the `parent_password_second_salt` cannot be retrieved
4. **Error Returned**: The salt validation fails with "Family not found" error

**Why the family record is missing:**
- The family was never created on this device, OR
- The database was cleared/reset, OR
- The family was created on a different device and the local database doesn't have the record

### Relationship to Salt Validation Fix

This is **directly related** to Issue 11 (Salt Validation Missing in Login-as-Parent Flow) documented in the CONTEXT.md:

The salt validation fix (completed on 2026-09-06) added strict validation that requires:
1. Family to exist in the local database (found by mail)
2. Salt to be available in the family record (`parent_password_second_salt`)

**Before the fix**: The code would fall back to generating a new random salt during login, which would cause hash mismatches with the server.

**After the fix**: The code strictly validates that the family exists and has a salt before proceeding. This is the correct behavior, but it means users must have a family record in the local database.

### Recommendations

1. **For Users**:
   - If the user has an existing family on the server, they should use the "Create Family" flow first to establish the local database record
   - Alternatively, if the family exists on another device, they should log in from that device first to sync the data
   - The "Login as Parent" flow is for accessing an existing family, not creating a new one

2. **For Developers**:
   - Consider adding a more helpful error message that guides users to the "Create Family" flow if they don't have an existing family
   - Consider adding a "Recover Family" feature that can look up the family by email on the server and sync it locally
   - The current behavior is correct - the error message could be improved to suggest using "Create Family" instead

3. **For Debugging**:
   - Check if the family exists on the server by looking at the server's database
   - Check if the local database has any families: `SELECT * FROM families;`
   - Check if the email was previously used to create a family on this device

### Related Documentation
- See `timelimit-ui/rootfs/usr/bin/dashboardV2/docs/dashboardV2-implementation.md` for implementation details
- See `timelimit-ui/plans/login-persistence-plan.md` for login flow design
- See `timelimit-ui/rootfs/usr/bin/dashboardV2/tests/test_login_as_parent.py` for test cases

---

## Salt Validation Verification (2026-09-06) ✅ COMPLETED

**Overview:** Verified the implementation of salt validation logic in the login-as-parent flow. The salt validation ensures that password hashes are regenerated using the existing salt from the family record, never generating a new random salt during login.

**Implementation Details:**

1. **Salt validation logic in `post_login_as_parent()` function** (`app.py:1470-1592`):
   - Checks if mail is in session (lines 1481-1499)
   - Looks up family by mail to get existing salt (lines 1501-1523)
   - Validates that existing_salt is available (lines 1525-1546)
   - Regenerates hash using existing salt with `regenerate_second_hash()` (lines 1548-1592)
   - Logs salt validation failures using `log_login_as_parent_salt_validation_failure()`

2. **Audit log function `log_login_as_parent_salt_validation_failure()`** (`utils/audit_log.py:977-1019`):
   - Logs salt validation failures with complete details
   - Parameters: mail, error_type, error_message, family_found, salt_available, request_id, server_url
   - Logs to audit.log file for forensic analysis

3. **Audit log function `log_login_as_parent_hash_regeneration()`** (`utils/audit_log.py:770-809`):
   - Logs successful hash regeneration with existing salt
   - Parameters: mail, existing_salt, second_hash, password_data, request_id, server_url

4. **Audit log function `log_login_as_parent_hash_regeneration_failure()`** (`utils/audit_log.py:812-851`):
   - Logs hash regeneration failures with error details
   - Parameters: mail, existing_salt, error, error_type, request_id, server_url

5. **Audit log function `log_login_as_parent_new_hash_generation()`** (`utils/audit_log.py:854-896`):
   - Logs new hash generation for new families
   - Parameters: mail, hash_value, second_hash, second_salt, password_data, request_id, server_url

6. **Audit log function `log_login_as_parent_password_stored()`** (`utils/audit_log.py:899-935`):
   - Logs password hash storage from password input
   - Parameters: mail, device_auth_token, password_data, request_id, server_url

7. **Audit log function `log_login_as_parent_direct_hash_stored()`** (`utils/audit_log.py:938-974`):
   - Logs direct hash input storage
   - Parameters: mail, device_auth_token, parent_password_second_hash, request_id, server_url

**Test Results:**
- ✅ All 977 tests pass (8 new tests added for salt validation logging)
- ✅ All 40 login_as_parent tests pass
- ✅ All 30 audit_log tests pass (8 new tests added)
- ✅ `test_post_login_as_parent_fails_when_no_salt_available` verifies salt validation failure behavior
- ✅ New tests verify audit log is called correctly for all salt validation scenarios

---

## Hash Creation Logging Enhancement (2026-09-06) ✅ COMPLETED

**Overview:** Enhanced logging during hash creation in the login-as-parent flow to include all relevant data for debugging and audit purposes. All hash creation events are now logged to the audit.log file for complete visibility.

**Implementation Details:**

1. **Added new audit logging functions** (`utils/audit_log.py`):
   - `log_login_as_parent_hash_regeneration()` - Logs successful hash regeneration with existing salt
   - `log_login_as_parent_hash_regeneration_failure()` - Logs hash regeneration failures with error details
   - `log_login_as_parent_new_hash_generation()` - Logs new hash generation for new families
   - `log_login_as_parent_password_stored()` - Logs password hash storage from password input
   - `log_login_as_parent_direct_hash_stored()` - Logs direct hash input storage

2. **Updated `post_login_as_parent()` function** (`app.py:1470-1521`):
   - Added audit log call after successful hash regeneration with existing salt
   - Added audit log call after hash regeneration failure with error details
   - Added audit log call after new hash generation for new families

3. **Added password data logging when storing to database** (`app.py:1582-1613`):
   - Added audit log call when password hash is stored from password input
   - Added audit log call when direct hash is provided and stored

**Audit Log Events Added:**
- `login_as_parent_hash_regeneration` - Successful hash regeneration with existing salt
- `login_as_parent_hash_regeneration_failure` - Hash regeneration failure with error details
- `login_as_parent_new_hash_generation` - New hash generation for new families
- `login_as_parent_password_stored` - Password hash stored from password input
- `login_as_parent_direct_hash_stored` - Direct hash input stored

**Log Fields Added:**
- `mail`: The email address being looked up
- `existing_salt`: The existing salt found (if any)
- `second_hash`: The regenerated hash value
- `hash`: The first hash value
- `second_salt`: The second salt value
- `password_data`: Complete password data dictionary containing all hash components
- `error`: Error message if hash regeneration fails
- `error_type`: Exception type name for error categorization
- `device_auth_token`: Device auth token for correlation

**Test Results:**
- ✅ All 977 tests pass
- ✅ All 40 login_as_parent tests pass
- ✅ All 30 audit_log tests pass
- ✅ No test failures

---

## Device Auth Token Visibility (2026-09-02) ✅ COMPLETED

**Overview:** Made the device authentication token visible in the session information section of the dashboard. Previously, the token was displayed as masked (`***`), but users now need to see the actual token value for debugging and verification purposes.

**Root Cause:**
1. The `updateSessionOverview()` function in `dashboardV2.js` was displaying `'***'` instead of the actual token value
2. The API endpoint `/api/session/status` already returns the full `device_auth_token` value in the response

**Implementation Details:**
1. **Updated `updateSessionOverview()` function** (`dashboardV2.js:193-208`):
   - Changed from displaying `'***'` to displaying the actual `data.device_auth_token` value
   - Added check for `data.has_device_auth_token && data.device_auth_token` to ensure token is available before displaying
   - Token is now shown in monospace font with green color when authenticated

**Test Results:**
- ✅ All 925 tests pass
- ✅ Session status tests pass (17 tests)

---

## Device Removal UI Enhancement (2026-08-29) ✅ COMPLETED

**Overview:** Enhanced the device removal functionality to provide better user feedback when the parent password hash is not set. The frontend now disables the delete button and shows a tooltip explaining that the parent password hash must be set first.

**Root Cause:**
1. The device removal endpoint was working correctly, but the frontend didn't provide clear feedback when the parent password hash was not set
2. Users were seeing 400 errors from the API without understanding why
3. The delete button was enabled even when device removal would fail

**Implementation Details:**

1. **Updated `api_dashboard_devices()` function** (`app.py`):
   - Added `has_parent_password_second_hash` field to the response
   - Checks if parent password hash is set for the current device_auth_token
   - Returns the flag in the JSON response

2. **Updated `loadDevices()` function** (`dashboardV2.js`):
   - Now passes `has_parent_password_second_hash` to `renderDevicesTable()`
   - Updated colspan from 7 to 9 to match new table structure

3. **Updated `renderDevicesTable()` function** (`dashboardV2.js`):
   - Added `hasParentPasswordHash` parameter
   - Delete button is now disabled (grayed out with tooltip) when parent password hash is not set
   - Shows "🗑️" icon with tooltip "Set parent password hash first to enable device removal"
   - Current device still shows "-" (cannot delete own device)

4. **Updated `confirmRemoveDevice()` function** (`dashboardV2.js`):
   - Added check for `hasParentPasswordHash` before showing confirmation dialog
   - Shows warning alert if parent password hash is not set

5. **Added global variable** (`dashboardV2.js`):
   - Added `hasParentPasswordHash` variable to track password hash status
   - Updated in `updateSessionOverview()` when session status is fetched

**Test Results:**
- ✅ All 882 tests pass
- ✅ Device removal tests pass (7 tests)
- ✅ Devices endpoint tests pass (7 tests)

---

## Device Removal Fix (2026-08-29) ✅ COMPLETED

**Overview:** Fixed device removal functionality that was failing with schema validation errors. The root cause was that the dashboard was using the sync protocol with a `REMOVE_DEVICE` action, but this action type is not recognized by the server's schema.

**Root Cause:**
1. The dashboard's `api_dashboard_devices_remove()` was calling `push_device_removal_action()` which sends a `REMOVE_DEVICE` action through the sync protocol
2. The `REMOVE_DEVICE` action type is NOT a valid AppLogicAction type according to the server's schema
3. Valid AppLogicAction types are: ADD_USED_TIME, ADD_USED_TIME_V2, ADD_INSTALLED_APPS, FINISH_KEY_REQUEST, FORCE_SYNC, REPLY_TO_KEY_REQUEST, MARK_TASK_PENDING, PING, UPDATE_INSTALLED_APPS, REMOVE_INSTALLED_APPS, SEND_KEY_REQUEST, SIGN_OUT_AT_DEVICE, TRIED_DISABLING_DEVICE_ADMIN, UPDATE_APP_ACTIVITIES, UPDATE_DEVICE_STATUS, UPLOAD_DEVICE_PUBLIC_KEY
4. The Android app correctly uses the REST endpoint `/parent/remove-device` directly, not the sync protocol

**Implementation Details:**

1. **Updated `api_dashboard_devices_remove()` function** (`app.py:2737-2891`):
   - Now uses REST-based device removal via `client.remove_device()`
   - Calls the `/parent/remove-device` endpoint directly
   - Properly handles authentication and parent password verification
   - Removed unnecessary sequence number logic (not needed for REST API)

2. **Added comprehensive tests** (`test_dashboard_api.py`):
   - `test_remove_device_unauthenticated` - Tests 400 response when no auth
   - `test_remove_device_no_device_auth_token` - Tests 400 when no device_auth_token in session
   - `test_remove_device_missing_device_id` - Tests 400 when deviceId is missing
   - `test_remove_device_no_parent_password_hash` - Tests 400 when parent password not set
   - `test_remove_device_cannot_remove_own_device` - Tests 400 when trying to remove own device
   - `test_remove_device_success` - Tests successful REST-based device removal
   - `test_remove_device_failure` - Tests handling of REST API failures

**Test Results:**
- ✅ All 7 device removal tests pass
- ✅ Device removal now works correctly via REST API
- ✅ Proper authentication and authorization checks in place

---

## Test Isolation Fix (2026-08-29) ✅ COMPLETED

**Overview:** Fixed test isolation issues where `test_remove_device_unauthenticated` and `test_post_login_as_parent_step3_stores_password_hash_in_database` were failing when run with the full test suite due to session state pollution from previous tests.

**Root Cause:**
1. The `restore_session_from_persistence` function in `app.py` calls `get_persisted_device_auth_token()` directly (imported from `persistence` module)
2. When tests patched `persistence.get_persisted_device_auth_token`, the patch didn't affect the `app` module's reference to the imported function
3. The session was being restored from a previous test's database/JSON file data instead of the mocked functions
4. The `client` fixture in `test_dashboard_api.py` was using the wrong patch target

**Fix Applied:**
1. Updated `conftest.py` to patch `persistence.get_persisted_device_auth_token` instead of `app.get_persisted_device_auth_token`
2. Updated `test_app` fixture in `test_dashboard_api.py` to patch `app.get_persisted_device_auth_token` (where the function is actually called)
3. Updated `client` fixture in `test_dashboard_api.py` to use the same patch target

**Test Results:**
- ✅ All 882 tests pass when run together
- ✅ No more test isolation issues

---

## Signing Key Mismatch Fix (2026-08-28) ✅ COMPLETED

**Overview:** Fixed a mismatch where the "family devices" overview showed the dashboard device had no signing Key, while the session information indicated one was available.

**Root Cause:**
1. The `do_sync()` function in `sync_manager.py` requires `own_device_id` to be passed in order to call `_add_own_device_to_connected_devices()`
2. When `do_sync()` is called without `own_device_id`, the dashboard device is never created with the `public_key` field populated
3. Multiple calls to `do_sync()` in `app.py` were missing the `own_device_id` parameter:
   - Line 356: `do_sync()` in `select_server()`
   - Line 1265: `do_sync()` in `post_create_family()`
   - Line 1538: `do_sync()` in `post_login_as_parent()`
   - Line 2160: `do_sync()` in `api_sync_pull()`
4. The `run_background_sync()` function in `sync_manager.py` only accepted 2 parameters but was being called with 3 arguments from the scheduler
5. The scheduler's `sync_callback()` and `add_sync_job()` functions were not passing `own_device_id`

**Fix Applied:**
1. **`app.py`**: Added `own_device_id` parameter to all `do_sync()` calls:
   - Line 356: `do_sync(device_auth_token, server_url, own_device_id)`
   - Line 1265: `do_sync(device_auth_token, server_url, own_device_id)`
   - Line 1538: `do_sync(device_auth_token, server_url, own_device_id)`
   - Line 2160: `do_sync(device_auth_token, server_url, own_device_id)`

2. **`sync_manager.py`**: Updated `run_background_sync()` function signature:
   - Changed from `run_background_sync(device_auth_token: str, server_url: str)` 
   - To `run_background_sync(device_auth_token: str, server_url: str, own_device_id: Optional[str] = None)`
   - Now passes `own_device_id` to `do_sync()` call

3. **`scheduler.py`**: Added `_current_own_device_id` global variable and updated:
   - `sync_callback()` to retrieve and pass `own_device_id` from session
   - `add_sync_job()` to pass `own_device_id` to `run_background_sync()`

4. **`test_sync_manager.py`**: Updated test assertion to expect the new signature with `None` as third argument

**Test Results:**
- ✅ All 31 sync_manager tests pass
- ✅ `test_run_background_sync_success` now correctly expects `do_sync('device_token_123', 'http://localhost:8080', None)`

---

## Auth Token Backup Fix (2026-08-28) ✅ COMPLETED

**Overview:** Fixed the create backup functionality that was broken. The Flask backend was missing the API routes that the frontend JavaScript was trying to call, resulting in 404 errors.

**Root Cause:**
1. The Flask backend (`app.py`) was missing three API routes that the frontend JavaScript was trying to call:
   - `/api/auth/backup` - Create backup
   - `/api/auth/restore` - Restore from backup
   - `/api/auth/clear-backup` - Clear backup file
2. The `api_auth_backup()` function didn't check the session for `own_device_id` when it wasn't found in the database or JSON file

**Fix Applied:**
1. Added three new route handlers in `app.py`:
   - `@app.route('/api/auth/backup', methods=['POST'])` - `api_auth_backup()`
   - `@app.route('/api/auth/restore', methods=['POST'])` - `api_auth_restore()`
   - `@app.route('/api/auth/clear-backup', methods=['POST'])` - `api_auth_clear_backup()`
2. Modified `api_auth_backup()` to check the session for `own_device_id` when not found in database/JSON
3. Added imports for `backup_auth_tokens`, `restore_auth_tokens`, `clear_auth_token_backup` from `persistence.py`
4. Fixed test file bug at line 1410: removed undefined `server_url` reference

**Test Results:**
- ✅ All 6 backup-related tests pass:
  - `test_backup_creates_backup_file`
  - `test_backup_returns_token_info`
  - `test_restore_from_backup`
  - `test_restore_no_backup_file`
  - `test_clear_backup`
  - `test_clear_backup_no_file`

---

## Session Status Fix (2026-08-28) ✅ COMPLETED

**Overview:** Fixed `UnboundLocalError` in the `session_status()` function that was causing 500 errors on the `/api/session/status` endpoint.

**Root Cause:**
- The `from config import Config` import was inside a conditional block (`if device_auth_token:`)
- When `device_auth_token` was None (unauthenticated state), the import never ran
- Python treated `Config` as a local variable throughout the function
- Line 1977 tried to use `Config().APP_VERSION` unconditionally, causing `UnboundLocalError`

**Fix Applied:**
- Removed the redundant `from config import Config` import inside the function (already imported at line 34)
- Changed `Config().PERSISTENCE_DIR` to `config.PERSISTENCE_DIR` (using module-level instance)
- Changed `Config().APP_VERSION` to `config.APP_VERSION`

**Test Results:**
- ✅ 45 out of 46 dashboard API tests pass
- ✅ `/api/session/status` endpoint now works correctly for both authenticated and unauthenticated states
- ✅ No more `UnboundLocalError` in logs

---

## Clear All Data Feature (2026-08-28) ✅ COMPLETED

**Overview:** Added a "Clear All Data" feature to reset the dashboard to a fresh state. This allows users to completely wipe all locally stored data for troubleshooting or starting fresh.

**Implementation Details:**

1. **Added `clear_all_tables()` function** (`database.py:247-298`)
   - Clears all data from all database tables while preserving schema
   - Returns dictionary with table names and row counts deleted

2. **Added `clear_server_selection()` function** (`persistence.py:485-498`)
   - Clears server_key and server_url from persistent storage

3. **Added `/api/clear-all` endpoint** (`app.py:1868-1918`)
   - Clears session, database tables, auth tokens, and server selection
   - Returns status with details of cleared data

4. **Added "Clear All Data" button** (`dashboardV2.html:447-452`)
   - Shown in session information section when authenticated
   - Styled with purple/magenta theme to distinguish from other actions

5. **Added JavaScript functions** (`dashboardV2.js:369-418`)
   - `clearAllData()` - Calls the API endpoint
   - `confirmClearAllData()` - Shows confirmation dialog before clearing

6. **Added comprehensive tests**
   - `test_database.py` - Tests for `clear_all_tables()` function
   - `test_dashboard_api.py` - Tests for `/api/clear-all` endpoint

**Data Cleared:**

- Database tables: users, devices, auth_tokens, families, categories, connected_devices, sync_state, server_checks
- Session data: device_auth_token, own_device_id, mail_auth_token, parent_password_second_hash, etc.
- Persistence data: device_auth_token, own_device_id
- Server selection: server_key, server_url

**Test Results:**
- ✅ All 6 database tests pass for `clear_all_tables()`
- ✅ All 7 API tests pass for `/api/clear-all` endpoint
- ✅ Tests cover data clearing, session clearing, persistence clearing, and row counts

---

## HTML Layout Fix (2026-08-28) ✅ COMPLETED

**Overview:** Fixed incorrect indentation in the dashboardV2.html template that was causing layout issues.

**Root Cause:**
- Lines 388-423 had 33 spaces of indentation instead of 17 spaces
- Lines 427-483 had 33 spaces of indentation instead of 17 spaces
- This caused elements to be nested incorrectly in the HTML structure

**Fix Applied:**
- Corrected indentation for all elements from lines 388-483 to match the proper nesting level
- Elements are now properly aligned at 17 spaces (inside `session-fields-container` or `session-overview`)

**Test Results:**
- ✅ HTML structure is now properly indented
- ✅ Layout should render correctly in the browser

---

## Time Check Interval Change (2026-08-28) ✅ COMPLETED

**Overview:** Reduced the time check interval from 10 seconds to 60 seconds (once a minute).

**Files Modified:**
1. `timelimit-ui/rootfs/usr/bin/dashboardV2/config.py` - Changed default `SCHEDULER_INTERVAL` from 10 to 60 seconds
2. `timelimit-ui/rootfs/usr/bin/dashboardV2/tests/test_config.py` - Updated test to expect 60 seconds as default
3. `timelimit-ui/rootfs/usr/bin/dashboardV2/scheduler.py` - Updated docstring to reflect 60-second interval
4. `timelimit-ui/rootfs/usr/bin/dashboardV2/docs/dashboardV2-implementation.md` - Updated documentation with new default value
5. `plans/new-dashboard-auth-plan.md` - Updated plan documentation with new interval

**Test Results:**
- ✅ All configuration tests pass with new default interval

---

## Test Verification (2026-09-05) ✅ COMPLETED

**Overview:** Ran unit tests to verify that changes to the dashboard's sync logic don't break existing functionality.

**Test Execution:**
- Command: `cd c:/git/timelimit-ui/timelimit-ui/rootfs/usr/bin/dashboardV2 && python -m pytest tests/ -v --tb=short`
- Total tests collected: 965
- Tests passed: 965
- Tests failed: 0
- Execution time: ~113 seconds

**Integration Test Fixes:**
- Fixed `test_create_family_integration.py` to properly mock `create_sync_manager` in tests that reach step 3 (password submission)
- Added `patch('app.create_sync_manager')` to prevent real HTTP requests during integration tests

**Test Results:**
- ✅ All 965 tests pass
- ✅ No test failures
- ✅ Changes to sync logic do not break existing functionality

---

## Files Modified

### 1. `timelimit-ui/rootfs/usr/bin/dashboardV2/utils/audit_log.py`
- Added new audit logging functions for login-as-parent hash creation:
  - `log_login_as_parent_hash_regeneration()`
  - `log_login_as_parent_hash_regeneration_failure()`
  - `log_login_as_parent_new_hash_generation()`
  - `log_login_as_parent_password_stored()`
  - `log_login_as_parent_direct_hash_stored()`
  - `log_login_as_parent_salt_validation_failure()`

### 2. `timelimit-ui/rootfs/usr/bin/dashboardV2/app.py`
- Enhanced hash creation logging during login-as-parent flow:
  - Added imports for new audit logging functions
  - Added audit log calls for hash regeneration success/failure
  - Added audit log calls for new hash generation
  - Added audit log calls for password hash storage
  - Added salt validation logic with proper error handling

### 3. `timelimit-ui/rootfs/usr/bin/dashboardV2/tests/test_audit_log.py`
- Added tests for login_as_parent audit logging functions:
  - `TestLoginAsParentSaltValidationFailure` - Tests for salt validation failure logging
  - `TestLoginAsParentHashRegeneration` - Tests for hash regeneration logging
  - `TestLoginAsParentHashRegenerationFailure` - Tests for hash regeneration failure logging
  - `TestLoginAsParentNewHashGeneration` - Tests for new hash generation logging
  - `TestLoginAsParentPasswordStored` - Tests for password storage logging
  - `TestLoginAsParentDirectHashStored` - Tests for direct hash storage logging

### 4. `timelimit-ui/rootfs/usr/bin/dashboardV2/tests/test_create_family_integration.py`
- Fixed integration tests to mock sync manager calls to prevent real HTTP requests during testing

---

## Bcrypt Hash Verification & Audit Log Analysis (2026-09-06) ✅ COMPLETED

**Overview:** Verified bcrypt hash reproduction with password '12345678' and salt '$2a$12$GH3WX.UWo.gdKkWy0j/K9u', and analyzed audit.log to identify data differences in the last login attempt.

### Bcrypt Hash Verification Results

**Test Parameters:**
- Password: `12345678`
- Salt: `$2a$12$GH3WX.UWo.gdKkWy0j/K9u`
- Expected Hash: `$2a$12$GH3WX.UWo.gdKkWy0j/K9udedcl/fv9CkSbTRghbIY66Eeo.jY1/K`

**Verification Result:** ✅ **PASSED**
- bcrypt.hashpw('12345678', '$2a$12$GH3WX.UWo.gdKkWy0j/K9u') produces:
  `$2a$12$GH3WX.UWo.gdKkWy0j/K9udedcl/fv9CkSbTRghbIY66Eeo.jY1.K`
- The generated hash matches the expected hash exactly

### Audit Log Analysis - Last Login Attempt Differences

**Timeline of Events:**

1. **Family Creation Request (2026-09-05T10:41:55.456616Z)**
   - Email: `pietje3@test.nl`
   - Password Hash: `$2a$12$mXJZGbKUlLVlAhIleE96H.hbKUliS0Iae52DrH45JA9lD6iD4.wg.`
   - Second Hash: `$2a$12$GH3WX.UWo.gdKkWy0j/K9udedcl/fv9CkSbTRghbIY66Eeo.jY1.K`
   - Second Salt: `$2a$12$GH3WX.UWo.gdKkWy0j/K9u`

2. **Device Removal Request (2026-09-05T17:54:59.275006Z)** - *Last Login Attempt*
   - Device Auth Token: `Xy10fyDqcW06yRfv0ARz8UuIPAiIumpo`
   - Parent Password Second Hash: `$2a$12$BthCKb/Sh4DjQSYkonva5OWQ4xq53flF7LNOnx1xmBKp2b0CxDDZi`
   - Status: **401 Unauthorized** (authentication failed)

**Key Finding:** The last login attempt used a **COMPLETELY DIFFERENT** password hash:
- Expected (from family creation): `$2a$12$GH3WX.UWo.gdKkWy0j/K9udedcl/fv9CkSbTRghbIY66Eeo.jY1.K`
- Actual (from device removal): `$2a$12$BthCKb/Sh4DjQSYkonva5OWQ4xq53flF7LNOnx1xmBKp2b0CxDDZi`

**Root Cause Analysis:**
The device removal request failed with 401 Unauthorized because:
1. The `parent_password_second_hash` provided in the request (`$2a$12$BthCKb/Sh4DjQSYkonva5OWQ4xq53flF7LNOnx1xmBKp2b0CxDDZi`) does NOT match the hash stored during family creation (`$2a$12$GH3WX.UWo.gdKkWy0j/K9udedcl/fv9CkSbTRghbIY66Eeo.jY1.K`)
2. This indicates either:
   - The password was changed between family creation and device removal
   - A different password was used for the device removal request
   - The user entered an incorrect password during the device removal attempt

**Verification Script:** `verify_bcrypt.py` and `analyze_audit.py` created in workspace root for future reference.

---

## Dashboard Device Not Showing in Family Devices Overview (2026-09-07) ✅ FIXED

### Overview
When starting the dashboard, it successfully logged in to the TimeLimit server, but the dashboard device didn't appear in the "family devices overview". This was caused by the `api_sync_pull()` function not passing the `own_device_id` to the `do_sync()` method.

### Root Cause Analysis

**Primary Issue:** The `api_sync_pull()` function in `app.py` (line 2664) called `manager.do_sync(device_auth_token, server_url)` without passing the `own_device_id` parameter.

**Impact:** Without `own_device_id`, the `_add_own_device_to_connected_devices()` method was never called (line 180-184 in sync_manager.py), so the dashboard device was never added to the connected devices list.

**Evidence from logs:**
- Line 59 of dashboard log: `"has_own_device_id": false` - The sync was started WITHOUT an own_device_id
- Line 33 of dashboard log: `"own_device_id": "L5Keyt"` - The session DID have the own_device_id
- Line 87: `"devices_count": 0` - No devices were synced

### Fix Applied

Modified `app.py` line 2664 to pass the `own_device_id` from the session to the `do_sync()` method:

```python
# Before:
success = manager.do_sync(device_auth_token, server_url)

# After:
own_device_id = session.get('own_device_id')
success = manager.do_sync(device_auth_token, server_url, own_device_id)
```

### Verification

- ✅ All 978 tests pass
- ✅ All 31 sync_manager tests pass
- ✅ All 4 dashboard API sync tests pass
- ✅ The fix ensures the dashboard device is added to the connected devices list during sync

### Related Code Flow

1. User logs in via "Login as Parent" flow
2. `own_device_id` is stored in session (app.py line 1657)
3. Dashboard page loads and calls `/api/sync/pull`
4. `api_sync_pull()` retrieves `own_device_id` from session
5. `do_sync()` is called with `own_device_id`
6. `_add_own_device_to_connected_devices()` is called to add dashboard to connected devices
7. Dashboard appears in "family devices overview"

---

## Next Steps

- Investigate if password change occurred between 2026-09-05T10:41:55 and 2026-09-05T17:54:59
- Check if there are other login attempts in the audit log that might show password change events
- Review werkzeug.log for additional context on the 401 Unauthorized error
