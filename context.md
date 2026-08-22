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

## Recent Changes

### Device Sync UNIQUE Constraint Fix (2026-08-22) ✅ COMPLETED
**Issue:** After successful login, the Users and Devices sections in the dashboard were empty. The sync was failing with `UNIQUE constraint failed: devices.id` error.

**Root Cause:** The `create_device()` function in `database.py` used a plain `INSERT INTO devices` statement, which fails when a device with the same ID already exists in the database. This happens during sync when devices are re-inserted from the server. Other save functions (`save_users`, `save_categories`, `save_sync_state`) correctly use `INSERT OR REPLACE INTO` to handle duplicates.

**Fix Applied:**
Changed `create_device()` in `database.py` (line 604-610) from:
```sql
INSERT INTO devices (...)
```
to:
```sql
INSERT OR REPLACE INTO devices (...)
```

This allows devices to be updated if they already exist, matching the behavior of other save functions.

**Files modified:**
1. `timelimit-ui/rootfs/usr/bin/dashboardV2/database.py` - Changed `INSERT INTO devices` to `INSERT OR REPLACE INTO devices`

**Test Results:**
- ✅ All 47 database tests pass
- ✅ All 17 sync_manager tests pass
- ✅ All 35 persistence tests pass
- ✅ All 11 startup tests pass

---

### Login Persistence (2026-08-22) ✅ COMPLETED
**Issue:** Flask sessions are ephemeral - stored in memory and lost when the application restarts. While `device_auth_token` is stored in the SQLite database, there's no mechanism to restore it to the session on application startup.

**Solution:** Implemented session persistence for authentication tokens by:
1. Adding database function to retrieve stored device_auth_tokens
2. Adding persistence layer for auth tokens (similar to server selection)
3. Restoring session on application startup via `before_request` handler

**Files modified:**
1. `timelimit-ui/rootfs/usr/bin/dashboardV2/database.py` - Added `get_device_auth_tokens()` function
2. `timelimit-ui/rootfs/usr/bin/dashboardV2/persistence.py` - Added auth token persistence functions:
   - `get_persisted_device_auth_token()` - retrieves device_auth_token from JSON file
   - `set_persisted_device_auth_token()` - saves device_auth_token to JSON file
   - `get_persisted_own_device_id()` - retrieves own_device_id from JSON file
   - `set_persisted_own_device_id()` - saves own_device_id to JSON file
   - `clear_persisted_auth_tokens()` - clears both tokens from JSON file
3. `timelimit-ui/rootfs/usr/bin/dashboardV2/app.py` - Added session restoration logic:
   - Added module-level `@app.before_request` handler `restore_session_from_persistence()`
   - Updated `api_create_family()` to persist tokens after successful family creation
   - Updated `api_create_family_rest()` to persist tokens after successful family creation
   - Updated `api_sign_in_into_family()` to persist tokens after successful sign-in
   - Updated `post_create_family()` to persist tokens after successful family creation
   - Updated `post_login_as_parent()` to persist tokens after successful login
   - Updated `clear_session()` to also clear persisted auth tokens
4. `timelimit-ui/rootfs/usr/bin/dashboardV2/tests/test_persistence.py` - Added `TestAuthTokenPersistence` class with 7 new tests

**Test Results:**
- ✅ All 93 persistence, database, and startup tests pass

---

### Auto-Sync After Authentication (2026-08-22) ✅ COMPLETED
**Issue:** The Users and Devices sections in the dashboard were empty after successful login. The server returned 0 users and 0 devices because no sync was performed to populate the local database.

**Root Cause:** The dashboard stored the `device_auth_token` in the session after authentication but did not trigger a sync to fetch the family data (users, devices, categories) from the server. The official Android app automatically calls `pullChanges` after create/sign-in operations to fetch this data.

**Fix Applied:**
1. Added sync call in `post_create_family()` after successful family creation (lines 1093-1103)
2. Added sync call in `post_login_as_parent()` after successful sign-in (lines 1325-1335)
3. Added sync trigger in `dashboard_v2()` when authenticated but has no local data (lines 253-291)
4. Both functions call `sync_manager.do_sync(device_auth_token, server_url)` to fetch family data
5. Sync results are logged appropriately (info on success, warning on failure)
6. Sync failures don't block the login flow - users still get redirected to dashboard

**Files modified:**
1. `timelimit-ui/rootfs/usr/bin/dashboardV2/app.py` - Added sync calls after authentication and on dashboard load

**Test Results:**
- ✅ All 713 tests pass

---

### device_auth_token as Primary Key (2026-08-21) ✅ COMPLETED
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

### ClientDataStatus Payload Format Fix (2026-08-20) ✅ COMPLETED
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

---

## Git Status (2026-08-22)

- **Local commits ahead of origin:** 17 commits
- **Working tree status:** Clean
- **Latest commit:** `6f9a7b2` - "Fix: Auto-sync after login to fetch users and devices"

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
