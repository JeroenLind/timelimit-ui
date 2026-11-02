# Add Dummy User Feature - Implementation Plan

## Overview
Add a button in the dashboard sidebar Actions section that creates a dummy user directly in the local database for testing time limit rules. This bypasses the need to go through the TimeLimit server API.

## Current State Analysis

### Sidebar Actions Section (dashboardV2.html:751-757)
```html
<h3>Actions</h3>
<ul>
    <li><button id="sync-now-btn" class="sidebar-action-link" role="menuitem">Sync Now</button></li>
    <li><a href="/login-as-parent" id="login-sidebar-link" class="sidebar-action-link" role="menuitem">Sign In</a></li>
    <li><a href="/create-family" id="create-family-sidebar-link" class="sidebar-action-link" role="menuitem">Create Family</a></li>
    <li><button id="signout-btn-sidebar" role="menuitem">Sign Out</button></li>
</ul>
```

### Session Status Endpoint (app.py:2588-2655)
Returns: `authenticated`, `server_url`, `has_device_auth_token`, `device_auth_token`, `has_parent_password_second_hash`, etc.

### Existing Add User Flow (app.py:3632-3861)
1. Requires `device_auth_token` in session
2. Requires `parent_password_second_hash` in session
3. Calls TimeLimit server API:
   - `create_add_device_token`
   - `add_device`
   - `pull_status`
4. Saves users to database via `save_users`

### Users Table Schema (database.py:168-186)
```sql
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    device_auth_token TEXT NOT NULL,
    name TEXT,
    password TEXT,
    second_password_salt TEXT,
    type TEXT,
    time_zone TEXT,
    disable_limits_until INTEGER,
    mail TEXT,
    current_device TEXT,
    category_for_not_assigned_apps TEXT,
    relax_primary_device INTEGER DEFAULT 0,
    flags INTEGER DEFAULT 0,
    limit_login_category TEXT,
    pre_block_duration INTEGER DEFAULT 0,
    last_updated INTEGER,
    FOREIGN KEY (device_auth_token) REFERENCES families(device_auth_token)
)
```

## Implementation Steps

### Step 1: Add Database Function (database.py)
Add `insert_dummy_user()` function to insert a dummy user directly into the database.

**Location**: After `save_users()` function (around line 1368)

**Function signature**:
```python
def insert_dummy_user(
    db: Database,
    device_auth_token: str,
    user_name: str = "Dummy User",
    user_type: str = "child",
    category_for_not_assigned_apps: Optional[str] = None
) -> Optional[str]:
    """Insert a dummy user directly into the database for testing purposes.
    
    Args:
        db: Database instance.
        device_auth_token: The device auth token this user belongs to.
        user_name: Display name for the dummy user.
        user_type: User type (default: 'child').
        category_for_not_assigned_apps: Default category for unassigned apps.
        
    Returns:
        User ID if successful, None otherwise.
    """
```

### Step 2: Add API Endpoint (app.py)
Add `/api/dashboard/users/add-dummy` endpoint.

**Location**: After `api_add_user_to_family()` function (around line 3862)

**Endpoint behavior**:
- Require authentication (device_auth_token in session)
- Generate a unique user ID
- Insert user directly into database
- Return user ID and device auth token

### Step 3: Add Button in HTML (dashboardV2.html)
Add button in sidebar Actions section.

**Location**: Line 756 (after Create Family link, before Sign Out button)

```html
<li><button id="add-dummy-user-btn" class="sidebar-action-link" role="menuitem">Add Dummy User</button></li>
```

### Step 4: Add JavaScript Function (dashboardV2.js)
Add `addDummyUser()` function to handle button click.

**Location**: After `submitAddUserForm()` function (around line 1298)

**Function behavior**:
- Call `/api/dashboard/users/add-dummy` endpoint
- Show success/error alert
- Refresh users view

### Step 5: Update updateSessionOverview (dashboardV2.js)
Update the function to handle the new button visibility.

**Location**: Lines 411-425

The button should be visible when authenticated (like Sign Out button).

### Step 6: Add CSS (dashboardV2.css)
Ensure the button has proper styling (should inherit from `.sidebar-action-link`).

### Step 7: Add Tests
Add tests for:
- Database function `insert_dummy_user`
- API endpoint `/api/dashboard/users/add-dummy`
- HTML button element
- JavaScript function `addDummyUser`
- Button visibility in `updateSessionOverview`

## Files to Modify

1. `timelimit-ui/rootfs/usr/bin/dashboardV2/database.py` - Add `insert_dummy_user()` function
2. `timelimit-ui/rootfs/usr/bin/dashboardV2/app.py` - Add `/api/dashboard/users/add-dummy` endpoint
3. `timelimit-ui/rootfs/usr/bin/dashboardV2/templates/dashboardV2.html` - Add button in sidebar
4. `timelimit-ui/rootfs/usr/bin/dashboardV2/static/js/dashboardV2.js` - Add `addDummyUser()` function
5. `timelimit-ui/rootfs/usr/bin/dashboardV2/tests/test_database.py` - Add database tests
6. `timelimit-ui/rootfs/usr/bin/dashboardV2/tests/test_dashboard_api.py` - Add API tests
7. `timelimit-ui/rootfs/usr/bin/dashboardV2/tests/test_visual_responsive.py` - Add UI tests

## Data Flow Diagram

```mermaid
flowchart TD
    A[User clicks "Add Dummy User" button] --> B[JavaScript addDummyUser() function]
    B --> C[POST /api/dashboard/users/add-dummy]
    C --> D[Backend validates authentication]
    D --> E[Generate unique user ID]
    E --> F[Insert user into database]
    F --> G[Return user ID to frontend]
    G --> H[Show success alert]
    H --> I[Refresh users view]
```

## Questions for Clarification

1. Should the dummy user have a specific name pattern (e.g., "Dummy User 1", "Dummy User 2")?
2. Should there be an option to specify the user name, or always use a default?
3. Should the dummy user be created with a specific category for unassigned apps?
4. Should there be a limit on how many dummy users can be created?