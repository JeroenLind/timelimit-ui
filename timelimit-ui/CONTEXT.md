# TimeLimit UI Project Context

## Project Overview
TimeLimit UI is a dashboard application for managing TimeLimit family accounts and devices. It communicates with an external TimeLimit backend server via REST API endpoints.

## Technical Stack
- **Frontend**: HTML/CSS/JavaScript (Vanilla JS)
- **Backend**: Python Flask (dashboardV2)
- **Database**: SQLite
- **HTTP Client**: requests library

## Key Components
- `timelimit-ui/rootfs/usr/bin/dashboardV2/auth_client.py` - HTTP client for server API communication
- `timelimit-ui/rootfs/usr/bin/dashboardV2/app.py` - Flask application with API endpoints
- `timelimit-ui/rootfs/usr/bin/dashboardV2/database.py` - Database operations
- `timelimit-ui/rootfs/usr/bin/dashboardV2/persistence.py` - Persistence abstraction for server selection and auth tokens
- `timelimit-ui/rootfs/usr/bin/dashboardV2/crypto_utils.py` - Crypto helpers for hashing and integrity calculations

## Current Issues
- Device removal via `/api/dashboard/devices/remove` endpoint - **RESOLVED**
- Session status API missing password hash fields - **RESOLVED**
- Server check records accumulation in database - **RESOLVED**
- Refresh button not syncing users/devices - **RESOLVED**
- Sync operations not logged to audit.log - **RESOLVED**
- Server selection not persisting correctly - **RESOLVED**
- Family creation 409 Conflict error shows raw HTML instead of user-friendly message - **RESOLVED**
- Dashboard Signing Key not displayed - **RESOLVED**
- Password hash mismatch in login-as-parent flow causing 401 Unauthorized device removal error - **RESOLVED**
- Password hash regeneration during login-as-parent not using existing salt - **RESOLVED**
- Salt validation missing in login-as-parent flow - **RESOLVED**
- Family record not created after sign-in causing "Family not found" error when entering password - **RESOLVED**
- Family overview showing "pending@unknown" instead of actual email address - **RESOLVED**
- "Failed to sync: loadUsers is not defined" error on refresh button - **RESOLVED**

## Family Email Display Fix (2026-09-18)

### Problem
The family overview section showed "pending@unknown" instead of the actual email address (e.g., pietje@test.nl) that the user entered during family creation/login.

### Root Cause Analysis
The issue had two aspects:

1. **Primary Issue**: The `upsert_family_password_hash()` function in `database.py` was correctly designed to accept and update the `mail` parameter, but the call in `post_create_family()` (app.py line 1485) was NOT passing the `mail` parameter. This caused the family record's mail field to remain as "pending@unknown" even when a valid email was provided during family creation.

2. **Secondary Issue**: The `/api/dashboard/family-overview` endpoint reads the email from the database via `get_family(db, device_auth_token)`. When the database still has "pending@unknown" (due to the primary issue or sync timing), the endpoint should check the session for the mail value as a fallback.

### Files Fixed
- `timelimit-ui/rootfs/usr/bin/dashboardV2/app.py` - Fixed `post_create_family()` to pass `mail` parameter to `upsert_family_password_hash()`
- `timelimit-ui/rootfs/usr/bin/dashboardV2/app.py` - Fixed `api_create_family_rest()` to store mail in session and persist it with auth token
- `timelimit-ui/rootfs/usr/bin/dashboardV2/app.py` - Fixed `api_dashboard_family_overview()` to check session for mail value when database has "pending@unknown"

### Changes Applied

#### 1. app.py - Fixed post_create_family() to pass mail parameter
Added `mail=mail` parameter to the `upsert_family_password_hash()` call:

```python
# Store password hash in database for session restoration
upsert_family_password_hash(
    db=db,
    device_auth_token=device_auth_token,
    parent_password_hash=password_data.get('hash'),
    parent_password_second_hash=password_data.get('secondHash'),
    parent_password_second_salt=password_data.get('secondSalt'),
    mail=mail  # Added this parameter
)
```

#### 2. app.py - Fixed api_create_family_rest() to store mail
Added mail to session and passed it to `set_persisted_device_auth_token()`:

```python
# Store device auth token in session
session['device_auth_token'] = response.data.get('deviceAuthToken')
session['own_device_id'] = response.data.get('ownDeviceId')
session['mail'] = email  # Store mail in session for family email display

# Persist auth token to file for session restoration after restart (with mail)
if response.data.get('deviceAuthToken'):
    set_persisted_device_auth_token(
        response.data.get('deviceAuthToken'),
        response.data.get('ownDeviceId'),
        email
    )
```

