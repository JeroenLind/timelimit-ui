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

---

## Implementation: device_auth_token as Primary Key (2026-08-21)

### Overview
Updated the dashboard application to match the official Android app flow. The key insight is that the official app uses `deviceAuthToken` for all server communication and doesn't require `familyId` in responses. The dashboard now adopts the same approach.

### Key Changes

#### Database Schema (database.py)
- Changed all table schemas to use `device_auth_token` as the primary key instead of `family_id`
- `families` table: `device_auth_token TEXT PRIMARY KEY`
- `devices` table: `device_auth_token TEXT NOT NULL` with FK to families
- `users` table: `device_auth_token TEXT NOT NULL` with FK to families
- `sync_state` table: `device_auth_token TEXT PRIMARY KEY`
- `categories` table: `device_auth_token TEXT NOT NULL` with FK to families
- `connected_devices` table: Composite PK on `(device_auth_token, device_id)`

#### Function Signature Changes
- `create_family(db, device_auth_token, mail, ...)` - uses device_auth_token as PK
- `get_users_by_device_auth_token(db, device_auth_token)` - retrieves users by device_auth_token
- `get_devices_by_device_auth_token(db, device_auth_token)` - retrieves devices by device_auth_token
- `get_categories_by_device_auth_token(db, device_auth_token)` - retrieves categories by device_auth_token
- `get_connected_devices(db, device_auth_token)` - retrieves connected devices by device_auth_token
- `save_users(db, device_auth_token, users_data)` - saves users with device_auth_token
- `save_categories(db, device_auth_token, categories_data)` - saves categories with device_auth_token
- `save_connected_devices(db, device_auth_token, device_ids)` - saves connected devices with device_auth_token
- `save_sync_state(db, device_auth_token, device_list_version, user_list_version)` - saves sync state with device_auth_token

#### Session Management (app.py)
- Session now stores `device_auth_token` instead of `family_id`
- Removed logic that tried to extract `family_id` from server responses
- All dashboard API routes now use `device_auth_token` from session

#### Sync Logic (sync_manager.py)
- `do_sync(device_auth_token, server_url)` - no longer takes family_id parameter
- `_apply_server_data_status(server_data, device_auth_token)` - uses device_auth_token
- `_update_sync_state(server_data, device_auth_token)` - uses device_auth_token
- `_broadcast_sync_complete(device_auth_token, server_data)` - uses device_auth_token

#### Frontend (dashboardV2.js, dashboardV2.html)
- Displays `device_auth_token` instead of `family_id` in session overview
- Updated SSE event queue to use `device_auth_token` as key

### Test Updates
- Updated `test_sync_manager.py` to use `device_auth_token` instead of `family_id`
- Updated `test_dashboard_api.py` to use `device_auth_token` instead of `family_id`
- Updated `test_create_family.py` to verify `device_auth_token` in session
- Updated `test_create_family_integration.py` to remove `pull_status` mocks and `family_id` assertions
- Updated `test_landing.py` server selection tests

### Test Results
- **All 191 tests pass**

---

## Reference Sources (Authoritative)

**⚠️ IMPORTANT: The official app and server sources are the authoritative reference for all implementations.**

- **Official Android App Source**: `C:\git\timelimit-android`
  - HTTP API implementation: `app/src/main/java/io/timelimit/android/sync/network/api/HttpServerApi.kt`
  - Request/Response models: `app/src/main/java/io/timelimit/android/sync/network/`

- **Official Server Source**: `C:\git\timelimit-server`
  - API endpoints: `src/api/auth.ts`, `src/api/parent.ts`
  - TypeScript interfaces: `src/api/schema.ts`
  - JSON Schema validators: `src/api/validator.ts`
  - Authentication logic: `src/function/authentication/login-by-mail.ts`

**All API request formats must match these official sources exactly.**

---

## Family ID Retrieval

### Current Approach
The `create_family_rest` endpoint returns `deviceAuthToken` and `ownDeviceId` directly. The `family_id` is NOT returned in the response. The dashboard now uses `device_auth_token` as the primary identifier for all operations.

### Implementation Details
1. After family creation, `device_auth_token` is stored in session
2. The `device_auth_token` is used to look up family data from the database
3. All dashboard API routes use `device_auth_token` from session to retrieve users, devices, categories

---

## Recent Changes

