# Dashboard V2 Current Implementation Analysis

**Analysis Date:** 2026-09-15  
**Purpose:** Document current implementation for dashboard redesign from dark theme to light theme with hamburger menu navigation

---

## 1. Current HTML Structure and Components

### 1.1 File Location
- **Template:** `timelimit-ui/rootfs/usr/bin/dashboardV2/templates/dashboardV2.html`
- **Base Template:** Extends `base.html`

### 1.2 Current Page Structure

```
┌─────────────────────────────────────────────────────────────────────────┐
│  Server Status Section (dark theme)                                    │
│  ┌───────────────────────────────────────────────────────────────────┐  │
│  │  Status Indicator (pulsing animation)                           │  │
│  │  Server Info (inline styling)                                     │  │
│  │  Error Message Container                                          │  │
│  └───────────────────────────────────────────────────────────────────┘  │
├─────────────────────────────────────────────────────────────────────────┤
│  Login Status Banner (dark theme)                                      │
├─────────────────────────────────────────────────────────────────────────┤
│  Dashboard Content Section 1: Dashboard Content                        │
│  ┌───────────────────────────────────────────────────────────────────┐  │
│  │  Version Badge (v1.0.0)                                           │  │
│  │  Welcome Message                                                  │  │
│  │  Refresh Button                                                   │  │
│  │  Last Update Timestamp                                            │  │
│  └───────────────────────────────────────────────────────────────────┘  │
├─────────────────────────────────────────────────────────────────────────┤
│  Dashboard Content Section 2: Session Information                      │
│  ┌───────────────────────────────────────────────────────────────────┐  │
│  │  Session Status Overview (inline flex layout)                   │  │
│  │  • Server Status Indicator                                        │  │
│  │  • Auth Status Indicator                                          │  │
│  │  • Device Token Status Indicator                                  │  │
│  │  Detailed Session Fields (inline server-info divs)                │  │
│  │  • Server URL                                                     │  │
│  │  • Device Auth Token                                              │  │
│  │  • Own Device ID                                                  │  │
│  │  • Mail Auth Token                                                │  │
│  │  • Login Status                                                   │  │
│  │  • Dashboard App Version                                          │  │
│  │  • Parent Password Hash                                           │  │
│  │  • Signing Key                                                    │  │
│  │  • Client Level                                                   │  │
│  │  Action Links (inline links, not hamburger menu)                  │  │
│  │  • Create New Family (link)                                       │  │
│  │  • Login to Existing Family (link)                                │  │
│  │  • Recover Parent Password (link)                                 │  │
│  │  • Sign Out (button)                                              │  │
│  │  • Clear All Data (button)                                        │  │
│  │  • Set Password Hash for Device Removal (link)                    │  │
│  │  • View Database Contents (link)                                  │  │
│  │  Auth Token Backup Section                                        │  │
│  │  • Create Backup (button)                                         │  │
│  │  • Restore Backup (button)                                        │  │
│  │  • Clear Backup (button)                                          │  │
│  └───────────────────────────────────────────────────────────────────┘  │
├─────────────────────────────────────────────────────────────────────────┤
│  Dashboard Content Section 3: Family Users                             │
│  ┌───────────────────────────────────────────────────────────────────┐  │
│  │  Users Table (6 columns)                                          │  │
│  │  • Name, Type, Email, Current Device, Time Zone, Limits Disabled  │  │
│  │  Refresh Users Button                                             │  │
│  │  Add User Button                                                  │  │
│  └───────────────────────────────────────────────────────────────────┘  │
├─────────────────────────────────────────────────────────────────────────┤
│  Dashboard Content Section 4: Family Devices                           │
│  ┌───────────────────────────────────────────────────────────────────┐  │
│  │  Devices Table (9 columns)                                        │  │
│  │  • Name, Model, Current User, Protection Level, App Version,      │  │
│  │    Platform, Signing Key, Added At, Actions                       │  │
│  │  Refresh Devices Button                                           │  │
│  └───────────────────────────────────────────────────────────────────┘  │
├─────────────────────────────────────────────────────────────────────────┤
│  Dashboard Content Section 5: Historical Data                          │
│  ┌───────────────────────────────────────────────────────────────────┐  │
│  │  Historical Table (4 columns)                                     │  │
│  │  • Timestamp, Status, Server Time, Error                            │  │
│  │  Refresh History Button                                           │  │
│  └───────────────────────────────────────────────────────────────────┘  │
├─────────────────────────────────────────────────────────────────────────┤
│  Dashboard Content Section 6: Connected Devices                        │
│  ┌───────────────────────────────────────────────────────────────────┐  │
│  │  Connected Devices Table (2 columns)                              │  │
│  │  • Name, Last Seen                                                │  │
│  │  Refresh Connected Devices Button                                 │  │
│  └───────────────────────────────────────────────────────────────────┘  │
├─────────────────────────────────────────────────────────────────────────┤
│  Dashboard Content Section 7: Time Limit Rules                         │
│  ┌───────────────────────────────────────────────────────────────────┐  │
│  │  Time Limit Rules Table (standalone, 6 columns)                   │  │
│  │  • User, Category, Days, Time, Duration, Actions                  │  │
│  │  Refresh Rules Button                                             │  │
│  │  Add Rule Button                                                  │  │
│  └───────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────┘
```