#### 3. app.py - Fixed api_dashboard_family_overview() to check session for mail
Added logic to check session for mail value when database has "pending@unknown":

```python
# If family email is still pending@unknown, check session for mail value
# This handles the case where sync hasn't completed yet or user just logged in
if family_email == 'pending@unknown':
    session_mail = session.get('mail')
    if session_mail and session_mail != 'pending@unknown':
        family_email = session_mail
        logger.debug(
            "Family email retrieved from session",
            request_id=request_id,
            device_auth_token=device_auth_token[:8] + '...' if device_auth_token else None,
            mail=session_mail
        )
```

### Test Results
- **117 tests passed** (7 new tests added for family overview endpoint)
- Family overview now correctly displays the user's email address
- New tests verify:
  - Session mail fallback when database has "pending@unknown"
  - Database mail is used when it's not "pending@unknown"
  - Proper handling of unauthenticated requests
  - Proper handling of missing device auth token
  - Proper handling of missing family record

## Input Field Contrast Fix (2026-09-18)

### Problem
Input fields in modal dialogs had light white text (`color: #fff`) on a very light background (`rgba(255, 255, 255, 0.05)`), making text barely visible. This affected 4 modal templates used for family creation and authentication flows.

### Files Fixed
- `timelimit-ui/rootfs/usr/bin/dashboardV2/templates/create_family.html`
- `timelimit-ui/rootfs/usr/bin/dashboardV2/templates/login_as_parent.html`
- `timelimit-ui/rootfs/usr/bin/dashboardV2/templates/set_parent_password.html`
- `timelimit-ui/rootfs/usr/bin/dashboardV2/templates/recover_parent_password.html`

### CSS Changes Applied
Changed input field text color from `#fff` (white) to `#212529` (dark gray) for proper WCAG 2.1 AA contrast compliance:

```css
.form-group input,
.form-group select {
    color: #212529;  /* Changed from #fff to #212529 */
}

.form-group input::placeholder,
.form-group select::placeholder {
    color: #6c757d;  /* Changed from #666 to #6c757d */
}

.form-group option {
    color: #212529;  /* Added for select elements */
}
```

### Test Results
- All tests for the modified templates pass
- 1165 tests passed overall

## Server Status Display Fix (2026-09-18)