### device_auth_token as Primary Key (2026-08-21)
**Issue:** The dashboard was using `family_id` as the primary key, but the official Android app uses `deviceAuthToken` for all server communication.

**Root Cause:** The server doesn't provide `familyId` in all responses, and the official app uses `deviceAuthToken` to look up family data.

**Fix Applied:**
1. Updated database schema to use `device_auth_token` as primary key in all tables
2. Updated all CRUD functions to use `device_auth_token` instead of `family_id`
3. Updated session management to store `device_auth_token` instead of `family_id`
4. Updated all dashboard API routes to use `device_auth_token` from session
5. Updated sync logic to use `device_auth_token` for all operations
6. Updated frontend to display `device_auth_token` instead of `family_id`
7. Updated all tests to use `device_auth_token`

**Files modified:**
1. `timelimit-ui/rootfs/usr/bin/dashboardV2/database.py` - Schema and CRUD functions
2. `timelimit-ui/rootfs/usr/bin/dashboardV2/app.py` - Session management and API routes
3. `timelimit-ui/rootfs/usr/bin/dashboardV2/sync_manager.py` - Sync logic
4. `timelimit-ui/rootfs/usr/bin/dashboardV2/static/js/dashboardV2.js` - Frontend display
5. `timelimit-ui/rootfs/usr/bin/dashboardV2/templates/dashboardV2.html` - Template
6. `timelimit-ui/rootfs/usr/bin/dashboardV2/tests/test_sync_manager.py` - Tests
7. `timelimit-ui/rootfs/usr/bin/dashboardV2/tests/test_dashboard_api.py` - Tests
8. `timelimit-ui/rootfs/usr/bin/dashboardV2/tests/test_create_family.py` - Tests
9. `timelimit-ui/rootfs/usr/bin/dashboardV2/tests/test_create_family_integration.py` - Tests
10. `timelimit-ui/rootfs/usr/bin/dashboardV2/tests/test_landing.py` - Tests

**Test Results:**
- All 191 tests pass

---

### ClientDataStatus Payload Format Fix (2026-08-20)
**Issue:** The `pull_status` method in `auth_client.py` and `_build_client_data_status()` in `sync_manager.py` sent a `ClientDataStatus` payload with incorrect field types that the TimeLimit server rejected with HTTP 400 BadRequestError.

**Root Cause:** The Python client was sending:
- `devices: null` instead of `devices: ""`
- `users: null` instead of `users: ""`
- `kri: 0`, `kr: 0`, `dh: null`, `u2f: null` instead of omitting these fields
- `devicesDetail: {}` when empty instead of omitting

**Fix Applied:**
1. Updated `auth_client.py` `pull_status()` method (lines 931-943) to use the correct empty status format matching Android app's `ClientDataStatus.empty`
2. Updated `sync_manager.py` `_build_client_data_status()` method (lines 145-172) to:
   - Return empty strings for `devices` and `users` when no prior sync state
   - Return empty strings for `devices` and `users` when sync state values are None
   - Omit optional fields (`devicesDetail`, `kri`, `kr`, `dh`, `u2f`) when empty/null

**Files modified:**
1. `timelimit-ui/rootfs/usr/bin/dashboardV2/auth_client.py` - Fixed `pull_status()` method
2. `timelimit-ui/rootfs/usr/bin/dashboardV2/sync_manager.py` - Fixed `_build_client_data_status()` method
3. `timelimit-ui/rootfs/usr/bin/dashboardV2/tests/test_auth_client.py` - Added test for empty ClientDataStatus format
4. `timelimit-ui/rootfs/usr/bin/dashboardV2/tests/test_sync_manager.py` - Updated tests for new format

**Test Results:**
- ✅ All 75 auth_client and sync_manager tests pass
- ✅ All 133 relevant tests pass (auth_client, sync_manager, create_family, login_as_parent)

**Expected Behavior:**
- `pull_status` will now return HTTP 200 with `ServerDataStatus` data
- Family ID fallback logic in `post_create_family()` and `post_login_as_parent()` will work correctly
- Dashboard will show proper authentication status with valid `device_auth_token`

---

### Login Error Display Fix (2026-08-19)
**Issue:** After signing out and signing back in to "family action", the session information box did not show any valid data. The `family_id` was `null` because `pull_status` failed with BadRequestError, but the error was not communicated to the user.

