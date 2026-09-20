# Add User to Family - UI Design Document

## Overview

This document specifies the UI design for the "Add User to Family" feature in the TimeLimit Dashboard V2. The design follows existing UI patterns established in the codebase for consistency and maintainability.

---

## 1. Add User Button

### HTML Structure

```html
<!-- Users Section - Modified from dashboardV2.html lines 781-805 -->
<div class="dashboard-content">
    <h2>Family Users <span class="version-badge">v1.0.0</span></h2>
    <div style="margin-bottom: 10px;">
        <button class="refresh-btn" id="refresh-users-btn" onclick="refreshUsers()">
            <span>🔄</span> Refresh Users
        </button>
        <button class="refresh-btn" id="add-user-btn" onclick="showAddUserModal()" 
                style="background: rgba(102, 126, 234, 0.2); border: 1px solid rgba(102, 126, 234, 0.5); color: #667eea; margin-left: 10px;">
            <span>+</span> Add User
        </button>
    </div>
    <div class="db-table-wrapper">
        <table class="dashboard-table" id="users-table">
            <thead>
                <tr>
                    <th>Name</th>
                    <th>Type</th>
                    <th>Email</th>
                    <th>Current Device</th>
                    <th>Time Zone</th>
                    <th>Limits Disabled</th>
                </tr>
            </thead>
            <tbody id="users-body">
                <tr><td colspan="6" style="text-align: center; color: #666;">Loading...</td></tr>
            </tbody>
        </table>
    </div>
</div>
```

### Styling

| Property | Value |
|----------|-------|
| Icon | `+` emoji |
| Background | `rgba(102, 126, 234, 0.2)` |
| Border | `1px solid rgba(102, 126, 234, 0.5)` |
| Text Color | `#667eea` |
| Margin Left | `10px` (from Refresh button) |
| Hover Effect | `background: rgba(102, 126, 234, 0.3)` |

### Placement

- Positioned immediately after the "Refresh Users" button
- Same button style as "Add Rule" button (see `dashboardV2.html` line 889)
- Visible only when authenticated

---

## 2. Modal Dialog Structure

### HTML Structure

```html
<!-- Add User Modal - Insert before alert-container -->
<div id="add-user-modal" style="display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0, 0, 0, 0.8); z-index: 1000; align-items: center; justify-content: center; opacity: 0; transition: opacity 0.3s ease;">
    <div style="background: rgba(255, 255, 255, 0.95); border-radius: 12px; max-width: 500px; width: 90%; padding: 20px; color: #333;">
        <h3 id="add-user-modal-title" style="margin-top: 0; color: #333;">Add User to Family</h3>
        <form id="add-user-form" onsubmit="event.preventDefault(); submitAddUserForm()">
            <!-- Form fields go here -->
            <div style="display: flex; justify-content: flex-end; gap: 10px; margin-top: 20px; padding-top: 15px; border-top: 1px solid #eee;">
                <button type="button" class="refresh-btn" onclick="hideAddUserModal()">Cancel</button>
                <button type="submit" class="refresh-btn" id="add-user-submit-btn" style="background: rgba(76, 175, 80, 0.2); border: 1px solid rgba(76, 175, 80, 0.5); color: #4caf50;">
                    Add
                </button>
            </div>
        </form>
    </div>
</div>
```

### CSS Styles

