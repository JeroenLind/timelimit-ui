# Device Removal Issue - Analysis

## Test Results and Logging

### Problem Summary
When trying to remove a device from the family, the dashboard returned a 401 Unauthorized error when calling the external server's `/parent/remove-device` endpoint.

### Exact Data Sent to Server (Failed Request)

#### Request Body
```json
{
  "deviceAuthToken": "5ry6B4bIKwk1gtjKcmhfPYTKlXfTsLdk",
  "parentUserId": "KSl70J",
  "parentPasswordSecondHash": "$2b$12$WFMR0fKceu.nn...",
  "deviceId": "0urTVM"
}
```

#### HTTP Request Details
- **Method**: POST
- **Endpoint**: `/parent/remove-device`
- **Server URL**: `http://192.168.68.30:8080`
- **Response**: 401 Unauthorized

### Server Error Response
```
UnauthorizedError: Unauthorized
    at assertAuthValidAndReturnDetails (/app/build/api/parent.js:213:23)
```

### Error Log Analysis

#### Server-side Error (from werkzeug.log)
```
Sat, 29 Aug 2026 17:29:45 GMT express:router dispatching POST /parent/remove-device
...
UnauthorizedError: Unauthorized
    at assertAuthValidAndReturnDetails (/app/build/api/parent.js:213:23)
    at async /app/build/api/parent.js:263:41
```

#### Dashboard-side Log (from dashboardV2-2026-08-31_19-33-34.log)
```
Line 390: {"device_id": "0urTVM", "parent_user_id": "KSl70J", "device_auth_token": "***REDACTED***", "server_url": "http://192.168.68.30:8080", "request_id": "1a4d59b7", "has_parent_password_second_hash": true, "parent_password_second_hash_preview": "$2b$12$WFMR0fKceu.nn...", "event": "Device removal requested", "level": "info", "timestamp": "2026-08-31T17:37:47.747516Z"}
Line 394: http://192.168.68.30:8080 "POST /parent/remove-device HTTP/1.1" 401 519
Line 395: {"request_id": "1a4d59b7", "method": "POST", "endpoint": "/parent/remove-device", "status_code": 401, "error_code": null, "error_message": null, "data": "b'<!DOCTYPE html>\\n<html lang=\"en\">\\n<head>\\n<meta charset=\"utf-8\">\\n<title>Error</title>\\n</head>\\n<body>\\n<pre>UnauthorizedError: Unauthorized<br> &nbsp; &nbsp;at assertAuthValidAndReturnDetails (/app/build/api/parent.js:213:23)...", "event": "API request failed", "level": "warning", "timestamp": "2026-08-31T17:37:47.891078Z"}
```

### Key Observations from Testing

#### 1. Request Data Was Correct
The request body contained all required fields:
- `deviceAuthToken`: Present (redacted in logs)
- `parentUserId`: "KSl70J"
- `parentPasswordSecondHash`: Present (bcrypt hash starting with `$2b$`)
- `deviceId`: "0urTVM"

#### 2. Authorization Header Was Being Sent (Initial Issue)
The `remove_device()` method in `auth_client.py` was passing `token=device_auth_token` to `_request_with_retry()`, which set the `Authorization: Bearer <token>` header.

#### 3. Server Rejected Request with 401 Unauthorized
The server's `assertAuthValidAndReturnDetails` function rejected the request because it received the token in BOTH places:
1. Request body: `deviceAuthToken`
2. Authorization header: `Bearer <token>`

The server expects the token ONLY in the request body, not in the Authorization header.

#### 4. Authorization Header Was Not Being Sent (After Fix)
The dashboard log shows:
```
"has_auth_header": false, "auth_header_present": false, "auth_header_value": null
```
This is correct after the fix - the Authorization header is no longer being sent.

#### 5. Server Still Returned 401 Unauthorized (Initial Issue)
Despite the fix, the server was still returning 401 Unauthorized. The error occurred at `assertAuthValidAndReturnDetails` in the server's `parent.js` file.

### Root Cause Analysis

#### Initial Root Cause (Fixed)
The server's `/parent/remove-device` endpoint expects the authentication token in the request body (`deviceAuthToken`) but does NOT accept it in the Authorization header.

When the dashboard was sending the token in BOTH places:
1. Request body: `deviceAuthToken: "T5NCtgR94egcLbZ7EHH4xYDKPopmLW2Y"`
2. Authorization header: `Bearer T5NCtgR94egcLbZ7EHH4xYDKPopmLW2Y`

The server rejected the request with 401 Unauthorized.

#### Secondary Root Cause (Fixed)
The `parent_user_id` was NOT being persisted in the database during family creation. It was only stored in the session. When the user restarted the app, the session was restored from persistence, but the `parent_user_id` was not restored because it was not stored in the database.

The `get_parent_user_id()` function was querying the `users` table, which is populated by the sync process. If sync hadn't run yet or the user data wasn't available, the `parent_user_id` wouldn't be restored.

---

## Actions Taken

### Fix 1: Remove Authorization Header
Removed the `token` parameter from the `_request_with_retry()` call in `auth_client.py:1095-1100`. The token is now only sent in the request body as `deviceAuthToken`, matching the server's expected format.

