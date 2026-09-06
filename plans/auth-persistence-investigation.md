# Authentication Persistence Investigation & Plan

## Current Implementation Analysis

### How Login Persistence Currently Works

1. **Flask Sessions** (ephemeral):
   - Stored in memory using Flask's `session` object
   - Lost when the application restarts
   - Used for request-scoped authentication state

2. **JSON File Persistence** (`persistence.py`):
   - `device_auth_token` and `own_device_id` are saved to `server_selection.json`
   - Functions: `set_persisted_device_auth_token()`, `get_persisted_device_auth_token()`, etc.
   - Survives application restarts

3. **SQLite Database** (`database.py`):
   - `auth_tokens` table stores tokens with metadata
   - `store_auth_token()` saves tokens to database
   - `get_device_auth_tokens()` retrieves all device auth tokens

4. **Session Restoration** (`app.py` lines 98-123):
   - `@app.before_request` handler `restore_session_from_persistence()`
   - Reads from JSON file and restores to Flask session
   - Runs on every request

### Current Flow on Login
```
User logs in → 
  device_auth_token stored in Flask session →
  set_persisted_device_auth_token() saves to JSON file →
  store_auth_token() saves to SQLite database
```

### Current Flow on App Restart
```
App starts →
  First request triggers before_request handler →
  get_persisted_device_auth_token() reads from JSON file →
  Session restored to Flask session
```

## Problem Statement

The user wants to store the logged-in state "in the python backend instead of the flask part" and keep it over restarting the dashboard.

### Interpretation of User's Request

The current implementation already stores auth tokens in the Python backend (via `persistence.py` JSON file). However, there are potential improvements:

1. **Use SQLite Database Instead of JSON File**:
   - More robust and consistent with other data storage
   - Better for multi-instance deployments
   - ACID guarantees

2. **Restore Session at App Startup (Not Just First Request)**:
   - Current: Session restored on first request via `before_request`
   - Improvement: Restore at module initialization before Flask app starts

3. **Verify Current Implementation Works**:
   - The JSON file approach should work, but may have edge cases

## Proposed Solutions

### Option A: Use SQLite Database for Auth Token Persistence (Recommended)

Store the primary auth token in SQLite database instead of JSON file.

**Pros:**
- Consistent with other data storage approach
- Better for production/Home Assistant deployments
- ACID guarantees
- No separate file to manage

**Cons:**
- Requires database to be initialized before session restoration
- Slightly more complex initialization

**Implementation:**
1. Add `get_latest_device_auth_token()` function in `database.py`
2. Modify `restore_session_from_persistence()` to check database first, then JSON file
3. Update `set_persisted_device_auth_token()` to also save to database
4. Keep JSON file as fallback for backward compatibility

### Option B: Restore Session at App Startup

Restore session state before the first request, not just on the first request.

**Pros:**
- Session is available immediately when app starts
- No need for first request to trigger restoration

**Cons:**
- Requires careful handling of Flask application context
- May need to restructure initialization code

**Implementation:**
1. Move session restoration logic to module level (outside `before_request`)
2. Use Flask's `app_context` to access session outside request
3. Or use a different approach to store session state

### Option C: Keep Current Implementation (Verify It Works)

The current JSON file approach should work. Verify and document it.

**Pros:**
- Minimal changes
- Already implemented

**Cons:**
- JSON file is separate from database
- May have race conditions in multi-instance scenarios

## Recommended Approach

**Option A** is recommended because:
1. It's more robust and consistent with the existing architecture
2. SQLite is already used for all other data
3. It provides better reliability for Home Assistant deployments
4. It maintains backward compatibility with JSON file fallback

## Implementation Plan

### Phase 1: Add Database Function for Latest Auth Token
- [ ] Add `get_latest_device_auth_token()` function in `database.py`
- [ ] Add tests for the new function

### Phase 2: Update Persistence Layer
- [ ] Modify `persistence.py` to use database as primary storage
- [ ] Keep JSON file as fallback for backward compatibility
- [ ] Add tests for database-based persistence

### Phase 3: Update Session Restoration
- [ ] Modify `restore_session_from_persistence()` in `app.py`
- [ ] Restore from database first, then JSON file
- [ ] Add tests for session restoration

### Phase 4: Update Token Storage
- [ ] Ensure `set_persisted_device_auth_token()` saves to database
- [ ] Ensure `set_persisted_own_device_id()` saves to database
- [ ] Add tests for token storage

### Phase 5: Cleanup and Documentation
- [ ] Update CONTEXT.md with changes
- [ ] Update login-persistence-plan.md
- [ ] Run full test suite to verify no regressions

## Files to Modify

1. `timelimit-ui/rootfs/usr/bin/dashboardV2/database.py` - Add auth token retrieval function
2. `timelimit-ui/rootfs/usr/bin/dashboardV2/persistence.py` - Update to use database
3. `timelimit-ui/rootfs/usr/bin/dashboardV2/app.py` - Update session restoration
4. `timelimit-ui/rootfs/usr/bin/dashboardV2/tests/test_database.py` - Add tests
5. `timelimit-ui/rootfs/usr/bin/dashboardV2/tests/test_persistence.py` - Add tests
6. `timelimit-ui/rootfs/usr/bin/dashboardV2/tests/test_dashboard_api.py` - Add tests

## Questions for User

1. Do you want to use SQLite database instead of JSON file for auth token persistence?
2. Or do you want to keep the current JSON file approach but ensure it works correctly?
3. Should we restore the session at app startup (before first request) or keep the current `before_request` approach?