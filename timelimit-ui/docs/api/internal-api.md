# Internal API Documentation

This document describes the internal API endpoints available in Dashboard V2.

## Authentication

### Session Status

**Endpoint**: `GET /api/session/status`

Returns the current session status including authentication state.

**Response**:
```json
{
    "authenticated": true,
    "server_url": "https://timeleap.org",
    "has_mail_auth_token": false,
    "has_device_auth_token": true,
    "device_auth_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "own_device_id": "device_123456",
    "has_parent_password_second_hash": true,
    "has_signing_key": true
}
```

---

## Server Selection

### Select Server

**Endpoint**: `POST /select-server`

Selects a server from the available options.

**Request Body**:
```json
{
    "server_key": "official"
}
```

**Response**:
```json
{
    "status": "ok",
    "server_url": "https://timeleap.org",
    "server_name": "Official TimeLimit Server",
    "server_key": "official"
}
```

---

## Sync Operations

### Sync Pull

**Endpoint**: `POST /api/sync/pull`

Triggers a manual sync with the TimeLimit server.

**Response**:
```json
{
    "status": "ok",
    "synced": true
}
```

---

## Dashboard API

### Get Users

**Endpoint**: `GET /api/dashboard/users`

Returns all users for the authenticated device.

**Response**:
```json
{
    "status": "ok",
    "count": 2,
    "users": [
        {
            "id": "user_123",
            "name": "Parent User",
            "type": "parent",
            "mail": "parent@example.com",
            "time_zone": "Europe/Amsterdam"
        },
        {
            "id": "user_456",
            "name": "Child User",
            "type": "child",
            "mail": null,
            "time_zone": "Europe/Amsterdam"
        }
    ]
}
```

### Get Devices

**Endpoint**: `GET /api/dashboard/devices`

Returns all devices for the authenticated device.

**Response**:
```json
{
    "status": "ok",
    "count": 2,
    "devices": [
        {
            "id": "device_123",
            "name": "Parent Phone",
            "model": "Pixel 7",
            "current_user_name": "Parent User",
            "current_protection_level": 2,
            "current_app_version": "226",
            "platform_type": "android",
            "platform_level": 33
        }
    ],
    "own_device_id": "device_123",
    "has_parent_password_second_hash": true
}
```

### Get Categories

**Endpoint**: `GET /api/dashboard/categories`

Returns all categories for the authenticated device.

**Response**:
```json
{
    "status": "ok",
    "count": 3,
    "categories": [
        {
            "id": "cat_001",
            "title": "Games",
            "blocked_times": "[]",
            "extra_time": 0
        }
    ]
}
```

### Get Time Limit Rules

**Endpoint**: `GET /api/dashboard/time-limit-rules`

Returns all time limit rules for the authenticated device.

**Response**:
```json
{
    "status": "ok",
    "count": 1,
    "rules": [
        {
            "id": "rule_abc123",
            "user_id": "user_456",
            "category_id": "cat_001",
            "rule": {
                "type": 0,
                "startTime": "18:00",
                "endTime": "21:00",
                "days": 127,
                "limitMinutes": 120
            }
        }
    ]
}
```

### Create Time Limit Rule

**Endpoint**: `POST /api/dashboard/time-limit-rules`

Creates a new time limit rule.

**Request Body**:
```json
{
    "userId": "user_456",
    "categoryId": "cat_001",
    "rule": {
        "type": 0,
        "startTime": "18:00",
        "endTime": "21:00",
        "days": 127,
        "limitMinutes": 120
    }
}
```

**Response**:
```json
{
    "status": "ok",
    "ruleId": "rule_abc123"
}
```

### Update Time Limit Rule

**Endpoint**: `PUT /api/dashboard/time-limit-rules/{ruleId}`

Updates an existing time limit rule.

**Request Body**:
```json
{
    "rule": {
        "startTime": "17:00",
        "endTime": "20:00",
        "limitMinutes": 90
    }
}
```

**Response**:
```json
{
    "status": "ok",
    "message": "Rule updated successfully"
}
```

### Delete Time Limit Rule

**Endpoint**: `DELETE /api/dashboard/time-limit-rules/{ruleId}`

Deletes a time limit rule.

**Response**:
```json
{
    "status": "ok",
    "message": "Rule deleted successfully"
}
```

---

## User Management

### Add User to Family

**Endpoint**: `POST /api/dashboard/users/add`

Adds a new user (child) to the family.

**Request Body**:
```json
{
    "name": "Child Name",
    "deviceName": "Child's Tablet",
    "deviceModel": "Samsung Galaxy Tab"
}
```

**Response**:
```json
{
    "status": "ok",
    "userId": "user_789",
    "deviceAuthToken": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "ownDeviceId": "device_789"
}
```

---

## Device Management