### 1.3 Modal Components

#### Rule Form Modal (`#rule-form-modal`)
- **Purpose:** Add/Edit time limit rules
- **Fields:**
  - User selector (dropdown)
  - Category selector (dropdown)
  - Duration (minutes, number input)
  - Days (7 checkboxes: Mon-Sun)
  - Time range (2 time inputs with "to" separator)
- **Actions:** Cancel, Save Rule

#### Add User Modal (`#add-user-modal`)
- **Purpose:** Add new user to family
- **Fields:**
  - User Name (required, text input)
  - Device Name (optional, text input)
  - Device Model (optional, text input)
- **Actions:** Cancel, Add

### 1.4 Alert Container
- **Element:** `.alert-container` (fixed position, top-right)
- **Types:** success, error, warning
- **Auto-dismiss:** 5 seconds
- **Close button:** × button in top-right corner

---

## 2. Current CSS Styling and Color Scheme

### 2.1 File Location
- **Main Stylesheet:** `timelimit-ui/rootfs/usr/bin/dashboardV2/static/css/dashboardV2.css`
- **Inline Styles:** Embedded in HTML template within `{% block extra_css %}`

### 2.2 Current Color Scheme (Dark Theme)

| Element | Current Color | Usage |
|---------|---------------|-------|
| Background | `linear-gradient(135deg, #1a1a2e 0%, #16213e 100%)` | Page background |
| Card Background | `rgba(255, 255, 255, 0.05)` | Content cards |
| Text Primary | `#fff` | Main text |
| Text Secondary | `#aaa` | Secondary text, labels |
| Text Muted | `#666` | Placeholder, muted text |
| Success | `#4caf50` | Success indicators |
| Warning | `#ff9800` | Warning indicators |
| Error | `#f44336` | Error indicators |
| Primary Accent | `#667eea` | Links, buttons |
| Delete Button | `#f44336` | Delete actions |

### 2.3 Status Indicator Colors (Current)

| Status | Background Color | Box Shadow |
|--------|------------------|------------|
| Success | `#4caf50` | `0 0 10px rgba(76, 175, 80, 0.5)` |
| Error | `#f44336` | `0 0 10px rgba(244, 67, 54, 0.5)` |
| Warning | `#ff9800` | `0 0 10px rgba(255, 152, 0, 0.5)` |

### 2.4 Typography (Current)

| Element | Font Size | Weight | Color |
|---------|-----------|--------|-------|
| Page Title | 24px | 600 | #fff |
| Section Heading | 18px | 600 | #fff |
| Card Title | 16px | 600 | #fff |
| Body Text | 14px | 400 | #aaa |
| Secondary Text | 12px | 500 | #aaa |
| Monospace (tokens) | 12px | 400 | #888 |

### 2.5 Current Navigation Pattern

**Inline Links (Current Implementation):**
- Session action links are displayed inline within the Session Information section
- Links are styled as buttons with inline CSS
- Visibility controlled via JavaScript `style.display` manipulation
- No hamburger menu exists

**Link Types:**
- `Create New Family` - `/create-family`
- `Login to Existing Family` - `/login-as-parent`
- `Recover Parent Password` - `/recover-parent-password`
- `Sign Out` - JavaScript function `clearSession()`
- `Clear All Data` - JavaScript function `confirmClearAllData()`
- `Set Password Hash for Device Removal` - `/set-parent-password`
- `View Database Contents` - `/debug/database`

---

## 3. Current JavaScript Functionality

