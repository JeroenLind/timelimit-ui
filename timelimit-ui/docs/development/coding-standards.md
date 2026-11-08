# Coding Standards

This document outlines the coding standards and conventions used in Dashboard V2.

## Python Standards

### Code Style

- **Indentation**: 4 spaces (no tabs)
- **Line Length**: Maximum 100 characters
- **Naming Convention**: snake_case for functions/variables, PascalCase for classes
- **Docstrings**: Google-style docstrings for all public functions

### Example

```python
def calculate_time_difference(start_time: str, end_time: str) -> int:
    """Calculate the time difference in minutes.
    
    Args:
        start_time: Start time in HH:MM format.
        end_time: End time in HH:MM format.
        
    Returns:
        Time difference in minutes.
        
    Raises:
        ValueError: If time format is invalid.
    """
    # Implementation
    pass
```

### Type Hints

Use type hints for all function parameters and return values:

```python
from typing import Optional, List, Dict, Any

def get_user_by_id(db: Database, user_id: str) -> Optional[Dict[str, Any]]:
    ...
```

### Imports

Organize imports in this order:
1. Standard library imports
2. Third-party imports
3. Local imports

```python
import os
import sqlite3
from datetime import datetime
from typing import Optional, List

from flask import Flask, jsonify, request

from database import Database
from utils.logging import get_logger
```

---

## JavaScript Standards

### Code Style

- **Indentation**: 2 spaces
- **Line Length**: Maximum 100 characters
- **Naming Convention**: camelCase for variables/functions, PascalCase for constructors
- **Semicolons**: Required

### Example

```javascript
/**
 * Format days bitmask to day names.
 * @param {number} days - Days bitmask (bit 0=Monday, bit 6=Sunday)
 * @returns {string} Comma-separated day names
 */
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

### Async/Await

Use async/await for asynchronous operations:

```javascript
async function fetchUsers() {
    try {
        const response = await fetch('/api/dashboard/users');
        const data = await response.json();
        return data.users;
    } catch (error) {
        console.error('Failed to fetch users:', error);
        throw error;
    }
}
```

### Error Handling

Always handle errors appropriately:

```javascript
try {
    const result = await apiCall();
    if (result.status === 'ok') {
        showAlert('Success!', 'success');
    } else {
        showAlert('Error: ' + result.error, 'error');
    }
} catch (error) {
    showAlert('Error: ' + error.message, 'error');
}
```

---

## HTML/CSS Standards

### HTML

- Use semantic HTML5 elements
- Include proper labels for form inputs
- Use ARIA attributes for accessibility

```html
<form id="user-form">
    <div class="form-group">
        <label for="user-name">User Name</label>
        <input type="text" id="user-name" name="name" required>
    </div>
</form>
```

### CSS

- Use BEM naming convention
- Keep CSS specific to components
- Use CSS variables for colors and spacing

```css
:root {
    --color-primary: #2196f3;
    --color-success: #4caf50;
    --color-error: #f44336;
    --spacing: 8px;
}

.form-group {
    margin-bottom: var(--spacing);
}

.form-group label {
    display: block;
    margin-bottom: 4px;
}
```

---

## Database Standards

### SQL Style

- Use uppercase for SQL keywords
- Use meaningful table and column names
- Include foreign key constraints

```sql
CREATE TABLE users (
    id TEXT PRIMARY KEY,
    device_auth_token TEXT NOT NULL,
    name TEXT,
    FOREIGN KEY (device_auth_token) REFERENCES families(device_auth_token)
);
```

### Migrations

Always create migrations for schema changes:

```python
def _run_migrations(self) -> None:
    """Run database migrations for existing databases."""
    with self._lock:
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Check if column exists
        cursor.execute("PRAGMA table_info(users)")
        columns = [row[1] for row in cursor.fetchall()]
        
        if 'new_column' not in columns:
            cursor.execute('ALTER TABLE users ADD COLUMN new_column TEXT')
            conn.commit()
```

---

## Logging Standards

### Log Levels

| Level | Usage |
|-------|-------|
| DEBUG | Detailed debugging information |
| INFO | General information |
| WARNING | Warning conditions |
| ERROR | Error events |

### Structured Logging

Use structured logging with context:

```python
logger.info(
    "User created successfully",
    user_id=user_id,
    device_auth_token=device_auth_token[:8] + '...',
    request_id=request_id
)
```

### Log Format

JSON format with the following fields:
- `timestamp`: ISO 8601 timestamp
- `level`: Log level
- `event`: Event type
- `component`: Component name
- `request_id`: Request identifier

---

## Testing Standards

### Test Naming

- Test functions: `test_<function>_<condition>`
- Test classes: `Test<ClassName>`

```python
def test_create_user_success():
    ...

def test_create_user_missing_name():
    ...
```

### Test Structure

```python
def test_user_creation(client, db):
    """Test user creation with valid data."""
    # Arrange
    user_data = {'name': 'Test User'}
    
    # Act
    response = client.post('/api/users', json=user_data)
    
    # Assert
    assert response.status_code == 201
    assert response.get_json()['status'] == 'ok'
```

### Fixtures

Use fixtures for test setup:

```python
@pytest.fixture
def authenticated_client(client):
    """Client with authenticated session."""
    with client.session_transaction() as sess:
        sess['device_auth_token'] = 'test_token'
    return client
```

---

## Security Standards

### Password Hashing

- Use bcrypt with `$2a$` prefix
- Minimum 8 characters
- Generate both first and second hashes

```python
from crypto_utils import generate_family_hashes

password_data = generate_family_hashes(password)
# Returns: {'hash': '...', 'secondHash': '...', 'secondSalt': '...'}
```

### Input Validation

Always validate user input:

```python
# Email validation
email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
if not re.match(email_pattern, mail):
    return error('Invalid email format')

# Password length
if len(password) < 8:
    return error('Password must be at least 8 characters')
```

### SQL Injection Prevention

Use parameterized queries:

```python
# Good
cursor.execute('SELECT * FROM users WHERE id = ?', (user_id,))

# Bad
cursor.execute(f'SELECT * FROM users WHERE id = {user_id}')
```

---

## Documentation Standards

### Docstrings

Use Google-style docstrings:

```python
def process_user_data(data: dict) -> dict:
    """Process user data and return result.
    
    Args:
        data: User data dictionary.
        
    Returns:
        Processed data dictionary.
        
    Raises:
        ValueError: If data is invalid.
    """
    ...
```

### API Documentation

Document all API endpoints with:
- Endpoint path and method
- Request body schema
- Response schema
- Error responses

---

## Git Standards

### Commit Messages

Use conventional commit format:
```
feat: Add new user creation endpoint
fix: Resolve password validation error
docs: Update API documentation
test: Add tests for time limit rules
refactor: Simplify sync manager logic
```

### Branch Naming

- Feature branches: `feature/<description>`
- Bug fixes: `fix/<description>`
- Documentation: `docs/<description>`

---

## Code Review Checklist

- [ ] Code follows style guidelines
- [ ] Type hints are used
- [ ] Docstrings are present
- [ ] Tests are written and passing
- [ ] Security considerations addressed
- [ ] Error handling is appropriate
- [ ] Logging is adequate
- [ ] Documentation is updated