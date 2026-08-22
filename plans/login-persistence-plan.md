# Login Persistence Implementation Plan

## Problem Statement
Flask sessions are ephemeral - stored in memory and lost when the application restarts. While `device_auth_token` is stored in the SQLite database, there's no mechanism to restore it to the session on application startup.

## Solution Overview
Implement session persistence for authentication tokens by:
1. Adding database functions to retrieve stored device_auth_tokens
2. Adding persistence layer for auth tokens (similar to server selection)
3. Restoring session on application startup

## Implementation Steps

### Step 1: Add Database Function to Get Device Auth Tokens
**File:** `timelimit-ui/rootfs/usr/bin/dashboardV2/database.py`

Add a new function `get_device_auth_tokens()` to retrieve all device_auth_tokens from the auth_tokens table.

```python
def get_device_auth_tokens(db: Database) -> List[Dict[str, Any]]:
    """Get all device_auth_tokens from the database.
    
    Returns:
        List of token records with token_type='device_auth_token'.
    """
```

### Step 2: Add Persistence Layer for Auth Tokens
**File:** `timelimit-ui/rootfs/usr/bin/dashboardV2/persistence.py`

Add functions to persist and retrieve the device_auth_token:
- `get_persisted_device_auth_token()` - Get from persistent storage
- `set_persisted_device_auth_token()` - Save to persistent storage

The persistence will use the same JSON file as server selection (`server_selection.json`).

### Step 3: Modify app.py to Restore Session on Startup
**File:** `timelimit-ui/rootfs/usr/bin/dashboardV2/app.py`

Add session restoration logic in the `create_app()` function or at module initialization:
1. Check for persisted device_auth_token
2. Check for persisted own_device_id
3. Restore to Flask session if found

### Step 4: Update store_auth_token Calls
**File:** `timelimit-ui/rootfs/usr/bin/dashboardV2/app.py`

Ensure `store_auth_token()` is called with the device_auth_token when storing in session (already done in lines 1101-1108, 1333-1340).

### Step 5: Add Tests
**File:** `timelimit-ui/rootfs/usr/bin/dashboardV2/tests/test_persistence.py`

Add tests for the new persistence functions.

## Technical Details

### Database Schema (auth_tokens table)
```sql
CREATE TABLE IF NOT EXISTS auth_tokens (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    token_type TEXT NOT NULL,
    token_value TEXT NOT NULL UNIQUE,
    device_id TEXT,
    device_auth_token TEXT,
    mail TEXT,
    code TEXT,
    created_at TEXT NOT NULL,
    expires_at TEXT,
    FOREIGN KEY (device_id) REFERENCES devices(id),
    FOREIGN KEY (device_auth_token) REFERENCES families(device_auth_token)
)
```

### Session Restoration Logic
On application startup:
1. Read persisted device_auth_token from JSON file
2. If found, restore to Flask session
3. Also restore own_device_id if persisted

### Persistence File Structure
The `server_selection.json` file will be extended to include:
```json
{
    "server_key": "...",
    "server_url": "...",
    "device_auth_token": "...",
    "own_device_id": "...",
    "updated_at": 1234567890
}
```

## Files to Modify
1. `database.py` - Add `get_device_auth_tokens()` function
2. `persistence.py` - Add auth token persistence functions
3. `app.py` - Add session restoration on startup
4. `tests/test_persistence.py` - Add tests for new functions

## Edge Cases to Handle
1. Multiple device_auth_tokens in database (should use the most recent)
2. Expired tokens (check expires_at field)
3. Database not initialized yet
4. Persisted token no longer valid (server-side revocation)