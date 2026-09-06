# Sequence Number Fix Plan

## Problem
The "sequence number repeated" error occurs because the `save_sync_state()` function uses `INSERT OR REPLACE` which resets the `next_sequence_number` to its default value (0) when the row is replaced.

## Root Cause
When `save_sync_state()` is called during sync, it replaces the entire row in the `sync_state` table, including the `next_sequence_number` column. This causes the sequence number to reset to 0, which leads to duplicate sequence numbers being sent to the server.

## Solution

### Step 1: Modify `save_sync_state()` in `database.py`
Change the function to preserve the existing `next_sequence_number` when updating the sync state.

**Current implementation:**
```python
cursor.execute('''
    INSERT OR REPLACE INTO sync_state
    (device_auth_token, device_list_version, user_list_version, last_sync_timestamp, last_sync_success)
    VALUES (?, ?, ?, ?, 1)
''', (device_auth_token, device_list_version, user_list_version, current_time))
```

**New implementation:**
```python
# First, get the existing next_sequence_number if it exists
cursor.execute('SELECT next_sequence_number FROM sync_state WHERE device_auth_token = ?', (device_auth_token,))
row = cursor.fetchone()
next_seq = row[0] if row and row[0] is not None else 0

# Then insert or replace, preserving the next_sequence_number
cursor.execute('''
    INSERT OR REPLACE INTO sync_state
    (device_auth_token, device_list_version, user_list_version, last_sync_timestamp, last_sync_success, next_sequence_number)
    VALUES (?, ?, ?, ?, 1, ?)
''', (device_auth_token, device_list_version, user_list_version, current_time, next_seq))
```

### Step 2: Test the fix
1. Restart the dashboard
2. Perform a sync
3. Try removing a device
4. Verify that the sequence number is properly maintained

## Implementation Order
1. Modify `save_sync_state()` in `database.py`
2. Test the implementation