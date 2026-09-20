# Add User to Family - UI Design

## Overview

This document describes the user interface design for the "Add User to Family" feature.

## Modal Dialog Design

### Modal Structure

```html
<div id="add-user-modal" class="modal">
    <div class="modal-content">
        <div class="modal-header">
            <h2 id="rule-form-title">Add User</h2>
            <button class="close-btn" onclick="hideAddUserModal()">&times;</button>
        </div>
        <div class="modal-body">
            <!-- Password Warning -->
            <div id="add-user-password-warning" class="warning-banner" style="display: none;">
                <strong>Warning:</strong> Parent password hash is required for device removal operations.
            </div>
            
            <!-- Form -->
            <form id="add-user-form">
                <div class="form-group">
                    <label for="add-user-name">User Name *</label>
                    <input type="text" id="add-user-name" name="name" required>
                    <div id="add-user-name-error" class="error-message" style="display: none;"></div>
                </div>
                
                <div class="form-group">
                    <label for="add-user-device-name">Device Name</label>
                    <input type="text" id="add-user-device-name" name="deviceName" placeholder="Optional">
                </div>
                
                <div class="form-group">
                    <label for="add-user-device-model">Device Model</label>
                    <input type="text" id="add-user-device-model" name="deviceModel" placeholder="Optional">
                </div>
            </form>
        </div>
        <div class="modal-footer">
            <button type="button" class="secondary-btn" onclick="hideAddUserModal()">Cancel</button>
            <button type="button" class="primary-btn" id="add-user-submit-btn" onclick="submitAddUserForm()">
                Add
            </button>
        </div>
    </div>
</div>
```

## Form Fields

### User Name (Required)

- **Type**: Text input
- **Validation**: Required, minimum 1 character
- **Placeholder**: "Child's name"
- **Error Message**: "User name is required"

### Device Name (Optional)

- **Type**: Text input
- **Validation**: None
- **Placeholder**: "Device name (optional)"

### Device Model (Optional)

- **Type**: Text input
- **Validation**: None
- **Placeholder**: "Device model (optional)"

## Password Warning Banner

Shown when parent password hash is not set:

```html
<div class="warning-banner">
    <strong>Warning:</strong> Parent password hash is required for device removal operations.
</div>
```

**Style**: Orange background (#ff9800), white text

## Action Buttons

### Cancel Button

- **Class**: `secondary-btn`
- **Action**: Closes modal, resets form
- **Icon**: None

### Add Button

- **Class**: `primary-btn`
- **States**:
  - Normal: Blue background
  - Loading: Disabled, shows "Adding..."
- **Action**: Submits form via API

## Validation

### Client-Side Validation

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

### Server-Side Validation

The API validates:
1. User name is present
2. User is authenticated
3. Parent password hash is set

## Error Handling

### Validation Errors

```html
<div id="add-user-name-error" class="error-message" style="display: block; color: #f44336;">
    User name is required
</div>
```

### API Errors

Displayed via toast notification:
- "Failed to add user: [error message]"

## Success Flow

1. Form submitted successfully
2. Toast: "User added successfully"
3. Modal closes
4. Users table refreshes
5. Form resets

## Accessibility

- All form fields have associated labels
- Error messages are announced by screen readers
- Modal can be closed with Escape key
- Focus is managed appropriately

## Mobile Responsiveness

- Modal takes full width on small screens
- Form fields stack vertically
- Buttons are full width on mobile

## CSS Classes

| Class | Purpose |
|-------|---------|
| `.modal` | Modal overlay |
| `.modal-content` | Modal container |
| `.modal-header` | Header section |
| `.modal-body` | Form content |
| `.modal-footer` | Action buttons |
| `.form-group` | Form field wrapper |
| `.warning-banner` | Warning message |
| `.error-message` | Error message |
| `.primary-btn` | Primary action button |
| `.secondary-btn` | Secondary action button |
| `.loading` | Loading state |

## JavaScript Functions

### showAddUserModal()

Shows the add user modal and checks password hash status.

### hideAddUserModal()

Hides the modal and resets the form.

### validateAddUserForm()

Validates the form inputs.

### submitAddUserForm()

Submits the form to the API.

### resetAddUserForm()

Resets form fields and error messages.