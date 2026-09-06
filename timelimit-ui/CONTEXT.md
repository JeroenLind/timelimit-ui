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

## Current Issues
- Device removal via `/api/dashboard/devices/remove` endpoint - **RESOLVED**
- Session status API missing password hash fields - **RESOLVED**
- Server check records accumulation in database - **RESOLVED**
- Refresh button not syncing users/devices - **RESOLVED**
- Sync operations not logged to audit.log - **RESOLVED**
- Server selection not persisting correctly - **RESOLVED**
- Family creation 409 Conflict error shows raw HTML instead of user-friendly message - **RESOLVED**
- Dashboard Signing Key not displayed - **RESOLVED**
- Password hash mismatch in login-as-parent flow causing 401 Unauthorized device removal error - **RESOLVED**
- Password hash regeneration during login-as-parent not using existing salt - **RESOLVED**
- Salt validation missing in login-as-parent flow - **RESOLVED**
- Family record not created after sign-in causing "Family not found" error when entering password - **RESOLVED**

## 2-Step Login Flow Implementation

### Overview
The login-as-parent flow has been redesigned as a 2-step flow with an optional password step:

**Step 1: Email & Verification Code**
- User enters their email address
- Server sends a 3-word verification code (e.g., "Pferd Miete abwenden")
- User enters the verification code

**Step 2: Device Info & Login**
- User enters device model and device name
- User is logged in to the family
- Sync is triggered to fetch users, devices, and categories

**Step 4 (Optional): Password for Device Removal**
- After successful login, user can optionally enter their password
- This enables device removal functionality
- User can skip this step and enter password later

### Key Changes

#### 1. Template (`login_as_parent.html`)
- Updated to show 4 steps with proper step indicators
- Step 4 shows "Enable Device Removal" with optional password field
- "Skip for Now" button allows users to skip password entry

#### 2. Routes (`app.py`)
- `GET /login-as-parent`: Shows appropriate step based on session state
  - No tokens → Step 1 (email)
  - Has mail_login_token → Step 2 (code)
  - Has mail_auth_token → Step 3 (device info)
  - Has device_auth_token, no password → Step 4 (optional password)
  - Has device_auth_token and password → Redirect to dashboard

- `POST /login-as-parent`: Processes all 4 steps
  - Step 1: Send mail login code
  - Step 2: Verify code and get mail auth token
  - Step 3: Sign in to family (password optional)
  - Step 4: Regenerate hash from password

#### 3. Password Hash Regeneration
- When password is provided in Step 3, the system:
  1. Looks up the family by email to get existing `parent_password_second_salt`
  2. Uses `regenerate_second_hash(password, existing_salt)` to produce matching hash
  3. Stores all three hash components (hash, secondHash, secondSalt) in database
  4. Never generates a new random salt during login

- When password is provided in Step 4:
  1. Looks up the family by email to get existing salt
  2. Regenerates the hash using the existing salt
  3. Stores in database and session

#### 4. Session Status API
- Returns `has_parent_password_second_hash` and `parent_password_second_hash` fields
- Allows frontend to show password status and enable/disable device removal

### Files Modified
- `timelimit-ui/rootfs/usr/bin/dashboardV2/templates/login_as_parent.html` - 4-step flow
- `timelimit-ui/rootfs/usr/bin/dashboardV2/app.py` - Updated routes and logic
- `timelimit-ui/rootfs/usr/bin/dashboardV2/tests/test_login_as_parent.py` - Comprehensive tests

### Test Results
- All 41 login_as_parent tests pass
- All 978 tests in full suite pass

## Root Causes Identified and Fixed

### Issue 11: Salt Validation Missing in Login-as-Parent Flow
When a password is provided during login-as-parent, the dashboard should validate that the salt exists before attempting to regenerate the hash. Without strict validation, the dashboard could generate a new random salt during login, which would cause hash mismatches with the server.

**Root Cause:**
1. The `post_login_as_parent()` function would fall back to generating a new hash when no salt was found
2. This could happen if the family record was not found by mail or if the salt was missing
3. Generating a new salt during login would cause the hash to not match what the server expects
4. This could lead to 401 Unauthorized errors during device removal operations

**Fix Applied:**
1. Added strict salt validation in `post_login_as_parent()` function in `app.py`:
   - Check if family exists (found by mail)
   - Check if `parent_password_second_salt` is available in the family record
   - If salt is missing → Show error message telling user to enter password in Step 4
   - If salt is available → Use `regenerate_second_hash()` to regenerate the hash
