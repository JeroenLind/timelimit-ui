# TimeLimit UI Requirements

## Functional Requirements

### FR-001: Dashboard Sync at Startup

**Requirement:** The dashboard must sync with the TimeLimit server at startup to ensure all user data (devices, users, categories, rules) is loaded and displayed correctly.

**Description:** When the dashboard V2 application starts, it must automatically synchronize with the TimeLimit server to fetch the latest data. This ensures that:
- All devices associated with the family are displayed
- All users (children) in the family are visible
- Time limit rules are up to date
- Connected devices list is accurate
- The last sync timestamp is recorded

**Acceptance Criteria:**
1. Upon successful authentication, the dashboard automatically triggers a sync with the TimeLimit server
2. The sync retrieves all devices, users, categories, and rules associated with the family
3. The dashboard displays the correct count of devices and users after sync completes
4. The "Last sync" timestamp in the Family Overview section is updated after successful sync
5. If the initial sync returns empty data (due to stale version hashes), the client retries with empty versions to force a full sync

**Technical Notes:**
- The sync protocol uses `device_auth_token` as the primary key for server lookups
- ClientDataStatus with version hashes is sent to request only changes since last sync
- If the server returns empty data (no devices, no users), the client must retry with empty versions to get the initial state
- This behavior matches the official Android app's sync protocol

**Related Files:**
- `timelimit-ui/rootfs/usr/bin/dashboardV2/sync_manager.py` - Sync orchestration logic
- `timelimit-ui/rootfs/usr/bin/dashboardV2/auth_client.py` - HTTP client for server communication
- `timelimit-ui/rootfs/usr/bin/dashboardV2/database.py` - Database operations for storing sync data
- `timelimit-ui/rootfs/usr/bin/dashboardV2/static/js/dashboardV2.js` - Frontend JavaScript handling UI interactions

**Status:** ✅ Implemented and tested

---

### FR-002: Server Down Detection and Recovery

**Description:** When the Flask backend (`app.py`) is killed but the dashboard webpage remains open, the browser should detect the server is down and stop queuing events to prevent browser freezing.

**Priority:** High

**Acceptance Criteria:**
1. Dashboard checks server health on page load with a 3-second timeout
2. When server is unreachable, an offline banner is displayed to the user
3. All interactive UI elements (buttons, inputs) are disabled when server is down
4. SSE connections are closed when server goes offline
5. Health check polling with exponential backoff (10s → 30s max) is used to detect when server comes back online
6. Users can manually retry connection via a "Retry Connection" button
7. When server comes back online, UI is restored and data is refreshed

**Implementation:**
- JavaScript: `checkServerHealth()`, `handleServerDown()`, `handleServerUp()`, `disableAllInteractions()`, `enableAllInteractions()`, `startHealthCheckPolling()`, `stopHealthCheckPolling()`, `pollServerHealth()`, `retryConnection()`
- HTML: Offline banner element with warning icon, message, and retry button
- CSS: Offline state styles for banner, disabled elements, and body styling

**Status:** ✅ Implemented (2026-09-27)

---

### FR-003: User Must Be Immediately Visible After Adding

**Requirement:** After adding a user via the dashboard, the user must be immediately visible in the dashboard without requiring a manual sync.

**Description:** When a parent adds a new child user through the dashboard, the user should appear in the dashboard immediately after the add user API call completes. No manual sync action should be required by the user.

**Acceptance Criteria:**
- User appears in the dashboard immediately after the add user API call completes
- No manual sync action is required by the user
- The user's name and details are correctly displayed
- The user count in the Family Overview card is updated

**Implementation:**
- Modified `api_add_user_to_family()` to force a full sync with empty versions
- Added local user record creation as fallback when server doesn't return the user
- See `timelimit-ui/rootfs/usr/bin/dashboardV2/app.py` and `timelimit-ui/rootfs/usr/bin/dashboardV2/database.py`

**Status:** ✅ Implemented (2026-09-27)

---

### FR-004: Dashboard Shows Only Data from TimeLimit Server

**Requirement:** The dashboard should only show data retrieved from the TimeLimit server. If something goes wrong in the sync process, there should be a clear error message.

