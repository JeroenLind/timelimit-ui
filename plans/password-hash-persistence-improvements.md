# Password Hash Persistence Improvements - Implementation Plan

## Overview

This plan outlines improvements to the password hash persistence system in the TimeLimit UI dashboard. The current implementation stores `parent_password_second_hash` in both session and database, but there are opportunities for enhancement in data integrity, error handling, and maintainability.

## Current State Analysis

### Existing Functions

#### `get_parent_password_hash(db, device_auth_token)` - `database.py:1023-1039`
```python
def get_parent_password_hash(db: Database, device_auth_token: str) -> Optional[str]:
    """Get the parent password hash for a device auth token."""
    with db._lock:
        conn = db.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT parent_password_second_hash FROM families WHERE device_auth_token = ?', (device_auth_token,))
        row = cursor.fetchone()
        return row['parent_password_second_hash'] if row else None
```

#### `upsert_family_password_hash(db, device_auth_token, parent_password_second_hash)` - `database.py:1067-1126`
- Handles both INSERT and UPDATE cases
- Creates placeholder mail value (`pending@unknown`) when inserting new family record
- Returns `True` on success

### Usage Locations
1. `restore_session_from_persistence()` - Session restoration on app restart
2. `session_status()` - Session status API endpoint
3. `post_set_parent_password()` - Set parent password page
4. `post_create_family()` - Family creation flow
5. `post_login_as_parent()` - Login as parent flow
6. `api_sign_in_into_family()` - API sign-in endpoint

## Proposed Improvements

### 1. Add Hash Validation Function

**Purpose:** Validate that stored hashes are in correct bcrypt format before use.

**Implementation:**
```python
def validate_password_hash(password_hash: str) -> bool:
    """Validate that a password hash is in correct bcrypt format.
    
    Args:
        password_hash: The hash to validate.
        
    Returns:
        True if valid bcrypt hash, False otherwise.
    """
    if not password_hash:
        return False
    
    # Check for valid bcrypt prefixes
    valid_prefixes = ('$2a$', '$2b$', '$2y$')
    return password_hash.startswith(valid_prefixes)
```

**Location:** `database.py` after `get_parent_password_hash()`

### 2. Add Function to Get Family Record with Hash Validation

**Purpose:** Retrieve family record with validation that hash exists and is valid.

**Implementation:**
```python
def get_family_with_valid_hash(db: Database, device_auth_token: str) -> Optional[Dict[str, Any]]:
    """Get family record with validated parent password hash.
    
    Args:
        device_auth_token: The device auth token to look up.
        
    Returns:
        Family record with valid hash, or None if not found or invalid.
    """
    family = get_family(db, device_auth_token)
    if not family:
        return None
    
    hash_value = family.get('parent_password_second_hash')
    if not validate_password_hash(hash_value):
        logger.warning(
            "Invalid or missing parent password hash in family record",
            component="database",
            device_auth_token=device_auth_token[:8] + "..." if device_auth_token else None
        )
        return None
    
    return family
```

**Location:** `database.py` after `get_parent_password_hash()`

### 3. Improve `upsert_family_password_hash` with Better Placeholder Handling

**Current Issue:** Uses `pending@unknown` as placeholder mail, which could cause issues.

**Improvement:** Add parameter for optional mail value, or use a more descriptive placeholder.

**Implementation:**
```python
def upsert_family_password_hash(
    db: Database,
    device_auth_token: str,
    parent_password_second_hash: str,
    mail: Optional[str] = None
) -> bool:
    """Upsert the family's parent password hash.
    
    This function handles both INSERT and UPDATE cases:
    - If the family record exists, it updates the hash
    - If the family record doesn't exist, it creates a new record
    
    Args:
        db: Database instance.
        device_auth_token: The device auth token (primary key).
        parent_password_second_hash: The parent password hash to store.
        mail: Optional email address (uses placeholder if not provided).
        
    Returns:
        True if successful, False otherwise.
    """
    with db._lock:
        conn = db.get_connection()
        cursor = conn.cursor()
        
        # Try UPDATE first
        cursor.execute('''
            UPDATE families SET parent_password_second_hash = ? WHERE device_auth_token = ?
        ''', (parent_password_second_hash, device_auth_token))
        
        if cursor.rowcount > 0:
            conn.commit()
            logger.debug(
                "Parent password hash updated in existing family record",
                component="database",
                device_auth_token=device_auth_token[:8] + "..." if device_auth_token else None
            )
            return True
        
        # If no row was updated, try INSERT
        placeholder_mail = mail or "pending@unknown"
        cursor.execute('''
            INSERT INTO families (device_auth_token, mail, created_at, parent_password_second_hash)
            VALUES (?, ?, ?, ?)
        ''', (
            device_auth_token,
            placeholder_mail,
            datetime.now(timezone.utc).isoformat(),
            parent_password_second_hash
        ))
        
        conn.commit()
        logger.debug(
            "Parent password hash inserted in new family record",
            component="database",
            device_auth_token=device_auth_token[:8] + "..." if device_auth_token else None
        )
        return True
```

### 4. Add Function to Clear Password Hash

**Purpose:** Allow clearing the password hash when needed (e.g., logout, password reset).