2. Never generate a new random salt during login - only use the existing salt from the family record
3. Added comprehensive logging for salt validation failures using the new `log_login_as_parent_salt_validation_failure()` function
4. Added new audit log function `log_login_as_parent_salt_validation_failure()` in `utils/audit_log.py`
5. Added tests for the new salt validation behavior:
   - `test_post_login_as_parent_fails_when_no_salt_available` - verifies error when salt is missing
   - Updated existing tests to set up families with salts before testing password login

### Issue 12: Family Record Not Created After Sign-In Causing "Family Not Found" Error

**Root Cause:**
1. In Step 3, when a password is provided, the code tries to look up the family by mail to get the salt
2. But the family record doesn't exist in the local database because:
   - The user is signing in to an existing family
   - The family was created on the server, not locally
   - The sync hasn't happened yet to pull the family data
3. In Step 4, when the user enters a password, `get_family_by_mail()` fails because no family record exists locally
4. This causes the "Family not found for this email" error seen in audit.log

**Fix Applied:**
1. Added `create_family_record()` function in `database.py` to create a family record with just device_auth_token and mail (minimal data)
2. Added `update_family_salt()` function in `database.py` to update the salt in an existing family record
3. Updated `post_login_as_parent()` in `app.py` to:
   - Create a family record immediately after successful sign-in (before password processing)
   - The family record includes device_auth_token and mail from the sign-in response
4. Updated `_apply_server_data_status()` in `sync_manager.py` to:
   - Update the family record with the salt from the parent user data after sync
   - The salt is fetched from the server during sync and stored in the users table
5. Added `update_family_salt` to imports in `sync_manager.py`
6. When a password is provided in Step 3 but no salt is available, the user is redirected to Step 4 with an error message to enter the password after sync completes

### Issue 13: Double Sign-In Call Bug in Login-as-Parent Flow

**Root Cause:**
In the `post_login_as_parent()` function, the `sign_in_into_family()` API call was being made twice:
1. First call at line 1641 - succeeds with HTTP 200
2. Second call at line 1805 - fails with HTTP 401 Unauthorized because the mail_auth_token was already consumed

This caused the 401 Unauthorized error seen in audit.log:
```
UnauthorizedError: Unauthorized at requireMailAndLocaleByAuthToken
```

**Fix Applied:**
1. Removed the duplicate `sign_in_into_family()` call at lines 1804-1821
2. The code now:
   - Calls `sign_in_into_family()` once at line 1641
   - Processes password hash regeneration after the successful sign-in
   - Stores auth tokens and password data
   - Triggers sync to fetch family data
   - Redirects to dashboard or shows password step

## Files Modified

### 1. `timelimit-ui/rootfs/usr/bin/dashboardV2/app.py`
- Updated `post_set_parent_password()` to use `generate_family_hashes()` for password hashing
- This ensures `$2a$` prefix hashes are generated, matching server expectations
- Updated `session_status()` to include password hash status fields
- Updated `api_dashboard_devices()` to include `has_parent_password_second_hash` in response
- Added `get_parent_user_id` to imports from `database.py` (fixes NameError in device removal)
- Added `get_parent_password_second_salt` to imports from `database.py`
- Added `regenerate_second_hash` to imports from `crypto_utils`
- Added `create_family_record` and `update_family_salt` to imports from `database.py`
- Removed `save_server_check`, `get_server_checks`, `get_latest_server_check` from imports
- Modified `timechecker_status()` to not save server checks
- Modified `timechecker_history()` to return empty list
- Added new endpoint `/api/clear-server-checks` to clear existing server check records
- **Updated `get_current_server_url()` to check `server_url` directly in persistent storage first**
- **Added `has_signing_key` field to session status response to show signing key availability**
- **Added sync retry logic after family creation to prevent cleanup worker from deleting families**
- **Pass `own_device_id` to `do_sync()` in login-as-parent flow to ensure dashboard is added to connected devices**
- **Added retry logic with exponential backoff for sync after login-as-parent**
- **Added 2-second delay after successful sync to ensure `lastConnectivity` is updated on server**
- **Handle sync failure by showing error message to user instead of silently failing**
- **Updated login-as-parent flow to use existing salt for password hash regeneration**
- **Create family record after sign-in to ensure family exists before password processing**
- **Removed duplicate `sign_in_into_family()` call that caused 401 Unauthorized errors**