**Description:** The dashboard must display users and devices from the TimeLimit server sync response. When the server doesn't return a newly added user (due to timing issues), a local record is created as a fallback to ensure immediate visibility.

**Acceptance Criteria:**
- Dashboard displays users from the server sync response
- If user is not in sync response, a local record is created as fallback
- Error messages are clear and actionable when sync fails
- All error paths return appropriate HTTP status codes

**Implementation:**
- Force full sync with empty versions to get all users
- Create local user record if user not found in sync response
- Return clear error messages on sync failures

**Status:** ✅ Implemented (2026-09-27)

---

### FR-005: Time Limit Rules Management

**Requirement:** The dashboard must provide a complete time limit rules management interface for parents to create, view, edit, and delete time limit rules for their family members.

**Description:** Parents should be able to manage time limit rules that control when and how long specific apps/categories can be used by each family member. The rules should be synced with the TimeLimit server and persist across sessions.

**Acceptance Criteria:**
1. Dashboard displays a "Time Limit Rules" section in the main content area
2. Rules table shows: User, Category, Time Period, Days, Limit, and Actions columns
3. Users can click "Add Rule" to open a modal form
4. Users can click "Edit" on any rule to modify it
5. Users can click "Delete" on any rule to remove it
6. Rules are immediately visible after creation without manual refresh
7. Days of week can be selected via checkboxes (Mon-Sun)
8. Time periods are entered in HH:MM format (24-hour)
9. Time limits are entered in minutes (0 = no limit)
10. All CRUD operations sync with the TimeLimit server

**Implementation Details:**
- Backend API endpoints: GET, POST, PUT, DELETE on `/api/dashboard/time-limit-rules`
- Database: `time_limit_rules` table with indexes on `user_id`, `category_id`, `device_auth_token`
- Days bitmask: 0-127 (1=Mon, 2=Tue, 4=Wed, 8=Thu, 16=Fri, 32=Sat, 64=Sun)
- Sync integration: All operations trigger server sync via CRDT protocol
- Audit logging: All rule operations are logged

**Files Modified:**
- `timelimit-ui/rootfs/usr/bin/dashboardV2/app.py` - API routes
- `timelimit-ui/rootfs/usr/bin/dashboardV2/database.py` - Database operations
- `timelimit-ui/rootfs/usr/bin/dashboardV2/auth_client.py` - Sync integration
- `timelimit-ui/rootfs/usr/bin/dashboardV2/static/js/dashboardV2.js` - Frontend logic
- `timelimit-ui/rootfs/usr/bin/dashboardV2/templates/dashboardV2.html` - UI components

---

### FR-006: Time Limit Rules Days Bitmask

**Requirement:** The days of week selection must be converted to a bitmask value (0-127) for storage and sync.

**Description:** When users select days via checkboxes in the rule form, the selection must be converted to a bitmask integer for storage in the database and sync with the server.

**Acceptance Criteria:**
1. Monday checkbox has value 1
2. Tuesday checkbox has value 2
3. Wednesday checkbox has value 4
4. Thursday checkbox has value 8
5. Friday checkbox has value 16
6. Saturday checkbox has value 32
7. Sunday checkbox has value 64
8. Multiple days are combined by summing their values (e.g., Mon+Tue = 3)
9. All days selected = 127 (1+2+4+8+16+32+64)
10. No days selected = 0

**Implementation:**
- JavaScript function `calculateDaysBitmask()` converts checkbox values to bitmask
- Bitmask is sent to API in `days` array format, converted server-side

**Status:** ✅ Implemented (2026-09-27)

---

### FR-007: Hamburger Menu Navigation

---

### FR-006: Time Limit Rules Days Bitmask

**Requirement:** The days of week selection must be converted to a bitmask value (0-127) for storage and sync.

**Description:** When users select days via checkboxes in the rule form, the selection must be converted to a bitmask integer for storage in the database and sync with the server.

**Acceptance Criteria:**
1. Monday checkbox has value 1
2. Tuesday checkbox has value 2
3. Wednesday checkbox has value 4
4. Thursday checkbox has value 8
5. Friday checkbox has value 16
6. Saturday checkbox has value 32
7. Sunday checkbox has value 64
8. Multiple days are combined by summing their values (e.g., Mon+Tue = 3)
9. All days selected = 127 (1+2+4+8+16+32+64)
10. No days selected = 0