**Implementation:**
```python
def clear_family_password_hash(db: Database, device_auth_token: str) -> bool:
    """Clear the family's parent password hash.
    
    Args:
        db: Database instance.
        device_auth_token: The device auth token to update.
        
    Returns:
        True if updated, False if family not found.
    """
    with db._lock:
        conn = db.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE families SET parent_password_second_hash = NULL WHERE device_auth_token = ?
        ''', (device_auth_token,))
        
        conn.commit()
        return cursor.rowcount > 0
```

**Location:** `database.py` after `upsert_family_password_hash()`

### 5. Add Function to Check if Hash Exists

**Purpose:** Quick check if a valid password hash exists for a device.

**Implementation:**
```python
def has_parent_password_hash(db: Database, device_auth_token: str) -> bool:
    """Check if a valid parent password hash exists for a device.
    
    Args:
        db: Database instance.
        device_auth_token: The device auth token to check.
        
    Returns:
        True if valid hash exists, False otherwise.
    """
    hash_value = get_parent_password_hash(db, device_auth_token)
    return hash_value is not None and validate_password_hash(hash_value)
```

**Location:** `database.py` after `clear_family_password_hash()`

### 6. Improve Session Restoration with Better Error Handling

**Current Issue:** Session restoration doesn't validate the hash before storing.

**Improvement:** Add validation and logging in `restore_session_from_persistence()`.

**Implementation:**
```python
# In app.py, restore_session_from_persistence()
if persisted_device_auth_token:
    db = get_database()
    parent_password_hash = get_parent_password_hash(db, persisted_device_auth_token)
    if parent_password_hash:
        # Validate hash format before storing in session
        from database import validate_password_hash
        if validate_password_hash(parent_password_hash):
            session['parent_password_second_hash'] = parent_password_hash
            logger.debug(
                "Parent password hash restored from database",
                component="session",
                device_auth_token=persisted_device_auth_token[:8] + "..."
            )
        else:
            logger.warning(
                "Invalid password hash format in database, not restoring to session",
                component="session",
                device_auth_token=persisted_device_auth_token[:8] + "..."
            )
```

### 7. Add Database Migration for Hash Validation

**Purpose:** Ensure all existing hashes are valid on database load.

**Implementation:**
```python
def _validate_existing_hashes(db: Database) -> int:
    """Validate all existing password hashes in the database.
    
    Returns:
        Number of invalid hashes found.
    """
    with db._lock:
        conn = db.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT device_auth_token, parent_password_second_hash FROM families')
        invalid_count = 0
        
        for row in cursor.fetchall():
            device_auth_token = row[0]
            hash_value = row[1]
            
            if hash_value and not validate_password_hash(hash_value):
                logger.warning(
                    "Invalid password hash found in database",
                    component="database",
                    device_auth_token=device_auth_token[:8] + "...",
                    hash_preview=hash_value[:20] + "..." if len(hash_value) > 20 else hash_value
                )
                invalid_count += 1
        
        return invalid_count
```

## Implementation Steps

### Phase 1: Core Database Functions (database.py)
1. Add `validate_password_hash()` function
2. Add `get_family_with_valid_hash()` function
3. Add `clear_family_password_hash()` function
4. Add `has_parent_password_hash()` function
5. Update `upsert_family_password_hash()` with optional mail parameter

### Phase 2: Session Management Improvements (app.py)
1. Update `restore_session_from_persistence()` with hash validation
2. Update `session_status()` to use new validation functions
3. Add logging for hash validation failures

### Phase 3: Testing
1. Add unit tests for `validate_password_hash()`
2. Add unit tests for `get_family_with_valid_hash()`
3. Add unit tests for `clear_family_password_hash()`
4. Add unit tests for `has_parent_password_hash()`
5. Update existing tests for modified `upsert_family_password_hash()`

### Phase 4: Documentation
1. Update `docs/password-hash-and-integrity.md` with new functions
2. Add inline documentation for all new functions
3. Update API documentation if needed

## Test Cases

### `validate_password_hash()` Tests
- Valid `$2a$` hash returns `True`
- Valid `$2b$` hash returns `True`
- Valid `$2y$` hash returns `True`
- Invalid hash (wrong prefix) returns `False`
- Empty string returns `False`
- `None` returns `False`
- Too short string returns `False`

### `get_family_with_valid_hash()` Tests
- Returns family when valid hash exists
- Returns `None` when family doesn't exist
- Returns `None` when hash is invalid
- Returns `None` when hash is `None`

### `clear_family_password_hash()` Tests
- Returns `True` when hash is cleared
- Returns `False` when family doesn't exist
- Verifies hash is `None` after clearing

### `has_parent_password_hash()` Tests
- Returns `True` when valid hash exists
- Returns `False` when family doesn't exist
- Returns `False` when hash is invalid
- Returns `False` when hash is `None`

## Risk Assessment

### Low Risk
- Adding new validation functions
- Adding new helper functions
- Adding tests

### Medium Risk
- Modifying `upsert_family_password_hash()` signature (adding optional parameter)
- Updating session restoration logic

### Mitigation
- All changes are backward compatible (optional parameters)
- Comprehensive test coverage
- Detailed logging for debugging

## Success Criteria
1. All new functions have 100% test coverage
2. All existing tests continue to pass
3. Hash validation prevents invalid data from being used
4. Better error messages and logging for debugging
5. Documentation is complete and accurate