### 3.1 File Location
- **Main Script:** `timelimit-ui/rootfs/usr/bin/dashboardV2/static/js/dashboardV2.js`

### 3.2 Core Architecture

**IIFE Pattern:** JavaScript is wrapped in an Immediately Invoked Function Expression
```javascript
(function() {
    'use strict';
    // ... code ...
})();
```

**Global Exposure:** Functions exposed on both `window` object and `window.dashboardV2` object

### 3.3 API Service Layer

#### `timeLimitRulesApi` Object
- `getRules()` - GET `/api/dashboard/time-limit-rules`
- `addRule(ruleData)` - POST `/api/dashboard/time-limit-rules`
- `updateRule(ruleId, ruleData)` - PUT `/api/dashboard/time-limit-rules/{ruleId}`
- `deleteRule(ruleId)` - DELETE `/api/dashboard/time-limit-rules/{ruleId}`

### 3.4 Authentication & Session Management

| Function | Purpose |
|----------|---------|
| `checkAuthentication()` | Check if user is authenticated via `/api/session/status` |
| `clearSession()` | Clear session via `/api/session/clear` |
| `clearAllData()` | Clear all local data via `/api/clear-all` |
| `confirmClearAllData()` | Show confirmation dialog before clearing |

### 3.5 Data Loading Functions

| Function | Target Element | Authentication Check |
|----------|---------------|---------------------|
| `loadUsers()` | `#users-body` | Yes |
| `loadDevices()` | `#devices-body` | Yes |
| `loadConnectedDevices()` | `#connected-devices-body` | Yes |
| `loadHistoricalData()` | `#history-body` | No |
| `refreshTimeLimitRules()` | `#time-limit-rules-container` | Yes |

### 3.6 Rendering Functions

| Function | Purpose |
|----------|---------|
| `renderUsersTable(users)` | Render users table HTML |
| `renderDevicesTable(devices, ownDeviceId, hasParentPasswordHash)` | Render devices table with action buttons |
| `renderConnectedDevicesTable(devices)` | Render connected devices table |
| `renderTimeLimitRulesTable(rules, users, categories)` | Render time limit rules table |
| `updateSessionOverview(data)` | Update session field displays |
| `updateLoginStatusBanner(data)` | Update login status banner |

### 3.7 Utility Functions

| Function | Purpose |
|----------|---------|
| `escapeHtml(str)` | XSS prevention - escape HTML entities |
| `getProtectionLevelLabel(level)` | Map protection level int to label |
| `formatDays(days)` | Convert days bitmask to day names |
| `formatRuleDescription(rule)` | Format rule for display |
| `getUserNameById(userId, users)` | Lookup user name by ID |
| `getCategoryNameById(categoryId, categories)` | Lookup category name by ID |

### 3.8 Modal Functions

| Function | Purpose |
|----------|---------|
| `showRuleForm(rule)` | Show rule form modal (add/edit) |
| `hideRuleForm()` | Hide rule form modal |
| `submitRuleForm()` | Submit rule form |
| `confirmDeleteRule(ruleId, userName)` | Confirm and delete rule |
| `showAddUserModal()` | Show add user modal |
| `hideAddUserModal()` | Hide add user modal |
| `submitAddUserForm()` | Submit add user form |
| `validateAddUserForm()` | Validate add user form |
| `resetAddUserForm()` | Reset add user form |

### 3.9 Alert/Notification Functions

| Function | Purpose |
|----------|---------|
| `showAlert(message, type)` | Show alert notification |
| `createBackup()` | Create auth token backup |
| `restoreBackup()` | Restore auth token backup |
| `clearBackup()` | Clear auth token backup |

### 3.10 Device Management Functions

| Function | Purpose |
|----------|---------|
| `confirmRemoveDevice(deviceId, deviceName)` | Confirm and remove device |
| `removeDevice(deviceId)` | API call to remove device |

### 3.11 Sync Functions

| Function | Purpose |
|----------|---------|
| `triggerSync()` | Trigger manual sync via `/api/sync/pull` |
| `refreshServerStatus()` | Refresh server status |
| `fetchSessionStatus()` | Fetch session status from `/api/session/status` |
| `connectSSE()` | Connect to Server-Sent Events for real-time updates |

### 3.12 Event Listeners