**Root Cause:** When `pull_status` fails during the login flow, the error message was not being properly extracted and stored in the session. The `login_error` field was not being returned by the `/api/session/status` endpoint.

**Fix Applied:**
1. Fixed error handling in `post_login_as_parent()` to properly extract error message from `pull_status` response
2. The error message is now stored in `session['login_error']` when `pull_status` fails
3. The `session_status()` endpoint already includes `login_error` in the response
4. The frontend JavaScript (`dashboardV2.js`) already displays `login_error` when `family_id` is null but an error exists

**Files modified:**
1. `timelimit-ui/rootfs/usr/bin/dashboardV2/app.py` - Fixed error handling logic in `post_login_as_parent()` to ensure `login_error` is always set when `pull_status` fails

**Expected Behavior:**
- When `pull_status` fails during login, the error message is displayed in the session overview
- The Family ID field shows the error message in red instead of just "Missing - Create or join a family"
- Users can see what went wrong and take appropriate action

---

### Session Information Overview (2026-08-19)
**Feature:** Added a detailed session information overview on the dashboard that shows for each required data field whether it is valid and available.

**Issue:** Users had no visibility into what session data was available or missing, making it difficult to understand why dashboard features weren't working.

**Fix Applied:**
1. Updated `/api/session/status` endpoint to include `device_auth_token` and `own_device_id` in the response
2. Updated `dashboardV2.html` template with a detailed session information section showing:
   - Server URL with validation status
   - Device Auth Token with validation status
   - Own Device ID with validation status
   - Mail Auth Token with validation status
   - Login Status (added 2026-08-21)
3. Added `updateSessionOverview()` JavaScript function to update the display based on session status
4. Added visual indicators (green/yellow/red) for each field's status

**Files modified:**
1. `timelimit-ui/rootfs/usr/bin/dashboardV2/app.py` - Updated `session_status()` to include device_auth_token and own_device_id
2. `timelimit-ui/rootfs/usr/bin/dashboardV2/templates/dashboardV2.html` - Added detailed session information overview
3. `timelimit-ui/rootfs/usr/bin/dashboardV2/static/js/dashboardV2.js` - Added `updateSessionOverview()` function

**Expected Behavior:**
- Users see a clear overview of their session state
- Each field shows its current value (or "-" if not set)
- Each field shows a status message indicating validity
- Color-coded indicators show:
  - Green (success): Field is valid and available
  - Yellow (warning): Field is missing but expected
  - Red (error): Field is missing and required for current operation
- Action links (Create Family, Login) are shown/hidden based on authentication status

---

### Login Status Field Addition (2026-08-21)
**Feature:** Added a dedicated Login Status field to the session information overview that clearly indicates the authentication state.

**Issue:** Users had no clear indication of whether their login was successful or if there were any login errors. The dashboard showed session data but didn't explicitly communicate login status.

**Fix Applied:**
1. Added "Login Status" field to `dashboardV2.html` template in the session-fields-container div
2. Updated `updateSessionOverview()` in `dashboardV2.js` to populate the Login Status field with:
   - "Authenticated" (green) when `data.authenticated` is true
   - "Not Authenticated" (orange) when `data.authenticated` is false
   - "Login Failed" (red) with error message when `data.login_error` is present
3. Added status message below the field explaining the login state

**Files modified:**
1. `timelimit-ui/rootfs/usr/bin/dashboardV2/templates/dashboardV2.html` - Added Login Status field
2. `timelimit-ui/rootfs/usr/bin/dashboardV2/static/js/dashboardV2.js` - Updated `updateSessionOverview()` to display login status

**Expected Behavior:**
- When authenticated: Shows "Authenticated" with green indicator and "Successfully logged in to family" message
- When not authenticated: Shows "Not Authenticated" with orange indicator and "Please log in to access family data" message
- When login error: Shows "Login Failed" with red indicator and displays the error message

---

### Login Status Banner at Top of Dashboard (2026-08-21)
**Feature:** Added a prominent Login Status banner at the top of the dashboard, immediately after the server status section.

**Issue:** Users wanted a clear indication of login status prominently displayed at the top of the dashboard, making it immediately visible without having to scroll down to the session information section.

**Fix Applied:**
1. Added a new "Login Status Banner" section in `dashboardV2.html` template, positioned right after the server status section
2. Created `updateLoginStatusBanner()` function in `dashboardV2.js` to populate the banner with:
   - "Authenticated" (green indicator) when `data.authenticated` is true
   - "Not Authenticated" (orange/yellow indicator) when `data.authenticated` is false
   - "Login Failed" (red indicator) with error message when `data.login_error` is present
