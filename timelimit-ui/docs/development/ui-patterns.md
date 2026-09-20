# UI Patterns

This document describes the UI patterns and conventions used in Dashboard V2.

## Modal Dialogs

### Modal Structure

```html
<div id="modal-id" class="modal" style="display: none;">
    <div class="modal-content">
        <div class="modal-header">
            <h2 id="modal-title">Title</h2>
            <button class="close-btn" onclick="hideModal()">&times;</button>
        </div>
        <div class="modal-body">
            <!-- Form content -->
        </div>
        <div class="modal-footer">
            <button onclick="hideModal()">Cancel</button>
            <button class="primary-btn">Submit</button>
        </div>
    </div>
</div>
```

### Modal CSS Classes

| Class | Description |
|-------|-------------|
| `.modal` | Modal overlay container |
| `.modal-content` | Modal content box |
| `.modal-header` | Header section with title |
| `.modal-body` | Main content area |
| `.modal-footer` | Action buttons area |
| `.primary-btn` | Primary action button |
| `.secondary-btn` | Secondary action button |

### Modal JavaScript Functions

```javascript
// Show modal
function showModal() {
    document.getElementById('modal-id').style.display = 'block';
    document.getElementById('modal-id').style.opacity = '1';
}

// Hide modal
function hideModal() {
    document.getElementById('modal-id').style.display = 'none';
    document.getElementById('modal-id').style.opacity = '0';
}
```

---

## Alert Messages

### Alert Container

```html
<div id="alert-container"></div>
```

### Alert Types