```css
/* Modal overlay - follows rule-form-modal pattern */
#add-user-modal {
    display: flex;
    align-items: center;
    justify-content: center;
}

#add-user-modal.show {
    display: flex;
    opacity: 1;
}

/* Modal content container */
#add-user-modal .modal-content {
    background: rgba(255, 255, 255, 0.95);
    border-radius: 12px;
    max-width: 500px;
    width: 90%;
    padding: 20px;
    color: #333;
}

/* Modal title */
#add-user-modal .modal-content h3 {
    margin-top: 0;
    color: #333;
}

/* Form inputs */
#add-user-modal .modal-content input[type="text"] {
    width: 100%;
    padding: 10px;
    border: 1px solid #444;
    border-radius: 6px;
    background: #222;
    color: #fff;
    box-sizing: border-box;
}

/* Form labels */
#add-user-modal .modal-content label {
    display: block;
    margin-bottom: 5px;
    color: #666;
    font-size: 14px;
}

/* Form field container */
#add-user-modal .modal-content .form-field {
    margin-bottom: 15px;
}

/* Validation error message */
#add-user-modal .modal-content .validation-error {
    color: #f44336;
    font-size: 12px;
    margin-top: 5px;
}

/* Warning message for parent password */
#add-user-modal .modal-content .password-warning {
    background: rgba(255, 152, 0, 0.1);
    border: 1px solid rgba(255, 152, 0, 0.3);
    border-radius: 6px;
    padding: 10px;
    margin-bottom: 15px;
    color: #ff9800;
    font-size: 13px;
}

/* Form actions */
#add-user-modal .modal-content .form-actions {
    display: flex;
    justify-content: flex-end;
    gap: 10px;
    margin-top: 20px;
    padding-top: 15px;
    border-top: 1px solid #eee;
}

/* Submit button (primary action) */
#add-user-modal .modal-content .form-actions button[type="submit"] {
    background: rgba(76, 175, 80, 0.2);
    border: 1px solid rgba(76, 175, 80, 0.5);
    border-radius: 8px;
    color: #4caf50;
    cursor: pointer;
    font-size: 14px;
    padding: 8px 16px;
    transition: all 0.2s ease;
}

#add-user-modal .modal-content .form-actions button[type="submit"]:hover {
    background: rgba(76, 175, 80, 0.3);
    transform: translateY(-1px);
}

#add-user-modal .modal-content .form-actions button[type="submit"].loading {
    opacity: 0.6;
    cursor: not-allowed;
}

/* Cancel button */
#add-user-modal .modal-content .form-actions button[type="button"] {
    background: rgba(155, 89, 182, 0.2);
    border: 1px solid rgba(155, 89, 182, 0.5);
    border-radius: 8px;
    color: #9b59b6;
    cursor: pointer;
    font-size: 14px;
    padding: 8px 16px;
    transition: all 0.2s ease;
}

#add-user-modal .modal-content .form-actions button[type="button"]:hover {
    background: rgba(155, 89, 182, 0.3);
    transform: translateY(-1px);
}
```

---

## 3. Form Fields

### Field Specifications

| Field | Type | Required | Placeholder | Max Length |
|-------|------|----------|-------------|------------|
| User Name | text | Yes | "Child's name" | 100 characters |
| Device Name | text | No | "Device name (optional)" | 100 characters |
| Device Model | text | No | "Device model (optional)" | 100 characters |

### HTML Structure

```html
<!-- User Name (required) -->
<div class="form-field">
    <label for="add-user-name">User Name <span style="color: #f44336;">*</span></label>
    <input type="text" id="add-user-name" name="name" placeholder="Child's name" maxlength="100" required>
    <div id="add-user-name-error" class="validation-error" style="display: none;"></div>
</div>

<!-- Device Name (optional) -->
<div class="form-field">
    <label for="add-user-device-name">Device Name (optional)</label>
    <input type="text" id="add-user-device-name" name="deviceName" placeholder="Device name (optional)" maxlength="100">
</div>

<!-- Device Model (optional) -->
<div class="form-field">
    <label for="add-user-device-model">Device Model (optional)</label>
    <input type="text" id="add-user-device-model" name="deviceModel" placeholder="Device model (optional)" maxlength="100">
</div>
```

---

## 4. Action Buttons

### Button Specifications

| Button | Type | Style | Behavior |
|--------|------|-------|----------|
| Add | submit | Primary (green) | Submits form, validates, calls API |
| Cancel | button | Secondary (purple) | Closes modal, resets form |

### HTML Structure

```html
<div class="form-actions">
    <button type="button" class="refresh-btn" onclick="hideAddUserModal()">Cancel</button>
    <button type="submit" class="refresh-btn" id="add-user-submit-btn">Add</button>
</div>
```

---

## 5. Validation Messages

### Validation Rules

1. **User Name Required**: Must not be empty or whitespace only
2. **Parent Password Hash Warning**: Shown when `has_parent_password_second_hash` is false

### HTML Structure for Validation

```html
<!-- Validation error for user name -->
<div id="add-user-name-error" class="validation-error" style="display: none;">
    User name is required
</div>

<!-- Warning for parent password hash -->
<div id="add-user-password-warning" class="password-warning" style="display: none;">
    ⚠️ Parent password hash is not set. Device removal operations will not be available for the new user.
</div>
```

### JavaScript Validation

