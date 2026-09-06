# Device Removal Data Flow Overview

This document provides a comprehensive overview of all data required for device removal and tracks when/where each piece of data is available and persisted throughout the entire flow: family creation → sign-in → sync → device removal.

## Data Required for Device Removal

To successfully remove a device from a family, the following data must be available:

| Data Item | Description | Required For |
|-----------|-------------|--------------|
| `device_auth_token` | Authentication token for the family | Server authentication |
| `parent_user_id` | ID of the parent user | Server authorization |
| `parent_password_second_hash` | Bcrypt hash of parent's second password | Server authorization |
| `device_id` | ID of the device to remove | Device identification |
| `own_device_id` | ID of the current device | Prevent self-removal |

---

## Complete Data Flow

### Phase 1: Family Creation

#### Step 1.1: Send Mail Login Code
**Data Available:**
- `mail` (user's email)

**Data Generated:**
- `mail_login_token` (temporary token for verification)

**Persistence:**
- Stored in session: `session['mail_login_token']`

#### Step 1.2: Sign In by Mail Code
**Data Available:**
- `mail_login_token` (from session)
- `received_code` (3-word passphrase from email)

**Data Generated:**
- `mail_auth_token` (authentication token for family operations)

**Persistence:**
- Stored in session: `session['mail_auth_token']`

#### Step 1.3: Create Family
**Data Available:**
- `mail_auth_token` (from session)
- `password` (user's password)
- `parent_name`, `device_name`, `time_zone`, `device_model`

**Data Generated:**
- `password_data` = `{hash, secondHash, secondSalt}` (from `generate_family_hashes()`)
- `device_auth_token` (family authentication token)
- `own_device_id` (current device ID)
- `parent_user_id` (extracted from server response)

**Persistence:**
- Session: `session['device_auth_token']`
- Session: `session['own_device_id']`
- Session: `session['parent_user_id']`
- Session: `session['parent_password_second_hash']` (from `password_data.secondHash`)
- Database: `upsert_family_password_hash(db, device_auth_token, secondHash)`
- File: `set_persisted_device_auth_token(device_auth_token)`
- File: `set_persisted_own_device_id(own_device_id)`

---

### Phase 2: Sign In to Family (Alternative Flow)

#### Step 2.1: Sign In Into Family
**Data Available:**
- `mail_auth_token` (from session)
- `parent_password_second_hash` (optional, for device removal)

**Data Generated:**
- `device_auth_token` (family authentication token)
- `own_device_id` (current device ID)
- `parent_user_id` (extracted from server response)

**Persistence:**
- Session: `session['device_auth_token']`
- Session: `session['own_device_id']`
- Session: `session['parent_user_id']`
- Session: `session['parent_password_second_hash']` (if provided)
- Database: `store_auth_token(db, 'device_auth_token', device_auth_token, own_device_id)`
- Database: `upsert_family_password_hash(db, device_auth_token, parent_password_second_hash)` (if provided)
- File: `set_persisted_device_auth_token(device_auth_token)`
- File: `set_persisted_own_device_id(own_device_id)`

---

### Phase 3: Session Restoration (On App Restart)

**Data Restored from:**
- File: `get_persisted_device_auth_token()` → `session['device_auth_token']`
- File: `get_persisted_own_device_id()` → `session['own_device_id']`
- Database: `get_parent_password_hash(db, device_auth_token)` → `session['parent_password_second_hash']`
- Database: `get_parent_user_id(db, device_auth_token)` → `session['parent_user_id']`

---

### Phase 4: Set Parent Password (Optional Step)

#### Step 4.1: Set Parent Password
**Data Available:**
- `password` (user's password)
- `device_auth_token` (from session)

**Data Generated:**
- `parent_password_second_hash` (bcrypt hash with rounds=12)

**Persistence:**
- Session: `session['parent_password_second_hash']`
- Database: `upsert_family_password_hash(db, device_auth_token, parent_password_second_hash)`

---

### Phase 5: Sync Data with Server

**Data Required:**
- `device_auth_token` (from session)
- `own_device_id` (from session)
- `server_url` (from config/persistence)

**Data Generated:**
- `sync_state` (sequence numbers, timestamps)
- `users`, `devices`, `categories`, `connected_devices` (from server)

**Persistence:**
- Database: `save_users()`, `save_categories()`, `save_connected_devices()`, `save_sync_state()`
- Database: `increment_sequence_number()`

---

### Phase 6: Device Removal

#### Step 6.1: Remove Device
**Data Required:**
- `device_auth_token` (from session or database)
- `parent_user_id` (from session or database)
- `parent_password_second_hash` (from session or database)
- `device_id` (from request body)
- `own_device_id` (from session - to prevent self-removal)

**Data Sent to Server:**
```json
{
  "deviceAuthToken": "<device_auth_token>",
  "parentUserId": "<parent_user_id>",
  "parentPasswordSecondHash": "<parent_password_second_hash>",
  "deviceId": "<device_id>"
}
```

**Note:** The `device_auth_token` is sent in the request body, NOT in the Authorization header.

---

## Data Persistence Summary

### Session Storage (Flask Session)
| Data Item | When Set | When Cleared |
|-----------|----------|--------------|
| `device_auth_token` | Family creation, sign-in | Session clear, logout |
| `own_device_id` | Family creation, sign-in | Session clear, logout |
| `parent_user_id` | Family creation, sign-in | Session clear, logout |
| `parent_password_second_hash` | Family creation, set-parent-password | Session clear, logout |
| `mail_auth_token` | Sign-in by mail code | After family creation/sign-in |
| `mail_login_token` | Send mail login code | After sign-in by mail code |

### Database Storage (SQLite)
| Table | Data Item | When Set | When Cleared |
|-------|-----------|----------|--------------|
| `families` | `parent_password_second_hash` | Family creation, set-parent-password | Family deletion |
| `devices` | `device_id`, `device_auth_token` | Device creation | Device removal |
| `auth_tokens` | `token_value`, `device_id` | Sign-in | Token expiration |
| `users` | `id`, `type` | Sync | N/A |
| `categories` | category data | Sync | N/A |
| `connected_devices` | device data | Sync | N/A |
| `sync_state` | sequence numbers | Sync | N/A |

### File Storage (JSON)
| File | Data Item | When Set | When Cleared |
|------|-----------|----------|--------------|
| `server_selection.json` | `server_url`, `server_key` | Server selection | N/A |
| `timelimit_ui_storage.json` | `device_auth_token`, `own_device_id` | Family creation, sign-in | Clear all |

---

## Critical Data Flow Points

### 1. Password Hash Generation
```
password → generate_family_hashes() → {hash, secondHash, secondSalt}
                                                                   |
                                                                   v
                                                      Used for:
                                                      - Server family creation (hash)
                                                      - Device removal (secondHash)
                                                      - Sync integrity (secondHash)
```

### 2. Device Auth Token Flow
```
Server response → session['device_auth_token'] → Database → File persistence
                                                                   |
                                                                   v
                                                      Used for:
                                                      - Server authentication
                                                      - Database lookups
                                                      - Session restoration
```

### 3. Parent User ID Flow
```
Server response (users.data[0].id) → session['parent_user_id'] → Database
                                                                   |
                                                                   v
                                                      Used for:
                                                      - Device removal authorization
                                                      - Database lookups
```

### 4. Parent Password Second Hash Flow
```
password_data.secondHash → session['parent_password_second_hash'] → Database
                                                                   |
                                                                   v
                                                      Used for:
                                                      - Device removal authorization
                                                      - Session restoration
                                                      - Sync integrity
```

---

## Common Issues and Troubleshooting

### Issue 1: Device Removal Returns 401 Unauthorized
**Possible Causes:**
1. `device_auth_token` is invalid or expired on the server
2. `parent_password_second_hash` doesn't match what the server expects
3. `parent_user_id` doesn't match the device's parent on the server

**Check:**
- Verify `device_auth_token` is present in session
- Verify `parent_password_second_hash` is present in session
- Check server logs for authentication failure details

### Issue 2: Parent Password Hash Not Stored
**Possible Causes:**
1. Family creation didn't include `secondHash` in `password_data`
2. `upsert_family_password_hash()` failed silently
3. Session restoration didn't find the hash in the database

**Check:**
- Verify `password_data` contains `secondHash` during family creation
- Check database for `parent_password_second_hash` in `families` table
- Verify `restore_session_from_persistence()` logs

### Issue 3: Device Removal Returns 400 "Parent password hash not set"
**Cause:**
- `parent_password_second_hash` is not in the session

**Check:**
- Verify `/set-parent-password` was called after family creation
- Check session contains `parent_password_second_hash`
- Verify database has the hash for the device_auth_token

---

## Key Code Locations

| Function | File | Lines | Purpose |
|----------|------|-------|---------|
| `generate_family_hashes()` | `crypto_utils.py` | 8-30 | Generate bcrypt hashes |
| `create_family()` | `auth_client.py` | 554-623 | Create family via API |
| `create_family_rest()` | `auth_client.py` | 625-692 | Create family via REST |
| `sign_in_into_family()` | `auth_client.py` | 694-760 | Sign in to existing family |
| `remove_device()` | `auth_client.py` | 1064-1125 | Remove device via API |
| `api_create_family()` | `app.py` | 713-842 | Handle family creation |
| `api_create_family_rest()` | `app.py` | 845-977 | Handle family creation (REST) |
| `api_sign_in_into_family()` | `app.py` | 980-1093 | Handle sign in |
| `api_dashboard_devices_remove()` | `app.py` | 2878-3038 | Handle device removal |
| `post_set_parent_password()` | `app.py` | 3067-3149 | Set parent password |
| `post_create_family()` | `app.py` | 1144-1419 | Handle family creation (form) |
| `post_login_as_parent()` | `app.py` | 1496-1720 | Handle login as parent |
| `restore_session_from_persistence()` | `app.py` | 101-180 | Restore session on restart |
| `upsert_family_password_hash()` | `database.py` | 1179-1239 | Store password hash |
| `get_parent_password_hash()` | `database.py` | 1123-1149 | Retrieve password hash |
| `get_parent_user_id()` | `database.py` | 1063-1078 | Retrieve parent user ID |

---

## Verification Checklist

Before attempting device removal, verify:

- [ ] `device_auth_token` is in session
- [ ] `parent_user_id` is in session
- [ ] `parent_password_second_hash` is in session
- [ ] `own_device_id` is in session (to prevent self-removal)
- [ ] `parent_password_second_hash` is in database for `device_auth_token`
- [ ] `parent_user_id` is in database for `device_auth_token`
- [ ] `device_auth_token` is persisted to file