```javascript
// DOM Ready
document.addEventListener('DOMContentLoaded', async function() {
    checkAuthentication();
    if (isAuthenticated) {
        loadUsers();
        loadDevices();
        loadConnectedDevices();
        refreshTimeLimitRules();
        connectSSE();
    }
});

// Keyboard Events
document.addEventListener('keydown', function(event) {
    if (event.key === 'Escape') {
        hideAddUserModal();
    }
});

// Modal Click Outside
document.getElementById('add-user-modal')?.addEventListener('click', function(event) {
    if (event.target === this) {
        hideAddUserModal();
    }
});
```

---

## 4. Mapping of Changes Needed (Old to New Design)

### 4.1 Color Scheme Migration

| Current (Dark) | New (Light) | CSS Variable |
|----------------|-------------|--------------|
| `#1a1a2e` / `#16213e` (bg gradient) | `#f5f7fa` | `--color-bg` |
| `rgba(255, 255, 255, 0.05)` (card bg) | `#ffffff` | `--color-card` |
| `#fff` (text) | `#212529` | `--color-text-primary` |
| `#aaa` (secondary text) | `#6c757d` | `--color-text-secondary` |
| `#666` (muted text) | `#9aa0a6` | `--color-text-muted` |
| `#4caf50` (success) | `#28a745` | `--color-success` |
| `#ff9800` (warning) | `#ffc107` | `--color-warning` |
| `#f44336` (error) | `#dc3545` | `--color-error` |
| `#667eea` (primary) | `#667eea` | `--color-primary` |

### 4.2 Navigation Pattern Changes

| Current | New |
|---------|-----|
| Inline session action links in Session Information section | Hamburger menu with sidebar navigation |
| No menu toggle button | `.menu-toggle` button in header |
| Links always visible (conditionally hidden via JS) | Menu items conditionally rendered based on role |

### 4.3 Layout Structure Changes

| Current | New |
|---------|-----|
| Single column layout with stacked sections | Fixed header + main content area |
| No sidebar | Hamburger menu sidebar (slides in from right) |
| Inline styles for most elements | CSS classes with CSS variables |
| Tables as standalone sections | Unified Users & Devices view |

---

## 5. Components to Add, Modify, or Remove

### 5.1 Components to REMOVE

| Component | Location | Reason |
|-----------|----------|--------|
| Standalone Time Limit Rules table | Lines 995-1009 in HTML | Rules will be displayed within user cards |
| Inline session action links | Lines 825-869 in HTML | Replaced by hamburger menu navigation |
| `.server-info` in header | Lines 686-688 in HTML | Moved to sidebar "Server Status" section |
| Dark theme background gradient | CSS body style | Replaced by light theme |
| Inline styles | Throughout HTML | Replaced by CSS classes |

### 5.2 Components to MODIFY

| Component | Current Implementation | Required Changes |
|-----------|----------------------|------------------|
| `.dashboard-header` | Dark theme, no menu toggle | Add hamburger button, change to light theme |
| `.dashboard-content` | Dark semi-transparent bg | Change to white bg with shadow |
| `.dashboard-table` | Dark text on dark bg | Light theme: dark text, light borders, white bg |
| `.refresh-btn` | Dark theme colors | Adjust colors for light background |
| `.alert` | Dark theme with white bg | Light theme: dark text, appropriate bg colors |
| `.status-indicator` | Custom colors | Use new status colors (green/orange/red) |
| Tables | 9 columns (devices) | May need restructuring for unified view |

### 5.3 Components to ADD

| Component | CSS Class | Purpose |
|-----------|-----------|---------|
| Hamburger Menu Toggle | `.menu-toggle` | Button in header to open sidebar |
| Sidebar Menu Panel | `.dashboard-sidebar` | Slide-in menu with navigation |
| Sidebar Overlay | `.sidebar-overlay` | Backdrop when sidebar is open |
| Family Overview Card | `.family-overview-card` | Summary card with family stats |
| User Card | `.user-card` | Card displaying user with rules and devices |
| Stat Badge | `.stat-badge` | Small stat display (count + label) |
| User Type Badge | `.user-type-badge` | Badge showing parent/child type |
| Rule Item | `.rule-item` | Individual rule display in user card |
| Device Item | `.device-item` | Individual device display in user card |
| Collapsible Section | `.collapsible-section` | Expandable/collapsible sections |
| Connected Devices Table | `.connected-devices-table` | Table for connected devices |

### 5.4 New JavaScript Functions Required