```javascript
function validateAddUserForm() {
    const userName = document.getElementById('add-user-name').value.trim();
    const errorElement = document.getElementById('add-user-name-error');
    
    if (!userName) {
        errorElement.style.display = 'block';
        errorElement.textContent = 'User name is required';
        return false;
    }
    
    errorElement.style.display = 'none';
    return true;
}
```

---

## 6. User Feedback Patterns

### Loading State

```javascript
// Add loading class to submit button
document.getElementById('add-user-submit-btn').classList.add('loading');
document.getElementById('add-user-submit-btn').textContent = 'Adding...';
```

### Toast Notifications

Uses existing `showAlert()` function from `dashboardV2.js`:

```javascript
// Success
showAlert('User added successfully', 'success');

// Error
showAlert('Failed to add user: ' + errorMessage, 'error');

// Warning
showAlert('Parent password hash is required. Please set it in the session settings first.', 'warning');
```

### Form Reset

```javascript
function resetAddUserForm() {
    document.getElementById('add-user-form').reset();
    document.getElementById('add-user-name-error').style.display = 'none';
    document.getElementById('add-user-password-warning').style.display = 'none';
}
```

---

## 7. JavaScript Functions

### Function: `showAddUserModal()`

```javascript
/**
 * Show the add user modal
 * Checks parent password hash status and shows warning if needed
 */
async function showAddUserModal() {
    const modal = document.getElementById('add-user-modal');
    if (!modal) return;
    
    // Check if parent password hash is set
    const passwordWarning = document.getElementById('add-user-password-warning');
    if (passwordWarning) {
        if (!hasParentPasswordHash) {
            passwordWarning.style.display = 'block';
        } else {
            passwordWarning.style.display = 'none';
        }
    }
    
    // Show modal
    modal.style.display = 'block';
    modal.style.opacity = '1';
}
```

### Function: `hideAddUserModal()`

```javascript
/**
 * Hide the add user modal
 */
function hideAddUserModal() {
    const modal = document.getElementById('add-user-modal');
    if (!modal) return;
    
    modal.style.display = 'none';
    modal.style.opacity = '0';
    resetAddUserForm();
}
```

### Function: `submitAddUserForm()`

```javascript
/**
 * Submit the add user form
 */
async function submitAddUserForm() {
    // Validate form
    if (!validateAddUserForm()) {
        return;
    }
    
    const form = document.getElementById('add-user-form');
    const submitBtn = document.getElementById('add-user-submit-btn');
    
    // Get form values
    const userName = document.getElementById('add-user-name').value.trim();
    const deviceName = document.getElementById('add-user-device-name').value.trim() || null;
    const deviceModel = document.getElementById('add-user-device-model').value.trim() || null;
    
    // Show loading state
    submitBtn.classList.add('loading');
    submitBtn.textContent = 'Adding...';
    
    try {
        const response = await fetch('/api/dashboard/users/add', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                name: userName,
                deviceName: deviceName,
                deviceModel: deviceModel
            })
        });
        
        const data = await response.json();
        
        if (data.status === 'ok') {
            showAlert('User added successfully', 'success');
            hideAddUserModal();
            await refreshUsers();
        } else {
            showAlert('Failed to add user: ' + (data.error || 'Unknown error'), 'error');
        }
    } catch (error) {
        console.error('Failed to add user:', error);
        showAlert('Failed to add user: ' + error.message, 'error');
    } finally {
        submitBtn.classList.remove('loading');
        submitBtn.textContent = 'Add';
    }
}
```

### Function: `confirmAddUser()`

```javascript
/**
 * Confirm and add user with validation
 * Checks parent password hash requirement
 */
async function confirmAddUser() {
    // Check if parent password hash is set
    if (!hasParentPasswordHash) {
        const confirmed = confirm(
            'Parent password hash is not set.\n\n' +
            'Adding a user without the parent password hash set means:\n' +
            '- The user will be added successfully\n' +
            '- But device removal operations will not be available for the new user\n\n' +
            'Do you want to continue anyway?'
        );
        
        if (!confirmed) {
            return;
        }
    }
    
    await submitAddUserForm();
}
```

---

## 8. Event Handling Patterns

### Window Exposures

```javascript
// Expose functions for HTML onclick handlers
window.showAddUserModal = showAddUserModal;
window.hideAddUserModal = hideAddUserModal;
window.submitAddUserForm = submitAddUserForm;
window.validateAddUserForm = validateAddUserForm;
```

