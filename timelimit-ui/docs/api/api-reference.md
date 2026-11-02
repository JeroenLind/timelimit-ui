# API Reference

Complete reference for Dashboard V2 API endpoints.

## Authentication Endpoints

### POST /api/auth/send-mail-login-code

Send a mail login code to the specified email.

**Request Body**:
```json
{
    "mail": "user@example.com",
    "locale": "en"
}
```

**Response**:
```json
{
    "status": "ok",
    "mailLoginToken": "token_string"
}
```

---

### POST /api/auth/sign-in-by-mail-code

Sign in using a mail login token and verification code.

**Request Body**:
```json
{
    "mailLoginToken": "token_string",
    "receivedCode": "word1 word2 word3"
}
```

**Response**:
```json
{
    "status": "ok",
    "mailAuthToken": "auth_token"
}
```

---

### POST /api/auth/sign-in-into-family

Sign in to an existing family.

**Request Body**:
```json
{
    "mailAuthToken": "auth_token",
    "parentPasswordSecondHash": "hash",
    "deviceName": "Device Name",
    "deviceModel": "Device Model",
    "clientLevel": 7
}
```

**Request Fields:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `mailAuthToken` | string | Yes | Mail auth token from sign-in-by-mail-code |
| `parentPasswordSecondHash` | string | No | Parent password second hash for device removal operations |
| `deviceName` | string | No | Name for the parent's device |
| `deviceModel` | string | No | Model of the parent's device |
| `clientLevel` | integer | No | Client level/version (typically 7) |

**Response**:
```json
{
    "status": "ok",
    "deviceAuthToken": "device_token",
    "ownDeviceId": "device_id"
}
```

**Session Behavior:**
- On successful sign-in, `device_auth_token` and `own_device_id` are stored in the session
- If `parentPasswordSecondHash` is provided, it is also stored in the session
- The stored `parent_password_second_hash` is required for subsequent operations like adding users to the family

**Note:** The `clientLevel` parameter is required by the TimeLimit server to properly identify the client making the request. The value `7` matches the Android app's `ClientDataStatus.CLIENT_LEVEL_VALUE`.

---

### POST /api/auth/create-family

Create a new family.

**Request Body**:
```json
{
    "mailAuthToken": "auth_token",
    "parentPassword": {
        "hash": "bcrypt_hash",
        "secondHash": "bcrypt_hash",
        "secondSalt": "salt",
        "encrypted": false
    },
    "parentDevice": {
        "model": "Device Model"
    },
    "deviceName": "Device Name",
    "timeZone": "Europe/Amsterdam",
    "parentName": "Parent Name",
    "locale": "en"
}
```

**Response**:
```json
{
    "status": "ok",
    "deviceAuthToken": "device_token",
    "ownDeviceId": "device_id"
}
```

---

### POST /api/auth/regenerate-hash

Regenerate password hash from password.

**Request Body**:
```json
{
    "mail": "user@example.com",
    "password": "new_password"
}
```

**Response**:
```json
{
    "status": "ok",
    "secondHash": "bcrypt_hash",
    "hash": "bcrypt_hash",
    "secondSalt": "salt"
}
```

---

### POST /api/auth/recover-parent-password

Recover parent password.

**Request Body**:
```json
{
    "mailAuthToken": "auth_token",
    "password": {
        "hash": "bcrypt_hash",
        "secondHash": "bcrypt_hash",
        "secondSalt": "salt"
    }
}
```

**Response**:
```json
{
    "status": "ok"
}
```

---

## Family Management Endpoints

### POST /api/families

Create a new family (RESTful alias).

Same as `POST /api/auth/create-family`.

---

## Device Management Endpoints

### POST /api/parent/create-add-device-token

Create a token for adding a device.