### Fix 2: Persist parent_user_id to Database
1. Added `parent_user_id` column to the `families` table schema
2. Added migration to add `parent_user_id` column to existing databases
3. Added `update_family_parent_user_id()` function to store `parent_user_id` in the `families` table
4. Updated `get_parent_user_id()` to first check the `families` table, then fall back to the `users` table
5. Updated family creation endpoints to persist `parent_user_id` to the database

### Session Persistence Analysis

#### Session Restoration Logic (`app.py` lines 101-159)
The `restore_session_from_persistence()` function:
1. Restores `device_auth_token` and `own_device_id` from persistent storage (JSON file)
2. Attempts to restore `parent_password_second_hash` from the local database
3. Attempts to restore `parent_user_id` from the local database

#### Password Hash Storage
The `parent_password_second_hash` is stored in the `families` table in the local SQLite database via `upsert_family_password_hash()`.

#### Family Creation Flow (`app.py` lines 1110-1299)
When a family is created via `post_create_family()`:
1. The password is hashed using `generate_family_hashes()` (bcrypt with `$2a$` prefix)
2. The server is called to create the family
3. The `deviceAuthToken` and `ownDeviceId` are stored in the session
4. The `parent_user_id` is extracted from the server response and stored in the session
5. The `parent_password_second_hash` is stored in the session
6. The `parent_password_second_hash` is persisted to the local database

#### Set Parent Password Flow (`app.py` lines 2931-2994)
When the user sets the parent password via `/set-parent-password`:
1. The password is hashed with bcrypt (rounds=12, `$2a$` prefix)
2. The hash is stored in the local database via `upsert_family_password_hash()`
3. The hash is stored in the session

---

## Next Steps

### Immediate Verification Steps

1. **Verify device_auth_token validity**: The token may be expired or invalid on the server. Try creating a new token.

2. **Check server-side family data**: The server maintains its own family records. The local database hash may not match the server's expected hash.

3. **Test with fresh family creation**: Create a new family with a different password to ensure the hash is properly synced with the server.

### Testing Instructions

#### Step 1: Run the Unit Tests
Execute the following command to run all device removal tests:

```bash
cd timelimit-ui/rootfs/usr/bin/dashboardV2
python -m pytest tests/test_dashboard_api.py::TestApiDashboardDevicesRemove -v --timeout=30
```

Expected result: All 7 tests should pass.

#### Step 2: Run All Dashboard Tests
To ensure no regressions, run all dashboard API tests:

```bash
cd timelimit-ui/rootfs/usr/bin/dashboardV2
python -m pytest tests/test_dashboard_api.py -v --timeout=30
```

#### Step 3: Check the Latest Log Files
After running tests or reproducing the issue, check the latest log files:

```bash
# Check the most recent dashboard log
ls -la logs/ | sort -k6,7 | tail -5

# View the latest log entries
type logs/dashboardV2.log | Select-String -Pattern "remove_device|device_removal|parent_password" -Context 2,2
```

### Log Analysis Checklist

When analyzing logs for device removal issues, follow this checklist:

- [ ] Check `restore_session_from_persistence()` logs for session restoration
- [ ] Check `api_create_family()` or `api_create_family_rest()` logs for family creation
- [ ] Check `upsert_family_password_hash()` logs for hash storage
- [ ] Check `api_dashboard_devices_remove()` logs for device removal request
- [ ] Check `remove_device()` in auth_client.py logs for the actual API call
- [ ] Verify `parent_password_second_hash` is present in session before device removal
- [ ] Verify `parent_user_id` is correctly extracted from server response
- [ ] Check server response for 401 error details

### Key Log Fields to Look For

1. `device_auth_token_preview` - Should be a valid token (starts with a letter, ~32 chars)
2. `parent_password_second_hash_preview` - Should be a bcrypt hash (starts with `$2a$`)
3. `parent_user_id` - Should be a valid user ID
4. `device_id` - Should be the ID of the device to remove
5. `success` - Should be `true` for successful removal
6. `error_code` - Should be `null` for success, or the error code for failure
7. `error_message` - Should describe the error if failed

### Common Issues to Check

1. **Missing parent_password_second_hash**: If the hash is not in the session, device removal will fail with 400 error
2. **Invalid device_auth_token**: If the token is expired or invalid, server returns 401
3. **Wrong parent_user_id**: If the user ID doesn't match, server returns 401
4. **Self-removal attempt**: If trying to remove own device, returns 400 with "Cannot remove the current device"

---

## Data Required for Device Removal

To successfully remove a device from a family, the following data must be available:

| Data Item | Description | Required For |
|-----------|-------------|--------------|
| `device_auth_token` | Authentication token for the family | Server authentication |
| `parent_user_id` | ID of the parent user | Server authorization |
| `parent_password_second_hash` | Bcrypt hash of parent's second password | Server authorization |
| `device_id` | ID of the device to remove | Device identification |
| `own_device_id` | ID of the current device | Prevent self-removal |

---

## Complete Data Flow

### Phase 1: Family Creation