### Event Listeners

```javascript
// Close modal on Escape key
document.addEventListener('keydown', function(event) {
    if (event.key === 'Escape') {
        const modal = document.getElementById('add-user-modal');
        if (modal && modal.style.display === 'block') {
            hideAddUserModal();
        }
    }
});

// Close modal when clicking outside
document.getElementById('add-user-modal').addEventListener('click', function(event) {
    if (event.target === this) {
        hideAddUserModal();
    }
});
```

---

## 9. Integration with Existing UI Patterns

### Consistency with "Add Rule" Pattern

| Aspect | Add Rule | Add User |
|--------|----------|----------|
| Button Icon | `+` | `+` |
| Button Color | `rgba(102, 126, 234, 0.2)` | `rgba(102, 126, 234, 0.2)` |
| Modal Position | Fixed overlay | Fixed overlay |
| Modal Background | `rgba(0, 0, 0, 0.8)` | `rgba(0, 0, 0, 0.8)` |
| Modal Content | White background | White background |
| Animation | Opacity transition | Opacity transition |
| Form Submit | `onsubmit` handler | `onsubmit` handler |
| Cancel Button | Calls `hideRuleForm()` | Calls `hideAddUserModal()` |
| Success Feedback | `showAlert()` | `showAlert()` |
| Loading State | `.loading` class | `.loading` class |

### API Integration Pattern

```javascript
// Follows the same pattern as timeLimitRulesApi
const usersApi = {
    addUser: async function(userData) {
        const response = await fetch('/api/dashboard/users/add', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(userData)
        });
        return await response.json();
    }
};
```

---

## 10. Complete Implementation Summary

### Files to Modify

1. **`dashboardV2.html`** (template)
   - Add "Add User" button to Users section (line ~786)
   - Add modal dialog HTML structure (after line ~805)

2. **`dashboardV2.js`** (static/js)
   - Add `showAddUserModal()` function
   - Add `hideAddUserModal()` function
   - Add `submitAddUserForm()` function
   - Add `validateAddUserForm()` function
   - Add `resetAddUserForm()` function
   - Expose functions on `window` object
   - Add to `dashboardV2` object

### CSS Styles

All CSS styles are inline in the template (following existing pattern) or can be added to the `<style>` block in `dashboardV2.html`.

### Event Flow

```mermaid
flowchart TD
    A[User clicks "Add User" button] --> B[showAddUserModal() called]
    B --> C[Check parent password hash status]
    C --> D{Parent password hash set?}
    D -->|Yes| E[Show modal without warning]
    D -->|No| F[Show modal with warning]
    E --> G[User fills form]
    F --> G
    G --> H[User clicks "Add" button]
    H --> I[validateAddUserForm()]
    I --> J{Valid?}
    J -->|No| K[Show validation error]
    J -->|Yes| L[submitAddUserForm()]
    L --> M[API call to POST /api/dashboard/users/add]
    M --> N{Response status}
    N -->|ok| O[showAlert success]
    N -->|error| P[showAlert error]
    O --> Q[hideAddUserModal()]
    P --> Q
    Q --> R[refreshUsers()]
```

---

## 11. Accessibility Considerations

- Form fields have proper `label` elements with `for` attributes
- Required fields marked with asterisk (`*`)
- Error messages associated with form fields
- Modal can be closed with Escape key
- Sufficient color contrast for all text
- Focus management for keyboard navigation

---

## 12. Responsive Design

The modal and form follow the existing responsive patterns:

- Modal width: 90% on mobile, max 500px on desktop
- Form fields stack vertically on small screens
- Button layout adjusts for smaller screens
- Text sizes adjust for mobile viewports

---

## 13. Testing Considerations

### Unit Tests to Add

1. Test `showAddUserModal()` displays modal correctly
2. Test `hideAddUserModal()` hides modal and resets form
3. Test `validateAddUserForm()` validates user name
4. Test `submitAddUserForm()` makes correct API call
5. Test success response handling
6. Test error response handling
7. Test loading state during API call
8. Test form reset on modal close

### Integration Tests

1. Test complete add user flow from button click to user appearing in table
2. Test validation error display
3. Test parent password hash warning display
4. Test modal close on Escape key
5. Test modal close on outside click