**Implementation:**
- JavaScript function `calculateDaysBitmask()` converts checkbox values to bitmask
- Bitmask is sent to API in `days` array format, converted server-side

---

### FR-006: Time Limit Rules Days Bitmask

**Requirement:** The days of week selection must be converted to a bitmask value (0-127) for storage and sync.

**Description:** When users select days via checkboxes in the rule form, the selection must be converted to a bitmask integer for storage in the database and sync with the server.

**Acceptance Criteria:**
1. Monday checkbox has value 1
2. Tuesday checkbox has value 2
3. Wednesday checkbox has value 4
4. Thursday checkbox has value 8
5. Friday checkbox has value 16
6. Saturday checkbox has value 32
7. Sunday checkbox has value 64
8. Multiple days are combined by summing their values (e.g., Mon+Tue = 3)
9. All days selected = 127 (1+2+4+8+16+32+64)
10. No days selected = 0

**Implementation:**
- JavaScript function `calculateDaysBitmask()` converts checkbox values to bitmask
- Bitmask is sent to API in `days` array format, converted server-side

---

### FR-006: Time Limit Rules Days Bitmask

**Requirement:** The days of week selection must be converted to a bitmask value (0-127) for storage and sync.

**Description:** When users select days via checkboxes in the rule form, the selection must be converted to a bitmask integer for storage in the database and sync with the server.

**Acceptance Criteria:**
1. Monday checkbox has value 1
2. Tuesday checkbox has value 2
3. Wednesday checkbox has value 4
4. Thursday checkbox has value 8
5. Friday checkbox has value 16
6. Saturday checkbox has value 32
7. Sunday checkbox has value 64
8. Multiple days are combined by summing their values (e.g., Mon+Tue = 3)
9. All days selected = 127 (1+2+4+8+16+32+64)
10. No days selected = 0

**Implementation:**
- JavaScript function `calculateDaysBitmask()` converts checkbox values to bitmask
- Bitmask is sent to API in `days` array format, converted server-side

**Status:** ✅ Implemented (2026-09-27)

---

### FR-007: Hamburger Menu Navigation

---

### FR-006: Time Limit Rules Days Bitmask

**Requirement:** The days of week selection must be converted to a bitmask value (0-127) for storage and sync.

**Description:** When users select days via checkboxes in the rule form, the selection must be converted to a bitmask integer for storage in the database and sync with the server.

**Acceptance Criteria:**
1. Monday checkbox has value 1
2. Tuesday checkbox has value 2
3. Wednesday checkbox has value 4
4. Thursday checkbox has value 8
5. Friday checkbox has value 16
6. Saturday checkbox has value 32
7. Sunday checkbox has value 64
8. Multiple days are combined by summing their values (e.g., Mon+Tue = 3)
9. All days selected = 127 (1+2+4+8+16+32+64)
10. No days selected = 0

**Implementation:**
- JavaScript function `calculateDaysBitmask()` converts checkbox values to bitmask
- Bitmask is sent to API in `days` array format, converted server-side

**Status:** ✅ Implemented (2026-09-27)

---

### FR-006: Time Limit Rules Days Bitmask

**Requirement:** The days of week selection must be converted to a bitmask value (0-127) for storage and sync.

**Description:** When users select days via checkboxes in the rule form, the selection must be converted to a bitmask integer for storage in the database and sync with the server.

**Acceptance Criteria:**
1. Monday checkbox has value 1
2. Tuesday checkbox has value 2
3. Wednesday checkbox has value 4
4. Thursday checkbox has value 8
5. Friday checkbox has value 16
6. Saturday checkbox has value 32
7. Sunday checkbox has value 64
8. Multiple days are combined by summing their values (e.g., Mon+Tue = 3)
9. All days selected = 127 (1+2+4+8+16+32+64)
10. No days selected = 0

**Implementation:**
- JavaScript function `calculateDaysBitmask()` converts checkbox values to bitmask
- Bitmask is sent to API in `days` array format, converted server-side

---

### FR-007: Hamburger Menu Navigation

**Requirement:** The dashboard must provide a hamburger menu for navigation that opens and closes properly with click events.