| Type | Class | Color |
|------|-------|-------|
| Success | `alert success` | Green (#4caf50) |
| Error | `alert error` | Red (#f44336) |
| Warning | `alert warning` | Orange (#ff9800) |
| Info | `alert info` | Blue (#2196f3) |

### Alert HTML Structure

```html
<div class="alert success">
    Message text
    <button class="alert-close" onclick="this.parentElement.remove()">&times;</button>
</div>
```

### Alert JavaScript Function

```javascript
function showAlert(message, type) {
    const container = document.getElementById('alert-container');
    if (!container) return;
    
    const alert = document.createElement('div');
    alert.className = 'alert ' + type;
    alert.innerHTML = message + 
        '<button class="alert-close" onclick="this.parentElement.remove()">&times;</button>';
    
    container.appendChild(alert);
    
    // Auto-remove after 5 seconds
    setTimeout(() => {
        if (alert.parentElement) {
            alert.remove();
        }
    }, 5000);
}
```

---

## Forms

### Form Validation

```javascript
function validateForm() {
    const field = document.getElementById('field-id').value;
    const errorElement = document.getElementById('field-error');
    
    if (!field) {
        errorElement.style.display = 'block';
        errorElement.textContent = 'Field is required';
        return false;
    }
    
    errorElement.style.display = 'none';
    return true;
}
```

### Form Submission with Loading State

```javascript
async function submitForm() {
    const btn = document.getElementById('submit-btn');
    
    // Show loading state
    btn.classList.add('loading');
    btn.textContent = 'Submitting...';
    
    try {
        const response = await fetch('/api/endpoint', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(formData)
        });
        const data = await response.json();
        
        if (data.status === 'ok') {
            showAlert('Success!', 'success');
        } else {
            showAlert('Error: ' + data.error, 'error');
        }
    } catch (error) {
        showAlert('Error: ' + error.message, 'error');
    } finally {
        btn.classList.remove('loading');
        btn.textContent = 'Submit';
    }
}
```

---

## Tables

### Table Structure

```html
<div class="db-table-wrapper">
    <table class="dashboard-table">
        <thead>
            <tr>
                <th>Column 1</th>
                <th>Column 2</th>
                <th>Actions</th>
            </tr>
        </thead>
        <tbody id="table-body">
            <!-- Rows will be inserted here -->
        </tbody>
    </table>
</div>
```

### Empty State

```html
<p style="text-align: center; color: #666; padding: 20px;">No items found</p>
```

### Row with Actions

```html
<tr data-item-id="123">
    <td>Item Name</td>
    <td>Item Value</td>
    <td>
        <button class="edit-btn" onclick="editItem('123')">✏️</button>
        <button class="delete-btn" onclick="deleteItem('123')">🗑️</button>
    </td>
</tr>
```

---

## Confirmation Dialogs

### Confirm Function

```javascript
function confirmAction(message) {
    return confirm(message);
}

// Example usage
async function confirmDelete(itemId, itemName) {
    const confirmed = confirm(
        'Delete "' + escapeHtml(itemName) + '"?\n\n' +
        'This action cannot be undone.\n\n' +
        'Are you sure you want to continue?'
    );
    
    if (!confirmed) return;
    
    // Proceed with deletion
    await deleteItem(itemId);
}
```

---

## Data Formatting

### Date/Time Formatting

```javascript
function formatDate(timestamp) {
    if (!timestamp) return 'N/A';
    return new Date(timestamp).toLocaleString();
}
```

### Days Bitmask Formatting

```javascript
function formatDays(days) {
    const dayNames = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
    const selectedDays = [];
    
    for (let i = 0; i < 7; i++) {
        if (days & (1 << i)) {
            selectedDays.push(dayNames[i]);
        }
    }
    
    return selectedDays.length === 7 ? 'Every day' : selectedDays.join(', ');
}
```

### Duration Formatting

```javascript
function formatDuration(minutes) {
    const hours = Math.floor(minutes / 60);
    const mins = minutes % 60;
    
    if (hours > 0) {
        return hours + 'h' + (mins > 0 ? mins + 'm' : '');
    }
    return mins + 'm';
}
```

---

## Protection Level Labels

```javascript
function getProtectionLevelLabel(level) {
    const protectionLevels = {
        0: 'None',
        1: 'Simple Device Admin',
        2: 'Password Device Admin',
        3: 'Device Owner'
    };
    return protectionLevels[level] || 'Unknown';
}
```

---

## HTML Escaping

```javascript
function escapeHtml(str) {
    if (!str) return 'N/A';
    return String(str)
        .replace(/&/g, '&')
        .replace(/</g, '<')
        .replace(/>/g, '>')
        .replace(/"/g, '"')
        .replace(/'/g, '&#039;');
}
```

---

## Event Handling

### SSE (Server-Sent Events) Connection

```javascript
function connectSSE() {
    if (!isAuthenticated) return;
    
    const eventSource = new EventSource('/api/dashboard/stream');
    
    eventSource.addEventListener('sync_complete', function(event) {
        console.log('Sync complete:', event.data);
        loadUsers();
        loadDevices();
    });
    
    eventSource.addEventListener('error', function(event) {
        console.error('SSE error:', event);
        setTimeout(() => {
            connectSSE();
        }, 5000);
    });
}
```

### Keyboard Events

```javascript
// Close modal on Escape key
document.addEventListener('keydown', function(event) {
    if (event.key === 'Escape') {
        const modal = document.getElementById('modal-id');
        if (modal && modal.style.display === 'block') {
            hideModal();
        }
    }
});
```

### Click Outside to Close

```javascript
document.getElementById('modal-id')?.addEventListener('click', function(event) {
    if (event.target === this) {
        hideModal();
    }
});
```

---

## Loading States

### Button Loading

```css
.loading {
    opacity: 0.7;
    cursor: wait;
}
```

```javascript
btn.classList.add('loading');
// ... operation
btn.classList.remove('loading');
```

---

## Responsive Design

### Time Cell Styling

```css
.time-cell {
    font-family: monospace;
    font-size: 12px;
    color: #888;
}
```

### Device Row Highlighting

```css
.device-current {
    background-color: rgba(76, 175, 80, 0.1);
}
```

---

## Accessibility

### ARIA Labels

```html
<button aria-label="Delete item" onclick="deleteItem()">🗑️</button>
```

### Focus Management

```javascript
// After modal close, focus back to trigger
document.getElementById('trigger-btn').focus();
```

---

## Best Practices

1. **Always escape HTML** when inserting user data into the DOM
2. **Use async/await** for API calls with proper error handling
3. **Show loading states** during async operations
4. **Provide user feedback** via alerts and status messages
5. **Handle errors gracefully** with user-friendly messages
6. **Clean up SSE connections** when component unmounts
7. **Use semantic HTML** for better accessibility