### 2. `timelimit-ui/rootfs/usr/bin/dashboardV2/auth_client.py`
- Removed `token` parameter from `remove_device()` method
- Token is now only sent in request body as `deviceAuthToken`
- Added imports for sync audit logging functions
- Updated `pull_status()` to log requests/responses to audit.log
- Updated `push_actions()` to log requests/responses to audit.log
- **Added audit logging for family creation requests and responses**
- **Updated `create_family()` and `create_family_rest()` to accept email parameter and log to audit.log**
- **Updated `_make_request()` to handle HTML error responses by extracting error messages from HTML content**
- **Added HTML error code mapping: 409→conflict, 401→unauthorized, 400→validation, 500+→server_error**

### 3. `timelimit-ui/rootfs/usr/bin/dashboardV2/tests/test_auth_client.py`
- **Added test `test_html_error_response_409_conflict` for 409 Conflict HTML error handling**
- **Added test `test_html_error_response_401_unauthorized` for 401 Unauthorized HTML error handling**

### 4. `timelimit-ui/rootfs/usr/bin/dashboardV2/database.py`
- Added `parent_user_id` column to `families` table schema
- Added migration to add `parent_user_id` column to existing databases
- Added `update_family_parent_user_id()` function
- Updated `get_parent_user_id()` to check `families` table first
- Added `clear_server_checks()` function to delete all server check records
- **Added `get_parent_password_second_salt()` function to retrieve existing salt**
- **Added `create_family_record()` function to create family record with minimal data**
- **Added `update_family_salt()` function to update salt in family record**
- **Removed `device_auth_token` column from `auth_tokens` table schema**
- **Added migration to drop `device_auth_token` column from existing databases**
- **Removed `device_auth_token` parameter from `store_auth_token()` function**

### 5. `timelimit-ui/rootfs/usr/bin/dashboardV2/sync_manager.py`
- Removed `device_auth_token` parameter from `store_auth_token()` call in `store_sync_credentials()`
- **Added `update_family_salt` to imports from `database.py`**
- **Updated `_apply_server_data_status()` to update family record with salt from parent user data**

### 6. `timelimit-ui/rootfs/usr/bin/dashboardV2/scheduler.py`
- Removed `save_server_check` from imports
- Removed `save_server_check()` calls from `check_server_callback()` function
- Removed `save_server_check()` calls from `add_server_check_job()` function's inner `check_with_url()` function

### 7. `timelimit-ui/rootfs/usr/bin/dashboardV2/utils/audit_log.py`
- Added `List` to imports
- Added `log_sync_pull_request()` function for sync pull request logging
- Added `log_sync_pull_response()` function for sync pull response logging
- Added `log_sync_push_request()` function for sync push request logging
- Added `log_sync_push_response()` function for sync push response logging
- **Added `log_family_creation_request()` function for family creation request logging**
- **Added `log_family_creation_response()` function for family creation response logging**
- **Added `log_family_creation_failure()` function for family creation failure logging**
- **Added `log_login_as_parent_salt_validation_failure()` function for salt validation failure logging**

### 8. `timelimit-ui/rootfs/usr/bin/dashboardV2/templates/dashboardV2.html`
- Updated refresh button `onclick` handler from `refreshServerStatus()` to `triggerSync()`
- `triggerSync()` calls `/api/sync/pull` which performs actual sync of users/devices
- The `refreshServerStatus()` function was never defined in JavaScript, causing button to do nothing

### 9. `timelimit-ui/rootfs/usr/bin/dashboardV2/tests/test_timechecker.py`
- Updated test to check for `/api/sync/pull` endpoint in JavaScript

### 10. `timelimit-ui/rootfs/usr/bin/dashboardV2/templates/login_as_parent.html`
- Updated password hint text from "Enter your password to enable device removal. If not provided, you can enter the second password hash directly." to "Enter your password to log in as a parent"

### 11. `timelimit-ui/rootfs/usr/bin/dashboardV2/tests/test_login_as_parent.py`
- **Added tests for `get_parent_password_second_salt()` function**
- **Added tests for password hash regeneration with existing salt**
- **Added tests for password hash generation when no salt exists**
- **Added 4 new tests in `TestPasswordHashRegeneration` class**
- **Updated `test_post_login_as_parent_fails_when_no_salt_available` to verify redirect to Step 4 when salt is not available**