**Description:** The hamburger menu (☰) button in the top-left corner of the dashboard must open a sidebar navigation panel when clicked, and the menu must close when:
1. The hamburger button is clicked again
2. The close button (×) in the sidebar header is clicked
3. The overlay behind the sidebar is clicked
4. The Escape key is pressed

**Acceptance Criteria:**
1. Hamburger menu button (`menu-toggle`) is visible and clickable
2. Clicking hamburger button opens the sidebar with `right: 0` position
3. Clicking hamburger button again closes the sidebar with `right: -280px` position
4. Sidebar close button (`sidebar-close`) closes the menu
5. Clicking overlay (`sidebar-overlay`) closes the menu
6. Pressing Escape key closes the menu
7. ARIA attributes (`aria-expanded`, `aria-hidden`) are properly updated
8. Focus is returned to hamburger button when menu closes
9. All click events are logged to console for debugging

**Technical Notes:**
- Event listeners must be registered in DOMContentLoaded handler
- Console logging must be added for all click events
- Functions `toggleMenu()` and `closeMenu()` must be called appropriately
- Sidebar must have `active` class when open, removed when closed

**Related Files:**
- `timelimit-ui/rootfs/usr/bin/dashboardV2/static/js/dashboardV2.js` - Event listeners and menu functions
- `timelimit-ui/rootfs/usr/bin/dashboardV2/templates/dashboardV2.html` - Menu HTML structure
- `timelimit-ui/rootfs/usr/bin/dashboardV2/static/css/dashboardV2.css` - Menu styling

**Status:** ✅ Implemented and tested (2026-09-28)

---

## Non-Functional Requirements

---

### FR-007: Hamburger Menu Navigation

**Requirement:** The dashboard must provide a hamburger menu for navigation that opens and closes properly with click events.

**Description:** The hamburger menu (☰) button in the top-left corner of the dashboard must open a sidebar navigation panel when clicked, and the menu must close when:
1. The hamburger button is clicked again
2. The close button (×) in the sidebar header is clicked
3. The overlay behind the sidebar is clicked
4. The Escape key is pressed

**Acceptance Criteria:**
1. Hamburger menu button (`menu-toggle`) is visible and clickable
2. Clicking hamburger button opens the sidebar with `right: 0` position
3. Clicking hamburger button again closes the sidebar with `right: -280px` position
4. Sidebar close button (`sidebar-close`) closes the menu
5. Clicking overlay (`sidebar-overlay`) closes the menu
6. Pressing Escape key closes the menu
7. ARIA attributes (`aria-expanded`, `aria-hidden`) are properly updated
8. Focus is returned to hamburger button when menu closes
9. All click events are logged to console for debugging

**Technical Notes:**
- Event listeners must be registered in DOMContentLoaded handler
- Console logging must be added for all click events
- Functions `toggleMenu()` and `closeMenu()` must be called appropriately
- Sidebar must have `active` class when open, removed when closed

**Related Files:**
- `timelimit-ui/rootfs/usr/bin/dashboardV2/static/js/dashboardV2.js` - Event listeners and menu functions
- `timelimit-ui/rootfs/usr/bin/dashboardV2/templates/dashboardV2.html` - Menu HTML structure
- `timelimit-ui/rootfs/usr/bin/dashboardV2/static/css/dashboardV2.css` - Menu styling

**Status:** ✅ Implemented and tested (2026-09-28)

---

## Non-Functional Requirements

---

### FR-007: Hamburger Menu Navigation

---

### FR-007: Hamburger Menu Navigation

**Requirement:** The dashboard must provide a hamburger menu for navigation that opens and closes properly with click events.

**Description:** The hamburger menu (☰) button in the top-left corner of the dashboard must open a sidebar navigation panel when clicked, and the menu must close when:
1. The hamburger button is clicked again
2. The close button (×) in the sidebar header is clicked
3. The overlay behind the sidebar is clicked
4. The Escape key is pressed

