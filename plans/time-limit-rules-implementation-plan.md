> **Outdated (2026-11-04):** this plan uses class-style action names (`AddTimeLimitRuleAction`, ...) and outer type `appLogic`. The real server only accepts the wire format in `timelimit-ui/docs/ServerAPI.md`; the implementation is in `action_builder.py` / `action_pusher.py`.

# Time Limit Rules Feature Implementation Plan

## Executive Summary

This plan outlines the implementation of a feature to add and manage time limit rules for users in the TimeLimit Dashboard V2. The feature will allow parents to configure time limits for child users through the web dashboard, leveraging the existing sync protocol with the TimeLimit server.

**Risk Level:** Medium (requires sync protocol integration)

---

## 1. API Investigation

### 1.1 Server API Endpoints Analysis

Based on the Android app source code (`context_android_app.md`) and ServerAPI documentation:

#### Time Limit Rule Actions
The sync protocol supports the following action types for time limit rules:
- `AddTimeLimitRuleAction` - Add a new time limit rule
- `RemoveTimeLimitRuleAction` - Remove an existing time limit rule

#### Action Structure (from Actions.kt lines 357-358)
```json
{
  "type": "AddTimeLimitRuleAction",
  "categoryId": "<category_id>",
  "userId": "<user_id>",
  "rule": {
    "type": 0,  // 0=TimeLimitRuleType.TIME_LIMIT, 1=TIME_LIMIT_EXCEPTIONS
    "startTime": "HH:MM",  // Start time in 24-hour format
    "endTime": "HH:MM",    // End time in 24-hour format
    "days": 127,           // Bitmask for days (bit 0=Monday, bit 6=Sunday)
    "limitMinutes": 120    // Duration in minutes
  }
}
```