**Request Body**:
```json
{
    "deviceAuthToken": "device_token",
    "parentPasswordSecondHash": "hash"
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

---

### POST /api/child/add-device

Add a child device to the family.

**Request Body**:
```json
{
    "registerToken": "register_token",
    "deviceName": "Device Name",
    "childDevice": {
        "model": "Device Model"
    },
    "clientLevel": 7
}
```

**Request Fields:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `registerToken` | string | Yes | Token from create-add-device-token |
| `deviceName` | string | Yes | Name for the child's device (defaults to "Unknown Device" if not provided) |
| `childDevice` | object | Yes | Device info object containing `model` field (defaults to `{"model": "Unknown"}` if not provided) |
| `clientLevel` | integer | Yes | Client level/version (defaults to 7 if not provided) |

**Note:** All fields are required by the TimeLimit server. The client provides default values for optional fields:
- `deviceName` defaults to "Unknown Device"
- `childDevice.model` defaults to "Unknown"
- `clientLevel` defaults to 7 (matches Android app's `ClientDataStatus.CLIENT_LEVEL_VALUE`)

**Response**:
```json
{
    "status": "ok",
    "deviceAuthToken": "device_token",
    "ownDeviceId": "device_id"
}
```

---

### POST /api/dashboard/devices/remove

Remove a device from the family.

**Request Body**:
```json
{
    "deviceId": "device_id"
}
```

**Response**:
```json
{
    "status": "ok",
    "message": "Device removed successfully"
}
```

---

## User Management Endpoints

### POST /api/dashboard/users/add

Add a user to the family.

**Request Body**:
```json
{
    "name": "User Name",
    "deviceName": "Device Name",
    "deviceModel": "Device Model"
}
```

**Response**:
```json
{
    "status": "ok",
    "userId": "user_id",
    "deviceAuthToken": "device_token",
    "ownDeviceId": "device_id"
}
```

---

## Dashboard API Endpoints

### GET /api/dashboard/users

Get all users.

**Response**:
```json
{
    "status": "ok",
    "count": 2,
    "users": [...]
}
```

---

### GET /api/dashboard/devices

Get all devices.

**Response**:
```json
{
    "status": "ok",
    "count": 2,
    "devices": [...],
    "own_device_id": "device_id",
    "has_parent_password_second_hash": true
}
```

---

### GET /api/dashboard/categories

Get all categories.

**Response**:
```json
{
    "status": "ok",
    "count": 3,
    "categories": [...]
}
```

---

### GET /api/dashboard/time-limit-rules

Get all time limit rules.

**Response**:
```json
{
    "status": "ok",
    "count": 1,
    "rules": [...]
}
```

---

### POST /api/dashboard/time-limit-rules

Create a time limit rule.

**Request Body**:
```json
{
    "userId": "user_id",
    "categoryId": "category_id",
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
    "ruleId": "rule_id"
}
```

---

### PUT /api/dashboard/time-limit-rules/{ruleId}

Update a time limit rule.

**Request Body**:
```json
{
    "rule": {
        "startTime": "17:00",
        "endTime": "20:00"
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

---

### DELETE /api/dashboard/time-limit-rules/{ruleId}

Delete a time limit rule.

**Response**:
```json
{
    "status": "ok",
    "message": "Rule deleted successfully"
}
```

---

## Sync Endpoints

### POST /api/sync/pull

Trigger a sync pull from the server.

**Response**:
```json
{
    "status": "ok",
    "synced": true
}
```

---

## Session Endpoints

### GET /api/session/status

Get current session status.

**Response**:
```json
{
    "authenticated": true,
    "server_url": "https://timeleap.org",
    "has_device_auth_token": true,
    "device_auth_token": "token",
    "own_device_id": "device_id",
    "has_parent_password_second_hash": true,
    "has_signing_key": true
}
```

---

### POST /api/session/clear

Clear the current session.

**Response**:
```json
{
    "status": "ok"
}
```

---

## Utility Endpoints

### POST /api/time

Proxy to server time endpoint.

**Response**:
```json
{
    "status": "ok",
    "time": 1234567890123
}
```

---

### GET /api/server-selection

Get current server selection.

**Response**:
```json
{
    "server_key": "official",
    "server_url": "https://timeleap.org"
}
```

---

### POST /select-server

Select a server.

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

### POST /api/log-level

Set log level at runtime.

**Request Body**:
```json
{
    "log_level": "DEBUG"
}
```

**Response**:
```json
{
    "status": "ok",
    "log_level": "DEBUG"
}
```

---

### GET /health

Health check endpoint.

**Response**:
```json
{
    "status": "healthy"
}
```

---

### POST /api/clear-all

Clear all data.

**Response**:
```json
{
    "status": "ok",
    "tables_cleared": {...},
    "message": "All data cleared successfully"
}
```

---

### POST /api/clear-server-checks

Clear server check history.

**Response**:
```json
{
    "status": "ok",
    "rows_deleted": 10,
    "message": "Server checks cleared successfully (10 records removed)"
}
```

---

### POST /api/auth/backup

Create auth token backup.

**Response**:
```json
{
    "status": "ok",
    "backup_successful": true,
    "device_auth_token": "token",
    "own_device_id": "device_id"
}
```

---

### POST /api/auth/restore

Restore auth token backup.

**Response**:
```json
{
    "status": "ok",
    "restore_successful": true,
    "device_auth_token": "token",
    "own_device_id": "device_id"
}
```

---

### POST /api/auth/clear-backup

Clear auth token backup.

**Response**:
```json
{
    "status": "ok",
    "cleared": true
}
```

---

## Timechecker Endpoints

### GET /api/timechecker/status

Get server check status.

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

---

### GET /api/timechecker/history

Get server check history.

**Response**:
```json
{
    "checks": [],
    "total": 0
}
```

---

### POST /api/timechecker/history

Clear server check history.

**Response**:
```json
{
    "status": "ok",
    "rows_deleted": 10
}
```

---

## Server-Sent Events

### GET /api/dashboard/stream

SSE endpoint for real-time updates.

**Events**:
- `sync_complete` - Sync completed successfully

**Example**:
```javascript
const eventSource = new EventSource('/api/dashboard/stream');

eventSource.addEventListener('sync_complete', function(event) {
    const data = JSON.parse(event.data);
    console.log('Sync complete:', data);
});
```

---

## Error Response Format

All error responses follow this format:

```json
{
    "status": "error",
    "error": "Error message",
    "error_code": "error_code"
}
```

### Common Error Codes

| Code | HTTP Status | Description |
|------|-------------|-------------|
| `unauthorized` | 401 | Not authenticated |
| `validation` | 400 | Validation error |
| `not_found` | 404 | Resource not found |
| `server_error` | 500 | Internal server error |
| `timeout` | 502 | Request timeout |
| `unreachable` | 502 | Server unreachable |

---

## Rate Limiting

API endpoints may have rate limiting. If you receive a 429 status code, wait before retrying.

## Authentication

Most endpoints require authentication via `device_auth_token` in the session. The token is automatically managed by the dashboard.