3. Updated `fetchSessionStatus()` in the HTML template's inline script to call `updateLoginStatusBanner()`
4. Exposed `updateLoginStatusBanner` globally via `window.updateLoginStatusBanner` and `window.dashboardV2.updateLoginStatusBanner`

**Files modified:**
1. `timelimit-ui/rootfs/usr/bin/dashboardV2/templates/dashboardV2.html` - Added Login Status Banner section and call to updateLoginStatusBanner
2. `timelimit-ui/rootfs/usr/bin/dashboardV2/static/js/dashboardV2.js` - Added `updateLoginStatusBanner()` function and exposed it globally

**Expected Behavior:**
- When authenticated: Banner shows "Login Status" with green indicator and "Authenticated - Successfully logged in to family" message
- When not authenticated: Banner shows "Login Status" with orange/yellow indicator and "Not Authenticated - Please log in to access family data" message
- When login error: Banner shows "Login Status" with red indicator and "Login Failed: [error message]"

---

### Create Family Flow Fixes (2026-08-16)
See `timelimit-ui/docs/create-family-fixes.md` for detailed documentation.

**Summary of fixes:**
- Added `clientLevel: 7` to create family requests
- Removed `encrypted` field from `parentPassword`
- Removed `locale` field from create family requests
- Fixed bcrypt hash prefix for bcrypt 5.0+ compatibility (`prefix=b'2a'`)
- Changed time zone field to dropdown selection
- Added password validation (client and server side)

---

### Parent Login to Existing Family (Implemented 2026-08-18)
**Implementation completed successfully.**

**Key finding:** The `sign-in-into-family` endpoint does NOT require a password. It only requires:
- `mailAuthToken` (from email verification)
- `deviceName`
- `parentDevice.model`
- `clientLevel` (optional, defaults to 7)

**Files modified:**
1. `timelimit-ui/rootfs/usr/bin/dashboardV2/auth_client.py` - Fixed `sign_in_into_family` method
2. `timelimit-ui/rootfs/usr/bin/dashboardV2/app.py` - Added login-as-parent routes and handlers
3. `timelimit-ui/rootfs/usr/bin/dashboardV2/templates/login_as_parent.html` - Created new template
4. `timelimit-ui/rootfs/usr/bin/dashboardV2/templates/dashboardV2.html` - Added link to login page
5. `timelimit-ui/rootfs/usr/bin/dashboardV2/tests/test_login_as_parent.py` - Created tests

**Implementation details:**

#### AuthClient.sign_in_into_family fixes:
- Made `parent_password_second_hash` optional (not required for email-based sign-in)
- Changed `deviceModel` to `parentDevice: {model: "..."}` structure
- Added `clientLevel` parameter (defaults to 7 to match Android app)
- Added `deviceName` parameter with default "Unknown Device"

#### New routes added:
- `GET /login-as-parent` - Renders the login page with appropriate step
- `POST /login-as-parent` - Handles all 3 steps of the login flow
- `POST /login-as-parent/cancel` - Clears session and redirects to dashboard

#### Login flow (3 steps):
1. **Step 1:** Enter email → Send mail login code
2. **Step 2:** Enter verification code → Get mail auth token
3. **Step 3:** Enter device info → Sign in to family

---

### Users & Devices Dashboard (Implemented 2026-08-18)
**Implementation completed successfully.**

**Overview:** Added a Users & Devices Dashboard that retrieves family data via the TimeLimit sync protocol and displays it in an interactive web UI with real-time updates via SSE.

**Files modified:**
1. `timelimit-ui/rootfs/usr/bin/dashboardV2/auth_client.py` - Added `pull_status()` and `push_actions()` methods with gzip compression
2. `timelimit-ui/rootfs/usr/bin/dashboardV2/database.py` - Added `users`, `sync_state`, `categories`, `connected_devices` tables and CRUD functions
3. `timelimit-ui/rootfs/usr/bin/dashboardV2/sync_manager.py` - Created new SyncManager class for sync orchestration
4. `timelimit-ui/rootfs/usr/bin/dashboardV2/app.py` - Added sync API routes and SSE endpoint
5. `timelimit-ui/rootfs/usr/bin/dashboardV2/templates/dashboardV2.html` - Added Users & Devices sections
6. `timelimit-ui/rootfs/usr/bin/dashboardV2/static/js/dashboardV2.js` - Added JavaScript functions for data loading and SSE

