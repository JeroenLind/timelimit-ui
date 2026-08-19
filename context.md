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

## Recent Changes

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
1. Updated `/api/session/status` endpoint to include `family_id` and `own_device_id` in the response
2. Updated `dashboardV2.html` template with a detailed session information section showing:
   - Server URL with validation status
   - Device Auth Token with validation status
   - Own Device ID with validation status
   - Family ID with validation status
   - Mail Auth Token with validation status
3. Added `updateSessionOverview()` JavaScript function to update the display based on session status
4. Added visual indicators (green/yellow/red) for each field's status

**Files modified:**
1. `timelimit-ui/rootfs/usr/bin/dashboardV2/app.py` - Updated `session_status()` to include family_id and own_device_id
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

### Family ID Storage Fix (2026-08-19)
**Issue:** The dashboard was showing "Failed to load users" while being connected and authenticated. The root cause was that the `family_id` was not being extracted from server responses and stored in session/database.

**Root Cause:** When users create a family or sign in, the server returns `deviceAuthToken`, `ownDeviceId`, and `initialData` with `familyId`. The implementation only stored `device_auth_token` and `own_device_id` in the session. The dashboard API endpoints require `family_id` to retrieve users/devices/categories.

**Fix Applied:** Updated all authentication routes to extract `familyId` from `initialData` and store it in both session and database:

1. **`api_create_family` route** (lines 646-678) - Already had the fix
2. **`api_create_family_rest` route** (lines 766-798) - Already had the fix
3. **`api_sign_in_into_family` route** (lines 873-905) - Already had the fix
4. **`post_create_family` route** (lines 1165-1205) - Added family_id extraction and storage
5. **`post_login_as_parent` route** (lines 1404-1444) - Added family_id extraction and storage
6. **`cancel_create_family` route** (line 1230) - Added family_id cleanup
7. **`cancel_login_as_parent` route** (line 1469) - Added family_id cleanup

**Code Pattern Applied:**
```python
# Extract and store family_id from initialData if present
initial_data = response.data.get('initialData', {})
family_id = initial_data.get('familyId')
if family_id:
    session['family_id'] = family_id
    logger.info("Family ID extracted from initialData", family_id=family_id, request_id=request_id)

# Store auth token in database for later lookup
if family_id and device_auth_token:
    db = get_database()
    store_auth_token(
        db=db,
        token_type='device_auth_token',
        token_value=device_auth_token,
        device_id=response.data.get('ownDeviceId'),
        family_id=family_id,
        mail=response.data.get('mail')
    )
    logger.info("Auth token stored in database", family_id=family_id, request_id=request_id)
```

**Test Results:**
- ✅ All 21 dashboard API tests pass
- ✅ All 45 create family integration and login as parent tests pass
- ✅ All 57 auth client tests pass
- ✅ All 47 database tests pass
- ✅ All 17 sync manager tests pass
- **Total: 213 relevant tests pass**

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

#### API endpoint updates:
- Updated `/api/auth/sign-in-into-family` to accept optional `parentPasswordSecondHash`
- Added support for `deviceName`, `parentDevice.model`, and `clientLevel` parameters

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
   - Database functions: `get_users_by_family`, `get_devices_by_family`, `get_categories_by_family`, `get_connected_devices`
   - Sync manager: `SyncManager`, `create_sync_manager`, `get_event_queue`

2. Fixed duplicate `session_status()` function - removed duplicate definition and added `@app.route` decorator to the first definition

3. Implemented the following API routes:
   - `POST /api/sync/pull` - Trigger manual sync with TimeLimit server
   - `GET /api/dashboard/users` - Get cached users for current family
   - `GET /api/dashboard/devices` - Get cached devices for current family
   - `GET /api/dashboard/categories` - Get cached categories for current family
   - `GET /api/dashboard/connected-devices` - Get connected devices list
   - `GET /api/dashboard/stream` - SSE endpoint for real-time updates

4. Each route includes:
   - Authentication check (returns 401 if not authenticated)
   - Family ID check (returns 400 if no family selected)
   - Proper error handling with descriptive error messages
   - Structured logging for debugging

5. Updated test file `test_dashboard_api.py` to patch `app.create_sync_manager` instead of `app.SyncManager` for proper mocking

**Files modified:**
1. `timelimit-ui/rootfs/usr/bin/dashboardV2/app.py` - Added imports, fixed duplicate session_status, added 6 new API routes
2. `timelimit-ui/rootfs/usr/bin/dashboardV2/tests/test_dashboard_api.py` - Updated mock patch target for sync tests

**Expected Behavior:**
- All dashboard API endpoints return proper JSON responses
- Unauthenticated requests return 401 with "Not authenticated" error
- Requests without family selected return 400 with "No family selected" error
- Successful requests return 200 with data
- SSE endpoint streams events for real-time updates

**Test Results:**
- ✅ All 21 dashboard API tests pass
- Total: 234 relevant tests pass (213 + 21 new tests)

---

## Status

**Local Git Commit (2026-08-19):**
- Commit: `cb28213` - "fix: Display login_error when pull_status fails during family sign-in"
- 4 files changed, 57 insertions(+), 65 deletions(-)

**Create Family Flow:** ✅ Complete and verified

**Parent Login Flow:** ✅ Complete and implemented

**Users & Devices Dashboard:** ✅ Complete and implemented