#### Step 1.1: Send Mail Login Code
**Data Available:**
- `mail` (user's email)

**Data Generated:**
- `mail_login_token` (temporary token for verification)

**Persistence:**
- Stored in session: `session['mail_login_token']`

#### Step 1.2: Sign In by Mail Code
**Data Available:**
- `mail_login_token` (from session)
- `received_code` (3-word passphrase from email)

**Data Generated:**
- `mail_auth_token` (authentication token for family operations)

**Persistence:**
- Stored in session: `session['mail_auth_token']`

#### Step 1.3: Create Family
**Data Available:**
- `mail_auth_token` (from session)
- `password` (user's password)
- `parent_name`, `device_name`, `time_zone`, `device_model`

**Data Generated:**
- `password_data` = `{hash, secondHash, secondSalt}` (from `generate_family_hashes()`)
- `device_auth_token` (family authentication token)
- `own_device_id` (current device ID)
- `parent_user_id` (extracted from server response)

**Persistence:**
- Session: `session['device_auth_token']`
- Session: `session['own_device_id']`
- Session: `session['parent_user_id']`
- Session: `session['parent_password_second_hash']` (from `password_data.secondHash`)
- Database: `upsert_family_password_hash(db, device_auth_token, secondHash)`
- Database: `update_family_parent_user_id(db, device_auth_token, parent_user_id)`
- File: `set_persisted_device_auth_token(device_auth_token)`
- File: `set_persisted_own_device_id(own_device_id)`

### Phase 2: Sign In to Family (Alternative Flow)

#### Step 2.1: Sign In Into Family
**Data Available:**
- `mail_auth_token` (from session)
- `parent_password_second_hash` (optional, for device removal)

**Data Generated:**
- `device_auth_token` (family authentication token)
- `own_device_id` (current device ID)
- `parent_user_id` (extracted from server response)

**Persistence:**
- Session: `session['device_auth_token']`
- Session: `session['own_device_id']`
- Session: `session['parent_user_id']`
- Session: `session['parent_password_second_hash']` (if provided)
- Database: `store_auth_token(db, 'device_auth_token', device_auth_token, own_device_id)`
- Database: `upsert_family_password_hash(db, device_auth_token, parent_password_second_hash)` (if provided)
- Database: `update_family_parent_user_id(db, device_auth_token, parent_user_id)` (if provided)
- File: `set_persisted_device_auth_token(device_auth_token)`
- File: `set_persisted_own_device_id(own_device_id)`

### Phase 3: Session Restoration (On App Restart)

**Data Restored from:**
- File: `get_persisted_device_auth_token()` → `session['device_auth_token']`
- File: `get_persisted_own_device_id()` → `session['own_device_id']`
- Database: `get_parent_password_hash(db, device_auth_token)` → `session['parent_password_second_hash']`
- Database: `get_parent_user_id(db, device_auth_token)` → `session['parent_user_id']`

### Phase 4: Set Parent Password (Optional Step)

#### Step 4.1: Set Parent Password
**Data Available:**
- `password` (user's password)
- `device_auth_token` (from session)

**Data Generated:**
- `parent_password_second_hash` (bcrypt hash with rounds=12)

**Persistence:**
- Session: `session['parent_password_second_hash']`
- Database: `upsert_family_password_hash(db, device_auth_token, parent_password_second_hash)`

### Phase 5: Sync Data with Server

**Data Required:**
- `device_auth_token` (from session)
- `own_device_id` (from session)
- `server_url` (from config/persistence)

**Data Generated:**
- `sync_state` (sequence numbers, timestamps)
- `users`, `devices`, `categories`, `connected_devices` (from server)

**Persistence:**
- Database: `save_users()`, `save_categories()`, `save_connected_devices()`, `save_sync_state()`
- Database: `increment_sequence_number()`

### Phase 6: Device Removal

#### Step 6.1: Remove Device
**Data Required:**
- `device_auth_token` (from session or database)
- `parent_user_id` (from session or database)
- `parent_password_second_hash` (from session or database)
- `device_id` (from request body)
- `own_device_id` (from session - to prevent self-removal)

**Data Sent to Server:**
```json
{
  "deviceAuthToken": "<device_auth_token>",
  "parentUserId": "<parent_user_id>",
  "parentPasswordSecondHash": "<parent_password_second_hash>",
  "deviceId": "<device_id>"
}
```

**Note:** The `device_auth_token` is sent in the request body, NOT in the Authorization header.

---

## Data Persistence Summary

### Session Storage (Flask Session)
| Data Item | When Set | When Cleared |
|-----------|----------|--------------|
| `device_auth_token` | Family creation, sign-in | Session clear, logout |
| `own_device_id` | Family creation, sign-in | Session clear, logout |
| `parent_user_id` | Family creation, sign-in | Session clear, logout |
| `parent_password_second_hash` | Family creation, set-parent-password | Session clear, logout |
| `mail_auth_token` | Sign-in by mail code | After family creation/sign-in |
| `mail_login_token` | Send mail login code | After sign-in by mail code |

### Database Storage (SQLite)
| Table | Data Item | When Set | When Cleared |
|-------|-----------|----------|--------------|
| `families` | `parent_password_second_hash` | Family creation, set-parent-password | Family deletion |
| `families` | `parent_user_id` | Family creation, sign-in | Family deletion |
| `devices` | `device_id`, `device_auth_token` | Device creation | Device removal |
| `auth_tokens` | `token_value`, `device_id` | Sign-in | Token expiration |
| `users` | `id`, `type` | Sync | N/A |
| `categories` | category data | Sync | N/A |
| `connected_devices` | device data | Sync | N/A |
| `sync_state` | sequence numbers | Sync | N/A |

### File Storage (JSON)
| File | Data Item | When Set | When Cleared |
|------|-----------|----------|--------------|
| `server_selection.json` | `server_url`, `server_key` | Server selection | N/A |
| `timelimit_ui_storage.json` | `device_auth_token`, `own_device_id` | Family creation, sign-in | Clear all |

---

## Critical Data Flow Points

### 1. Password Hash Generation
```
password → generate_family_hashes() → {hash, secondHash, secondSalt}
                                                       |
                                                       v
                                              Used for:
                                              - Server family creation (hash)
                                              - Device removal (secondHash)
                                              - Sync integrity (secondHash)
```

### 2. Device Auth Token Flow
```
Server response → session['device_auth_token'] → Database → File persistence
                                                                     |
                                                                     v
                                                    Used for:
                                                    - Server authentication
                                                    - Database lookups
                                                    - Session restoration
```

### 3. Parent User ID Flow
```
Server response (users.data[0].id) → session['parent_user_id'] → Database
                                                                     |
                                                                     v
                                                    Used for:
                                                    - Device removal authorization
                                                    - Database lookups
```

### 4. Parent Password Second Hash Flow
```
password_data.secondHash → session['parent_password_second_hash'] → Database
                                                                     |
                                                                     v
                                                    Used for:
                                                    - Device removal authorization
                                                    - Session restoration
                                                    - Sync integrity
```

---

## Key Code Locations

| Function | File | Lines | Purpose |
|----------|------|-------|---------|
| `generate_family_hashes()` | `crypto_utils.py` | 8-30 | Generate bcrypt hashes |
| `create_family()` | `auth_client.py` | 554-623 | Create family via API |
| `create_family_rest()` | `auth_client.py` | 625-692 | Create family via REST |
| `sign_in_into_family()` | `auth_client.py` | 694-760 | Sign in to existing family |
| `remove_device()` | `auth_client.py` | 1064-1125 | Remove device via API |
| `api_create_family()` | `app.py` | 713-842 | Handle family creation |
| `api_create_family_rest()` | `app.py` | 845-977 | Handle family creation (REST) |
| `api_sign_in_into_family()` | `app.py` | 980-1093 | Handle sign in |
| `api_dashboard_devices_remove()` | `app.py` | 2878-3038 | Handle device removal |
| `post_set_parent_password()` | `app.py` | 3067-3149 | Set parent password |
| `post_create_family()` | `app.py` | 1144-1419 | Handle family creation (form) |
| `post_login_as_parent()` | `app.py` | 1496-1720 | Handle login as parent |
| `restore_session_from_persistence()` | `app.py` | 101-180 | Restore session on restart |
| `upsert_family_password_hash()` | `database.py` | 1179-1239 | Store password hash |
| `get_parent_password_hash()` | `database.py` | 1123-1149 | Retrieve password hash |
| `get_parent_user_id()` | `database.py` | 1063-1078 | Retrieve parent user ID |
| `update_family_parent_user_id()` | `database.py` | 1208-1232 | Store parent user ID |

---

## Verification Checklist

Before attempting device removal, verify:

- [ ] `device_auth_token` is in session
- [ ] `parent_user_id` is in session
- [ ] `parent_password_second_hash` is in session
- [ ] `own_device_id` is in session (to prevent self-removal)
- [ ] `parent_password_second_hash` is in database for `device_auth_token`
- [ ] `parent_user_id` is in database for `device_auth_token`
- [ ] `device_auth_token` is persisted to file

---

## Audit Log Format for Device Removal Operations

### Overview

The device removal feature includes comprehensive audit logging that preserves complete request details with exact fidelity to the transmitted message. This enables security analysis, compliance audits, and forensic investigations.

### Log Location

Audit logs are written to: `logs/audit.log`

The log file uses rotation with:
- Maximum size: 10MB per file
- Backup count: 10 files
- Format: JSON (one entry per line)

### Log Functions

Three audit logging functions are used for device removal operations:

#### 1. `log_device_removal_request()`

Logs the complete request details before sending to the server.

**Called from:**
- `app.py:api_dashboard_devices_remove()` (lines 3075-3085)
- `auth_client.py:remove_device()` (lines 1100-1109)

**Log Entry Structure:**
```json
{
  "timestamp": "2026-08-31T17:37:47.747516Z",
  "timestamp_unix_ms": 1761932267747,
  "event": "device_removal_request",
  "device_id": "0urTVM",
  "parent_user_id": "KSl70J",
  "device_auth_token": "5ry6B4bIKwk1gtjKcmhfPYTKlXfTsLdk",
  "parent_password_second_hash": "$2b$12$WFMR0fKceu.nn...",
  "request_payload": {
    "deviceAuthToken": "5ry6B4bIKwk1gtjKcmhfPYTKlXfTsLdk",
    "parentUserId": "KSl70J",
    "parentPasswordSecondHash": "$2b$12$WFMR0fKceu.nn...",
    "deviceId": "0urTVM"
  },
  "request_headers": {
    "Content-Type": "application/json",
    "User-Agent": "dashboardV2/1.0",
    "Authorization": "Bearer 5ry6B4bIKwk1gtjKcmhfPYTKlXfTsLdk",
    ...
  },
  "client_ip": "192.168.1.100",
  "request_id": "1a4d59b7",
  "server_url": "http://192.168.68.30:8080"
}
```

#### 2. `log_device_removal_response()`

Logs the server response after the API call completes.

**Called from:**
- `app.py:api_dashboard_devices_remove()` (lines 3108-3117)
- `auth_client.py:remove_device()` (lines 1130-1139)

**Log Entry Structure (Success):**
```json
{
  "timestamp": "2026-08-31T17:37:47.891078Z",
  "timestamp_unix_ms": 1761932267891,
  "event": "device_removal_response",
  "device_id": "0urTVM",
  "parent_user_id": "KSl70J",
  "success": true,
  "status_code": 200,
  "response_data": {
    "ok": true
  },
  "request_id": "1a4d59b7",
  "error_code": null,
  "error_message": null
}
```

**Log Entry Structure (Failure):**
```json
{
  "timestamp": "2026-08-31T17:37:47.891078Z",
  "timestamp_unix_ms": 1761932267891,
  "event": "device_removal_response",
  "device_id": "0urTVM",
  "parent_user_id": "KSl70J",
  "success": false,
  "status_code": 401,
  "response_data": {
    "error": "Unauthorized"
  },
  "request_id": "1a4d59b7",
  "error_code": "UnauthorizedError",
  "error_message": "Unauthorized"
}
```

#### 3. `log_device_removal_failure()`

Logs failures in the device removal process (validation errors, authentication failures, etc.).

**Called from:**
- `auth_client.py:remove_device()` (when exceptions occur)

**Log Entry Structure:**
```json
{
  "timestamp": "2026-08-31T17:37:47.891078Z",
  "timestamp_unix_ms": 1761932267891,
  "event": "device_removal_failure",
  "device_id": "0urTVM",
  "parent_user_id": "KSl70J",
  "error_type": "validation",
  "error_message": "Missing deviceId in request",
  "request_payload": {
    "deviceAuthToken": "5ry6B4bIKwk1gtjKcmhfPYTKlXfTsLdk",
    "parentUserId": "KSl70J",
    "parentPasswordSecondHash": "$2b$12$WFMR0fKceu.nn...",
    "deviceId": null
  },
  "request_headers": {
    "Content-Type": "application/json",
    ...
  },
  "request_id": "1a4d59b7"
}
```

### Log Field Reference

| Field | Type | Description |
|-------|------|-------------|
| `timestamp` | string | ISO 8601 timestamp with microsecond precision (UTC) |
| `timestamp_unix_ms` | integer | Unix timestamp in milliseconds |
| `event` | string | Event type: `device_removal_request`, `device_removal_response`, or `device_removal_failure` |
| `device_id` | string | ID of the device being removed |
| `parent_user_id` | string | ID of the parent user making the request |
| `device_auth_token` | string | Device auth token (logged in full for audit purposes) |
| `parent_password_second_hash` | string | Parent's second password hash (bcrypt format) |
| `request_payload` | object | Complete request payload as sent to server |
| `request_headers` | object | Complete HTTP headers as sent |
| `client_ip` | string | Client IP address (from Flask request.remote_addr) |
| `request_id` | string | Unique request identifier for correlation |
| `server_url` | string | Target server URL |
| `success` | boolean | Whether the operation succeeded |
| `status_code` | integer | HTTP status code of the response |
| `response_data` | object | Complete response data from server |
| `error_code` | string | Error code if failed |
| `error_message` | string | Error message if failed |
| `error_type` | string | Type of error: `validation`, `authentication`, `server`, etc. |

### Log Analysis Commands

```powershell
# View all device removal audit logs
Get-Content logs/audit.log | Select-String "device_removal"

# View only successful device removals
Get-Content logs/audit.log | Select-String '"success": true' | Select-String "device_removal"

# View only failed device removals
Get-Content logs/audit.log | Select-String '"success": false' | Select-String "device_removal"

# Find logs for a specific device
Get-Content logs/audit.log | Select-String "0urTVM"

# Find logs for a specific request ID
Get-Content logs/audit.log | Select-String "1a4d59b7"

# Parse logs as JSON for analysis
Get-Content logs/audit.log | ForEach-Object { $_ | ConvertFrom-Json } | Where-Object { $_.event -like "*device_removal*" }
```

### Key Code Locations

| Function | File | Lines | Purpose |
|----------|------|-------|---------|
| `log_device_removal_request()` | `utils/audit_log.py` | 123-175 | Log request with exact fidelity |
| `log_device_removal_response()` | `utils/audit_log.py` | 178-238 | Log response with exact fidelity |
| `log_device_removal_failure()` | `utils/audit_log.py` | 241-283 | Log failures with exact fidelity |
| `api_dashboard_devices_remove()` | `app.py` | 2958-3157 | Device removal endpoint |
| `remove_device()` | `auth_client.py` | 1068-1158 | Auth client device removal |

---

## Expected Request Data and Format

This section documents the expected data structure, validation rules, and format for the `/parent/remove-device` API endpoint. This information is derived from cross-referencing the ServerAPI.md documentation with the actual implementation in `auth_client.py` and verified against the server's expected behavior.

### Endpoint Overview

| Property | Value |
|----------|-------|
| **HTTP Method** | POST |
| **Endpoint Path** | `/parent/remove-device` |
| **Full URL** | `{server_url}/parent/remove-device` |
| **Content-Type** | `application/json` |
| **Authentication** | Token in request body only (NOT in Authorization header) |

### Required Request Fields

| Field Name | Type | Required | Description | Validation Rules |
|------------|------|----------|-------------|------------------|
| `deviceAuthToken` | string | Yes | Family authentication token | - Must be a valid, non-expired token<br>- ~32 alphanumeric characters<br>- Starts with a letter<br>- Must match server's stored token |
| `parentUserId` | string | Yes | ID of the parent user making the request | - Must be a valid user ID<br>- Must belong to the family<br>- Must match the device's parent on the server |
| `parentPasswordSecondHash` | string | Yes | Bcrypt hash of parent's second password | - Must be a valid bcrypt hash<br>- Format: `$2a$` or `$2b$` prefix followed by 2 rounds, cost factor, and 53 character hash<br>- Must match server's stored hash for the family |
| `deviceId` | string | Yes | ID of the device to remove | - Must be a valid device ID in the family<br>- Cannot be the same as `own_device_id` (self-removal prevention) |

### Request Payload Format

#### Successful Request Payload

```json
{
  "deviceAuthToken": "5ry6B4bIKwk1gtjKcmhfPYTKlXfTsLdk",
  "parentUserId": "KSl70J",
  "parentPasswordSecondHash": "$2b$12$WFMR0fKceu.nn...",
  "deviceId": "0urTVM"
}
```

#### Minimal Valid Request Payload

```json
{
  "deviceAuthToken": "device_token_abc123",
  "parentUserId": "user_123",
  "parentPasswordSecondHash": "$2a$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/X4.qO.1BoWBPfGKWe",
  "deviceId": "device_xyz789"
}
```

### Authorization Header Behavior

**IMPORTANT**: The server's `/parent/remove-device` endpoint expects the authentication token ONLY in the request body (`deviceAuthToken` field). The token should NOT be sent in the `Authorization` header.

**Incorrect (causes 401 Unauthorized):**
```http
POST /parent/remove-device HTTP/1.1
Content-Type: application/json
Authorization: Bearer 5ry6B4bIKwk1gtjKcmhfPYTKlXfTsLdk

{
  "deviceAuthToken": "5ry6B4bIKwk1gtjKcmhfPYTKlXfTsLdk",
  "parentUserId": "KSl70J",
  "parentPasswordSecondHash": "$2b$12$...",
  "deviceId": "0urTVM"
}
```

**Correct:**
```http
POST /parent/remove-device HTTP/1.1
Content-Type: application/json

{
  "deviceAuthToken": "5ry6B4bIKwk1gtjKcmhfPYTKlXfTsLdk",
  "parentUserId": "KSl70J",
  "parentPasswordSecondHash": "$2b$12$...",
  "deviceId": "0urTVM"
}
```

### Successful Response Format

```json
{
  "ok": true
}
```

### Error Response Formats

#### 401 Unauthorized - Invalid Token

```json
{
  "ok": false,
  "error": "Unauthorized"
}
```

**Causes:**
- Invalid or expired `deviceAuthToken`
- Token sent in both body and Authorization header
- `parentPasswordSecondHash` doesn't match server's stored hash
- `parentUserId` doesn't match the device's parent

#### 400 Bad Request - Missing Parent Password Hash

```json
{
  "status": "error",
  "error": "Parent password hash not set. Please enter it in the session settings."
}
```

**Cause:** The `parent_password_second_hash` is not set in the session. This must be set via `/set-parent-password` endpoint before device removal can be performed.

#### 400 Bad Request - Missing Device ID

```json
{
  "status": "error",
  "error": "Missing deviceId"
}
```

**Cause:** The `deviceId` field is missing from the request body.

#### 400 Bad Request - Self-Removal Attempt

```json
{
  "status": "error",
  "error": "Cannot remove the current device"
}
```

**Cause:** The `deviceId` matches the `own_device_id` in the session (prevents a device from removing itself).

### Password Hash Format Details

The `parentPasswordSecondHash` must be a bcrypt hash with the following characteristics:

| Property | Value |
|----------|-------|
| **Prefix** | `$2a$` or `$2b$` |
| **Cost Factor** | 12 (recommended) |
| **Hash Length** | 60 characters total |
| **Format** | `$2a$12$[22 character salt][31 character hash]` |

**Example valid hashes:**
```
$2a$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/X4.qO.1BoWBPfGKWe
$2b$12$WFMR0fKceu.nn...
```

### Hash Prefix Mismatch Issue

**Problem:** The `post_set_parent_password()` function was using `bcrypt.gensalt()` directly, which produces `$2b$` prefix hashes. However, the server expects `$2a$` prefix hashes (as used during family creation via `generate_family_hashes()`).

**Server Validation Regex:** `/^($2a$[123][0-9]$[./A-Za-z0-9]{53})?$/`

**Root Cause:**
- Family creation uses `generate_family_hashes()` which explicitly sets `prefix=b'2a'` in `bcrypt.gensalt(rounds=12, prefix=b'2a')`
- Set parent password was using `bcrypt.gensalt(rounds=12)` which defaults to `$2b$` prefix
- The server's `assertAuthValidAndReturnDetails` function validates the hash against the regex, which only matches `$2a$` prefix

**Evidence from audit.log:**
```
"parent_password_second_hash": "$2b$12$WFMR0fKceu.nnRsUzFhSkOOlshv5yX7/VsCTssPvuqTY14WGdTKC."
```
The hash in the audit log shows `$2b$` prefix, which would fail server validation.

**Fix Applied:**
Changed `post_set_parent_password()` in `app.py` to use `generate_family_hashes(password)['secondHash']` instead of `bcrypt.gensalt()` directly. This ensures the hash uses `$2a$` prefix to match server expectations.

**Code Change:**
```python
# Before (incorrect - produces $2b$ prefix):
salt = bcrypt.gensalt(rounds=12)
parent_password_second_hash = bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')

# After (correct - produces $2a$ prefix):
password_data = generate_family_hashes(password)
parent_password_second_hash = password_data['secondHash']
```

**Verification:**
Run `test_hash_mismatch.py` to verify the hash generation:
```bash
python test_hash_mismatch.py
```

Expected output:
```
Family hash prefix: $2a$
Set password hash prefix: $2a$
Server regex matches family hash: True
Server regex matches set password hash: True
Hashes are equal: True
```

### Cross-Reference with ServerAPI.md

Per `timelimit-ui/docs/ServerAPI.md` (lines 517-543):

> **POST /api/v1/parent/remove-device**
>
> Remove a device from the family.
>
> **Request:**
> ```json
> {
>   "deviceAuthToken": "device_token_abc123",
>   "parentUserId": "user_123",
>   "parentPasswordSecondHash": "$2a$12$...",
>   "deviceId": "device_id_to_remove"
> }
> ```
>
> **Response:**
> ```json
> {
>   "ok": true
> }
> ```
>
> **Note:** Device removal uses the REST API endpoint directly, NOT the sync protocol. The `REMOVE_DEVICE` action type is not a valid AppLogicAction type in the server's schema.

### Implementation Reference

| Component | File | Lines | Purpose |
|-----------|------|-------|---------|
| `remove_device()` | `auth_client.py` | 1068-1158 | Auth client method that sends the removal request |
| `api_dashboard_devices_remove()` | `app.py` | 2958-3157 | Dashboard endpoint that handles device removal |
| `log_device_removal_request()` | `utils/audit_log.py` | 123-175 | Audit logging for request |
| `log_device_removal_response()` | `utils/audit_log.py` | 178-238 | Audit logging for response |

### Data Flow for Device Removal

1. **Session Check**: Verify `device_auth_token` is in session
2. **Password Hash Check**: Verify `parent_password_second_hash` is set (via `/set-parent-password`)
3. **Device ID Validation**: Ensure `deviceId` is provided in request body
4. **Self-Removal Prevention**: Check `deviceId` != `own_device_id`
5. **Parent User ID Retrieval**: Get from session or database
6. **Server Request**: Send POST to `/parent/remove-device` with body only (no Authorization header)
7. **Response Handling**: Log response and return to client

### Common Issues and Troubleshooting

| Issue | Symptom | Solution |
|-------|---------|----------|
| 401 Unauthorized | Token rejected | Remove `token` parameter from `_request_with_retry()` call in `auth_client.py` |
| 401 Unauthorized | Hash mismatch | Ensure `parent_password_second_hash` matches server's stored hash |
| 401 Unauthorized | Wrong parent user | Verify `parent_user_id` matches the device's parent on server |
| 400 Missing hash | Password not set | Call `/set-parent-password` before attempting removal |
| 400 Self-removal | Cannot remove own device | Ensure `deviceId` is different from `own_device_id` |

---

## Files Modified
1. `timelimit-ui/rootfs/usr/bin/dashboardV2/auth_client.py` - Removed `token` parameter from `remove_device()` method, added debug logging
2. `timelimit-ui/rootfs/usr/bin/dashboardV2/app.py` - Added debug logging to multiple functions
3. `timelimit-ui/rootfs/usr/bin/dashboardV2/database.py` - Added `parent_user_id` column and persistence functions
4. `timelimit-ui/CONTEXT.md` - Updated with current status
5. `timelimit-ui/RemoveDeviceIssue.md` - Detailed analysis document
6. `timelimit-ui/rootfs/usr/bin/dashboardV2/utils/audit_log.py` - New audit logging module
7. `timelimit-ui/rootfs/usr/bin/dashboardV2/tests/test_audit_log.py` - Tests for audit logging



Loganalysis:
Summary of Key Findings
1. Audit Log Analysis (audit.log)
The audit log shows TWO separate entries for the same device removal operation:

Entry 1 (Line 1) - From app.py dashboard endpoint:

{
  "event": "device_removal_request",
  "device_id": "rrkF6b",
  "parent_user_id": "KSl70J",
  "device_auth_token": "5ry6B4bIKwk1gtjKcmhfPYTKlXfTsLdk",
  "parent_password_second_hash": "$2b$12$WFMR0fKceu.nnRsUzFhSkOOlshv5yX7/VsCTssPvuqTY14WGdTKC.",
  "request_payload": {
    "deviceAuthToken": "5ry6B4bIKwk1gtjKcmhfPYTKlXfTsLdk",
    "parentUserId": "KSl70J",
    "parentPasswordSecondHash": "$2b$12$WFMR0fKceu.nnRsUzFhSkOOlshv5yX7/VsCTssPvuqTY14WGdTKC.",
    "deviceId": "rrkF6b"
  },
  "request_headers": {
    "Host": "localhost:8099",
    "Connection": "keep-alive",
    "User-Agent": "Mozilla/5.0...",
    "Content-Type": "application/json",
    ...
  }
}

NO Authorization header - This is the browser's request headers
Entry 2 (Line 2) - From auth_client.py remove_device():

{
  "event": "device_removal_request",
  "device_id": "rrkF6b",
  "parent_user_id": "KSl70J",
  "device_auth_token": "5ry6B4bIKwk1gtjKcmhfPYTKlXfTsLdk",
  "parent_password_second_hash": "$2b$12$WFMR0fKceu.nnRsUzFhSkOOlshv5yX7/VsCTssPvuqTY14WGdTKC.",
  "request_payload": {
    "deviceAuthToken": "5ry6B4bIKwk1gtjKcmhfPYTKlXfTsLdk",
    "parentUserId": "KSl70J",
    "parentPasswordSecondHash": "$2b$12$WFMR0fKceu.nnRsUzFhSkOOlshv5yX7/VsCTssPvuqTY14WGdTKC.",
    "deviceId": "rrkF6b"
  },
  "request_headers": {
    "Content-Type": "application/json",
    "Authorization": "Bearer 5ry6B4bIKwk1gtjKcmhfPYTKlXfTsLdk",
    "X-Request-ID": "03e25f49"
  }
}

HAS Authorization header - This is the API request headers being logged
2. Dashboard Log Analysis (dashboardV2-2026-08-31_20-56-30-2d05741d.log)
Line 101 shows the actual API request made to the server:

{
  "has_auth_header": false,
  "auth_header_present": false,
  "auth_header_value": null,
  "all_headers": {
    "Content-Type": "application/json",
    "X-Request-ID": "03e25f49"
  },
  "event": "Making API request"
}

The Authorization header is NOT being sent to the server - This is CORRECT behavior
3. Server Response
The server returned 401 Unauthorized with the error:

UnauthorizedError: Unauthorized
    at assertAuthValidAndReturnDetails (/app/build/api/parent.js:213:23)

4. Root Cause Analysis
The Authorization header issue is NOT the cause of the 401 error. The actual request to the server does NOT include the Authorization header (as shown in the dashboard log).

The 401 error is caused by assertAuthValidAndReturnDetails failing to find a matching parent user. Looking at the server code in parent.ts:

// Line 238-254: The else branch for regular password hash
const parentEntry = await database.user.findOne({
  where: {
    familyId: deviceEntry.familyId,
    type: 'parent',
    userId: parentId,
    secondPasswordHash: secondPasswordHash  // <-- This must match EXACTLY
  },
  transaction
})

if (!parentEntry) {
  throw new Unauthorized()  // <-- This is where the error occurs
}

5. Potential Causes for 401
Password hash mismatch: The parentPasswordSecondHash sent in the request doesn't match what's stored in the server's database for the parent user
Parent user ID mismatch: The parentUserId doesn't match the device's parent on the server
Device auth token mismatch: The deviceAuthToken doesn't match a valid device on the server
6. Data Verification
The request data appears correct:

deviceAuthToken: "5ry6B4bIKwk1gtjKcmhfPYTKlXfTsLdk" (valid format, ~32 chars, starts with letter)
parentUserId: "KSl70J" (valid user ID format)
parentPasswordSecondHash: "
2
b
2b12
W
F
M
R
0
f
K
c
e
u
.
n
n
R
s
U
z
F
h
S
k
O
O
l
s
h
v
5
y
X
7
/
V
s
C
T
s
s
P
v
u
q
T
Y
14
W
G
d
T
K
C
.
"
(
v
a
l
i
d
b
c
r
y
p
t
h
a
s
h
w
i
t
h
WFMR0fKceu.nnRsUzFhSkOOlshv5yX7/VsCTssPvuqTY14WGdTKC."(validbcrypthashwith2b$ prefix and 12 rounds)
deviceId: "rrkF6b" (valid device ID)
7. Discrepancy Found
The audit log in auth_client.py is capturing incorrect headers - it's logging headers with the Authorization header, but the actual request doesn't include it. This is misleading for debugging.

The issue is in auth_client.py line 1097:

headers = self._get_headers(token=device_auth_token)  # This includes Authorization

But the actual request (line 1123-1127) doesn't pass a token:

response = self._request_with_retry(
    'POST',
    '/parent/remove-device',
    data
)  # No token parameter, so no Authorization header

Please confirm which of these potential causes you'd like me to investigate further:

Password hash mismatch - Check if the hash stored on the server matches what's being sent
Parent user ID issue - Verify the parent_user_id is correctly associated with the device on the server
Audit log discrepancy - Fix the audit logging to capture the actual headers sent (without Authorization)