### Remove Device

**Endpoint**: `POST /api/dashboard/devices/remove`

Removes a device from the family.

**Request Body**:
```json
{
    "deviceId": "device_to_remove"
}
```

**Response**:
```json
{
    "status": "ok",
    "message": "Device removed successfully"
}
```

**Note**: Requires `parent_password_second_hash` to be set in session.

---

## Authentication Token Management

### Create Add Device Token

**Endpoint**: `POST /api/parent/create-add-device-token`

Creates a token for adding a new device.

**Request Body**:
```json
{
    "deviceAuthToken": "parent_device_token",
    "parentPasswordSecondHash": "bcrypt_hash"
}
```

**Response**:
```json
{
    "status": "ok",
    "token": "register_token",
    "deviceId": "device_id"
}
```

### Add Device

**Endpoint**: `POST /api/child/add-device`

Adds a child device to the family.

**Request Body**:
```json
{
    "registerToken": "register_token",
    "deviceName": "Child's Device",
    "deviceModel": "Device Model"
}
```

**Response**:
```json
{
    "status": "ok",
    "deviceAuthToken": "child_device_token",
    "ownDeviceId": "device_id"
}
```

---

## Session Management

### Clear Session

**Endpoint**: `POST /api/session/clear`

Clears the current session and persisted auth tokens.

**Response**:
```json
{
    "status": "ok"
}
```

---

## Password Management

### Regenerate Hash

**Endpoint**: `POST /api/auth/regenerate-hash`

Regenerates password hash from password and existing salt.

**Request Body**:
```json
{
    "mail": "parent@example.com",
    "password": "new_password"
}
```

**Response**:
```json
{
    "status": "ok",
    "secondHash": "bcrypt_hash",
    "hash": "bcrypt_hash",
    "secondSalt": "salt_value"
}
```

### Set Parent Password

**Endpoint**: `POST /set-parent-password`

Sets the parent password hash for device removal.

**Form Data**:
- `password`: New password (will be hashed)
- `parentPasswordSecondHash`: Direct hash input (alternative to password)

**Response**: Redirect to dashboard on success.

---

## Backup and Restore

### Create Backup

**Endpoint**: `POST /api/auth/backup`

Creates a backup of auth tokens.

**Response**:
```json
{
    "status": "ok",
    "backup_successful": true,
    "device_auth_token": "token_value",
    "own_device_id": "device_id",
    "has_device_auth_token": true,
    "has_own_device_id": true
}
```

### Restore Backup

**Endpoint**: `POST /api/auth/restore`

Restores auth tokens from backup.

**Response**:
```json
{
    "status": "ok",
    "restore_successful": true,
    "device_auth_token": "token_value",
    "own_device_id": "device_id"
}
```

### Clear Backup

**Endpoint**: `POST /api/auth/clear-backup`

Clears the auth token backup file.

**Response**:
```json
{
    "status": "ok",
    "cleared": true
}
```

---

## Utility Endpoints

### Clear All Data

**Endpoint**: `POST /api/clear-all`

Clears all data from the dashboard.

**Response**:
```json
{
    "status": "ok",
    "tables_cleared": {
        "time_limit_rules": 5,
        "connected_devices": 2,
        "categories": 3,
        "sync_state": 1,
        "users": 2,
        "auth_tokens": 3,
        "devices": 2,
        "families": 1,
        "server_checks": 10
    },
    "message": "All data cleared successfully",
    "duration_ms": 150
}
```

### Clear Server Checks

**Endpoint**: `POST /api/clear-server-checks`

Clears all server check records.

**Response**:
```json
{
    "status": "ok",
    "rows_deleted": 10,
    "message": "Server checks cleared successfully (10 records removed)"
}
```

### Health Check

**Endpoint**: `GET /health`

Returns the health status of the application.

**Response**:
```json
{
    "status": "healthy"
}
```

---

## Time Checker

### Get Status

**Endpoint**: `GET /api/timechecker/status`

Gets the current server check status.

**Response**:
```json
{
    "success": true,
    "server_time": 1234567890123,
    "error_code": null,
    "error_message": null,
    "timestamp": 1234567890123,
    "attempts": 1
}
```

### Get History

**Endpoint**: `GET /api/timechecker/history?limit=10`

Gets historical server check results.

**Response**:
```json
{
    "checks": [],
    "total": 0
}
```

---

## Error Responses

All endpoints may return error responses:

```json
{
    "status": "error",
    "error": "Error message",
    "error_code": "error_code"
}
```

### Common Error Codes

| Code | Description |
|------|-------------|
| `unauthorized` | Not authenticated |
| `validation` | Validation error |
| `not_found` | Resource not found |
| `server_error` | Internal server error |
| `timeout` | Request timeout |
| `unreachable` | Server unreachable |