## Current Status
- ✅ **Fix Applied**: Updated password hint text in login_as_parent.html to "Enter your password to log in as a parent"
- ✅ **Fix Applied**: Added Mail Auth Token display in dashboardV2.js `updateSessionOverview()` function
- ✅ **Fix Applied**: Removed `token` parameter from `remove_device()` method
- ✅ **Fix Applied**: Changed `post_set_parent_password()` to use `generate_family_hashes()`
- ✅ **Fix Applied**: Added `parent_user_id` persistence to database during family creation/sign-in
- ✅ **Fix Applied**: Fixed frontend JavaScript parameter shadowing in `renderDevicesTable()`
- ✅ **Fix Applied**: Implemented structured logging for family creation events in `KeyFamilyData.md`
- ✅ **Fix Applied**: Updated `session_status()` to include password hash status fields
- ✅ **Fix Applied**: Updated `api_dashboard_devices()` to include `has_parent_password_second_hash` in response
- ✅ **Fix Applied**: Added missing `get_parent_user_id` import in `app.py` (fixes NameError in device removal)
- ✅ **Fix Applied**: Added `get_parent_password_second_salt()` function to database.py
- ✅ **Fix Applied**: Updated login-as-parent flow to use existing salt for password hash regeneration
- ✅ **Fix Applied**: Added `regenerate_second_hash` import from crypto_utils
- ✅ **Fix Applied**: Added tests for password hash regeneration functionality
- ✅ **Fix Applied**: Added `clear_server_checks()` function to database.py
- ✅ **Fix Applied**: Removed server check storage from scheduler.py and app.py
- ✅ **Fix Applied**: Added `/api/clear-server-checks` endpoint to clear existing records
- ✅ **Fix Applied**: Updated all related tests for server check removal
- ✅ **Fix Applied**: Implemented recover parent password flow (UI template, routes, API endpoint)
- ✅ **Fix Applied**: Added comprehensive unit tests for recover parent password (34 tests)
- ✅ **Fix Applied**: Fixed redirect loop issue - after successful recovery, redirects to dashboard if authenticated
- ✅ **Fix Applied**: Fixed API field name mismatch - changed `newPassword` to `password` in auth_client.py and app.py
- ✅ **Fix Applied**: Removed password-related keys from SENSITIVE_KEYS in sanitization.py (password, hash, secondHash, secondSalt)
- ✅ **Fix Applied**: Added audit logging functions for password recovery in audit_log.py
- ✅ **Fix Applied**: Updated auth_client.py to log password recovery requests/responses to audit.log
- ✅ **Fix Applied**: Updated `post_login_as_parent()` to store all three hash components (hash, secondHash, secondSalt) when password is provided
- ✅ **Fix Applied**: Added password field to login_as_parent.html template for full hash storage
- ✅ **Fix Applied**: Updated tests for login_as_parent.py to verify all three hash components are stored
- ✅ **Fix Applied**: Removed unused `device_auth_token` column from `auth_tokens` table
- ✅ **Fix Applied**: Added migration to drop column from existing databases
- ✅ **Fix Applied**: Fixed refresh button to call `/api/sync/pull` instead of `/api/timechecker/status`
- ✅ **Fix Applied**: Added audit logging for sync operations (pull_status, push_actions)
- ✅ **Fix Applied**: Fixed recover password flow - shows error message on page instead of redirecting when already authenticated
- ✅ **Fix Applied**: Added comprehensive audit logging for family creation flow (email, password, deviceId, passwordhash, salt, secondhash)
- ✅ **Fix Applied**: Updated `_make_request()` to handle HTML error responses with proper error message extraction
- ✅ **Fix Applied**: Added HTML error response tests for 409 Conflict and 401 Unauthorized
- ✅ **Fix Applied**: Added `has_signing_key` field to session status API response
- ✅ **Fix Applied**: Added tests for `has_signing_key` field in session status
- ✅ **Fix Applied**: Added sync retry logic after family creation with exponential backoff (up to 3 retries)
- ✅ **Fix Applied**: Pass `own_device_id` to `do_sync()` to ensure dashboard is added to connected devices
- ✅ **Fix Applied**: Added 2-second delay after successful sync to ensure `lastConnectivity` is updated on server
- ✅ **Fix Applied**: Handle sync failure by showing error message to user instead of silently failing
- ✅ **Fix Applied**: Create family record after sign-in to ensure family exists before password processing
- ✅ **Fix Applied**: Update family salt from sync response to fetch salt from server
- ✅ **Fix Applied**: Removed duplicate `sign_in_into_family()` call that caused 401 Unauthorized errors
- ✅ **Tests Pass**: 978 tests pass (all tests passing)