### Problem
When the dashboard was not signed in, the "Server Status" section at the top of the dashboard showed "Checking server..." instead of the actual server URL. This was confusing because users need to know the server status even when not logged in (to understand why they can't sign in).

### Root Cause
The top "Server Status" section (lines 1576-1584 in `dashboardV2.html`) had a `status-content` div that displayed "Checking server..." but was never updated by JavaScript. The JavaScript code only updated the Session Overview section's server status indicators (`server-status-indicator` and `server-status-text`), but not the top section's `status-indicator` and `status-content` elements.

### Fix Applied
Updated the `updateSessionOverview()` function in `dashboardV2/static/js/dashboardV2.js` to also update the top "Server Status" section:

```javascript
// Update top Server Status section
const statusIndicator = document.getElementById('status-indicator');
const statusContent = document.getElementById('status-content');
const errorMessage = document.getElementById('error-message');
if (statusIndicator && statusContent) {
    if (data.server_url) {
        statusIndicator.className = 'status-indicator status-success';
        statusContent.innerHTML = '<div class="server-info">' +
            '<span class="server-label">Server:</span>' +
            '<span class="server-url" style="color: #00ff88; font-family: monospace; font-size: 12px;"> ' + escapeHtml(data.server_url) + '</span>' +
            '</div>';
        if (errorMessage) {
            errorMessage.style.display = 'none';
        }
    } else {
        statusIndicator.className = 'status-indicator status-warning';
        statusContent.innerHTML = '<div class="server-info">' +
            '<span class="server-label">Server:</span>' +
            '<span class="server-url" style="color: #ff9800; font-family: monospace; font-size: 12px;"> Not available</span>' +
            '</div>';
        if (errorMessage) {
            errorMessage.style.display = 'none';
        }
    }
}
```

### Problem
User reported that after pressing sign-out:
1. They are redirected to the landing page (not staying on dashboard)
2. The dashboard still thinks they are logged in
3. Login buttons don't appear after sign-out

### Root Cause
Multiple issues in `dashboardV2.js`:
1. `clearSession()` just reloaded the page instead of properly updating the UI
2. `checkAuthentication()` returned a boolean instead of full session data
3. `updateSessionOverview()` did NOT handle `recover-password-link` element
4. DOMContentLoaded handler didn't call `updateLoginStatusBanner()` or `updateSessionOverview()` after checking authentication
5. The prominent `sign-in-section` in HTML was not being toggled properly

### Fixes Applied

#### 1. Fixed `checkAuthentication()` to return full session data
```javascript
async function checkAuthentication() {
    console.log('[DEBUG] checkAuthentication() called');
    try {
        console.log('[DEBUG] Fetching session status from /api/session/status');
        const response = await fetch('/api/session/status');
        console.log('[DEBUG] Response status:', response.status);
        const data = await response.json();
        console.log('[DEBUG] Session status data:', JSON.stringify(data));
        isAuthenticated = data.authenticated || false;
        console.log('[DEBUG] isAuthenticated set to:', isAuthenticated);
        return data;
    } catch (error) {
        console.error('[DEBUG] Failed to check authentication status:', error);
        isAuthenticated = false;
        return { authenticated: false };
    }
}
```

#### 2. Fixed `clearSession()` to properly update the UI
```javascript
async function clearSession() {
    console.log('[DEBUG] clearSession() called');
    try {
        console.log('[DEBUG] Making API request to /session/clear');
        const response = await apiRequest('/session/clear', 'POST');
        console.log('[DEBUG] Response received:', response);
        
        if (response && response.status === 'ok') {
            console.log('[DEBUG] Session cleared successfully');
            parentPasswordHash = null;
            isAuthenticated = false;
            
            const sessionData = { authenticated: false };
            updateLoginStatusBanner(sessionData);
            updateSessionOverview(sessionData);
            
            showAlert('Signed out successfully. Please sign in to continue.', 'success');
        } else {
            console.error('[DEBUG] Failed to clear session:', response);
            showAlert('Failed to clear session: ' + (response?.error || 'Unknown error'), 'error');
        }
    } catch (error) {
        console.error('[DEBUG] Failed to clear session:', error);
        showAlert('Failed to clear session: ' + error.message, 'error');
    }
}
```

#### 3. Fixed `updateSessionOverview()` to handle `recover-password-link` and `sign-in-section`
```javascript
// Show/hide action links based on authentication status
const createFamilyLink = document.getElementById('create-family-link');
const loginExistingFamilyLink = document.getElementById('login-existing-family-link');
const recoverPasswordLink = document.getElementById('recover-password-link');
const signoutLink = document.getElementById('signout-link');
const signInSection = document.getElementById('sign-in-section');

console.log('[DEBUG] Authentication status:', data.authenticated);
console.log('[DEBUG] createFamilyLink exists:', !!createFamilyLink);
console.log('[DEBUG] loginExistingFamilyLink exists:', !!loginExistingFamilyLink);
console.log('[DEBUG] recoverPasswordLink exists:', !!recoverPasswordLink);
console.log('[DEBUG] signoutLink exists:', !!signoutLink);
console.log('[DEBUG] signInSection exists:', !!signInSection);

if (createFamilyLink && loginExistingFamilyLink && recoverPasswordLink) {
    if (data.authenticated) {
        console.log('[DEBUG] Hiding login links, showing signout');
        createFamilyLink.style.display = 'none';
        loginExistingFamilyLink.style.display = 'none';
        recoverPasswordLink.style.display = 'none';
        if (signoutLink) {
            signoutLink.style.display = 'block';
        }
        if (signInSection) {
            signInSection.style.display = 'none';
        }
    } else {
        console.log('[DEBUG] Showing login links, hiding signout');
        createFamilyLink.style.display = 'block';
        loginExistingFamilyLink.style.display = 'block';
        recoverPasswordLink.style.display = 'block';
        if (signoutLink) {
            signoutLink.style.display = 'none';
        }
        if (signInSection) {
            signInSection.style.display = 'block';
        }
    }
}
```

#### 4. Updated DOMContentLoaded handler to call update functions
```javascript
document.addEventListener('DOMContentLoaded', async function() {
    console.log('DashboardV2 initialized');
    
    const sessionData = await checkAuthentication();
    
    updateLoginStatusBanner(sessionData);
    updateSessionOverview(sessionData);
    
    if (isAuthenticated) {
        loadUsers();
        loadDevices();
        loadConnectedDevices();
        connectSSE();
    } else {
        console.log('User not authenticated - dashboard data will not be loaded');
    }
});
```

#### 5. Added missing JavaScript functions
- `toggleMenu()` - Hamburger menu toggle function
- `closeMenu()` - Hamburger menu close function
- `checkAdminVisibility()` - Admin visibility check function
- `updateAdminOnlyElements()` - Admin-only elements visibility function
- `updateAdminSectionVisibility()` - Admin section visibility function
- `renderFamilyOverview()` - Family overview rendering function
- Escape key handler for closing modals

### HTML Changes
The HTML template already had a prominent `sign-in-section` (lines 1592-1609 in `dashboardV2.html`) with:
- Gradient background
- "Create New Family" button
- "Login to Existing Family" button
- "Recover Parent Password" link

### Test Results
- **1165 tests passed**
- All sign-out functionality tests pass

## Dashboard V2 HTML Structure Changes (2026-09-19)

### Changes Made
1. **Removed "Historical Data" section** - The historical data table and related JavaScript function `loadHistoricalData()` were removed from the dashboard as server checks are no longer persisted.

2. **Moved "Session Information" section** - The Session Information section was moved to appear after the "Connected Devices" section (previously it was before Family Users).

### Files Modified
- `timelimit-ui/rootfs/usr/bin/dashboardV2/templates/dashboardV2.html` - HTML structure updated
- `timelimit-ui/rootfs/usr/bin/dashboardV2/tests/test_visual_responsive.py` - Fixed `test_family_overview_card_exists` to check for `family-overview-card` class without requiring exact `class="family-overview-card"` string match (since it's a multi-class attribute)

### Dashboard V2 Sections (Current Order)
1. **Server Status** - Shows server connectivity status with status indicator
2. **Login Status Banner** - Prominent banner showing login status (hidden by default)
3. **Family Overview Card** - Shows family email, devices count badge, users count badge, last sync timestamp
4. **Dashboard Content** - Welcome message and refresh button
5. **Family Users** - Table showing family members with their details
6. **Family Devices** - Table showing family devices with their details
7. **Connected Devices** - Table showing currently connected devices
8. **Session Information** - Detailed session status including server URL, auth tokens, device info
9. **Alert Container** - Container for notification alerts

### Test Results
- **71 tests passed** in `test_visual_responsive.py`
- All tests pass including hamburger menu, admin visibility, responsive layout, and family overview card tests

## Historical Data Section Removal (2026-09-18)

### Problem
The "Historical Data" section on the Dashboard V2 was showing "No history data available" because server checks are no longer stored in the database. The `/api/timechecker/history` endpoint returns an empty `checks` array.

### Root Cause
The historical data feature was disabled (server checks are no longer persisted), but the UI section was never removed. This created a confusing empty section in the dashboard.

### Files Modified
1. **`timelimit-ui/rootfs/usr/bin/dashboardV2/templates/dashboardV2.html`**
   - Removed the Historical Data HTML section (lines 1843-1865)
   - Removed the `loadHistoricalData()` JavaScript function (lines 2102-2132)
   - Removed all `.historical-table` CSS styles from the style block

2. **`timelimit-ui/rootfs/usr/bin/dashboardV2/tests/test_timechecker.py`**
   - Removed `test_dashboard_v2_has_historical_table` test
   - Removed `loadHistoricalData` assertion from `test_dashboard_v2_has_javascript`
   - Removed `/api/timechecker/history` assertion from `test_dashboard_v2_has_api_endpoints_in_js`

3. **`timelimit-ui/rootfs/usr/bin/dashboardV2/CONTEXT.md`**
   - Added documentation of the change

### Changes Made
- Removed the entire `<div class="dashboard-content">` block containing:
  - `<h2>Historical Data</h2>`
  - Refresh History button
  - Historical data table with columns: Timestamp, Status, Server Time, Error
- Removed the `loadHistoricalData()` function that fetched from `/api/timechecker/history`
- Removed all CSS styles for `.historical-table` class

### Test Results
- All 1171 tests pass
- No regressions introduced

### Problem
User reported that after pressing sign-out:
1. They are redirected to the landing page (not staying on dashboard)
2. The dashboard still thinks they are logged in
3. Login buttons don't appear after sign-out

### Root Cause
Multiple issues in `dashboardV2.js`:
1. `clearSession()` just reloaded the page instead of properly updating the UI
2. `checkAuthentication()` returned a boolean instead of full session data
3. `updateSessionOverview()` did NOT handle `recover-password-link` element
4. DOMContentLoaded handler didn't call `updateLoginStatusBanner()` or `updateSessionOverview()` after checking authentication
5. The prominent `sign-in-section` in HTML was not being toggled properly

### Fixes Applied

#### 1. Fixed `checkAuthentication()` to return full session data
```javascript
async function checkAuthentication() {
    console.log('[DEBUG] checkAuthentication() called');
    try {
        console.log('[DEBUG] Fetching session status from /api/session/status');
        const response = await fetch('/api/session/status');
        console.log('[DEBUG] Response status:', response.status);
        const data = await response.json();
        console.log('[DEBUG] Session status data:', JSON.stringify(data));
        isAuthenticated = data.authenticated || false;
        console.log('[DEBUG] isAuthenticated set to:', isAuthenticated);
        return data;
    } catch (error) {
        console.error('[DEBUG] Failed to check authentication status:', error);
        isAuthenticated = false;
        return { authenticated: false };
    }
}
```

#### 2. Fixed `clearSession()` to properly update the UI
```javascript
async function clearSession() {
    console.log('[DEBUG] clearSession() called');
    try {
        console.log('[DEBUG] Making API request to /session/clear');
        const response = await apiRequest('/session/clear', 'POST');
        console.log('[DEBUG] Response received:', response);
        
        if (response && response.status === 'ok') {
            console.log('[DEBUG] Session cleared successfully');
            parentPasswordHash = null;
            isAuthenticated = false;
            
            const sessionData = { authenticated: false };
            updateLoginStatusBanner(sessionData);
            updateSessionOverview(sessionData);
            
            showAlert('Signed out successfully. Please sign in to continue.', 'success');
        } else {
            console.error('[DEBUG] Failed to clear session:', response);
            showAlert('Failed to clear session: ' + (response?.error || 'Unknown error'), 'error');
        }
    } catch (error) {
        console.error('[DEBUG] Failed to clear session:', error);
        showAlert('Failed to clear session: ' + error.message, 'error');
    }
}
```

#### 3. Fixed `updateSessionOverview()` to handle `recover-password-link` and `sign-in-section`
```javascript
// Show/hide action links based on authentication status
const createFamilyLink = document.getElementById('create-family-link');
const loginExistingFamilyLink = document.getElementById('login-existing-family-link');
const recoverPasswordLink = document.getElementById('recover-password-link');
const signoutLink = document.getElementById('signout-link');
const signInSection = document.getElementById('sign-in-section');

console.log('[DEBUG] Authentication status:', data.authenticated);
console.log('[DEBUG] createFamilyLink exists:', !!createFamilyLink);
console.log('[DEBUG] loginExistingFamilyLink exists:', !!loginExistingFamilyLink);
console.log('[DEBUG] recoverPasswordLink exists:', !!recoverPasswordLink);
console.log('[DEBUG] signoutLink exists:', !!signoutLink);
console.log('[DEBUG] signInSection exists:', !!signInSection);

if (createFamilyLink && loginExistingFamilyLink && recoverPasswordLink) {
    if (data.authenticated) {
        console.log('[DEBUG] Hiding login links, showing signout');
        createFamilyLink.style.display = 'none';
        loginExistingFamilyLink.style.display = 'none';
        recoverPasswordLink.style.display = 'none';
        if (signoutLink) {
            signoutLink.style.display = 'block';
        }
        if (signInSection) {
            signInSection.style.display = 'none';
        }
    } else {
        console.log('[DEBUG] Showing login links, hiding signout');
        createFamilyLink.style.display = 'block';
        loginExistingFamilyLink.style.display = 'block';
        recoverPasswordLink.style.display = 'block';
        if (signoutLink) {
            signoutLink.style.display = 'none';
        }
        if (signInSection) {
            signInSection.style.display = 'block';
        }
    }
}
```

#### 4. Updated DOMContentLoaded handler to call update functions
```javascript
document.addEventListener('DOMContentLoaded', async function() {
    console.log('DashboardV2 initialized');
    
    const sessionData = await checkAuthentication();
    
    updateLoginStatusBanner(sessionData);
    updateSessionOverview(sessionData);
    
    if (isAuthenticated) {
        loadUsers();
        loadDevices();
        loadConnectedDevices();
        connectSSE();
    } else {
        console.log('User not authenticated - dashboard data will not be loaded');
    }
});
```

#### 5. Added missing JavaScript functions
- `toggleMenu()` - Hamburger menu toggle function
- `closeMenu()` - Hamburger menu close function
- `checkAdminVisibility()` - Admin visibility check function
- `updateAdminOnlyElements()` - Admin-only elements visibility function
- `updateAdminSectionVisibility()` - Admin section visibility function
- `renderFamilyOverview()` - Family overview rendering function
- Escape key handler for closing modals

### HTML Changes
The HTML template already had a prominent `sign-in-section` (lines 1592-1609 in `dashboardV2.html`) with:
- Gradient background
- "Create New Family" button
- "Login to Existing Family" button
- "Recover Parent Password" link

### Test Results
- **1165 tests passed**
- All sign-out functionality tests pass