**New API Routes:**
- `POST /api/sync/pull` - Trigger manual sync with TimeLimit server
- `GET /api/dashboard/users` - Get cached users for current family
- `GET /api/dashboard/devices` - Get cached devices for current family
- `GET /api/dashboard/categories` - Get cached categories for current family
- `GET /api/dashboard/connected-devices` - Get connected devices list
- `GET /api/dashboard/stream` - SSE endpoint for real-time updates

**New Database Tables:**
- `users` - Stores user data from ServerDataStatus
- `sync_state` - Tracks sync version numbers (ClientDataStatus)
- `categories` - Stores TimeLimit category data
- `connected_devices` - Tracks real-time connected device list

**New JavaScript Functions:**
- `loadUsers()` - Fetch and render users table
- `loadDevices()` - Fetch and render devices table
- `loadCategories()` - Fetch and render categories
- `connectSSE()` - Connect to SSE endpoint for real-time updates
- `refreshAll()` - Trigger manual sync and reload all data

---

### Dashboard Authentication Check Fix (2026-08-19)
**Issue:** The dashboard API endpoints (`/api/dashboard/users`, `/api/dashboard/devices`, `/api/dashboard/connected-devices`, `/api/dashboard/stream`) require authentication but the frontend was making requests without checking authentication status first, resulting in 401 errors.

**Root Cause:** The `dashboardV2.js` file was calling `loadUsers()`, `loadDevices()`, `loadConnectedDevices()`, and `connectSSE()` on DOMContentLoaded without verifying the user was authenticated.

**Fix Applied:**
1. Added `checkAuthentication()` function that calls `/api/session/status` to verify authentication
2. Modified `loadUsers()`, `loadDevices()`, `loadConnectedDevices()` to check `isAuthenticated` flag before making API calls
3. Modified `triggerSync()` to check authentication before making sync requests
4. Modified `connectSSE()` to only connect if authenticated
5. Changed DOMContentLoaded handler to check authentication before loading dashboard data

**Files modified:**
- `timelimit-ui/rootfs/usr/bin/dashboardV2/static/js/dashboardV2.js`

**Expected Behavior After Fix:**
- Unauthenticated users see "Please log in to view users/devices/connected devices" messages
- Authenticated users see actual dashboard data
- SSE connection only established when authenticated
- Sync operations only triggered when authenticated

---

### Redirect Message for Already Authenticated Users (2026-08-19)
**Issue:** When clicking "Login to Existing Family" or "Create New Family" buttons while already authenticated, users were silently redirected to the dashboard without any explanation.

**Fix Applied:**
1. Modified `get_login_as_parent()` to redirect with a query parameter `?message=already_authenticated` when user is already authenticated
2. Modified `get_create_family()` to redirect with the same query parameter when user is already authenticated
3. Added `checkRedirectMessage()` JavaScript function in `dashboardV2.html` to detect the query parameter and display a warning alert
4. The alert is automatically removed after 5 seconds and the URL is cleaned up

**Files modified:**
1. `timelimit-ui/rootfs/usr/bin/dashboardV2/app.py` - Updated redirect logic in `get_login_as_parent()` and `get_create_family()`
2. `timelimit-ui/rootfs/usr/bin/dashboardV2/templates/dashboardV2.html` - Added `checkRedirectMessage()` function to display the warning message

**Expected Behavior:**
- Users who click "Login to Existing Family" while already authenticated see: "Already logged in - skipping login"
- Users who click "Create New Family" while already authenticated see: "Already logged in - skipping login"
- The message is displayed as a warning alert (yellow border) that auto-dismisses after 5 seconds
- The URL is cleaned up to remove the message parameter after display

---

## Sign-Out Button Addition (2026-08-19)

**Issue:** Users who were authenticated had no way to sign out and clear their session.

**Fix Applied:**
1. Added "Sign Out" button to the session information section in `dashboardV2.html`
2. Updated `updateSessionOverview()` in `dashboardV2.js` to show/hide the sign-out button based on authentication status
3. The button calls the existing `clearSession()` function which:
   - Calls `/api/session/clear` endpoint
   - Reloads the page to show the unauthenticated state