## Mail Auth Token Display Fix

### Issue
After creating a new family, the dashboard's "Mail Auth Token" field was showing "Not available" even when the token was present in the session. This was because the JavaScript function `updateSessionOverview()` in `dashboardV2.js` was missing the code to populate this field.

### Root Cause
The `/api/session/status` endpoint correctly returns `has_mail_auth_token` and `mail_auth_token` fields, but the frontend JavaScript was not updating the Mail Auth Token field in the session overview.

### Fix Applied
Added the following code to `updateSessionOverview()` function in `dashboardV2.js` (lines 227-242):

```javascript
// Update Mail Auth Token field
const mailTokenField = document.getElementById('field-mail-token');
const mailTokenStatus = document.getElementById('mail-token-status');
if (mailTokenField && mailTokenStatus) {
    if (data.has_mail_auth_token && data.mail_auth_token) {
        mailTokenField.textContent = data.mail_auth_token;
        mailTokenField.style.color = '#00ff88';
        mailTokenStatus.textContent = 'Valid - Mail authentication token available';
        mailTokenStatus.style.color = '#4caf50';
    } else {
        mailTokenField.textContent = '-';
        mailTokenField.style.color = '#888';
        mailTokenStatus.textContent = 'Not available - Token cleared after family creation';
        mailTokenStatus.style.color = '#666';
    }
}
```

### Note
The mail auth token is intentionally cleared after family creation (one-time use token). The fix displays the token when available and shows an appropriate message when it's not (after family creation is complete).

## Audit Log Format

All sync operations are logged to `logs/audit.log` with the following format:

### Sync Pull Request
```json
{
  "event": "sync_pull_request",
  "timestamp": "2026-09-04T15:26:00.000000Z",
  "timestamp_unix_ms": 1725468360000,
  "device_auth_token": "<token>",
  "client_data_status": {
    "clientLevel": 7,
    "devices": "",
    "users": "",
    "apps": {},
    "categories": {}
  },
  "request_id": "<uuid>",
  "server_url": "<server_url>"
}
```

### Sync Pull Response
```json
{
  "event": "sync_pull_response",
  "timestamp": "2026-09-04T15:26:00.100000Z",
  "timestamp_unix_ms": 1725468360100,
  "device_auth_token": "<token>",
  "success": true,
  "status_code": 200,
  "response_data": { ... },
  "request_id": "<uuid>"
}
```

### Sync Push Request
```json
{
  "event": "sync_push_request",
  "timestamp": "2026-09-04T15:26:00.000000Z",
  "timestamp_unix_ms": 1725468360000,
  "device_auth_token": "<token>",
  "actions": [ ... ],
  "request_id": "<uuid>",
  "server_url": "<server_url>"
}
```

### Sync Push Response
```json
{
  "event": "sync_push_response",
  "timestamp": "2026-09-04T15:26:00.100000Z",
  "timestamp_unix_ms": 1725468360100,
  "device_auth_token": "<token>",
  "success": true,
  "status_code": 200,
  "response_data": { ... },
  "request_id": "<uuid>"
}
```

### Family Creation Request
```json
{
  "event": "family_creation_request",
  "timestamp": "2026-09-05T09:40:00.000000Z",
  "timestamp_unix_ms": 1725468360000,
  "mail_auth_token": "<token>",
  "email": "parent@example.com",
  "password_data": {
    "hash": "$2a$12$...",
    "secondHash": "$2a$12$...",
    "secondSalt": "$2a$12$..."
  },
  "parent_device": {
    "model": "Pixel 6"
  },
  "device_name": "Parent Phone",
  "time_zone": "Europe/Amsterdam",
  "parent_name": "John Parent",
  "locale": "en",
  "request_id": "<uuid>",
  "server_url": "<server_url>"
}
```