#### Sync Protocol Requirements
- **Client Level**: 7 (matches Android app's `ClientDataStatus.CLIENT_LEVEL_VALUE`)
- **Authentication**: `device_auth_token` in Bearer header
- **Request Format**: Gzip-compressed JSON
- **Integrity**: HMAC-SHA256 signature per action
- **Sequence Numbers**: Monotonically increasing per device

#### ServerDataStatus Structure (from context_android_app.md lines 314-334)
```json
{
  "rules": [
    {
      "categoryId": "<category_id>",
      "userId": "<user_id>",
      "rule": {
        "type": 0,
        "startTime": "HH:MM",
        "endTime": "HH:MM",
        "days": 127,
        "limitMinutes": 120
      },
      "version": "<version_string>"
    }
  ]
}
```

### 1.2 Authentication Flow
1. User authenticates via email verification
2. Server returns `device_auth_token` and `own_device_id`
3. All API calls use `device_auth_token` in Authorization header
4. Parent password hash required for write operations (device removal, etc.)

### 1.3 Data Models

#### User Model (from ServerAPI.md lines 596-614)
```typescript
interface User {
    id: string;
    name: string;
    type: "parent" | "child";
    mail: string;
    time_zone: string;
    disable_limits_until: number | null;
    current_device: string;
    password: string;
    second_password_salt: string;
    flags: number;
    limit_login_category: string;
    pre_block_duration: number;
}
```

#### Category Model (from ServerAPI.md lines 637-654)
```typescript
interface Category {
    id: string;
    title: string;
    blocked_times: string;  // Bitmask string
    extra_time: number;
    extra_time_day: number;
    temp_blocked: number;
    temp_block_time: number;
    version: string;
    parent_category_id: string | null;
    flags: number;
    last_updated: number;
}
```

---

## 2. UI/UX Design

### 2.1 Wireframes

#### Time Limit Rules Management Page
```
┌─────────────────────────────────────────────────────────────┐
│ Time Limit Rules                                   [Back] │
├─────────────────────────────────────────────────────────────┤
│ User: [Child User ▼]                                       │
│ Category: [All Categories ▼]                               │
│                                                            │
│ ┌─────────────────────────────────────────────────────────┐│
│ │ Rule 1: Weekdays 9:00 - 17:00 (2 hours)              ││
│ │ [Edit] [Delete]                                        ││
│ └─────────────────────────────────────────────────────────┘│
│                                                            │
│ ┌─────────────────────────────────────────────────────────┐│
│ │ Rule 2: Weekends Unlimited                             ││
│ │ [Edit] [Delete]                                        ││
│ └─────────────────────────────────────────────────────────┘│
│                                                            │
│ + Add New Rule                                             │
└─────────────────────────────────────────────────────────────┘
```

#### Add/Edit Time Limit Rule Modal
```
┌─────────────────────────────────────────────────────────────┐
│ Add Time Limit Rule                                        │
├─────────────────────────────────────────────────────────────┤
│ User: [Select User ▼]                                      │
│ Category: [Select Category ▼]                              │
│                                                            │
│ Duration: [ ] minutes                                       │
│                                                            │
│ Days:                                                      │
│ [x] Mon [x] Tue [x] Wed [x] Thu [x] Fri [ ] Sat [ ] Sun     │
│                                                            │
│ Time:                                                      │
│ From: [__:__] AM/PM    To: [__:__] AM/PM                   │
│                                                            │
│ [Cancel] [Save Rule]                                       │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 UI Components

1. **TimeLimitRulesList** - Displays existing rules with edit/delete options
2. **AddRuleButton** - Floating action button to add new rules
3. **RuleFormModal** - Modal for creating/editing rules
4. **UserSelector** - Dropdown for selecting child users
5. **CategorySelector** - Dropdown for selecting categories
6. **TimePicker** - Time selection component
7. **DaysPicker** - Checkbox group for day selection

### 2.3 Accessibility Considerations
- Keyboard navigation support
- ARIA labels for screen readers
- High contrast mode support
- Focus management for modals

---

## 3. Backend Integration

### 3.1 API Endpoints to Implement

#### 3.1.1 GET /api/dashboard/time-limit-rules
Retrieve all time limit rules for the authenticated family.

**Request:**
```http
GET /api/dashboard/time-limit-rules
Authorization: Bearer <device_auth_token>
```

**Response:**
```json
{
  "status": "ok",
  "rules": [
    {
      "id": "rule_123",
      "categoryId": "cat_456",
      "userId": "user_789",
      "rule": {
        "type": 0,
        "startTime": "09:00",
        "endTime": "17:00",
        "days": 127,
        "limitMinutes": 120
      },
      "version": "v1"
    }
  ]
}
```

#### 3.1.2 POST /api/dashboard/time-limit-rules
Create a new time limit rule.

**Request:**
```http
POST /api/dashboard/time-limit-rules
Authorization: Bearer <device_auth_token>
Content-Type: application/json

{
  "userId": "user_789",
  "categoryId": "cat_456",
  "rule": {
    "type": 0,
    "startTime": "09:00",
    "endTime": "17:00",
    "days": 127,
    "limitMinutes": 120
  }
}
```

**Response:**
```json
{
  "status": "ok",
  "ruleId": "rule_123"
}
```

#### 3.1.3 PUT /api/dashboard/time-limit-rules/{ruleId}
Update an existing time limit rule.

#### 3.1.4 DELETE /api/dashboard/time-limit-rules/{ruleId}
Delete a time limit rule.

### 3.2 Backend Implementation Details

#### 3.2.1 Database Schema Changes
Add `time_limit_rules` table to `database.py`:

```python
# Create time_limit_rules table
cursor.execute('''
    CREATE TABLE IF NOT EXISTS time_limit_rules (
        id TEXT PRIMARY KEY,
        device_auth_token TEXT NOT NULL,
        user_id TEXT NOT NULL,
        category_id TEXT NOT NULL,
        rule_type INTEGER DEFAULT 0,
        start_time TEXT,
        end_time TEXT,
        days INTEGER DEFAULT 127,
        limit_minutes INTEGER DEFAULT 0,
        version TEXT,
        created_at TEXT NOT NULL,
        last_updated INTEGER,
        FOREIGN KEY (device_auth_token) REFERENCES families(device_auth_token),
        FOREIGN KEY (user_id) REFERENCES users(id),
        FOREIGN KEY (category_id) REFERENCES categories(id)
    )
''')
```

#### 3.2.2 Sync Integration
Use the existing `push_actions()` method in `auth_client.py` to send `AddTimeLimitRuleAction` to the server:

```python
def add_time_limit_rule(
    self,
    device_auth_token: str,
    user_id: str,
    category_id: str,
    rule: Dict[str, Any]
) -> APIResponse:
    """Add a time limit rule via sync protocol."""
    # Build the action
    action = {
        "type": "AddTimeLimitRuleAction",
        "categoryId": category_id,
        "userId": user_id,
        "rule": rule
    }
    
    # Push via sync protocol
    return self.push_actions(device_auth_token, [action])
```

#### 3.2.3 Validation Logic
- Validate time format (HH:MM 24-hour)
- Validate days bitmask (0-127)
- Validate limitMinutes (positive integer)
- Ensure user exists and is a child
- Ensure category exists and belongs to user

---

## 4. Frontend Implementation

### 4.1 React Component Structure

```
src/
├── components/
│   ├── TimeLimitRules/
│   │   ├── TimeLimitRulesList.jsx
│   │   ├── RuleFormModal.jsx
│   │   ├── UserSelector.jsx
│   │   ├── CategorySelector.jsx
│   │   └── DaysPicker.jsx
│   └── common/
│       ├── TimePicker.jsx
│       └── ConfirmDialog.jsx
├── hooks/
│   └── useTimeLimitRules.js
└── services/
    └── timeLimitRulesApi.js
```

### 4.2 API Service Layer

```javascript
// services/timeLimitRulesApi.js
const API_BASE = '/api';

export const timeLimitRulesApi = {
  getRules: async () => {
    const response = await fetch(`${API_BASE}/dashboard/time-limit-rules`);
    return response.json();
  },
  
  addRule: async (ruleData) => {
    const response = await fetch(`${API_BASE}/dashboard/time-limit-rules`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(ruleData)
    });
    return response.json();
  },
  
  updateRule: async (ruleId, ruleData) => {
    const response = await fetch(`${API_BASE}/dashboard/time-limit-rules/${ruleId}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(ruleData)
    });
    return response.json();
  },
  
  deleteRule: async (ruleId) => {
    const response = await fetch(`${API_BASE}/dashboard/time-limit-rules/${ruleId}`, {
      method: 'DELETE'
    });
    return response.json();
  }
};
```

### 4.3 Integration with Existing Dashboard

Add a new tab to the dashboard for time limit rules:

```javascript
// In dashboardV2.html, add after Connected Devices section
<div class="dashboard-content">
    <h2>Time Limit Rules</h2>
    <div style="margin-bottom: 10px;">
        <button class="refresh-btn" id="refresh-rules-btn" onclick="refreshTimeLimitRules()">
            <span>🔄</span> Refresh Rules
        </button>
    </div>
    <div id="time-limit-rules-container">
        <!-- TimeLimitRulesList component will render here -->
    </div>
</div>
```

---

## 5. Testing

### 5.1 Unit Tests

#### 5.1.1 API Interaction Tests
```python
# tests/test_time_limit_rules_api.py
def test_add_time_limit_rule_success():
    """Test successful time limit rule creation."""
    # Mock server response
    # Verify action is correctly formatted
    # Verify sync protocol is called

def test_add_time_limit_rule_validation():
    """Test validation of time limit rule data."""
    # Test invalid time format
    # Test invalid days bitmask
    # Test negative limit minutes
    # Test missing required fields

def test_remove_time_limit_rule():
    """Test time limit rule removal."""
    # Verify RemoveTimeLimitRuleAction is sent
    # Verify correct rule ID is used
```

#### 5.1.2 Frontend Component Tests
```javascript
// tests/TimeLimitRules.test.jsx
describe('TimeLimitRulesList', () => {
  it('renders rules correctly', () => {
    // Test rule display
  });
  
  it('handles rule deletion', () => {
    // Test delete confirmation
    // Test API call on delete
  });
});

describe('RuleFormModal', () => {
  it('validates form inputs', () => {
    // Test time validation
    // Test days selection
  });
  
  it('submits valid rule', () => {
    // Test form submission
    // Test API call
  });
});
```

### 5.2 Integration Tests

#### 5.2.1 End-to-End Flow
1. User logs in to dashboard
2. User navigates to Time Limit Rules page
3. User creates a new time limit rule
4. Rule syncs to server
5. Rule appears in UI after refresh
6. User edits the rule
7. User deletes the rule
8. Rule is removed from server and UI

### 5.3 Edge Cases

- Overlapping time limits for same user/category
- Time limits spanning midnight
- Empty days selection (all days)
- Maximum limit minutes (24 hours = 1440 minutes)
- Concurrent rule modifications
- Network failures during sync

---

## 6. Documentation

### 6.1 Technical Documentation

#### 6.1.1 API Documentation Update
Update `timelimit-ui/docs/ServerAPI.md` with:
- New endpoints documentation
- Request/response schemas
- Error codes
- Rate limiting information

#### 6.1.2 Code Documentation
- Docstrings for all new functions
- Type hints for TypeScript components
- Inline comments for complex logic

### 6.2 User Documentation

#### 6.2.1 User Guide
Create `docs/time-limit-rules-user-guide.md`:
- How to create time limit rules
- Understanding rule types
- Best practices for setting limits
- Troubleshooting common issues

#### 6.2.2 FAQ Section
- "Why can't I see time limit rules?"
- "Why is my rule not syncing?"
- "How do I edit an existing rule?"

---

## Dependencies

### Critical Path
1. API Investigation → Backend Integration
2. UI/UX Design → Frontend Implementation
3. Backend Integration → Testing
4. Testing → Documentation

### Parallel Tasks
- Documentation can run in parallel with implementation

---

## Risk Mitigation

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Sync protocol changes | Low | High | Monitor server API version, maintain compatibility |
| Time zone handling issues | Medium | Medium | Use UTC internally, convert for display |
| Overlapping rules conflict | Medium | Medium | Implement conflict detection UI |
| Performance with many rules | Low | Medium | Implement pagination, lazy loading |
| Mobile responsiveness | Medium | Low | Test on multiple screen sizes |

---

## Acceptance Criteria

1. ✅ Users can view all time limit rules
2. ✅ Users can create new time limit rules
3. ✅ Users can edit existing rules
4. ✅ Users can delete rules
5. ✅ Rules sync correctly with server
6. ✅ UI is responsive and accessible
7. ✅ All tests pass (unit, integration, e2e)
8. ✅ Documentation is complete

---

## Implementation Notes

### Key Files to Modify

1. **Backend (Python)**
   - `timelimit-ui/rootfs/usr/bin/dashboardV2/app.py` - Add new API routes
   - `timelimit-ui/rootfs/usr/bin/dashboardV2/auth_client.py` - Add sync methods
   - `timelimit-ui/rootfs/usr/bin/dashboardV2/database.py` - Add time_limit_rules table
   - `timelimit-ui/rootfs/usr/bin/dashboardV2/utils/audit_log.py` - Add logging functions

2. **Frontend (JavaScript/HTML)**
   - `timelimit-ui/rootfs/usr/bin/dashboardV2/static/js/dashboardV2.js` - Add UI logic
   - `timelimit-ui/rootfs/usr/bin/dashboardV2/templates/dashboardV2.html` - Add UI markup

3. **Documentation**
   - `timelimit-ui/docs/ServerAPI.md` - Update API documentation

### Sync Protocol Integration

The implementation must use the existing sync protocol infrastructure:
- Use `push_actions()` from `auth_client.py`
- Generate HMAC-SHA256 signatures for each action
- Use proper sequence numbers from `get_next_sequence_number()`
- Handle gzip compression automatically

### Database Migration

The `time_limit_rules` table should be added in the `init_db()` method and also handled in `_run_migrations()` for existing databases.

---

## Verification Requirements

During implementation, the following must be verified:

### Backend Verification
- [ ] API endpoints return correct JSON structure
- [ ] Database schema matches specification
- [ ] Sync protocol actions are correctly formatted
- [ ] HMAC signatures are valid
- [ ] Sequence numbers are properly incremented
- [ ] All validation logic works correctly

### Frontend Verification
- [ ] UI components render correctly
- [ ] Form validation works as expected
- [ ] API calls are made with correct parameters
- [ ] Error handling displays user-friendly messages
- [ ] Accessibility requirements are met

### Integration Verification
- [ ] Rules sync to server successfully
- [ ] Rules appear in UI after sync
- [ ] Edit operations update correctly
- [ ] Delete operations remove from server and UI
- [ ] Edge cases are handled properly

### Testing Verification
- [ ] All unit tests pass
- [ ] All integration tests pass
- [ ] Edge cases are covered by tests
- [ ] Test coverage meets project standards

---

## 7. Sequential Implementation Steps

This section provides step-by-step instructions for AI agent implementation. Each step is self-contained and produces a verifiable result.

### Step 1: Add Database Table for Time Limit Rules

**File**: `timelimit-ui/rootfs/usr/bin/dashboardV2/database.py`

**Action**: Add the `time_limit_rules` table to the database schema.

**Verification**:
```bash
cd timelimit-ui/rootfs/usr/bin/dashboardV2
python -c "from database import Database; db = Database(); db.init_db(); print('Table created successfully')"
```

**Expected Result**: No errors, table exists in database.

---

### Step 2: Add Database Helper Functions

**File**: `timelimit-ui/rootfs/usr/bin/dashboardV2/database.py`

**Action**: Add the following functions after the existing table operations:
- `save_time_limit_rule()` - Save a single rule
- `get_time_limit_rules_by_device_auth_token()` - Get all rules for a device
- `get_time_limit_rule_by_id()` - Get a single rule by ID
- `update_time_limit_rule()` - Update an existing rule
- `delete_time_limit_rule()` - Delete a rule

**Verification**:
```bash
cd timelimit-ui/rootfs/usr/bin/dashboardV2
python -c "from database import save_time_limit_rule, get_time_limit_rules_by_device_auth_token; print('Functions imported successfully')"
```

**Expected Result**: All functions can be imported without errors.

---

### Step 3: Add Audit Logging Functions

**File**: `timelimit-ui/rootfs/usr/bin/dashboardV2/utils/audit_log.py`

**Action**: Add the following audit logging functions:
- `log_time_limit_rule_created()` - Log rule creation
- `log_time_limit_rule_updated()` - Log rule update
- `log_time_limit_rule_deleted()` - Log rule deletion

**Verification**:
```bash
cd timelimit-ui/rootfs/usr/bin/dashboardV2
python -c "from utils.audit_log import log_time_limit_rule_created; print('Function imported successfully')"
```

**Expected Result**: Function can be imported without errors.

---

### Step 4: Add Sync Client Methods

**File**: `timelimit-ui/rootfs/usr/bin/dashboardV2/auth_client.py`

**Action**: Add the following methods to the `AuthClient` class:
- `add_time_limit_rule()` - Create rule via sync protocol
- `remove_time_limit_rule()` - Delete rule via sync protocol

**Verification**:
```bash
cd timelimit-ui/rootfs/usr/bin/dashboardV2
python -c "from auth_client import AuthClient; c = AuthClient(); print('Methods exist:', hasattr(c, 'add_time_limit_rule'))"
```

**Expected Result**: Methods exist on AuthClient instance.

---

### Step 5: Add API Route for GET Time Limit Rules

**File**: `timelimit-ui/rootfs/usr/bin/dashboardV2/app.py`

**Action**: Add route `GET /api/dashboard/time-limit-rules` that:
- Validates device_auth_token from session
- Retrieves all rules from database
- Returns JSON response with rules array

**Verification**:
```bash
cd timelimit-ui/rootfs/usr/bin/dashboardV2
python -c "from app import app; print('Route exists:', '/api/dashboard/time-limit-rules' in [r.rule for r in app.url_map.iter_rules()])"
```

**Expected Result**: Route is registered in Flask app.

---

### Step 6: Add API Route for POST Time Limit Rules

**File**: `timelimit-ui/rootfs/usr/bin/dashboardV2/app.py`

**Action**: Add route `POST /api/dashboard/time-limit-rules` that:
- Validates request body
- Validates time format, days bitmask, limit minutes
- Creates rule in database
- Pushes action to server via sync protocol
- Returns rule ID

**Verification**:
```bash
cd timelimit-ui/rootfs/usr/bin/dashboardV2
python -c "from app import app; print('Route exists:', '/api/dashboard/time-limit-rules' in [r.rule for r in app.url_map.iter_rules()])"
```

**Expected Result**: Route is registered in Flask app.

---

### Step 7: Add API Route for PUT Time Limit Rules

**File**: `timelimit-ui/rootfs/usr/bin/dashboardV2/app.py`

**Action**: Add route `PUT /api/dashboard/time-limit-rules/<ruleId>` that:
- Validates rule exists
- Updates rule in database
- Pushes update action to server
- Returns success status

**Verification**:
```bash
cd timelimit-ui/rootfs/usr/bin/dashboardV2
python -c "from app import app; rules = [r.rule for r in app.url_map.iter_rules()]; print('Route exists:', any('/api/dashboard/time-limit-rules/' in r for r in rules))"
```

**Expected Result**: Route is registered in Flask app.

---

### Step 8: Add API Route for DELETE Time Limit Rules

**File**: `timelimit-ui/rootfs/usr/bin/dashboardV2/app.py`

**Action**: Add route `DELETE /api/dashboard/time-limit-rules/<ruleId>` that:
- Validates rule exists
- Deletes rule from database
- Pushes remove action to server
- Returns success status

**Verification**:
```bash
cd timelimit-ui/rootfs/usr/bin/dashboardV2
python -c "from app import app; rules = [r.rule for r in app.url_map.iter_rules()]; print('Route exists:', any('/api/dashboard/time-limit-rules/' in r for r in rules))"
```

**Expected Result**: Route is registered in Flask app.

---

### Step 9: Add Frontend API Service

**File**: `timelimit-ui/rootfs/usr/bin/dashboardV2/static/js/dashboardV2.js`

**Action**: Add `timeLimitRulesApi` object with methods:
- `getRules()` - GET request to fetch rules
- `addRule()` - POST request to create rule
- `updateRule()` - PUT request to update rule
- `deleteRule()` - DELETE request to delete rule

**Verification**:
```bash
cd timelimit-ui/rootfs/usr/bin/dashboardV2
grep -n "timeLimitRulesApi" static/js/dashboardV2.js
```

**Expected Result**: `timeLimitRulesApi` object is defined in JavaScript file.

---

### Step 10: Add Time Limit Rules UI Section

**File**: `timelimit-ui/rootfs/usr/bin/dashboardV2/templates/dashboardV2.html`

**Action**: Add HTML section for Time Limit Rules after Connected Devices section:
- Header with "Time Limit Rules" title
- Refresh button
- Container for rules list
- Modal for add/edit rule form

**Verification**:
```bash
cd timelimit-ui/rootfs/usr/bin/dashboardV2
grep -n "Time Limit Rules" templates/dashboardV2.html
```

**Expected Result**: "Time Limit Rules" text appears in HTML template.

---

### Step 11: Add Time Limit Rules List Rendering

**File**: `timelimit-ui/rootfs/usr/bin/dashboardV2/static/js/dashboardV2.js`

**Action**: Add `renderTimeLimitRulesTable()` function that:
- Takes rules array as input
- Renders HTML table with rules
- Includes edit/delete buttons for each rule

**Verification**:
```bash
cd timelimit-ui/rootfs/usr/bin/dashboardV2
grep -n "renderTimeLimitRulesTable" static/js/dashboardV2.js
```

**Expected Result**: Function is defined in JavaScript file.

---

### Step 12: Add Rule Form Modal Logic

**File**: `timelimit-ui/rootfs/usr/bin/dashboardV2/static/js/dashboardV2.js`

**Action**: Add functions for rule form modal:
- `showRuleForm()` - Display modal for adding/editing
- `hideRuleForm()` - Hide modal
- `submitRuleForm()` - Handle form submission

**Verification**:
```bash
cd timelimit-ui/rootfs/usr/bin/dashboardV2
grep -n "showRuleForm\|hideRuleForm\|submitRuleForm" static/js/dashboardV2.js
```

**Expected Result**: All three functions are defined.

---

### Step 13: Add Time Limit Rules Page Integration

**File**: `timelimit-ui/rootfs/usr/bin/dashboardV2/static/js/dashboardV2.js`

**Action**: Add `refreshTimeLimitRules()` function that:
- Fetches rules from API
- Renders rules table
- Handles errors gracefully

**Verification**:
```bash
cd timelimit-ui/rootfs/usr/bin/dashboardV2
grep -n "refreshTimeLimitRules" static/js/dashboardV2.js
```

**Expected Result**: Function is defined in JavaScript file.

---

### Step 14: Add Unit Tests for Database Functions

**File**: `timelimit-ui/rootfs/usr/bin/dashboardV2/tests/test_database.py`

**Action**: Add tests for:
- `save_time_limit_rule()`
- `get_time_limit_rules_by_device_auth_token()`
- `get_time_limit_rule_by_id()`
- `update_time_limit_rule()`
- `delete_time_limit_rule()`

**Verification**:
```bash
cd timelimit-ui/rootfs/usr/bin/dashboardV2
python -m pytest tests/test_database.py -v -k "time_limit" --collect-only
```

**Expected Result**: Tests are discovered by pytest.

---

### Step 15: Add Unit Tests for API Routes

**File**: `timelimit-ui/rootfs/usr/bin/dashboardV2/tests/test_dashboard_api.py`

**Action**: Add tests for:
- GET /api/dashboard/time-limit-rules
- POST /api/dashboard/time-limit-rules
- PUT /api/dashboard/time-limit-rules/{ruleId}
- DELETE /api/dashboard/time-limit-rules/{ruleId}

**Verification**:
```bash
cd timelimit-ui/rootfs/usr/bin/dashboardV2
python -m pytest tests/test_dashboard_api.py -v -k "time_limit" --collect-only
```

**Expected Result**: Tests are discovered by pytest.

---

### Step 16: Add Unit Tests for Auth Client Methods

**File**: `timelimit-ui/rootfs/usr/bin/dashboardV2/tests/test_auth_client.py`

**Action**: Add tests for:
- `add_time_limit_rule()`
- `remove_time_limit_rule()`

**Verification**:
```bash
cd timelimit-ui/rootfs/usr/bin/dashboardV2
python -m pytest tests/test_auth_client.py -v -k "time_limit" --collect-only
```

**Expected Result**: Tests are discovered by pytest.

---

### Step 17: Run All Tests

**Action**: Execute the full test suite to verify all changes.

**Verification**:
```bash
cd timelimit-ui/rootfs/usr/bin/dashboardV2
python -m pytest tests/ -v --timeout=30
```

**Expected Result**: All tests pass (exit code 0).

---

### Step 18: Update API Documentation

**File**: `timelimit-ui/docs/ServerAPI.md`

**Action**: Add documentation for:
- GET /api/dashboard/time-limit-rules
- POST /api/dashboard/time-limit-rules
- PUT /api/dashboard/time-limit-rules/{ruleId}
- DELETE /api/dashboard/time-limit-rules/{ruleId}

**Verification**:
```bash
cd timelimit-ui
grep -n "time-limit-rules" docs/ServerAPI.md
```

**Expected Result**: Documentation for all endpoints is present.

---

### Step 19: Create User Guide

**File**: `timelimit-ui/docs/time-limit-rules-user-guide.md`

**Action**: Create user guide with:
- How to create time limit rules
- Understanding rule types
- Best practices for setting limits
- Troubleshooting common issues

**Verification**:
```bash
cd timelimit-ui
ls -la docs/time-limit-rules-user-guide.md
```

**Expected Result**: File exists and is not empty.

---

### Step 20: Final Integration Test

**Action**: Perform end-to-end test by:
1. Starting the dashboard
2. Logging in
3. Navigating to Time Limit Rules page
4. Creating a rule
5. Verifying rule appears in list
6. Editing the rule
7. Deleting the rule

**Verification**:
Manual test or automated E2E test script.

**Expected Result**: All operations complete successfully without errors.

---

## Sequential Implementation Flow

```
Step 1  → Step 2  → Step 3  → Step 4  → Step 5  → Step 6  → Step 7  → Step 8
   ↓         ↓         ↓         ↓         ↓         ↓         ↓         ↓
Step 9  → Step 10 → Step 11 → Step 12 → Step 13 → Step 14 → Step 15 → Step 16
   ↓         ↓         ↓         ↓         ↓         ↓         ↓         ↓
Step 17 → Step 18 → Step 19 → Step 20
```

Each step produces a verifiable result before proceeding to the next.

---

This plan provides a comprehensive roadmap for implementing the time limit rules feature. Each phase includes specific deliverables, verification requirements, and ownership assignments to enable smooth team coordination under an orchestrator role.