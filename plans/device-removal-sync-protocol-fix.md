# Device Removal Sync Protocol Fix Plan

## Problem
The "sequence number repeated" error when removing devices indicates that device removal should go through the sync protocol (push-actions) instead of the direct `/parent/remove-device` API call.

## Root Cause
1. Current implementation calls `/parent/remove-device` directly
2. Server expects device removal actions through sync protocol
3. Sync protocol requires unique sequence numbers for each action

## Solution

### Step 1: Add `push_device_removal_action()` method to `auth_client.py`
- Get next sequence number from database
- Build device removal action with proper integrity hash
- Push action via `/sync/push-actions`
- Increment sequence number after success

### Step 2: Update `api_dashboard_remove_device()` route in `app.py`
- Replace direct `auth_client.remove_device()` call with sync-based method
- Import necessary functions from `crypto_utils.py`

### Step 3: Update JavaScript (if needed)
- Frontend already calls correct endpoint

### Step 4: Test implementation
- Verify device removal works through sync protocol
- Ensure sequence numbers are properly managed

## Technical Details

### Device Removal Action Format
```json
{
  "encodedAction": "{\"type\":\"REMOVE_DEVICE\",\"deviceId\":\"<device_id>\"}",
  "sequenceNumber": <next_sequence_number>,
  "integrity": "password:<base64_hmac>",
  "type": "appLogic",
  "userId": "<parent_user_id>"
}
```

### Integrity Calculation
Use `calculate_hmac_sha256_binary()` from `crypto_utils.py`:
- Key: `parent_password_second_hash`
- Message: Binary format with sequenceNumber, deviceId, encodedAction

## Implementation Order
1. Add `push_device_removal_action()` to `auth_client.py`
2. Update `api_dashboard_remove_device()` in `app.py`
3. Test the implementation