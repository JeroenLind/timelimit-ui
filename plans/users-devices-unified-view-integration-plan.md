# Users & Devices Unified View Integration Plan

## Overview
This plan outlines the step-by-step process to integrate the "USERS & DEVICES (unified view)" from `plans/dashboard-redesign-mockup.md` into Dashboard V2. The unified view replaces separate tables with user cards that display associated rules and devices in a single organized layout.

## Current State Analysis

### What Exists
- Separate tables for Users, Devices, and Time Limit Rules
- API endpoints: `/api/dashboard/users`, `/api/dashboard/devices`, `/api/dashboard/time-limit-rules`, `/api/dashboard/categories`
- CSS styles for user cards, collapsible sections, stat badges
- Family Overview Card already implemented
- Connected Devices table already implemented

### What's Missing
- Unified user card view with associated rules and devices
- Collapsible sections within user cards
- User type badges (Parent/Child)
- Integration of rules within user cards instead of standalone table

## Implementation Steps

### Phase 1: UI Widget Design & Implementation

#### Task 1.1: Create User Card HTML Structure
- **File**: `timelimit-ui/rootfs/usr/bin/dashboardV2/templates/dashboardV2.html`
- **Action**: Add user card template with:
  - User info section (name, email, time zone, user type badge)
  - Current device indicator
  - Collapsible "Associated Rules" section
  - Collapsible "Associated Devices" section
- **Status**: Pending

#### Task 1.2: Add CSS Styles for User Cards
- **File**: `timelimit-ui/rootfs/usr/bin/dashboardV2/static/css/dashboardV2.css`
- **Action**: Add/verify styles for:
  - `.user-card` - Card container
  - `.user-card-header` - Header with name and type badge
  - `.user-type-badge` - Parent (purple) / Child (blue) badges
  - `.collapsible-section` - Expandable/collapsible sections
  - `.rule-item` - Individual rule display
  - `.device-item` - Individual device display
  - `.current-device-badge` - Green checkmark for current device
- **Status**: Pending

#### Task 1.3: Implement Collapsible Section JavaScript
- **File**: `timelimit-ui/rootfs/usr/bin/dashboardV2/static/js/dashboardV2.js`
- **Action**: Add `toggleCollapsible()` function to handle expand/collapse
- **Status**: Pending

### Phase 2: Backend Logic Implementation (Python)

#### Task 2.1: Create Unified Data API Endpoint
- **File**: `timelimit-ui/rootfs/usr/bin/dashboardV2/app.py`
- **Action**: Add `/api/dashboard/unified-view` endpoint that:
  - Fetches users, devices, and rules
  - Joins data by user_id
  - Returns unified structure for frontend rendering
- **Status**: Pending

#### Task 2.2: Add Data Joining Logic
- **File**: `timelimit-ui/rootfs/usr/bin/dashboardV2/database.py`
- **Action**: Add helper functions to join users, devices, and rules data
- **Status**: Pending

### Phase 3: Frontend Integration

#### Task 3.1: Implement renderUnifiedView Function
- **File**: `timelimit-ui/rootfs/usr/bin/dashboardV2/static/js/dashboardV2.js`
- **Action**: Add `renderUnifiedView()` function that:
  - Fetches unified data from API
  - Renders user cards with associated rules and devices
  - Handles empty states
- **Status**: Pending

#### Task 3.2: Replace Users Table with Unified View
- **File**: `timelimit-ui/rootfs/usr/bin/dashboardV2/templates/dashboardV2.html`
- **Action**: Replace `#users-table` section with `#unified-view-container`
- **Status**: Pending

#### Task 3.3: Update Data Loading Logic
- **File**: `timelimit-ui/rootfs/usr/bin/dashboardV2/static/js/dashboardV2.js`
- **Action**: Modify `loadUsers()` to call `renderUnifiedView()` instead
- **Status**: Pending

### Phase 4: Testing & Validation

#### Task 4.1: Create Unit Tests
- **File**: `timelimit-ui/rootfs/usr/bin/dashboardV2/tests/test_unified_view.py`
- **Action**: Create tests for:
  - API endpoint response structure
  - User card rendering
  - Collapsible section functionality
  - Role-based visibility
- **Status**: Pending

#### Task 4.2: Run Existing Test Suite
- **Action**: Ensure no regressions in existing tests
- **Status**: Pending

## Technical Details

### Data Structure for Unified View

```javascript
{
  status: 'ok',
  users: [
    {
      id: 'user_123',
      name: 'Alice',
      type: 'parent',  // or 'child'
      mail: 'alice@example.com',
      time_zone: 'Europe/Amsterdam',
      current_device: 'Living Room Tablet',
      rules: [
        {
          id: 'rule_456',
          category: 'Games',
          limit_minutes: 120,
          days: 31,  // bitmask: Mon-Fri
          start_time: '16:00',
          end_time: '21:00'
        }
      ],
      devices: [
        {
          id: 'device_789',
          name: 'Living Room Tablet',
          platform: 'Android',
          app_version: '12.0',
          is_current: true
        }
      ]
    }
  ]
}
```

### API Endpoint Design

**GET /api/dashboard/unified-view**
- Returns: `{ status: 'ok', users: [...] }`
- Authentication: Required (device_auth_token in session)

### CSS Classes to Add/Verify

```css
.user-card { /* Card container */ }
.user-card-header { /* Header with name and badge */ }
.user-type-badge { /* Parent/Child badge */ }
.user-type-badge.parent { /* Purple for parent */ }
.user-type-badge.child { /* Blue for child */ }
.collapsible-section { /* Section container */ }
.collapsible-header { /* Header with toggle */ }
.collapsible-content { /* Expandable content */ }
.rule-item { /* Individual rule display */ }
.device-item { /* Individual device display */ }
.current-device-badge { /* Green checkmark */ }
```

## Rollback Plan
If issues arise, the original table-based implementation can be restored by:
1. Reverting HTML changes
2. Removing new CSS classes
3. Removing new JavaScript functions
4. Removing new API endpoint

## Success Criteria
1. Users can view all family members in a unified card view
2. Each user card shows associated rules and devices
3. Rules and devices sections are collapsible
4. User type badges correctly identify parent vs child
5. Current device is highlighted
6. All existing tests pass
7. No visual regressions in other dashboard sections