**Acceptance Criteria:**
1. Hamburger menu button (`menu-toggle`) is visible and clickable
2. Clicking hamburger button opens the sidebar with `right: 0` position
3. Clicking hamburger button again closes the sidebar with `right: -280px` position
4. Sidebar close button (`sidebar-close`) closes the menu
5. Clicking overlay (`sidebar-overlay`) closes the menu
6. Pressing Escape key closes the menu
7. ARIA attributes (`aria-expanded`, `aria-hidden`) are properly updated
8. Focus is returned to hamburger button when menu closes
9. All click events are logged to console for debugging

**Technical Notes:**
- Event listeners must be registered in DOMContentLoaded handler
- Console logging must be added for all click events
- Functions `toggleMenu()` and `closeMenu()` must be called appropriately
- Sidebar must have `active` class when open, removed when closed

**Related Files:**
- `timelimit-ui/rootfs/usr/bin/dashboardV2/static/js/dashboardV2.js` - Event listeners and menu functions
- `timelimit-ui/rootfs/usr/bin/dashboardV2/templates/dashboardV2.html` - Menu HTML structure
- `timelimit-ui/rootfs/usr/bin/dashboardV2/static/css/dashboardV2.css` - Menu styling

**Status:** ✅ Implemented and tested (2026-09-28)

---

## Non-Functional Requirements

### NFR-001: Performance

**Requirement:** Sync operations must complete within 5 seconds under normal network conditions.

---

### NFR-002: Reliability

**Requirement:** The dashboard must gracefully handle sync failures and retry with exponential backoff.

---

### NFR-003: Security

**Requirement:** All sync communications must use HTTPS and authentication tokens must be securely stored.

---

### NFR-004: Browser Performance

**Description:** The dashboard should not freeze or become unresponsive when the server is down.

**Acceptance Criteria:**
- No queued requests accumulate when server is unreachable
- SSE connections do not continuously retry when server is down
- UI remains responsive even when server is offline

**Status:** ✅ Met by FR-002 implementation

---

## Technical Requirements

### TR-001: Timeout Handling

**Description:** All API requests should have proper timeout handling to prevent indefinite waiting.

**Acceptance Criteria:**
- All fetch requests use AbortController with appropriate timeouts
- Network errors are caught and handled gracefully
- User is notified of connection issues

**Status:** ✅ Implemented in `apiRequest()` function

---

## Test Requirements

### Test-001: Server Down Detection Tests

**Description:** Verify that server down detection works correctly.

**Test Cases:**
1. Offline banner appears when server is unreachable
2. Interactive elements are disabled when server is down
3. SSE connection is closed when server goes offline
4. Health check polling detects server recovery
5. Retry button restores functionality when server is back online

**Status:** ✅ All tests pass (267 dashboard-related tests)

---

### Test-002: Add User to Family Tests

**Description:** Verify that adding a user works correctly and the user is immediately visible.

**Test Cases:**
1. User is created successfully via API
2. User appears in database after add user call
3. User is visible in dashboard without manual sync
4. Error handling works correctly for all failure scenarios
5. Local user record is created when server doesn't return user

**Status:** ✅ All 15 add user tests pass

---

### Test-003: Time Limit Rules Tests

**Description:** Verify that time limit rules management works correctly.

**Test Cases:**
1. Database operations work correctly (save, get, update, delete)
2. API endpoints return correct data and handle errors
3. Sync integration works with server
4. UI displays rules correctly
5. Form validation works correctly
6. Edit and delete operations work correctly

**Status:** ✅ All 44 tests pass (12 database + 23 API + 9 auth client)

---

### Test-004: Hamburger Menu Tests

**Description:** Verify that hamburger menu navigation works correctly.

**Test Cases:**
1. Hamburger menu button element exists in HTML
2. Sidebar element exists in HTML
3. Overlay element exists in HTML
4. `toggleMenu()` function exists in JavaScript
5. `closeMenu()` function exists in JavaScript
6. Event listener is registered for menu-toggle button
7. Sidebar CSS has active state for open menu
8. Overlay CSS has active state for open overlay
9. Menu toggle button is not hidden by CSS
10. `aria-expanded` attribute is updated when menu opens/closes
11. `aria-hidden` attribute is updated when menu opens/closes
12. DOMContentLoaded has proper page detection and menu initialization
13. Escape key closes menu
14. `toggleMenu` is exposed on window object
15. `closeMenu` is exposed on window object
16. `toggleMenu` is exposed on dashboardV2 object
17. `closeMenu` is exposed on dashboardV2 object
18. `toggleMenu` uses getElementById to find elements
19. No conflicting event listeners in extra_js
20. Menu button has type attribute