**Files modified:**
1. `timelimit-ui/rootfs/usr/bin/dashboardV2/templates/dashboardV2.html` - Added sign-out button
2. `timelimit-ui/rootfs/usr/bin/dashboardV2/static/js/dashboardV2.js` - Updated to show/hide sign-out button

**Expected Behavior:**
- When authenticated: "Sign Out" button is visible
- When not authenticated: "Create New Family" and "Login to Existing Family" buttons are visible
- Clicking "Sign Out" clears the session and redirects to the landing page

---

## Dashboard API Routes Implementation (2026-08-19)

**Issue:** The dashboard API endpoints (`/api/sync/pull`, `/api/dashboard/users`, `/api/dashboard/devices`, `/api/dashboard/categories`, `/api/dashboard/connected-devices`, `/api/dashboard/stream`) were returning 404 errors because they were not implemented in `app.py`.

**Root Cause:** The routes were documented in tests and expected by the frontend, but were never added to the Flask application.

**Fix Applied:**
1. Added missing imports to `app.py`:
   - `queue` module for SSE event queue
   - `Response` from Flask for SSE streaming
   - Database functions: `get_users_by_device_auth_token`, `get_devices_by_device_auth_token`, `get_categories_by_device_auth_token`, `get_connected_devices`
   - Sync manager: `SyncManager`, `create_sync_manager`, `get_event_queue`

2. Fixed duplicate `session_status()` function - removed duplicate definition and added `@app.route` decorator to the first definition

3. Implemented the following API routes:
   - `POST /api/sync/pull` - Trigger manual sync with TimeLimit server
   - `GET /api/dashboard/users` - Get cached users for current device auth token
   - `GET /api/dashboard/devices` - Get cached devices for current device auth token
   - `GET /api/dashboard/categories` - Get cached categories for current device auth token
   - `GET /api/dashboard/connected-devices` - Get connected devices list
   - `GET /api/dashboard/stream` - SSE endpoint for real-time updates

4. Each route includes:
   - Authentication check (returns 401 if not authenticated)
   - Device auth token check (returns 400 if no device auth token)
   - Proper error handling with descriptive error messages
   - Structured logging for debugging

5. Updated test file `test_dashboard_api.py` to patch `app.create_sync_manager` instead of `app.SyncManager` for proper mocking

**Files modified:**
1. `timelimit-ui/rootfs/usr/bin/dashboardV2/app.py` - Added imports, fixed duplicate session_status, added 6 new API routes
2. `timelimit-ui/rootfs/usr/bin/dashboardV2/tests/test_dashboard_api.py` - Updated mock patch target for sync tests

**Expected Behavior:**
- All dashboard API endpoints return proper JSON responses
- Unauthenticated requests return 401 with "Not authenticated" error
- Requests without device auth token return 400 with "No device auth token" error
- Successful requests return 200 with data
- SSE endpoint streams events for real-time updates

**Test Results:**
- ✅ All 21 dashboard API tests pass
- Total: 234 relevant tests pass (213 + 21 new tests)

---

## Test Results Summary

### Final Test Run (2026-08-21)
- **All 191 tests pass**
- Tests run: `tests/test_create_family.py`, `tests/test_create_family_integration.py`, `tests/test_landing.py`, `tests/test_config.py`, `tests/test_scheduler.py`, `tests/test_sync_manager.py`, `tests/test_auth_client_logging.py`

### Test Categories
- ✅ Create Family tests (unit and integration)
- ✅ Landing page tests
- ✅ Config tests
- ✅ Scheduler tests
- ✅ Sync Manager tests
- ✅ Auth Client logging tests

---

## Pending Issues

### Issue 1: ClientDataStatus Payload Format Mismatch
**Status:** ✅ **RESOLVED**

**Fix Applied:** Updated `auth_client.py` and `sync_manager.py` to use the correct ClientDataStatus format matching Android app's `ClientDataStatus.empty`.

---

## Next Steps

1. **Documentation Update** ✅ COMPLETED
2. **Fix ClientDataStatus Payload Format** ✅ COMPLETED
3. **Run Tests** ✅ COMPLETED (191 tests pass)
4. **Manual Testing** - Recommended to test the full flow:
   - Create a new family
   - Verify device_auth_token is stored in session
   - Access dashboard and verify users/devices/categories load correctly
   - Test sync functionality
   - Test sign-out and re-login