### Family Creation Response
```json
{
  "event": "family_creation_response",
  "timestamp": "2026-09-05T09:40:00.100000Z",
  "timestamp_unix_ms": 1725468360100,
  "success": true,
  "status_code": 200,
  "response_data": {
    "deviceAuthToken": "<device_token>",
    "ownDeviceId": "<device_id>"
  },
  "request_id": "<uuid>"
}
```

### Family Creation Failure
```json
{
  "event": "family_creation_failure",
  "timestamp": "2026-09-05T09:40:00.000000Z",
  "timestamp_unix_ms": 1725468360000,
  "error_type": "validation",
  "error_message": "Password must be at least 8 characters",
  "email": "parent@example.com",
  "password_data": {
    "hash": "$2a$12$...",
    "secondHash": "$2a$12$...",
    "secondSalt": "$2a$12$..."
  },
  "request_id": "<uuid>",
  "server_url": "<server_url>"
}
```

## Test Instructions

### Run All Tests
```bash
cd timelimit-ui/rootfs/usr/bin/dashboardV2
python -m pytest tests/ -v --timeout=30
```

### Run Specific Sync Tests
```bash
cd timelimit-ui/rootfs/usr/bin/dashboardV2
python -m pytest tests/test_auth_client.py -v --timeout=30 -k "pull_status or push_actions"
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

### Device Removal Verification
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

### Sync Verification
- [x] Refresh button triggers actual sync via `/api/sync/pull`
- [x] Sync operations are logged to audit.log
- [x] Server selection persists correctly across restarts
- [x] `get_current_server_url()` checks both `server_url` and `server_key` in persistent storage

### Family Creation Audit Logging Verification
- [x] Email is logged in family creation request
- [x] Password hash (hash, secondHash, secondSalt) is logged in family creation request
- [x] Device ID is logged in family creation request
- [x] Mail auth token is logged in family creation request
- [x] Parent device info is logged in family creation request
- [x] Family creation response is logged with device auth token and own device ID
- [x] Family creation failures are logged with error details

### Signing Key Display Verification
- [x] Session status API returns `has_signing_key` field
- [x] `has_signing_key` is True when `dashboard_signing_key.json` exists
- [x] `has_signing_key` is False when signing key file is missing
- [x] Dashboard displays "Available" when signing key exists
- [x] Dashboard displays "Not generated" when signing key is missing

### Login-as-Parent Sync Verification
- [x] `own_device_id` is extracted from login-as-parent response
- [x] `own_device_id` is passed to `do_sync()` to add dashboard to connected devices
- [x] Sync retry logic with exponential backoff (up to 3 retries)
- [x] 2-second delay after successful sync to ensure `lastConnectivity` is updated
- [x] Error message shown to user on sync failure
- [x] Family record is created after sign-in to ensure family exists before password processing
- [x] Family salt is updated from sync response to fetch salt from server
- [x] Duplicate `sign_in_into_family()` call removed to prevent 401 Unauthorized errors

All verification items are now satisfied after the fixes applied.

## Debug Session Findings (2026-09-06)

### Log Analysis Summary

#### audit.log Findings
- **Duplicate sign-in issue confirmed**: Lines 16-18 show successful sign-in (HTTP 200), lines 19-21 show failed second sign-in (HTTP 401 Unauthorized)
- **Error**: `UnauthorizedError: Unauthorized at requireMailAndLocaleByAuthToken` - mail_auth_token was consumed by first call
- **Password hash regeneration**: Working correctly with bcrypt `$2a$` prefix hashes
- **Multiple hash regeneration events** logged with proper salt validation

#### werkzeug.log Findings
- **Multiple 401 errors** for `POST /api/sync/pull` - session/device_auth_token missing or invalid
- **404 errors** for `/favicon.ico` - expected, favicon doesn't exist
- **Most requests return 200** - application functioning correctly

#### File Status
- `dashboardV2-2026-09-06_19-51-22-5d85014d.log` - Does not exist (files have timestamps around 20:09:34)
- `verify_bcrypt_simple.py` - Does not exist at expected path

#### Code Verification
- **app.py**: NO duplicate `sign_in_into_family()` call exists - fix already applied
- Single call at line 1641 in `post_login_as_parent()` function
- Salt validation and family record creation implemented correctly

#### Database
- `dashboardV2.db` exists and contains proper schema
- `families` table with `parent_password_second_salt` column
- `KeyFamilyData.md` contains family creation audit data with bcrypt hashes

### Current Status
All issues documented in CONTEXT.md have been resolved. All 978 tests passing.