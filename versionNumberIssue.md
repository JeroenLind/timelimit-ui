# Version Number Reporting Issue - Investigation & Implementation Plan

## Problem Statement
The dashboard application is updated to version 226, matching the official Android app, but the session information still reports version 0. The `/api/session/status` endpoint correctly returns `configured_app_version: 226`, but the device's `current_app_version` in the server's database remains 0.

## Current State ✅

### What's Working
1. **Dashboard APP_VERSION**: Correctly hardcoded to 226 in `config.py` (line 180)
2. **Session Status API**: `/api/session/status` correctly returns `configured_app_version: 226` (app.py line 1770)
3. **Local Database Update**: After sync, `do_sync()` updates the LOCAL database's device record with the app version via `update_device_app_version()` (sync_manager.py lines 117-134)

### What's NOT Working
The server's device record still shows `currentAppVersion: 0` and `highestAppVersion: 0` because the dashboard doesn't send its app version to the server.

## Root Cause Analysis

### How the Official Android App Sends App Version
1. **Action Creation**: The Android app creates an `UpdateDeviceStatusAction` with `newAppVersion = BuildConfig.VERSION_CODE` (SyncUtil.kt line 947)
2. **Storage**: The action is stored in the `pendingSyncAction` table with:
   - `type = "appLogic"`
   - `userId = ""`
   - `integrity = ""`
   - `encodedAction = JSON serialized action`
3. **Push**: Actions are pushed via `/sync/push-actions` endpoint (UploadActionsUtil.kt)
4. **Server Processing**: Server's `dispatchUpdateDeviceStatus` updates `deviceEntry.currentAppVersion` and `deviceEntry.highestAppVersion` (updatedevicestatus.ts lines 130-143)

### How the Dashboard Currently Works
1. **Sync Pull**: Dashboard calls `pull_status()` to get data from server
2. **Local Update**: Dashboard updates LOCAL database via `update_device_app_version()`
3. **Missing**: Dashboard NEVER sends `UpdateDeviceStatusAction` to server

## Investigation Findings

### 1. appLogic Action Validation ✅
**Finding**: appLogic type actions are NOT validated by `assertActionIntegrity()`.

**Implication**: The dashboard can send appLogic actions with `integrity = ""` and `userId = ""` without any integrity validation.

### 2. Sequence Number Handling ✅
**Finding**: The server uses `nextSequenceNumber` to prevent duplicate actions.

**Implication**: 
- Initial `nextSequenceNumber` is 0
- Dashboard can start with `sequenceNumber = 0`
- After pushing, server updates to `nextSequenceNumber = 1`
- Dashboard needs to track and increment sequence number locally

### 3. UpdateDeviceStatusAction Format ✅
**Finding**: The action format is:
```json
{
  "type": "UPDATE_DEVICE_STATUS",
  "appVersion": 226
}
```

### 4. Server Action Parsing ✅
**Finding**: The server parses `encodedAction` as JSON and validates against schema.

## Implementation Plan

### Step 1: Add Sequence Number Tracking to database.py

**File**: `timelimit-ui/rootfs/usr/bin/dashboardV2/database.py`

**Changes**:
1. Add `next_sequence_number INTEGER DEFAULT 0` column to `sync_state` table in `init_db()`
2. Add `get_next_sequence_number(db, device_auth_token)` function
3. Add `increment_sequence_number(db, device_auth_token)` function

**Verification**:
- [ ] Column added to CREATE TABLE statement
- [ ] Function retrieves sequence number correctly
- [ ] Function increments and returns new sequence number

### Step 2: Add Action Building Method in sync_manager.py

**File**: `timelimit-ui/rootfs/usr/bin/dashboardV2/sync_manager.py`

**Changes**:
1. Add `build_update_device_status_action(app_version)` method
2. Add `push_app_version_action(device_auth_token, server_url, app_version)` method

**Verification**:
- [ ] Action JSON format is correct: `{"type":"UPDATE_DEVICE_STATUS","appVersion":226}`
- [ ] Action structure for push is correct:
  ```python
  {
      "encodedAction": '{"type":"UPDATE_DEVICE_STATUS","appVersion":226}',
      "sequenceNumber": <next_sequence_number>,
      "integrity": "",
      "type": "appLogic",
      "userId": ""
  }
  ```
- [ ] push_actions() is called correctly with AuthClient

### Step 3: Integrate into Sync Flow

**File**: `timelimit-ui/rootfs/usr/bin/dashboardV2/sync_manager.py`

**Changes**:
1. Call `push_app_version_action()` in `do_sync()` before or after `pull_status()`

**Verification**:
- [ ] Method is called during sync
- [ ] Errors are handled gracefully (don't break sync)

### Step 4: Add Tests

**File**: `timelimit-ui/rootfs/usr/bin/dashboardV2/tests/test_database.py`
**File**: `timelimit-ui/rootfs/usr/bin/dashboardV2/tests/test_sync_manager.py`

**Changes**:
1. Add tests for `get_next_sequence_number()`
2. Add tests for `increment_sequence_number()`
3. Add tests for `build_update_device_status_action()`
4. Add tests for `push_app_version_action()`

**Verification**:
- [ ] All new tests pass
- [ ] Existing tests still pass

### Step 5: Update CONTEXT.md

**File**: `context.md`

**Changes**:
1. Document the implementation
2. Update recent changes section

**Verification**:
- [ ] Implementation documented
- [ ] Test results recorded

## Verification Checklist

After implementation, verify:

1. **Local Database**: Dashboard's local device record shows correct app version
2. **Server Database**: Server's device record shows correct app version (check via API or database)
3. **Session Status**: `/api/session/status` returns `configured_app_version: 226`
4. **Devices Table**: Other users see the dashboard's device with correct version
5. **All Tests Pass**: Run `pytest` to verify no regressions

## Files to Modify

1. `timelimit-ui/rootfs/usr/bin/dashboardV2/database.py`
2. `timelimit-ui/rootfs/usr/bin/dashboardV2/sync_manager.py`
3. `timelimit-ui/rootfs/usr/bin/dashboardV2/tests/test_database.py`
4. `timelimit-ui/rootfs/usr/bin/dashboardV2/tests/test_sync_manager.py`
5. `context.md`

## API Endpoints Used

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/sync/pull-status` | POST | Pull server data (already implemented) |
| `/sync/push-actions` | POST | Push UpdateDeviceStatusAction (needs implementation) |

## Action Format Reference

### Request to /sync/push-actions
```json
{
  "deviceAuthToken": "string",
  "actions": [
    {
      "encodedAction": "{\"type\":\"UPDATE_DEVICE_STATUS\",\"appVersion\":226}",
      "sequenceNumber": 0,
      "integrity": "",
      "type": "appLogic",
      "userId": ""
    }
  ]
}
```

### Response from /sync/push-actions
```json
{
  "shouldDoFullSync": false
}
```

## Sequence Diagram

```
Dashboard                    Server
    |                            |
    |--- pull-status --------->|  (get server data)
    |<-- ServerDataStatus ------|  (includes device data with cAppVersion: 0)
    |                            |
    |--- push-actions ---------->|  (send UpdateDeviceStatusAction)
    |                            |
    |<-- shouldDoFullSync ------|  (response)
    |                            |
    |--- pull-status --------->|  (next sync)
    |<-- ServerDataStatus ------|  (device now has cAppVersion: 226)