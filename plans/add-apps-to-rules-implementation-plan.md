> **Outdated (2026-11-04):** this plan uses class-style action names (`AddTimeLimitRuleAction`, ...) and outer type `appLogic`. The real server only accepts the wire format in `timelimit-ui/docs/ServerAPI.md`; the implementation is in `action_builder.py` / `action_pusher.py`.

# Implementation Plan: Add Apps to Time Limit Rules

## Overview

This plan outlines the implementation of the missing functionality to add apps to time limit rules. Based on analysis of the official Android app source code, apps are added to categories via `AddCategoryAppAction`, and rules are tied to categories.

## Verification of Current Implementation

### ✅ What's Working

1. **Add Rule functionality** - Verified in audit.log (line 1):
   ```json
   {"type":"AddTimeLimitRuleAction","categoryId":"af11aeef-9a54-46fc-bb91-33dc96c60645","userId":"cTTAQY","rule":{...}}
   ```

2. **Database schema** - `time_limit_rules` table exists with proper columns (id, user_id, category_id, rule_type, start_time, end_time, days, limit_minutes)

3. **API endpoints** - GET, POST, PUT, DELETE on `/api/dashboard/time-limit-rules`

4. **Frontend UI** - Rule form modal with user/category dropdowns, time selection, and limit input

5. **Sync client methods** - `add_time_limit_rule`, `remove_time_limit_rule`, `update_time_limit_rule` in auth_client.py

### ❌ What's Missing

1. **Category-App Assignments** - No way to add/remove apps from categories
2. **Database table** - No `category_apps` table for storing app assignments
3. **API endpoints** - No endpoints for managing apps in categories
4. **Sync client methods** - No `add_category_app`, `remove_category_app` methods
5. **Frontend UI** - No UI for managing apps in categories

## Understanding How Apps Are Added to Rules (from Android App)

### Key Insight from `context_android_app.md` Section 8.12

```python
def add_app_to_category(device_auth_token, server_url, category_id, app_package_name, user_id):
    action = {
        "type": "AddCategoryAppAction",
        "categoryId": category_id,
        "app": app_package_name,
        "userId": user_id
    }
    upload_action(device_auth_token, server_url, action, user_id)
```

### Action Types (from Actions.kt lines 677-703)

```kotlin
data class AddCategoryAppsAction(val categoryId: String, val packageNames: List<String>): ParentAction()
data class RemoveCategoryAppsAction(val categoryId: String, val packageNames: List<String>): ParentAction()
```

### Sync Protocol Flow

1. **Rules are tied to categories** - A rule has a `categoryId` field
2. **Apps are assigned to categories** - `AddCategoryAppAction` assigns apps to a category
3. **When a rule is created, it applies to all apps in that category**

## Implementation Plan

### Phase 1: Database Layer

#### 1.1 Add category_apps Table Schema
**File**: `timelimit-ui/rootfs/usr/bin/dashboardV2/database.py`

Add migration to create `category_apps` table:
```sql
CREATE TABLE IF NOT EXISTS category_apps (
    category_id TEXT NOT NULL,
    device_auth_token TEXT NOT NULL,
    app_package TEXT NOT NULL,
    user_id TEXT,
    created_at INTEGER,
    PRIMARY KEY (category_id, app_package, device_auth_token),
    FOREIGN KEY (device_auth_token) REFERENCES families(device_auth_token)
)
```

#### 1.2 Add Database Functions
**File**: `timelimit-ui/rootfs/usr/bin/dashboardV2/database.py`

Add functions:
- `save_category_app(db, device_auth_token, category_id, app_package, user_id)` - Add single app
- `save_category_apps(db, device_auth_token, category_id, apps, user_id)` - Add multiple apps
- `get_category_apps(db, device_auth_token, category_id)` - Get apps for category
- `remove_category_app(db, device_auth_token, category_id, app_package)` - Remove single app
- `remove_category_apps(db, device_auth_token, category_id, app_packages)` - Remove multiple apps
- `delete_category_apps(db, device_auth_token, category_id)` - Delete all apps for category

### Phase 2: Sync Client Methods

#### 2.1 Add Category App Action
**File**: `timelimit-ui/rootfs/usr/bin/dashboardV2/auth_client.py`

Add method:
```python
def add_category_app(
    self,
    device_auth_token: str,
    category_id: str,
    app_package: str,
    user_id: str,
    sequence_number: int,
    parent_password_second_hash: str
) -> APIResponse:
    """Add an app to a category via sync protocol."""
    # Build AddCategoryAppAction
    # Calculate integrity hash
    # Push via push_actions
```

#### 2.2 Remove Category App Action
**File**: `timelimit-ui/rootfs/usr/bin/dashboardV2/auth_client.py`

Add method:
```python
def remove_category_app(
    self,
    device_auth_token: str,
    category_id: str,
    app_package: str,
    user_id: str,
    sequence_number: int,
    parent_password_second_hash: str
) -> APIResponse:
    """Remove an app from a category via sync protocol."""
    # Build RemoveCategoryAppAction
    # Calculate integrity hash
    # Push via push_actions
```

### Phase 3: Backend API Endpoints

#### 3.1 Add Apps to Category Endpoint
**File**: `timelimit-ui/rootfs/usr/bin/dashboardV2/app.py`