| Function | Purpose |
|----------|---------|
| `toggleMenu()` | Open/close hamburger menu sidebar |
| `closeMenu()` | Close sidebar (click outside, Escape) |
| `renderFamilyOverview(data)` | Render family overview card |
| `renderUserCards(users, devices, rules, categories)` | Render unified user cards |
| `renderConnectedDevicesTable(devices)` | Render connected devices table |
| `toggleCollapsible(sectionId)` | Expand/collapse sections |
| `checkAdminVisibility()` | Check session and show/hide admin menu items |

---

## 6. Role-Based Visibility Requirements

### 6.1 Role Detection
- **Field:** `has_parent_password_second_hash` from `/api/session/status`
- **True:** Parent/Admin role
- **False:** Standard User role

### 6.2 Menu Item Visibility Matrix

| Menu Item | Parent/Admin | Standard User | Unauthenticated |
|-----------|-------------|---------------|-----------------|
| Overview | ✅ | ✅ | ❌ |
| Users & Devices | ✅ | ✅ | ❌ |
| Time Limit Rules | ✅ | ✅ | ❌ |
| Connected Devices | ✅ | ✅ | ❌ |
| Server Status | ✅ | ✅ | ✅ |
| Sync Now | ✅ | ✅ | ❌ |
| Session Details | ✅ | ✅ | ❌ |
| Sign Out | ✅ | ✅ | ❌ |
| Create New Family | ✅ | ❌ | ❌ |
| View Database Content | ✅ | ❌ | ❌ |
| Set Parent Password | ✅ | ❌ | ❌ |
| Clear All Data | ✅ | ❌ | ❌ |
| Documentation | ✅ | ✅ | ✅ |
| Keyboard Shortcuts | ✅ | ✅ | ✅ |

---

## 7. Responsive Breakpoints (Current vs. New)

### 7.1 Current Breakpoints
- Desktop: 1200px+
- Tablet: 768px - 1199px
- Mobile: 480px - 767px
- Small Mobile: < 480px

### 7.2 Mobile Adaptations Required
- Header: Server info moves below title, hamburger icon larger (28px)
- Family Overview: Stat cards stack vertically (1 column)
- User Cards: Avatar smaller, rules/devices collapsed by default
- Tables: Horizontal scroll container with `overflow-x: auto`
- Menu Sidebar: Full width (90vw), close button larger

---

## 8. Accessibility Requirements

### 8.1 WCAG 2.1 AA Compliance
- **Color Contrast:** All text/background combinations must meet 4.5:1 contrast ratio
- **Keyboard Navigation:** All interactive elements focusable via Tab
- **ARIA Labels:** Hamburger button needs `aria-label="Open menu"`, `aria-expanded`
- **Focus Management:** Focus moves to first menu item when opened
- **Screen Reader Support:** All icons have `aria-hidden="true"` with text alternatives

---

## 9. Summary of Key Changes

### 9.1 Visual Theme
- **From:** Dark theme with gradient background
- **To:** Light theme with white cards and dark text

### 9.2 Navigation
- **From:** Inline links in Session Information section
- **To:** Hamburger menu sidebar with role-based visibility

### 9.3 Layout
- **From:** Single column, stacked sections
- **To:** Fixed header, unified Users & Devices view, user cards with associated rules/devices

### 9.4 Data Organization
- **From:** Separate tables for Users, Devices, Historical Data, Time Limit Rules
- **To:** Unified view with user cards containing associated rules and devices

### 9.5 Components to Remove
1. Standalone Time Limit Rules table
2. Inline session action links
3. Server info in header (moved to sidebar)

### 9.6 Components to Add
1. Hamburger menu toggle button
2. Sidebar navigation panel
3. Family overview card
4. User cards with associated rules and devices
5. Stat badges
6. Collapsible sections

---

## 10. File References

| File | Path |
|------|------|
| HTML Template | `timelimit-ui/rootfs/usr/bin/dashboardV2/templates/dashboardV2.html` |
| CSS Stylesheet | `timelimit-ui/rootfs/usr/bin/dashboardV2/static/css/dashboardV2.css` |
| JavaScript File | `timelimit-ui/rootfs/usr/bin/dashboardV2/static/js/dashboardV2.js` |
| Base Template | `timelimit-ui/rootfs/usr/bin/dashboardV2/templates/base.html` |
| Redesign Spec | `docs/dashboard-redesign-spec-summary.md` |

---

*Document created as part of Step 2: Analyze Current Implementation for dashboard redesign project.*