**Dashboard Authentication Fix:** ✅ Complete and verified

**Connected Devices Data Source Fix:** ✅ Complete and verified

**Family ID Storage Fix:** ✅ Complete and verified

**Session Information Overview:** ✅ Complete and verified

**Dashboard API Routes:** ✅ Complete and verified

**Login Error Display Fix:** ✅ Complete and verified

**Family ID Fallback Fix (2026-08-19):**
**Issue:** After family creation, the `family_id` was `null` in the session because the create family API response doesn't include `initialData` with `familyId`.

**Root Cause:** The `post_create_family()` function only extracted `family_id` from `initialData` which doesn't exist in the response. It lacked the fallback logic that `post_login_as_parent()` already has.

**Fix Applied:** Added fallback logic to `post_create_family()` that calls `pull_status()` when `family_id` is not found in the response:
1. Check `initialData.familyId` first
2. Check `data.familyId` second
3. If still not found, call `pull_status()` to retrieve family information
4. Store error message in `session['login_error']` when `pull_status()` fails

**Files modified:**
1. `timelimit-ui/rootfs/usr/bin/dashboardV2/app.py` - Added fallback logic to `post_create_family()` function
2. `timelimit-ui/rootfs/usr/bin/dashboardV2/tests/test_create_family.py` - Added tests for fallback logic
3. `timelimit-ui/rootfs/usr/bin/dashboardV2/tests/test_create_family_integration.py` - Updated existing tests to mock `pull_status()`

**Test Results:**
- ✅ All 73 tests in create_family and login_as_parent tests pass
- ✅ New tests verify fallback logic works correctly
- ✅ Error messages are properly displayed when `pull_status()` fails

**Login Flow Verification (2026-08-18):**
- ✅ Step 1 (Email): Successfully sent mail login code to `test@pietje.nl`
- ✅ Step 2 (Verification): Successfully verified code and obtained mail auth token
- ✅ Step 3 (Device): Successfully signed in to family with device "Laptop" (Windows)
- ✅ Dashboard Access: User authenticated and dashboard rendered with `is_authenticated: true`

**Users & Devices Dashboard Verification:**
- ✅ `pull_status()` method added to AuthClient with gzip compression
- ✅ `push_actions()` method added to AuthClient with gzip compression
- ✅ Database tables created: users, sync_state, categories, connected_devices
- ✅ CRUD functions implemented for all new tables
- ✅ SyncManager class created with sync orchestration
- ✅ API routes added for sync and dashboard data
- ✅ SSE endpoint implemented for real-time updates
- ✅ Frontend HTML and JavaScript updated

**Test Results (2026-08-19):**
- ✅ All 30 login_as_parent tests pass
- ✅ All 43 create_family tests pass
- ✅ All 4 session management tests pass
- ✅ All 115 landing page tests pass (3 pre-existing failures in server selection tests unrelated to this fix)
- ✅ All 21 dashboard API tests pass

**Bug Fixes Applied:**
1. Fixed `test_app` fixture to delete existing database file before creating new one
2. Fixed `DATABASE_PATH` environment variable to use full absolute path instead of basename
3. Fixed mock patch target from `sync_manager.get_event_queue` to `app.get_event_queue`
4. Added `TEST_MAX_KEEPALIVES` environment variable support in `event_stream()` for testing
5. Fixed `store_auth_token` to use `INSERT OR REPLACE` instead of `INSERT` for UNIQUE constraint handling
6. **Fixed authentication check in dashboardV2.js** - Added authentication verification before loading dashboard data
7. **Fixed indentation in sync_manager.py** - Connected devices code block was not properly indented
8. **Fixed duplicate DOMContentLoaded handler** - Removed duplicate handler from HTML template
9. **Fixed test assertions** - Updated test to check device_id in dictionaries instead of strings
10. **Fixed family_id storage** - Added family_id extraction and storage in all authentication routes
11. **Added session information overview** - Added detailed session field status display on dashboard
12. **Fixed JavaScript error in updateSessionOverview()** - The function was trying to call `.substring()` on `undefined` when `data.device_auth_token` and `data.mail_auth_token` were not returned by the `/api/session/status` endpoint. Fixed to display '***' instead of trying to access non-existent token values.
13. **Added redirect message for already authenticated users** - When clicking "Login to Existing Family" or "Create New Family" while already authenticated, users now see a clear warning message "Already logged in - skipping login" instead of being silently redirected.
14. **Fixed cancel_create_family to clear family_id** - Added `session.pop('family_id', None)` to properly clean up session data when canceling create family flow
15. **Implemented missing dashboard API routes** - Added `/api/sync/pull`, `/api/dashboard/users`, `/api/dashboard/devices`, `/api/dashboard/categories`, `/api/dashboard/connected-devices`, `/api/dashboard/stream` routes with proper error handling
16. **Fixed test mock patch target** - Updated `test_dashboard_api.py` to patch `app.create_sync_manager` instead of `app.SyncManager`
17. **Fixed login_error display** - Fixed error handling in `post_login_as_parent()` to properly extract and store error message when `pull_status` fails, ensuring users see meaningful error messages in the session overview
18. **Fixed family_id fallback in post_create_family** - Added fallback logic to call `pull_status()` when `family_id` is not in the create family response, ensuring users always get a valid family_id after family creation