Add endpoint:
```python
@app.route('/api/dashboard/categories/<category_id>/apps', methods=['POST'])
def api_add_apps_to_category(category_id):
    """Add apps to a category."""
    # Validate authentication
    # Get device_auth_token from session
    # Validate category exists
    # Get apps list from request body
    # Save to database
    # Push AddCategoryAppAction via sync protocol
    # Return success response
```

#### 3.2 Remove Apps from Category Endpoint
**File**: `timelimit-ui/rootfs/usr/bin/dashboardV2/app.py`

Add endpoint:
```python
@app.route('/api/dashboard/categories/<category_id>/apps', methods=['DELETE'])
def api_remove_apps_from_category(category_id):
    """Remove apps from a category."""
    # Validate authentication
    # Get device_auth_token from session
    # Validate category exists
    # Get apps list from request body
    # Save to database
    # Push RemoveCategoryAppAction via sync protocol
    # Return success response
```

#### 3.3 Get Category Apps Endpoint
**File**: `timelimit-ui/rootfs/usr/bin/dashboardV2/app.py`

Add endpoint:
```python
@app.route('/api/dashboard/categories/<category_id>/apps', methods=['GET'])
def api_get_category_apps(category_id):
    """Get apps assigned to a category."""
    # Validate authentication
    # Get device_auth_token from session
    # Return list of app package names
```

### Phase 4: Frontend UI

#### 4.1 Update Dashboard HTML
**File**: `timelimit-ui/rootfs/usr/bin/dashboardV2/templates/dashboardV2.html`

Add UI elements for managing apps in categories:
- Apps list display in rules table
- Add app button/modal
- Remove app button

#### 4.2 Add JavaScript Functions
**File**: `timelimit-ui/rootfs/usr/bin/dashboardV2/static/js/dashboardV2.js`

Add functions:
- `loadCategoryApps(categoryId)` - Load apps for a category
- `addAppToCategory(categoryId, appPackage)` - Add app via API
- `removeAppFromCategory(categoryId, appPackage)` - Remove app via API
- `renderAppsInCategory(categoryId, apps)` - Render apps list in UI
- Update `renderTimeLimitRulesTable` to show apps per category

### Phase 5: Testing

#### 5.1 Database Tests
**File**: `timelimit-ui/rootfs/usr/bin/dashboardV2/tests/test_database.py`

Add tests for:
- `save_category_app` function
- `get_category_apps` function
- `remove_category_app` function
- `delete_category_apps` function

#### 5.2 API Tests
**File**: `timelimit-ui/rootfs/usr/bin/dashboardV2/tests/test_dashboard_api.py`

Add tests for:
- POST `/api/dashboard/categories/<id>/apps`
- DELETE `/api/dashboard/categories/<id>/apps`
- GET `/api/dashboard/categories/<id>/apps`

#### 5.3 Sync Client Tests
**File**: `timelimit-ui/rootfs/usr/bin/dashboardV2/tests/test_auth_client.py`

Add tests for:
- `add_category_app` method
- `remove_category_app` method

#### 5.4 E2E Tests
**File**: `timelimit-ui/rootfs/usr/bin/dashboardV2/tests/test_time_limit_rules_e2e.py`

Add tests for:
- Adding apps to category via UI
- Removing apps from category via UI
- Integration with time limit rules

## Technical Details

### Action JSON Format

**AddCategoryAppAction**:
```json
{
    "type": "AddCategoryAppAction",
    "categoryId": "<category_id>",
    "app": "<package_name>",
    "userId": "<user_id>"
}
```

**RemoveCategoryAppAction**:
```json
{
    "type": "RemoveCategoryAppAction",
    "categoryId": "<category_id>",
    "app": "<package_name>",
    "userId": "<user_id>"
}
```

### Integrity Calculation

The integrity hash is calculated using HMAC-SHA256:
```python
integrity = calculate_hmac_sha256_binary(
    parent_password_second_hash,
    sequence_number,
    user_id,  # or category_id for category actions
    encoded_action
)
```

### Database Schema Extension

Add a new table for category-app assignments:
```sql
CREATE TABLE category_apps (
    category_id TEXT NOT NULL,
    device_auth_token TEXT NOT NULL,
    app_package TEXT NOT NULL,
    user_id TEXT,
    created_at INTEGER,
    PRIMARY KEY (category_id, app_package, device_auth_token),
    FOREIGN KEY (device_auth_token) REFERENCES families(device_auth_token)
)
```

## Implementation Order

1. **Phase 1**: Add database operations (database.py)
2. **Phase 2**: Add sync client methods (auth_client.py)
3. **Phase 3**: Add backend API endpoints (app.py)
4. **Phase 4**: Add frontend UI (dashboardV2.html, dashboardV2.js)
5. **Phase 5**: Add tests and verify functionality

## Success Criteria

1. Users can add apps to a category via the dashboard UI
2. Users can remove apps from a category via the dashboard UI
3. Apps assigned to a category are synced to the TimeLimit server
4. Time limit rules apply to the apps in their associated category
5. All existing tests continue to pass
6. New tests cover the added functionality

## Notes

- The current implementation stores rules locally but syncs them to the server
- Apps should also be synced to the server for proper enforcement
- The UI should show which apps are in each category
- Consider adding a way to browse installed apps (requires device integration)
- The `categoryApp` field in `ServerDataStatus` contains the assigned apps per category