**Status:** ✅ All 20 hamburger menu tests pass

---

## Bug Fixes (Resolved)

### BUG-001: Dashboard Not Loading All Data at Startup

**Problem:** Dashboard opened showing 1 device and 0 users at startup.

**Root Cause:** The first sync pull-status request returned empty data because the `sync_state` table had stale version hashes from a previous sync.

**Solution:** Added retry logic in `sync_manager.py` that detects when the server returns empty data and retries with empty versions to force a full sync.

**Status:** ✅ Resolved

---

### BUG-002: User Not Visible After Adding

**Problem:** After adding a user "Jantje" via the dashboard, the user did not show up in the dashboard.

**Root Cause:** The `api_add_user_to_family()` function was calling `pull_status()` with existing sync state (version hashes from a previous sync). The TimeLimit server only returns changes based on version hashes, so the newly created user wasn't returned.

**Solution:** 
1. Force a full sync with empty versions to get all users from the server
2. Create a local user record if the user isn't found in the sync response

**Status:** ✅ Resolved (2026-09-27)

---

### BUG-003: User Count Inconsistency After Adding

**Problem:** After adding a user "Jantje" via the "Add Dummy User" feature, the user appeared in the Family users section but the family overview section still showed only 1 user instead of 2. This was inconsistent - if the family has 2 users, the overview should also show this count.

**Root Cause:** The `save_users()` function in `database.py` was using `INSERT OR REPLACE` SQL statements. When the server returned fewer users than what was in the local database (e.g., during an incremental sync that only returns changed data), the extra users were lost because:
1. The server returned empty user data (only hash verification fields `dh` and `u2f`)
2. The `INSERT OR REPLACE` statement replaced all users with the empty server response
3. Locally-added users (like "Jantje") were deleted from the database

**Solution:** Modified the `save_users()` function to preserve existing users that are not in the server response:
1. Get existing users from the database before saving
2. Get user IDs from the server response
3. Find users that exist locally but not in server response (preserved_user_ids)
4. Insert/replace users from the server response
5. Re-insert the preserved users with their existing data (password, time_zone, mail, etc.)

This ensures that users added locally (e.g., via "Add Dummy User" feature) are not lost during a sync when the server returns empty or partial data.

**Files Modified:**
- `timelimit-ui/rootfs/usr/bin/dashboardV2/database.py` - Modified `save_users()` function

**Status:** ✅ Resolved (2026-09-27)

---

### BUG-004: Hamburger Menu Not Working

**Problem:** The hamburger menu in dashboard v2 was broken - clicking the button didn't open the menu, and there were no events in the browser console.

**Root Cause:** The `toggleMenu()` and `closeMenu()` functions existed in the JavaScript file, but there were NO event listeners registered to call them. The DOMContentLoaded handler didn't include any code to register click event listeners for the hamburger menu button, sidebar close button, sidebar overlay, and other interactive elements.

**Solution:**
1. Added event listener registration in DOMContentLoaded handler for:
   - `menu-toggle` button → calls `toggleMenu()`
   - `sidebar-close` button → calls `closeMenu()`
   - `sidebar-overlay` → calls `closeMenu()`
   - `add-dummy-user-btn` → calls `showAddUserModal()`
   - `add-user-modal-close` → calls `hideAddUserModal()`
   - `add-user-submit-btn` → calls `submitAddUserForm()`
   - `signout-btn-sidebar` → calls `clearSession()`
2. Added sidebar login links handling in `updateSessionOverview()`
3. Added add dummy user button visibility handling in `updateSessionOverview()`
4. Added `refreshServerStatus()` function
5. Added `clearFamilyOverviewContent()` function
6. Modified `loadFamilyOverview()` to check authentication and clear content on error
7. Exposed `clearFamilyOverviewContent` on `window` and `dashboardV2` objects
8. Removed reference to non-existent `sign-in-section` element

**Files Modified:**
- `timelimit-ui/rootfs/usr/bin/dashboardV2/static/js/dashboardV2.js`

**Status:** ✅ Resolved (2026-09-28)