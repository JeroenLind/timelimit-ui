# Pull Status Fix Plan

## Issue Summary

The `pull_status` method in `auth_client.py` sends a `ClientDataStatus` payload with incorrect field types that the TimeLimit server rejects with HTTP 400 BadRequestError.

## Root Cause Analysis

### Login Flow Timeline
1. **Step 1 (Email)**: ✅ Success - Sent mail login code
2. **Step 2 (Code)**: ✅ Success - Verified code, received `mailAuthToken`
3. **Step 3 (Device Info)**: ✅ Success - Signed in to family, received `deviceAuthToken` and `ownDeviceId`
4. **Fallback `pull_status`**: ❌ Failed with HTTP 400 BadRequestError

### The Problem

The `pull_status` method sends a `ClientDataStatus` payload that doesn't match the format expected by the server.

**Python client sends:**
```json
{
    "clientLevel": 7,
    "devices": null,
    "users": null,
    "apps": {},
    "devicesDetail": {},
    "categories": {},
    "kri": 0,
    "kr": 0,
    "dh": null,
    "u2f": null
}
```

**Server expects (Android app format):**
```json
{
    "clientLevel": 7,
    "devices": "",
    "users": "",
    "apps": {},
    "categories": {}
}
```

### Key Differences

| Field | Python Client | Android App | Server Expects |
|-------|---------------|-------------|----------------|
| `devices` | `null` | `""` (empty string) | String |
| `users` | `null` | `""` (empty string) | String |
| `kri` | `0` | **omitted** | Omitted/null |
| `kr` | `0` | **omitted** | Omitted/null |
| `dh` | `null` | **omitted** | Omitted/null |
| `u2f` | `null` | **omitted** | Omitted/null |
| `devicesDetail` | `{}` | **omitted when empty** | Omitted when empty |

### Server Error

The server returns HTTP 400 with `BadRequestError: Bad Request` at `/app/build/api/sync.js:66:23`.

## Fix Plan

### Step 1: Documentation Update ✅ COMPLETED
- Added `ClientDataStatus` payload format documentation to `CONTEXT.md`
- Documented the correct format matching Android app's `ClientDataStatus.empty`

### Step 2: Fix `auth_client.py` `pull_status()` Method
**File:** `timelimit-ui/rootfs/usr/bin/dashboardV2/auth_client.py`
**Lines:** 932-943

**Change:**
```python
# Before:
if client_data_status is None:
    client_data_status = {
        "clientLevel": 7,
        "devices": None,
        "users": None,
        "apps": {},
        "devicesDetail": {},
        "categories": {},
        "kri": 0,
        "kr": 0,
        "dh": None,
        "u2f": None
    }

# After:
if client_data_status is None:
    client_data_status = {
        "clientLevel": 7,
        "devices": "",
        "users": "",
        "apps": {},
        "categories": {}
    }
```

### Step 3: Fix `sync_manager.py` `_build_client_data_status()` Method
**File:** `timelimit-ui/rootfs/usr/bin/dashboardV2/sync_manager.py`
**Lines:** 147-158, 161-172

**Change:**
```python
# Before:
if sync_state is None:
    return {
        "clientLevel": 7,
        "devices": None,
        "users": None,
        "apps": {},
        "devicesDetail": {},
        "categories": {},
        "kri": 0,
        "kr": 0,
        "dh": None,
        "u2f": None
    }

# After:
if sync_state is None:
    return {
        "clientLevel": 7,
        "devices": "",
        "users": "",
        "apps": {},
        "categories": {}
    }
```

### Step 4: Investigate Family ID Retrieval
**Status:** NEEDS INVESTIGATION

The `sign-in-into-family` endpoint response does NOT include `familyId` in `initialData` or `data` fields.

**Investigation needed:**
1. Check if `familyId` is returned in a different field in the `sign-in-into-family` response
2. Check if `familyId` is available in the `pull_status` response (may be in an undocumented field)
3. Consider alternative approaches to obtain `familyId`

### Step 5: Add Tests
- Add tests to verify the `ClientDataStatus` payload format
- Add tests for `familyId` retrieval

## Reference Sources

- Android app `ClientDataStatus.kt`: `C:\git\timelimit-android\app\src\main\java\io\timelimit\android\sync\network\ClientDataStatus.kt`
- Android app `HttpServerApi.kt`: `C:\git\timelimit-android\app\src\main\java\io\timelimit\android\sync\network\api\HttpServerApi.kt`
- Python `auth_client.py`: `timelimit-ui/rootfs/usr/bin/dashboardV2/auth_client.py`
- Python `sync_manager.py`: `timelimit-ui/rootfs/usr/bin/dashboardV2/sync_manager.py`

## Expected Outcome

After the fix:
1. `pull_status` will return HTTP 200 with `ServerDataStatus` data
2. `familyId` will be extracted from the response (if available)
3. Dashboard will show proper authentication status with valid `family_id`